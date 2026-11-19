"""Check pagination without spending real OpenAQ requests."""

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "audit_openaq_coverage.py"
spec = importlib.util.spec_from_file_location("audit_openaq_coverage", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PaginationTest(unittest.TestCase):
    def test_second_page_is_fetched_and_merged(self):
        class Client:
            def __init__(self):
                self.pages = []

            def get(self, path, params):
                self.pages.append(params["page"])
                size = 1000 if params["page"] == 1 else 2
                return {"meta": {"found": 1002}, "results": list(range(size))}

        client = Client()
        now = datetime.now(timezone.utc)
        rows = audit.fetch_hours(client, 123, now, now)
        self.assertEqual(client.pages, [1, 2])
        self.assertEqual(len(rows), 1002)


if __name__ == "__main__":
    unittest.main()
