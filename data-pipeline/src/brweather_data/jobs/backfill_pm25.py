"""Backfill PM2.5 history from OpenAQ (T2.3-1).

    python -m brweather_data.jobs.backfill_pm25 --days 14
    python -m brweather_data.jobs.backfill_pm25 --days 90 --stations 2161306,2161292

Only PM2.5 is fetched (no weather snapshots), in chunks of --chunk-days so one failure does not lose the
whole range. Re-running is safe: rows already stored are skipped (ON CONFLICT DO NOTHING), so the job can
simply be run again after an error. Each run is logged in ingest_runs with job = 'backfill_pm25'.

At the end it prints, per station, how many of the expected hours are stored and usable, which is the
evidence for "Đủ dữ liệu 14 ngày cho 5 trạm".

API budget: one request per chunk per station (1,000 hours per page), plus one per station for the
location. 5 stations x 14 days is about 10 requests, far below 60/min and 2,000/hour.
"""
import argparse
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from brweather_data import db
from brweather_data.config import load_settings
from brweather_data.connectors.openaq import OpenAQClient
from brweather_data.jobs.ingest_hourly import error_entry, run_status
from brweather_data.quality.reliability import range_flag

log = logging.getLogger("backfill_pm25")


@dataclass
class Coverage:
    station_id: int
    expected: int
    stored: int
    usable: int

    @property
    def usable_pct(self) -> float:
        return 100.0 * self.usable / self.expected if self.expected else 0.0


def chunks(start: datetime, end: datetime, days: int) -> list[tuple[datetime, datetime]]:
    """Split [start, end) into consecutive windows of at most `days` days."""
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")
    out, step, t = [], timedelta(days=days), start
    while t < end:
        out.append((t, min(t + step, end)))
        t += step
    return out


COVERAGE_SQL = """
    SELECT count(*) FILTER (WHERE status <> 'missing') AS stored,
           count(*) FILTER (WHERE status = 'ok')       AS usable,
           count(*)                                    AS expected
    FROM pm25_hourly_series(%s, %s, %s)
"""


def coverage(conn, station_id: int, start: datetime, end: datetime) -> Coverage:
    with conn.cursor() as cur:
        cur.execute(COVERAGE_SQL, (station_id, start, end))
        stored, usable, expected = cur.fetchone()
    return Coverage(station_id, expected, stored, usable)


def run(days: int, station_ids: list[int] | None = None, chunk_days: int = 7,
        end: datetime | None = None) -> list[Coverage]:
    settings = load_settings()
    ids = station_ids or settings.station_ids
    client = OpenAQClient(settings.openaq_api_key)
    end = (end or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    total, stages_ok, errors = 0, 0, []

    with db.connect(settings.db_dsn) as conn:
        run_id = db.start_run(conn, "backfill_pm25")
        for station_id in ids:
            try:
                location = client.location(station_id)
                sensor_id = client.pm25_sensor_id(location)
                db.upsert_station(conn, location, sensor_id)
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                errors.append(error_entry(station_id, "location", exc))
                log.exception("Station %s: location lookup failed", station_id)
                continue
            if sensor_id is None:
                log.warning("Station %s has no PM2.5 sensor, skipped", station_id)
                continue

            for a, b in chunks(start, end, chunk_days):
                try:
                    def keep_page(request: str, payload: dict) -> None:
                        db.save_raw(conn, "openaq", request, payload, run_id)

                    rows = [(t, v, range_flag(v)) for t, v in client.hourly(sensor_id, a, b, on_page=keep_page)]
                    added = db.insert_pm25(conn, station_id, rows)
                    conn.commit()
                    total += added
                    stages_ok += 1
                    log.info("Station %s %s → %s: %d hours from OpenAQ, %d new",
                             station_id, a.date(), b.date(), len(rows), added)
                except Exception as exc:  # noqa: BLE001
                    conn.rollback()
                    errors.append(error_entry(station_id, f"pm25 {a.date()}..{b.date()}", exc))
                    log.exception("Station %s: chunk %s → %s failed", station_id, a, b)

        status = run_status(stages_ok, errors)
        db.finish_run(conn, run_id, status, total,
                      "; ".join(f"{e['station_id']}/{e['stage']}/{e['kind']}" for e in errors) or None, errors)
        report = [coverage(conn, sid, start, end) for sid in ids]

    print(f"\nBackfill {start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M} UTC ({days} ngày), run {run_id}: {status}")
    print(f"{'Trạm':>10} {'Giờ cần':>8} {'Có bản ghi':>11} {'Dùng được':>10} {'% dùng được':>12}")
    for c in report:
        print(f"{c.station_id:>10} {c.expected:>8} {c.stored:>11} {c.usable:>10} {c.usable_pct:>11.1f}%")
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=14, help="How many days back from now (default 14)")
    parser.add_argument("--stations", help="Comma-separated OpenAQ location ids (default ACTIVE_STATION_IDS)")
    parser.add_argument("--chunk-days", type=int, default=7)
    args = parser.parse_args()
    ids = [int(x) for x in args.stations.split(",") if x.strip()] if args.stations else None
    run(args.days, ids, args.chunk_days)


if __name__ == "__main__":
    main()
