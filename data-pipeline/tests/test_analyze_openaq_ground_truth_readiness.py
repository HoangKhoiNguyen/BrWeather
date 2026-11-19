"""Check gap and sample exclusions on small synthetic observation series."""

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "analyze_openaq_ground_truth_readiness.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("readiness", SCRIPT)
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


class ReadinessTest(unittest.TestCase):
    def test_gap_boundaries_and_adjacent_values(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        hours = {start: 10, start + 4*readiness.HOUR: 20}
        gaps = readiness.gaps(hours, start, start + 5*readiness.HOUR, 1, "test")
        self.assertEqual((gaps[0]["duration_hours"], gaps[0]["previous_value"], gaps[0]["next_value"]), (3, 10, 20))

    def test_suspect_zero_exclusion_reduces_valid_samples(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = start + 10*readiness.HOUR
        hours = {start+i*readiness.HOUR: 0 for i in range(10)}
        keep, _ = readiness.sample_counts(hours, start, end, (1, 3), 1)
        exclude, _ = readiness.sample_counts(hours, start, end, (1, 3), 1,
                                             {start+5*readiness.HOUR})
        self.assertGreater(keep["valid_samples"], exclude["valid_samples"])
        self.assertEqual(exclude["invalid_due_to_suspect_data"], 3)


if __name__ == "__main__":
    unittest.main()
