"""Synthetic checks for anomaly semantics and prospective collection."""

import copy
import csv
import gzip
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import collect_openaq_observation_snapshot as observation
import detect_pm25_anomalies as anomaly
import validate_prospective_collection as prospective

FIXTURE = Path(__file__).parent / "fixtures/pm25_anomaly_synthetic.csv"


def fixture_rows():
    with FIXTURE.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        row["time"] = datetime.fromisoformat(row["observation_time_utc"])
        row["value"] = float(row["pm2_5"]) if row["pm2_5"] else None
    return rows


class AnomalyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(anomaly.CONFIG_PATH.read_text(encoding="utf-8"))
        cls.rows = fixture_rows()
        cls.quality = anomaly.quality_events(cls.rows, cls.config, "2026-01-03T00:00:00+00:00")

    def test_missing_run_is_merged(self):
        missing = [e for e in self.quality if e["event_type"] == "MISSING_DATA"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["duration_hours"], 3)

    def test_zero_run_is_data_quality_only(self):
        zeros = [e for e in self.quality if e["event_type"] == "SUSPECT_ZERO_RUN"]
        self.assertEqual((len(zeros), zeros[0]["duration_hours"], zeros[0]["category"]),
                         (1, 7, "DATA_QUALITY"))

    def test_flatline_negative_and_duplicate(self):
        self.assertTrue(any(e["event_type"] == "FLATLINE" and e["duration_hours"] >= 8 for e in self.quality))
        invalid_text = " ".join(e["explanation"] for e in self.quality if e["event_type"] == "INVALID_VALUE")
        self.assertIn("TECHNICAL_RANGE", invalid_text)
        self.assertIn("DUPLICATE_TIMESTAMP", invalid_text)

    def test_rapid_change_and_robust_score_never_read_future(self):
        rows = [r for r in self.rows if r["time"] <= datetime(2026, 1, 2, 7, tzinfo=timezone.utc)]
        valid = {r["time"]: r["value"] for r in rows if r["quality_flag"] == "VALID" and r["value"] is not None}
        change = valid[datetime(2026, 1, 2, 6, tzinfo=timezone.utc)] - valid[datetime(2026, 1, 2, 5, tzinfo=timezone.utc)]
        rows.append({"time": datetime(2026, 1, 3, tzinfo=timezone.utc), "value": 9999.0, "quality_flag": "VALID"})
        valid_after = {r["time"]: r["value"] for r in rows if r["quality_flag"] == "VALID" and r["value"] is not None}
        self.assertEqual(change, valid_after[datetime(2026, 1, 2, 6, tzinfo=timezone.utc)]-valid_after[datetime(2026, 1, 2, 5, tzinfo=timezone.utc)])
        times = sorted(valid_after)
        values = [valid_after[t] for t in times]
        index = times.index(datetime(2026, 1, 2, 6, tzinfo=timezone.utc))
        before = anomaly.past_robust_score(times, values, index, 24, 8)
        values[-1] = -9999
        self.assertEqual(before, anomaly.past_robust_score(times, values, index, 24, 8))

    def test_threshold_fit_uses_train_only_and_splits_do_not_overlap(self):
        real = anomaly.load_rows()
        first = anomaly.fit_thresholds(real, self.config)
        changed = copy.deepcopy(real)
        train_end = anomaly.utc(self.config["split_boundaries_utc"]["train_end"])
        for row in changed:
            if row["time"] >= train_end and isinstance(row["value"], float):
                row["value"] *= 1000
        self.assertEqual(first, anomaly.fit_thresholds(changed, self.config))
        bounds = self.config["split_boundaries_utc"]
        self.assertLessEqual(anomaly.utc(bounds["train_end"]), anomaly.utc(bounds["validation_end"]))
        self.assertLessEqual(anomaly.utc(bounds["validation_end"]), anomaly.utc(bounds["test_end"]))

    def test_persistence_prediction_matches_observation_valid_time(self):
        with gzip.open(anomaly.BASELINES, "rt", encoding="utf-8", newline="") as file:
            predictions = [r for r in csv.DictReader(file) if r["model_name"] == "Persistence" and
                           r["horizon_hours"] == "1" and r["quality_scenario"] == "B_EXCLUDE_ZERO"]
        values = {r["time"]: r["value"] for r in anomaly.load_rows() if r["quality_flag"] == "VALID"}
        self.assertTrue(all(anomaly.utc(r["valid_time"]) in values and
                            float(r["observed"]) == values[anomaly.utc(r["valid_time"])] for r in predictions))

    def test_event_id_stable_and_consecutive_points_merge(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(anomaly.stable_id(1, "X", "D", start, start),
                         anomaly.stable_id(1, "X", "D", start, start))
        points = [{"time": start+i*anomaly.HOUR, "score": 2.0, "observed": 10.0,
                   "reference": 1.0, "detector": "D"} for i in range(3)]
        merged = anomaly.merge_candidates(points, "X", "D", self.config,
                                          "2026-01-01T00:00:00+00:00", 1.0, [])
        self.assertEqual((len(merged), merged[0]["duration_hours"]), (1, 3))

    def test_known_real_zero_run_is_detected_and_raw_unchanged(self):
        raw = BASE.parent / "data/audit/openaq_hours_180d/sensor_14581375.json.gz"
        before = hashlib.sha256(raw.read_bytes()).hexdigest()
        events = anomaly.quality_events(anomaly.load_rows(), self.config, "2026-11-12T00:00:00+00:00")
        zero = next(e for e in events if e["event_type"] == "SUSPECT_ZERO_RUN")
        self.assertEqual((zero["start_time"], zero["end_time"], zero["duration_hours"]),
                         ("2026-11-09T10:00:00+00:00", "2026-11-09T16:00:00+00:00", 7))
        self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(), before)
        thresholds = anomaly.fit_thresholds(anomaly.load_rows(), self.config)
        air = anomaly.air_candidates(anomaly.load_rows(), thresholds, self.config,
                                     "2026-11-12T00:00:00+00:00", events)
        zero_start, zero_end = anomaly.utc(zero["start_time"]), anomaly.utc(zero["end_time"])
        self.assertFalse(any(anomaly.utc(e["start_time"]) <= zero_end and
                             zero_start <= anomaly.utc(e["end_time"]) for e in air))


class ProspectiveTest(unittest.TestCase):
    def test_observation_identity_idempotency_and_pending_review(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        item = {"value": 12.0, "period": {"datetimeFrom": {"utc": "2026-01-01T00:00:00Z"}},
                "parameter": {"name": "pm25", "units": "ug/m3"}, "flagInfo": {"hasFlags": False}}
        pages = [{"results": [item, item]}]
        with tempfile.TemporaryDirectory() as directory:
            path, created = observation.save_snapshot(pages, now, Path(directory))
            same, created_again = observation.save_snapshot(pages, now+timedelta(minutes=1), Path(directory))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(created)
            self.assertFalse(created_again)
            self.assertEqual(path, same)
            self.assertEqual(len(data["records"]), 1)
            self.assertEqual(data["records"][0]["quality_flag"], "PENDING_REVIEW")
            self.assertNotIn("API_KEY", path.read_text(encoding="utf-8"))

    def test_overlapping_later_snapshot_keeps_only_new_observation(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        def item(hour, value):
            return {"value": value, "period": {"datetimeFrom": {"utc": f"2026-01-01T{hour:02d}:00:00Z"}},
                    "parameter": {"name": "pm25", "units": "ug/m3"}, "flagInfo": {"hasFlags": False}}
        with tempfile.TemporaryDirectory() as directory:
            observation.save_snapshot([{"results": [item(0, 10)]}], now, Path(directory))
            later, _ = observation.save_snapshot([{"results": [item(0, 10), item(1, 11)]}],
                                                  now+timedelta(hours=1), Path(directory))
            self.assertEqual([r["measurement_time_utc"] for r in json.loads(later.read_text())["records"]],
                             ["2026-01-01T01:00:00Z"])

    def test_stale_uses_supplied_as_of(self):
        config = json.loads(anomaly.CONFIG_PATH.read_text(encoding="utf-8"))
        record = [{"measurement_time_utc": "2026-01-01T00:00:00+00:00"}]
        self.assertIsNone(anomaly.stale_event(record, datetime(2026, 1, 1, 2, tzinfo=timezone.utc), config, "x"))
        self.assertEqual(anomaly.stale_event(record, datetime(2026, 1, 1, 4, tzinfo=timezone.utc), config, "x")["event_type"], "STALE_OBSERVATION")


if __name__ == "__main__":
    unittest.main()
