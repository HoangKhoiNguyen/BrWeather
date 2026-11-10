"""Minimal scheduler: runs the hourly ingest at minute 10 of every hour. Enough for the demo scale."""
import logging
import time
from datetime import datetime, timedelta

from brweather_data.jobs import ingest_hourly

log = logging.getLogger("scheduler")


def seconds_until_next_run(minute: int = 10) -> float:
    now = datetime.now()
    target = now.replace(minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(hours=1)
    return (target - now).total_seconds()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        try:
            ingest_hourly.run()
        except Exception:
            log.exception("Ingest failed; the run is logged in ingest_runs and will retry next hour")
        time.sleep(seconds_until_next_run())


if __name__ == "__main__":
    main()
