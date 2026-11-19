"""Small checks for long-term window and constant-run calculations."""

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "audit_openaq_long_term.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("audit_openaq_long_term", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class WindowTest(unittest.TestCase):
    def test_month_windows_cover_180_days_without_overlap(self):
        end = datetime(2026, 11, 11, 9, tzinfo=timezone.utc)
        start = end - timedelta(days=180)
        windows = list(audit.month_bounds(start, end))
        self.assertEqual(windows[0][0], start)
        self.assertEqual(windows[-1][1], end)
        self.assertEqual(sum((stop - begin) / audit.HOUR for begin, stop, _ in windows), 4320)
        self.assertTrue(all(a[1] == b[0] for a, b in zip(windows, windows[1:])))

    def test_constant_run_requires_consecutive_hours(self):
        start = datetime(2026, 11, 9, 10, tzinfo=timezone.utc)
        hours = {start + i * audit.HOUR: 0 for i in range(7)}
        self.assertEqual(audit.runs(hours)[0]["hours"], 7)
        del hours[start + 3 * audit.HOUR]
        self.assertEqual(audit.runs(hours), [])


if __name__ == "__main__":
    unittest.main()
