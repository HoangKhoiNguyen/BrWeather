"""Hourly PM2.5 anomaly detection and classification (T5.1-1, T5.2-1).

    python -m brweather_data.jobs.detect_anomalies

For every active station: read the last LOOKBACK + HISTORY hours from pm25_hourly_series, flag hours
with the past-only robust z-score (ml/anomaly.py), group them into events, classify each event against
neighbours within 10 km (quality/anomaly_classifier.py), and write it to `anomalies`.

Re-running is safe: an event that touches an existing one (same station, detector, direction) extends it;
otherwise it is inserted once (unique key station_id, detected_by, start_time). Events a person has
reviewed (reviewed = TRUE) keep their category. Logged in ingest_runs with job = 'detect_anomalies'.
"""
import logging
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from brweather_data import db
from brweather_data.config import load_settings
from brweather_data.jobs.ingest_hourly import error_entry, run_status
from brweather_data.ml.anomaly import DETECTOR, LIVE_THRESHOLD, MIN_ABS_DEVIATION, MIN_HISTORY, WINDOW, \
    Event, detect_events
from brweather_data.quality.anomaly_classifier import StationSeries, classify, describe
from brweather_data.quality.reliability import NEIGHBOUR_RADIUS_KM, haversine_km

log = logging.getLogger("detect_anomalies")
LOOKBACK_HOURS = 48           # re-examine the last 48 h each run (late data, ongoing events)
HISTORY_HOURS = WINDOW        # hours before the lookback needed for the robust baseline

STATIONS_SQL = "SELECT id, lat, lon FROM stations WHERE is_active ORDER BY id"
SERIES_SQL = "SELECT hour, raw_value, quality_flag FROM pm25_hourly_series(%s, %s, %s)"

UPDATE_SQL = """
    UPDATE anomalies SET
        start_time     = least(start_time, %(start)s),
        end_time       = greatest(end_time, %(end)s),
        peak_time      = CASE WHEN abs(%(score)s) >= abs(coalesce(score, 0)) THEN %(peak_time)s ELSE peak_time END,
        peak_value     = CASE WHEN abs(%(score)s) >= abs(coalesce(score, 0)) THEN %(peak_value)s ELSE peak_value END,
        baseline_value = CASE WHEN abs(%(score)s) >= abs(coalesce(score, 0)) THEN %(baseline)s ELSE baseline_value END,
        score          = CASE WHEN abs(%(score)s) >= abs(coalesce(score, 0)) THEN %(score)s ELSE score END,
        category       = CASE WHEN reviewed THEN category ELSE %(category)s END,
        description    = CASE WHEN reviewed THEN description ELSE %(description)s END,
        details        = CASE WHEN reviewed THEN details ELSE %(details)s END,
        updated_at     = now()
    WHERE station_id = %(station_id)s AND detected_by = %(detector)s AND direction = %(direction)s
      AND end_time >= %(start)s - interval '2 hours' AND start_time <= %(end)s
    RETURNING id
"""

INSERT_SQL = """
    INSERT INTO anomalies (station_id, start_time, end_time, category, description, detected_by,
                           direction, peak_time, peak_value, baseline_value, score, details)
    VALUES (%(station_id)s, %(start)s, %(end)s, %(category)s, %(description)s, %(detector)s,
            %(direction)s, %(peak_time)s, %(peak_value)s, %(baseline)s, %(score)s, %(details)s)
    ON CONFLICT (station_id, detected_by, start_time) DO NOTHING
    RETURNING id
"""


def to_series(rows: list[tuple]) -> tuple[list[datetime], list[float | None], StationSeries]:
    """pm25_hourly_series rows (hour, raw_value, quality_flag) -> times, detector values, StationSeries.

    Detector values keep flatline-flagged hours (a stuck high value is still an anomaly, classified as
    'data') but drop out_of_range values.
    """
    times = [r[0] for r in rows]
    values = [raw if raw is not None and flag != "out_of_range" else None for _, raw, flag in rows]
    series = StationSeries(raw={h: raw for h, raw, _ in rows},
                           flags={h: flag for h, _, flag in rows if flag is not None})
    return times, values, series


def analyse(times, values, station: StationSeries, neighbours: dict[int, StationSeries],
            first_index: int) -> list[tuple[Event, object]]:
    """Detect events from first_index on and classify each one. Pure: used by the job and the tests."""
    return [(e, classify(e, station, neighbours)) for e in detect_events(times, values, first_index)]


def event_params(station_id: int, event: Event, classification) -> dict:
    return {
        "station_id": station_id, "detector": DETECTOR,
        "start": event.start, "end": event.end, "direction": event.direction,
        "peak_time": event.peak_time, "peak_value": event.peak_value,
        "baseline": round(event.baseline, 2), "score": event.score,
        "category": classification.category, "description": describe(event, classification),
        "details": Jsonb({
            **classification.details,
            "reason": classification.reason,
            "category_label": classification.label,
            "parameters": {"window_hours": WINDOW, "min_history": MIN_HISTORY,
                           "threshold": LIVE_THRESHOLD, "min_abs_deviation": MIN_ABS_DEVIATION},
        }),
    }


def save_event(conn, params: dict) -> str:
    with conn.cursor() as cur:
        cur.execute(UPDATE_SQL, params)
        if cur.fetchone():
            return "updated"
        cur.execute(INSERT_SQL, params)
        return "inserted" if cur.fetchone() else "unchanged"


def run(now: datetime | None = None) -> int:
    settings = load_settings(require_openaq_key=False)
    now = now or datetime.now(timezone.utc)
    end = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    start = end - timedelta(hours=LOOKBACK_HOURS + HISTORY_HOURS)
    saved, stages_ok, errors = 0, 0, []

    with db.connect(settings.db_dsn) as conn:
        run_id = db.start_run(conn, "detect_anomalies")
        with conn.cursor() as cur:
            cur.execute(STATIONS_SQL)
            stations = cur.fetchall()
        data = {}
        for sid, lat, lon in stations:
            with conn.cursor() as cur:
                cur.execute(SERIES_SQL, (sid, start, end))
                data[sid] = (lat, lon, to_series(cur.fetchall()))
        conn.commit()

        for sid, (lat, lon, (times, values, series)) in data.items():
            try:
                neighbours = {nid: other[2][2] for nid, other in data.items()
                              if nid != sid and haversine_km(lat, lon, other[0], other[1]) <= NEIGHBOUR_RADIUS_KM}
                results = analyse(times, values, series, neighbours, first_index=HISTORY_HOURS)
                for event, classification in results:
                    outcome = save_event(conn, event_params(sid, event, classification))
                    log.info("Station %s: %s %s %s→%s %s (%s)", sid, outcome, event.direction,
                             event.start, event.end, classification.category, classification.reason)
                    saved += outcome != "unchanged"
                conn.commit()
                stages_ok += 1
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                errors.append(error_entry(sid, "anomalies", exc))
                log.exception("Station %s: anomaly detection failed", sid)

        status = run_status(stages_ok, errors) if stations else "success"
        db.finish_run(conn, run_id, status, saved,
                      "; ".join(f"{e['station_id']}/{e['stage']}" for e in errors) or None, errors)
    return saved


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()


if __name__ == "__main__":
    main()
