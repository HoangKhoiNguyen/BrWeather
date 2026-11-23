"""PostgreSQL access for the pipeline. Schema lives in db/schema.sql (+ db/migrations)."""
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb


def _utc(local_iso: str) -> datetime:
    """Open-Meteo returns naive ISO times when timezone=UTC; mark them as UTC."""
    return datetime.fromisoformat(local_iso).replace(tzinfo=timezone.utc)


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, autocommit=False)


def start_run(conn: psycopg.Connection, job: str) -> int:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO ingest_runs (job) VALUES (%s) RETURNING run_id", (job,))
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def finish_run(
    conn: psycopg.Connection,
    run_id: int,
    status: str,
    records: int,
    error: str | None = None,
    errors: list[dict] | None = None,
) -> None:
    """status: success | partial | failed. errors: one dict per failed station/stage (see migration 008)."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ingest_runs SET finished_at = now(), status = %s, records = %s, error = %s, errors = %s"
            " WHERE run_id = %s",
            (status, records, error, Jsonb(errors or []), run_id),
        )
    conn.commit()


def save_raw(conn: psycopg.Connection, source: str, request: str, payload: dict, run_id: int) -> int:
    """Keep the response exactly as received; returns raw_payloads.id so clean rows can point back to it."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO raw_payloads (source, request, payload, run_id) VALUES (%s, %s, %s, %s) RETURNING id",
            (source, request, Jsonb(payload), run_id),
        )
        return cur.fetchone()[0]


def station_coords(conn: psycopg.Connection, station_id: int) -> tuple[float, float] | None:
    """Coordinates already stored for a station (used when OpenAQ is down but weather can still be fetched)."""
    with conn.cursor() as cur:
        cur.execute("SELECT lat, lon FROM stations WHERE id = %s", (station_id,))
        row = cur.fetchone()
    return (row[0], row[1]) if row else None


def upsert_station(conn: psycopg.Connection, location: dict, pm25_sensor_id: int | None) -> None:
    coords = location.get("coordinates") or {}
    first = (location.get("datetimeFirst") or {}).get("utc")
    last = (location.get("datetimeLast") or {}).get("utc")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stations (id, name, provider, lat, lon, pm25_sensor_id, first_seen, last_seen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name, provider = EXCLUDED.provider,
                pm25_sensor_id = EXCLUDED.pm25_sensor_id, last_seen = EXCLUDED.last_seen
            """,
            (
                location["id"], location["name"], (location.get("provider") or {}).get("name"),
                coords.get("latitude"), coords.get("longitude"), pm25_sensor_id, first, last,
            ),
        )


def latest_measurement(conn: psycopg.Connection, station_id: int) -> datetime | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT max(measured_at) FROM air_measurements WHERE source = 'openaq' AND station_id = %s AND parameter = 'pm25'",
            (station_id,),
        )
        return cur.fetchone()[0]


def insert_pm25(conn: psycopg.Connection, station_id: int, rows: list[tuple[datetime, float | None, str]]) -> int:
    """rows: (hour start UTC, value, quality_flag). Re-running the same hours inserts nothing."""
    inserted = 0
    with conn.cursor() as cur:
        for measured_at, value, flag in rows:
            cur.execute(
                """
                INSERT INTO air_measurements (source, station_id, parameter, measured_at, value, unit, kind, quality_flag)
                VALUES ('openaq', %s, 'pm25', %s, %s, 'µg/m³', 'observed', %s)
                ON CONFLICT DO NOTHING
                """,
                (station_id, measured_at, value, flag),
            )
            inserted += cur.rowcount
    return inserted


def _fetched_at(data: dict) -> datetime:
    """When the pipeline fetched the payload (set by connectors.open_meteo.fetch_weather), else now."""
    meta = (data.get("brweather_meta") or {}).get("fetched_at")
    return datetime.fromisoformat(meta) if meta else datetime.now(timezone.utc)


def _col(block: dict, name: str, i: int):
    """Value i of an Open-Meteo column; a column missing from the response gives NULL, never 0."""
    values = block.get(name)
    return values[i] if values is not None and i < len(values) else None


def insert_weather_snapshot(
    conn: psycopg.Connection,
    lat: float,
    lon: float,
    data: dict,
    raw_payload_id: int | None = None,
) -> int:
    """Store one Open-Meteo response as a snapshot; snapshots are never overwritten.

    Keeps the source, fetched_at (= issue time of this forecast for brWeather), the valid time of the
    "current" block and a link to the raw payload (T1.1-2), plus hourly and daily rows (T1.3-2).
    """
    current = data.get("current") or {}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO weather_snapshots (lat, lon, fetched_at, source, raw_payload_id, current_valid_time,
                current_temperature_c, current_apparent_temperature_c, current_humidity_pct,
                current_precipitation_mm, current_weather_code, current_wind_speed_kmh,
                current_wind_direction_deg, current_uv_index)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING snapshot_id
            """,
            (
                lat, lon, _fetched_at(data), "open-meteo", raw_payload_id,
                _utc(current["time"]) if current.get("time") else None,
                current.get("temperature_2m"), current.get("apparent_temperature"),
                current.get("relative_humidity_2m"), current.get("precipitation"),
                current.get("weather_code"), current.get("wind_speed_10m"),
                current.get("wind_direction_10m"), current.get("uv_index"),
            ),
        )
        snapshot_id = cur.fetchone()[0]
        h = data.get("hourly") or {}
        for i, t in enumerate(h.get("time") or []):
            cur.execute(
                """
                INSERT INTO weather_hourly (snapshot_id, valid_time, temperature_c, apparent_temperature_c,
                    humidity_pct, precipitation_mm, precipitation_prob_pct, weather_code, wind_speed_kmh,
                    wind_direction_deg, uv_index, boundary_layer_height_m)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    snapshot_id, _utc(t), _col(h, "temperature_2m", i), _col(h, "apparent_temperature", i),
                    _col(h, "relative_humidity_2m", i), _col(h, "precipitation", i),
                    _col(h, "precipitation_probability", i), _col(h, "weather_code", i),
                    _col(h, "wind_speed_10m", i), _col(h, "wind_direction_10m", i),
                    _col(h, "uv_index", i), _col(h, "boundary_layer_height", i),
                ),
            )
        d = data.get("daily") or {}
        for i, day in enumerate(d.get("time") or []):
            sunrise, sunset = _col(d, "sunrise", i), _col(d, "sunset", i)
            cur.execute(
                """
                INSERT INTO weather_daily (snapshot_id, day, temperature_max_c, temperature_min_c,
                    precipitation_sum_mm, precipitation_prob_max_pct, weather_code, sunrise, sunset)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    snapshot_id, day, _col(d, "temperature_2m_max", i), _col(d, "temperature_2m_min", i),
                    _col(d, "precipitation_sum", i), _col(d, "precipitation_probability_max", i),
                    _col(d, "weather_code", i),
                    _utc(sunrise) if sunrise else None, _utc(sunset) if sunset else None,
                ),
            )
    return snapshot_id
