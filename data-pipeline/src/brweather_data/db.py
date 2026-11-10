"""PostgreSQL access for the pipeline. Schema lives in db/schema.sql."""
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


def finish_run(conn: psycopg.Connection, run_id: int, status: str, records: int, error: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ingest_runs SET finished_at = now(), status = %s, records = %s, error = %s WHERE run_id = %s",
            (status, records, error, run_id),
        )
    conn.commit()


def save_raw(conn: psycopg.Connection, source: str, request: str, payload: dict, run_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO raw_payloads (source, request, payload, run_id) VALUES (%s, %s, %s, %s)",
            (source, request, Jsonb(payload), run_id),
        )


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


def insert_weather_snapshot(conn: psycopg.Connection, lat: float, lon: float, data: dict) -> int:
    """Store one Open-Meteo response as a snapshot; snapshots are never overwritten."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO weather_snapshots (lat, lon) VALUES (%s, %s) RETURNING snapshot_id", (lat, lon)
        )
        snapshot_id = cur.fetchone()[0]
        h = data["hourly"]
        for i, t in enumerate(h["time"]):
            cur.execute(
                """
                INSERT INTO weather_hourly (snapshot_id, valid_time, temperature_c, apparent_temperature_c,
                    humidity_pct, precipitation_mm, precipitation_prob_pct, weather_code, wind_speed_kmh,
                    wind_direction_deg, uv_index, boundary_layer_height_m)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    snapshot_id, _utc(t), h["temperature_2m"][i], h["apparent_temperature"][i],
                    h["relative_humidity_2m"][i], h["precipitation"][i], h["precipitation_probability"][i],
                    h["weather_code"][i], h["wind_speed_10m"][i], h["wind_direction_10m"][i],
                    h["uv_index"][i], h["boundary_layer_height"][i],
                ),
            )
        d = data["daily"]
        for i, day in enumerate(d["time"]):
            cur.execute(
                """
                INSERT INTO weather_daily (snapshot_id, day, temperature_max_c, temperature_min_c,
                    precipitation_sum_mm, weather_code, sunrise, sunset)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    snapshot_id, day, d["temperature_2m_max"][i], d["temperature_2m_min"][i],
                    d["precipitation_sum"][i], d["weather_code"][i], _utc(d["sunrise"][i]), _utc(d["sunset"][i]),
                ),
            )
    return snapshot_id
