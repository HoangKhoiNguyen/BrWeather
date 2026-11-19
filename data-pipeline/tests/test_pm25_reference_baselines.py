"""Guard quality flags and baseline time ordering."""

import gzip
import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load("prepare_pm25_reference_dataset")
baseline = load("evaluate_pm25_baselines")
HOUR = timedelta(hours=1)
T = datetime(2026, 11, 9, 10, tzinfo=timezone.utc)


class BaselineTest(unittest.TestCase):
    def test_all_baseline_sources_are_known_at_issue_time(self):
        for model in baseline.MODELS:
            for horizon in baseline.HORIZONS:
                self.assertLessEqual(baseline.source_time(model, T, horizon), T)

    def test_formulas_and_issue_before_valid(self):
        series = {T: {"pm2_5": 10, "quality_flag": "VALID"},
                  T+HOUR: {"pm2_5": 12, "quality_flag": "VALID"},
                  T-23*HOUR: {"pm2_5": 8, "quality_flag": "VALID"},
                  T-167*HOUR: {"pm2_5": 7, "quality_flag": "VALID"}}
        for model, expected in zip(baseline.MODELS, (10, 8, 7)):
            rows, _ = baseline.evaluate_one(series, model, "test", T, T+2*HOUR, 1, "B_EXCLUDE_ZERO")
            self.assertEqual(rows[0]["prediction"], expected)
            self.assertLess(baseline.stamp(rows[0]["issued_at"]), baseline.stamp(rows[0]["valid_time"]))

    def test_missing_feature_or_target_is_excluded(self):
        valid = {"pm2_5": 10, "quality_flag": "VALID"}
        rows, _ = baseline.evaluate_one({T+HOUR: valid}, "Persistence", "test", T, T+2*HOUR, 1, "B_EXCLUDE_ZERO")
        self.assertEqual(rows, [])
        rows, _ = baseline.evaluate_one({T: valid}, "Persistence", "test", T, T+2*HOUR, 1, "B_EXCLUDE_ZERO")
        self.assertEqual(rows, [])

    def test_zero_run_is_excluded_only_in_scenario_b(self):
        suspect = {"pm2_5": 0, "quality_flag": "SUSPECT_ZERO_RUN"}
        valid = {"pm2_5": 10, "quality_flag": "VALID"}
        series = {T: suspect, T+HOUR: valid}
        a, _ = baseline.evaluate_one(series, "Persistence", "test", T, T+2*HOUR, 1, "A_KEEP_ZERO")
        b, _ = baseline.evaluate_one(series, "Persistence", "test", T, T+2*HOUR, 1, "B_EXCLUDE_ZERO")
        self.assertEqual((len(a), len(b)), (1, 0))

    def test_splits_do_not_overlap(self):
        self.assertTrue(all(a[2] <= b[1] for a, b in zip(baseline.SPLITS, baseline.SPLITS[1:])))

    def test_raw_is_unchanged_and_zero_value_retained(self):
        raw = prepare.RAW
        before = hashlib.sha256(raw.read_bytes()).hexdigest()
        data = json.loads(gzip.decompress(raw.read_bytes()))
        rows, _, _ = prepare.prepare(data["records"], prepare.stamp(data["window_start"]),
                                     prepare.stamp(data["window_end"]))
        zero = next(r for r in rows if r["observation_time_utc"] == T.isoformat())
        self.assertEqual(zero["pm2_5"], 0)
        self.assertIsNone(zero["pm2_5_ml"])
        self.assertEqual(zero["quality_flag"], "SUSPECT_ZERO_RUN")
        self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
