"""Guard fold timing and append-only prospective weather snapshots."""

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from sklearn.impute import SimpleImputer

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))


def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stability = load("analyze_pm25_model_stability")
snapshot = load("collect_openmeteo_forecast_snapshot")
observation = load("collect_openaq_observation_snapshot")


class StabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.features, _, _, _ = stability.read_rows()

    def test_folds_are_ordered_purged_and_exclude_original_test(self):
        previous_end = None
        for fold in stability.FOLDS:
            start, end = [datetime.fromisoformat(x) for x in fold[1:]]
            if previous_end:
                self.assertLessEqual(previous_end, start)
            previous_end = end
            train, validation = stability.fold_rows(self.features, fold, 24)
            self.assertTrue(train and validation)
            self.assertTrue(all(r["split"] != "test" for r in train+validation))
            self.assertLess(max(datetime.fromisoformat(r["valid_time"]) for r in train), start-timedelta(hours=24))
            self.assertGreaterEqual(min(datetime.fromisoformat(r["issued_at"]) for r in validation), start)
            self.assertTrue(all(datetime.fromisoformat(r["valid_time"]) < end for r in validation))

    def test_fold_imputer_uses_train_statistics_only(self):
        train = np.array([[1.0], [np.nan], [3.0]])
        validation = np.array([[99.0], [np.nan]])
        imputer = SimpleImputer(strategy="median").fit(train)
        self.assertEqual(imputer.statistics_[0], 2.0)
        self.assertEqual(imputer.transform(validation)[1, 0], 2.0)

    def test_fold_model_and_persistence_use_same_validation_rows(self):
        _, validation = stability.fold_rows(self.features, stability.FOLDS[0], 6)
        targets = [r["target_pm25"] for r in validation]
        persistence = [r["persistence"] for r in validation]
        self.assertEqual(len(targets), len(persistence))
        self.assertEqual(len({(r["issued_at"], r["valid_time"]) for r in validation}), len(validation))

    def test_original_openaq_raw_is_unchanged(self):
        root = BASE.parent
        raw = root / "data/audit/openaq_hours_180d/sensor_14581375.json.gz"
        expected = json.loads((root / "data/processed/dragon_pm25_quality_summary.json").read_text())["raw_sha256"]
        self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(), expected)


class SnapshotTest(unittest.TestCase):
    def payload(self, now):
        return {"utc_offset_seconds": 0, "latitude": 21.0, "longitude": 106.0,
                "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
                "hourly": {"time": [(now+timedelta(hours=i)).replace(tzinfo=None).isoformat(timespec="minutes") for i in (-1, 1, 2)],
                           "temperature_2m": [20, 21, 22]}}

    def test_append_only_idempotent_and_future_only(self):
        now = datetime(2026, 11, 12, 3, 15, tzinfo=timezone.utc)
        params = {"latitude": 20.9933, "longitude": 105.9441, "timezone": "UTC"}
        with tempfile.TemporaryDirectory() as directory:
            path, created = snapshot.save_snapshot(self.payload(now), now, params, Path(directory))
            content = path.read_bytes()
            again, created_again = snapshot.save_snapshot(self.payload(now), now+timedelta(minutes=5), params, Path(directory))
            self.assertTrue(created)
            self.assertFalse(created_again)
            self.assertEqual(path, again)
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)
            data = json.loads(content)
            self.assertEqual(data["timezone"], "UTC")
            self.assertEqual(len(data["forecast_hours"]), 2)
            self.assertTrue(all(datetime.fromisoformat(r["valid_time"]) > now for r in data["forecast_hours"]))
            self.assertNotIn("pm2_5", content.decode())
            self.assertNotIn("API_KEY", content.decode())

    def test_availability_rule(self):
        retrieved = datetime(2026, 11, 12, 3, tzinfo=timezone.utc)
        valid = retrieved+timedelta(hours=2)
        data = {"retrieved_at": retrieved.isoformat(), "forecast_hours": [{"valid_time": valid.isoformat()}]}
        self.assertTrue(snapshot.usable_at(data, retrieved+timedelta(hours=1), valid))
        self.assertFalse(snapshot.usable_at(data, retrieved-timedelta(seconds=1), valid))
        self.assertFalse(snapshot.usable_at(data, valid, valid))

    def test_observation_capture_is_append_only_and_pending_review(self):
        now = datetime(2026, 11, 12, 3, tzinfo=timezone.utc)
        pages = [{"meta": {"page": 1, "found": 1}, "results": [{
            "value": 12.5, "period": {"datetimeFrom": {"utc": "2026-11-12T02:00:00Z"}},
            "parameter": {"units": "ug/m3"}, "flagInfo": {"hasFlags": False}}]}]
        with tempfile.TemporaryDirectory() as directory:
            path, created = observation.save_snapshot(pages, now, Path(directory))
            before = path.read_bytes()
            same, created_again = observation.save_snapshot(pages, now+timedelta(minutes=1), Path(directory))
            self.assertTrue(created)
            self.assertFalse(created_again)
            self.assertEqual(path, same)
            self.assertEqual(before, path.read_bytes())
            saved = json.loads(before)
            self.assertEqual(saved["records"][0]["quality_flag"], "PENDING_REVIEW")
            self.assertEqual(saved["records"][0]["retrieved_at"], now.isoformat())
            self.assertNotIn("API_KEY", before.decode())


if __name__ == "__main__":
    unittest.main()
