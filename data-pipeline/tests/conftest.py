"""Shared pytest setup.

Some research tests (Dragon baselines, tree models, anomaly evaluation) read local research data under
<repo>/data/, which is git-ignored and therefore absent in CI and in fresh clones. Such a test is reported
as SKIPPED (with the missing path) instead of FAILED, so CI shows real failures only. On a machine that has
the data, the tests run normally. Any other FileNotFoundError still fails.
"""
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if call.excinfo is None or not call.excinfo.errisinstance(FileNotFoundError):
        return
    missing = str(getattr(call.excinfo.value, "filename", "") or "")
    if missing.startswith(str(DATA_DIR)):
        report.outcome = "skipped"
        report.longrepr = (str(item.path), item.location[1] or 0,
                           f"Skipped: needs local research data (git-ignored): {missing}")
