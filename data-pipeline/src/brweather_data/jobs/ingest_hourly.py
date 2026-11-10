"""Hourly ingest (F00, F09): PM2.5 from OpenAQ and weather from Open-Meteo for each active station.

Run once:  python -m brweather_data.jobs.ingest_hourly
Backfill:  python -m brweather_data.jobs.ingest_hourly --since 2024-01-01
"""
import argparse
import logging
from datetime import datetime, timedelta, timezone

from brweather_data import db
from brweather_data.config import load_settings
from brweather_data.connectors.open_meteo import fetch_weather
from brweather_data.connectors.openaq import OpenAQClient
from brweather_data.quality.reliability import range_flag

log = logging.getLogger("ingest_hourly")
DEFAULT_LOOKBACK = timedelta(hours=48)


def run(since: datetime | None = None) -> int:
    settings = load_settings()
    client = OpenAQClient(settings.openaq_api_key)
    now = datetime.now(timezone.utc)
    total = 0

    with db.connect(settings.db_dsn) as conn:
        run_id = db.start_run(conn, "ingest_hourly")
        try:
            for station_id in settings.station_ids:
                location = client.location(station_id)
                sensor_id = client.pm25_sensor_id(location)
                db.upsert_station(conn, location, sensor_id)
                if sensor_id is None:
                    log.warning("Station %s has no PM2.5 sensor, skipped", station_id)
                    continue

                start = since or db.latest_measurement(conn, station_id) or now - DEFAULT_LOOKBACK
                rows = [(t, v, range_flag(v)) for t, v in client.hourly(sensor_id, start, now)]
                added = db.insert_pm25(conn, station_id, rows)

                coords = location["coordinates"]
                weather = fetch_weather(coords["latitude"], coords["longitude"])
                db.save_raw(conn, "open-meteo", f"forecast {station_id}", weather, run_id)
                db.insert_weather_snapshot(conn, coords["latitude"], coords["longitude"], weather)

                conn.commit()
                total += added
                log.info("Station %s: %d new PM2.5 hours, weather snapshot saved", station_id, added)

            db.finish_run(conn, run_id, "success", total)
        except Exception as exc:
            conn.rollback()
            db.finish_run(conn, run_id, "failed", total, str(exc))
            raise
    return total


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", help="Backfill from this UTC date, e.g. 2024-01-01")
    args = parser.parse_args()
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc) if args.since else None
    run(since)


if __name__ == "__main__":
    main()
