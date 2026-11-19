"""Boundary and safety checks for Dragon assessment policy."""

import csv
import gzip
import hashlib
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import build_air_quality_assessments as assessment


class AssessmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(assessment.AIR_POLICY.read_text(encoding="utf-8"))
        cls.rec_policy = json.loads(assessment.REC_POLICY.read_text(encoding="utf-8"))
        cls.t = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)

    def row(self, **changes):
        result = {"sensor_id": "14581375", "observation_time_utc": self.t.isoformat(),
                  "pm2_5": "20", "pm2_5_ml": "20", "unit": "ug/m3",
                  "quality_flag": "VALID"}
        result.update(changes)
        return result

    def test_provisional_breakpoint_boundaries_not_called_vn_aqi(self):
        expected = [(0, "PROVISIONAL_LOW"), (25, "PROVISIONAL_LOW"),
                    (25.0001, "PROVISIONAL_MODERATE"), (50, "PROVISIONAL_MODERATE"),
                    (50.0001, "PROVISIONAL_ELEVATED"), (80, "PROVISIONAL_ELEVATED"),
                    (150, "PROVISIONAL_HIGH"), (250, "PROVISIONAL_VERY_HIGH"),
                    (350, "PROVISIONAL_EXTREME"), (351, "PROVISIONAL_ABOVE_SCALE")]
        self.assertEqual([(value, assessment.provisional_status(value, self.policy)) for value, _ in expected], expected)
        self.assertFalse(self.policy["vn_aqi_eligible"])
        self.assertEqual(self.policy["method"], "PROVISIONAL_PM25_CONCENTRATION_STATUS")

    def test_official_nowcast_example(self):
        newest_first = [20.6, 19.6, 22.4, 20.3, 16.5, 19.0, 16.5, 19.5, 23.5, 20.5, 24.7, 26.9]
        self.assertAlmostEqual(assessment.nowcast(newest_first), 20.3, places=1)

    def test_one_missing_hour_and_coverage_boundary(self):
        full = {self.t-i*assessment.HOUR: 20.0 for i in range(12)}
        del full[self.t-5*assessment.HOUR]
        self.assertTrue(assessment.coverage_window(full, self.t, self.policy)["eligible"])
        below = {self.t-i*assessment.HOUR: 20.0 for i in range(8)}
        above = {self.t-i*assessment.HOUR: 20.0 for i in range(9)}
        self.assertFalse(assessment.coverage_window(below, self.t, self.policy)["eligible"])
        self.assertTrue(assessment.coverage_window(above, self.t, self.policy)["eligible"])

    def test_rolling_window_never_uses_future(self):
        values = {self.t-i*assessment.HOUR: float(i+1) for i in range(12)}
        before = assessment.coverage_window(values, self.t, self.policy)
        values[self.t+assessment.HOUR] = 9999
        self.assertEqual(before, assessment.coverage_window(values, self.t, self.policy))

    def test_zero_missing_pending_wrong_unit_and_wrong_sensor_suppress(self):
        cases = [
            (self.row(quality_flag="SUSPECT_ZERO_RUN"), "SUPPRESSED_DATA_QUALITY"),
            (self.row(quality_flag="MISSING", pm2_5="", pm2_5_ml=""), "INSUFFICIENT_DATA"),
            (self.row(quality_flag="PENDING_REVIEW"), "PENDING_REVIEW"),
            (self.row(unit="ppm"), "SUPPRESSED_DATA_QUALITY"),
            (self.row(sensor_id="1"), "SUPPRESSED_DATA_QUALITY")]
        for row, expected in cases:
            self.assertEqual(assessment.gate(row, self.t, self.policy)[0], expected)

    def test_stale_prospective_observation_suppresses(self):
        row = self.row(measurement_time_utc=self.t.isoformat(), retrieved_at=(self.t+timedelta(hours=4)).isoformat())
        availability, quality, stale = assessment.gate(row, self.t+timedelta(hours=4), self.policy, True)
        self.assertEqual((availability, quality, stale), ("STALE_DATA", "STALE", True))

    def test_pending_review_emits_no_status_or_recommendation(self):
        row = self.row(quality_flag="PENDING_REVIEW", measurement_time_utc=self.t.isoformat(),
                       retrieved_at=(self.t+timedelta(hours=1)).isoformat())
        result = assessment.observed_assessment(row, {}, [], self.policy, self.rec_policy,
                                                "GENERAL", "x", self.t+timedelta(hours=1), True)
        self.assertEqual(result["assessment_availability"], "PENDING_REVIEW")
        self.assertIsNone(result["air_quality_status"])
        self.assertEqual(result["recommendations"], [])

    def test_persistence_uses_current_observation_and_future_valid_time(self):
        result = assessment.forecast_assessment(self.row(), [], 6, self.policy, self.rec_policy,
                                                "GENERAL", "2026-01-01T00:00:00+00:00")
        self.assertEqual(result["pm25_value"], 20.0)
        self.assertEqual(result["forecast_model"], "PERSISTENCE")
        self.assertGreater(assessment.utc(result["valid_time"]), assessment.utc(result["issued_at"]))

    def test_air_candidate_does_not_raise_status_and_quality_has_priority(self):
        by_time = {self.t-i*assessment.HOUR: 20.0 for i in range(12)}
        air = {"event_id": "air", "start_time": self.t.isoformat(), "end_time": self.t.isoformat(),
               "event_type": "RAPID_CHANGE", "category": "AIR_QUALITY_EVENT", "status": "CANDIDATE",
               "severity": "CRITICAL", "detector": "test", "quality_context": "NONE"}
        without = assessment.observed_assessment(self.row(), by_time, [], self.policy, self.rec_policy,
                                                 "GENERAL", "x")
        with_air = assessment.observed_assessment(self.row(), by_time, [air], self.policy, self.rec_policy,
                                                  "GENERAL", "x")
        self.assertEqual(without["air_quality_status"], with_air["air_quality_status"])
        self.assertTrue(with_air["anomaly_candidate_present"])
        quality = {**air, "event_id": "quality", "event_type": "INVALID_VALUE", "category": "DATA_QUALITY"}
        suppressed = assessment.observed_assessment(self.row(), by_time, [air, quality], self.policy,
                                                    self.rec_policy, "GENERAL", "x")
        self.assertEqual(suppressed["assessment_availability"], "SUPPRESSED_DATA_QUALITY")
        self.assertEqual(suppressed["recommendations"], [])

    def test_recommendation_audience_source_disclaimer_and_no_diagnosis_or_drugs(self):
        general = assessment.recommendations("PROVISIONAL_HIGH", "AVAILABLE", "GENERAL", self.rec_policy)
        sensitive = assessment.recommendations("PROVISIONAL_HIGH", "AVAILABLE", "SENSITIVE_GROUP", self.rec_policy)
        self.assertTrue(general and sensitive)
        self.assertTrue(any(item["audience"] == "SENSITIVE_GROUP" for item in sensitive))
        for item in general+sensitive:
            self.assertTrue(item["source_reference"]["url"])
            self.assertTrue(item["disclaimer"])
            text = item["message"].lower()
            self.assertNotIn("thuốc", text)
            self.assertNotIn("chẩn đoán", text)

    def test_stable_id_raw_unchanged_and_secret_absent(self):
        first = assessment.stable_id(14581375, "X", self.t, self.t, 0)
        self.assertEqual(first, assessment.stable_id(14581375, "X", self.t, self.t, 0))
        raw = BASE.parent / "data/audit/openaq_hours_180d/sensor_14581375.json.gz"
        expected = "a3e0f22db35c38f9a900577a101787a4ff25e486a19b055b556c28de22b602ee"
        self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(), expected)
        outputs = list((BASE.parent / "data/assessments").glob("*"))
        self.assertTrue(outputs)
        self.assertTrue(all(b"OPENAQ_API_KEY" not in path.read_bytes() for path in outputs))
        schema = json.loads((BASE.parent / "data/assessments/dragon_air_quality_assessment_schema.json").read_text())
        self.assertFalse(schema["vn_aqi"])
        self.assertIn("forecast_confidence", schema["properties"])


if __name__ == "__main__":
    unittest.main()
