"""Minimal scheduler: at minute 10 of every hour, ingest then compute reliability. Enough for the demo scale.

Each job logs its own run in ingest_runs; one failing job does not stop the other or the next hour.
"""
import logging
import time
from datetime import datetime, timedelta

from brweather_data.jobs import compute_reliability, ingest_hourly

log = logging.getLogger("scheduler")

HOURLY_JOBS = (
    ("ingest_hourly", ingest_hourly.run),
    ("compute_reliability", compute_reliability.run),  # T4.1-3: after ingest, on the fresh data
)


def seconds_until_next_run(minute: int = 10) -> float:
    now = datetime.now()
    target = now.replace(minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(hours=1)
    return (target - now).total_seconds()


def run_hourly_jobs(jobs=HOURLY_JOBS) -> None:
    for name, job in jobs:
        try:
            job()
        except Exception:
            log.exception("%s failed; the run is logged in ingest_runs and will retry next hour", name)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        run_hourly_jobs()
        time.sleep(seconds_until_next_run())


if __name__ == "__main__":
    main()
