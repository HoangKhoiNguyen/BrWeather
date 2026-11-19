"""Guard weather feature timing, cache use, split integrity, and comparisons."""

import csv
import gzip
import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))


def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


weather = load("fetch_openmeteo_weather")
features = load("build_pm25_weather_features")
trees = load("train_pm25_tree_models")


class WeatherTreeTest(unittest.TestCase):
    def test_feature_and_target_times_and_horizons(self):
        with gzip.open(features.OUT / "dragon_pm25_weather_features.csv.gz", "rt", encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual({int(r["horizon_hours"]) for r in rows}, {1, 6, 24})
        for row in rows:
            issued, valid = [datetime.fromisoformat(row[k]) for k in ("issued_at", "valid_time")]
            self.assertLessEqual(datetime.fromisoformat(row["max_feature_time_utc"]), issued)
            self.assertEqual(valid-issued, timedelta(hours=int(row["horizon_hours"])))
            self.assertGreater(valid, issued)

    def test_future_weather_cannot_change_features(self):
        issued = datetime(2026, 9, 1, tzinfo=timezone.utc)
        pm = {issued-i*features.HOUR: 20.0 for i in range(169)}
        past = {issued: {v: 1.0 for v in features.WEATHER_VARS}}
        before = features.features_at(issued, pm, past)
        past[issued+features.HOUR] = {v: 9999.0 for v in features.WEATHER_VARS}
        self.assertEqual(before, features.features_at(issued, pm, past))
        self.assertEqual(before["pm25_count_168h"], 168)

    def test_suspect_zero_is_not_feature_or_target(self):
        with gzip.open(features.PM, "rt", encoding="utf-8", newline="") as file:
            source = list(csv.DictReader(file))
        suspect = {r["observation_time_utc"] for r in source if r["quality_flag"] == "SUSPECT_ZERO_RUN"}
        self.assertEqual(len(suspect), 7)
        self.assertTrue(all(r["pm2_5_ml"] == "" for r in source if r["observation_time_utc"] in suspect))
        with gzip.open(features.OUT / "dragon_pm25_weather_features.csv.gz", "rt", encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertTrue(all(r["issued_at"] not in suspect and r["valid_time"] not in suspect for r in rows))

    def test_splits_do_not_overlap(self):
        from evaluate_pm25_baselines import SPLITS
        self.assertTrue(all(a[2] <= b[1] for a, b in zip(SPLITS, SPLITS[1:])))

    def test_imputer_statistics_come_from_train_only(self):
        artifact = joblib.load(trees.OUT / "dragon_pm25_weather_24h.joblib")
        with gzip.open(trees.DATA, "rt", encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        train = trees.group(rows, "train", 24)
        val = trees.group(rows, "validation", 24)
        column = artifact["features"].index("weather_temperature_2m_current")
        train_median = np.median(trees.matrix(train, artifact["features"])[:, column])
        val_median = np.median(trees.matrix(val, artifact["features"])[:, column])
        fitted = artifact["pipeline"].named_steps["imputer"].statistics_[column]
        self.assertAlmostEqual(fitted, train_median)
        self.assertNotEqual(train_median, val_median)

    def test_tree_and_persistence_have_same_timestamps(self):
        with gzip.open(trees.OUT / "dragon_tree_model_predictions.csv.gz", "rt", encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        for horizon in (1, 6, 24):
            for split in ("validation", "test"):
                for ablation in ("PM25_ONLY", "PM25_WEATHER"):
                    part = [r for r in rows if r["horizon_hours"] == str(horizon) and r["split"] == split and r["ablation"] == ablation]
                    model = {(r["issued_at"], r["valid_time"]) for r in part if r["model_name"] != "Persistence"}
                    baseline = {(r["issued_at"], r["valid_time"]) for r in part if r["model_name"] == "Persistence"}
                    self.assertEqual(model, baseline)
                    self.assertEqual(len(model), len(part)//2)

    def test_selection_uses_only_validation_scores(self):
        scores = {(h, a): {"validation_MAE": (1 if a == "PM25_ONLY" else 2)}
                  for h in (1, 6, 24) for a in ("PM25_ONLY", "PM25_WEATHER")}
        chosen = trees.choose_by_validation(scores, ("PM25_ONLY", "PM25_WEATHER"))
        self.assertEqual({x["ablation"] for x in chosen.values()}, {"PM25_ONLY"})

    def test_weather_cache_metadata_and_no_network_on_rerun(self):
        metadata = json.loads(weather.METADATA.read_text(encoding="utf-8"))
        self.assertEqual(metadata["timezone"], "UTC")
        self.assertEqual(metadata["model"], "ERA5 reanalysis")
        self.assertEqual(metadata["requested_coordinates"], {"latitude": 20.9933, "longitude": 105.9441})
        self.assertIn("fetched_at", metadata)
        with patch.object(sys, "argv", ["fetch_openmeteo_weather.py"]), patch.object(weather.requests, "get", side_effect=AssertionError("network called")):
            weather.main()

    def test_input_raw_and_processed_files_are_not_modified(self):
        paths = [features.PM, BASE.parent / "data/audit/openaq_hours_180d/sensor_14581375.json.gz"]
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
        pm, meteo, _ = features.load_inputs()
        features.features_at(datetime(2026, 9, 1, tzinfo=timezone.utc), pm, meteo)
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths])


if __name__ == "__main__":
    unittest.main()
