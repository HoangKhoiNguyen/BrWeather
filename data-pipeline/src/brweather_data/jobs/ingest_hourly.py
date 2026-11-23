"""Hourly ingest (F00, F09): PM2.5 from OpenAQ and weather from Open-Meteo for each active station.

Run once:  python -m brweather_data.jobs.ingest_hourly
Backfill:  python -m brweather_data.jobs.backfill_pm25 --days 14   (PM2.5 only, see that module)

Every run is logged in ingest_runs (T2.1-1). Each station and each stage (pm25, weather) is committed on
its own, so one failing station or source does not throw away the others:
  success : every stage of every station worked
  partial : some stages failed; the failures are in ingest_runs.errors, tagged "source" or "internal"
  failed  : nothing worked (or the configuration is wrong)
"""
import argparse
import logging
from datetime import datetime, timedelta, timezone

import requests

from brweather_data import db
from brweather_data.config import load_settings
from brweather_data.connectors.open_meteo import fetch_weather
from brweather_data.connectors.openaq import OpenAQClient, SourceError
from brweather_data.quality.reliability import range_flag
from brweather_data.quality.weather_checks import check_daily, check_hourly_window

log = logging.getLogger("ingest_hourly")
DEFAULT_LOOKBACK = timedelta(hours=48)


def error_kind(exc: BaseException) -> str:
    """'source' when the data provider failed (HTTP error, timeout, rate limit), else 'internal'."""
    if isinstance(exc, (requests.RequestException, SourceError)):
        return "source"
    return "internal"


def error_entry(station_id: int, stage: str, exc: BaseException) -> dict:
    return {
        "station_id": station_id,
        "stage": stage,
        "kind": error_kind(exc),
        "message": f"{type(exc).__name__}: {exc}"[:500],
    }


def run_status(stages_ok: int, errors: list[dict]) -> str:
    if not errors:
        return "success"
    return "partial" if stages_ok > 0 else "failed"


def ingest_pm25(conn, client: OpenAQClient, station_id: int, run_id: int, now: datetime,
                since: datetime | None = None) -> tuple[int, tuple[float, float] | None]:
    """Fetch and store new PM2.5 hours of one station. Returns (rows inserted, station coordinates)."""
    location = client.location(station_id)
    db.save_raw(conn, "openaq", f"/locations/{station_id}", {"results": [location]}, run_id)
    sensor_id = client.pm25_sensor_id(location)
    db.upsert_station(conn, location, sensor_id)
    coords = location.get("coordinates") or {}
    point = (coords["latitude"], coords["longitude"]) if coords.get("latitude") is not None else None
    if sensor_id is None:
        log.warning("Station %s has no PM2.5 sensor, skipped", station_id)
        return 0, point

    start = since or db.latest_measurement(conn, station_id) or now - DEFAULT_LOOKBACK

    def keep_page(request: str, payload: dict) -> None:
        db.save_raw(conn, "openaq", request, payload, run_id)

    rows = [(t, v, range_flag(v)) for t, v in client.hourly(sensor_id, start, now, on_page=keep_page)]
    return db.insert_pm25(conn, station_id, rows), point


def ingest_weather(conn, station_id: int, point: tuple[float, float], run_id: int, now: datetime) -> int:
    """Fetch and store one Open-Meteo snapshot for the station's coordinates. Returns the snapshot id."""
    lat, lon = point
    weather = fetch_weather(lat, lon)
    raw_id = db.save_raw(conn, "open-meteo", f"forecast {station_id} {lat},{lon}", weather, run_id)
    snapshot_id = db.insert_weather_snapshot(conn, lat, lon, weather, raw_payload_id=raw_id)

    # T1.2-1 / T1.3-1: a gap in the source's forecast is logged, not treated as a pipeline failure.
    hourly = check_hourly_window(weather, now, hours=24)
    daily = check_daily(weather, days=7)
    for name, result in (("24h", hourly), ("7d", daily)):
        if not result.ok:
            log.warning("Station %s weather %s check: %d/%d present, issues=%s",
                        station_id, name, result.found, result.expected, result.issues[:10])
    return snapshot_id


def run(since: datetime | None = None) -> int:
    settings = load_settings()
    client = OpenAQClient(settings.openaq_api_key)
    now = datetime.now(timezone.utc)
    total, stages_ok, errors = 0, 0, []

    with db.connect(settings.db_dsn) as conn:
        run_id = db.start_run(conn, "ingest_hourly")
        if not settings.station_ids:
            db.finish_run(conn, run_id, "failed", 0, "ACTIVE_STATION_IDS is empty")
            raise RuntimeError("ACTIVE_STATION_IDS is empty")

        for station_id in settings.station_ids:
            point = None
            try:
                added, point = ingest_pm25(conn, client, station_id, run_id, now, since)
                conn.commit()
                total += added
                stages_ok += 1
                log.info("Station %s: %d new PM2.5 hours", station_id, added)
            except Exception as exc:  # noqa: BLE001 - every failure is recorded, the run goes on
                conn.rollback()
                errors.append(error_entry(station_id, "pm25", exc))
                log.exception("Station %s: PM2.5 failed (%s)", station_id, error_kind(exc))

            try:
                point = point or db.station_coords(conn, station_id)
                if point is None:
                    raise LookupError(f"no coordinates for station {station_id} (OpenAQ never answered)")
                snapshot_id = ingest_weather(conn, station_id, point, run_id, now)
                conn.commit()
                stages_ok += 1
                log.info("Station %s: weather snapshot %s saved", station_id, snapshot_id)
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                errors.append(error_entry(station_id, "weather", exc))
                log.exception("Station %s: weather failed (%s)", station_id, error_kind(exc))

        status = run_status(stages_ok, errors)
        summary = "; ".join(f"{e['station_id']}/{e['stage']}/{e['kind']}" for e in errors) or None
        db.finish_run(conn, run_id, status, total, summary, errors)
        log.info("Run %s finished: %s, %d new PM2.5 hours, %d errors", run_id, status, total, len(errors))

    if status == "failed":
        raise RuntimeError(f"ingest_hourly run {run_id} failed: {summary}")
    return total


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", help="Re-fetch PM2.5 from this UTC date, e.g. 2026-11-01 (prefer backfill_pm25)")
    args = parser.parse_args()
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc) if args.since else None
    run(since)


if __name__ == "__main__":
    main()
