"""Hourly reliability score per station (T4.1-3).

    python -m brweather_data.jobs.compute_reliability

For each active station: read the last 24 hours from pm25_hourly_series, run the four checks of
quality/reliability.py, and insert one row into reliability_scores (level, reasons, details).
When a station is stuck (flatline), the stuck hours are also flagged 'flatline' in air_measurements, so
the forecast eligibility rule (T3.1-2) stops treating them as usable. Values are never changed, only flags.

Runs after ingest_hourly in the scheduler; logged in ingest_runs with job = 'compute_reliability'.
"""
import logging
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from brweather_data import db
from brweather_data.config import load_settings
from brweather_data.jobs.ingest_hourly import error_entry, run_status
from brweather_data.quality.reliability_text import messages
from brweather_data.quality.reliability import FLATLINE_HOURS, Reading, assess, flatline_length, neighbour_values

log = logging.getLogger("compute_reliability")
WINDOW = timedelta(hours=24)

STATIONS_SQL = "SELECT id, lat, lon FROM stations WHERE is_active ORDER BY id"
SERIES_SQL = "SELECT hour, value, raw_value, quality_flag, status FROM pm25_hourly_series(%s, %s, %s)"


def station_inputs(series: list[tuple]) -> dict:
    """From pm25_hourly_series rows (hour, value, raw_value, quality_flag, status), oldest first, build:

    values        hourly raw values for the flatline check (None for missing or out-of-range hours,
                  so a run continues across hours already flagged 'flatline')
    latest_value  latest raw value, for the range check
    last_measured hour of the latest raw value, for the stale check
    latest_usable (hour, value) of the latest usable reading, shared with neighbours
    """
    values = [raw if raw is not None and flag != "out_of_range" else None for _, _, raw, flag, _ in series]
    raw_rows = [(hour, raw) for hour, _, raw, _, _ in series if raw is not None]
    usable = [(hour, v) for hour, v, _, _, status in series if status == "ok"]
    return {
        "values": values,
        "latest_value": raw_rows[-1][1] if raw_rows else None,
        "last_measured": raw_rows[-1][0] if raw_rows else None,
        "latest_usable": usable[-1] if usable else (None, None),
    }


def flatline_hours(series: list[tuple], length: int) -> tuple[datetime, datetime] | None:
    """[first, last] hour of the trailing stuck run, if it is at least FLATLINE_HOURS long."""
    if length < FLATLINE_HOURS:
        return None
    present = [hour for hour, _, raw, _, _ in series if raw is not None]
    return present[-length], present[-1]


def run(now: datetime | None = None) -> int:
    settings = load_settings(require_openaq_key=False)
    now = now or datetime.now(timezone.utc)
    end = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)  # include the current hour
    start = end - WINDOW
    written, stages_ok, errors = 0, 0, []

    with db.connect(settings.db_dsn) as conn:
        run_id = db.start_run(conn, "compute_reliability")
        with conn.cursor() as cur:
            cur.execute(STATIONS_SQL)
            stations = cur.fetchall()

        inputs, readings = {}, []
        for sid, lat, lon in stations:
            with conn.cursor() as cur:
                cur.execute(SERIES_SQL, (sid, start, end))
                series = cur.fetchall()
            inputs[sid] = (series, station_inputs(series))
            hour, value = inputs[sid][1]["latest_usable"]
            if flatline_length(inputs[sid][1]["values"]) >= FLATLINE_HOURS:
                value = None  # a stuck station is not a trustworthy neighbour for the others
            readings.append(Reading(sid, lat, lon, value, hour))
        conn.commit()

        for reading in readings:
            sid = reading.station_id
            series, inp = inputs[sid]
            try:
                neighbours = neighbour_values(reading, readings)
                level, reasons, details = assess(
                    inp["values"], inp["last_measured"], now, neighbours, latest_value=inp["latest_value"])
                details.update(messages(level, reasons, details))  # T4.1-4: sentences shown in the app
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO reliability_scores (station_id, computed_at, level, reasons, details)"
                        " VALUES (%s, %s, %s, %s, %s)",
                        (sid, now, level, Jsonb(reasons), Jsonb(details)),
                    )
                    stuck = flatline_hours(series, details["flatline_hours"])
                    if stuck:
                        cur.execute(
                            "UPDATE air_measurements SET quality_flag = 'flatline'"
                            " WHERE source = 'openaq' AND parameter = 'pm25' AND station_id = %s"
                            "   AND measured_at >= %s AND measured_at < %s AND quality_flag = 'ok'",
                            (sid, stuck[0], stuck[1] + timedelta(hours=1)),
                        )
                conn.commit()
                written += 1
                stages_ok += 1
                log.info("Station %s: %s %s", sid, level, reasons)
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                errors.append(error_entry(sid, "reliability", exc))
                log.exception("Station %s: reliability failed", sid)

        status = run_status(stages_ok, errors) if stations else "success"
        db.finish_run(conn, run_id, status, written,
                      "; ".join(f"{e['station_id']}/{e['stage']}" for e in errors) or None, errors)
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()


if __name__ == "__main__":
    main()
