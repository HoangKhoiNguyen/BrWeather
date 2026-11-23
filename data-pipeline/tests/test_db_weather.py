"""T1.1-2 / T1.3-2: what insert_weather_snapshot writes (SQL is checked against Postgres in db/tests)."""
from contextlib import contextmanager
from datetime import datetime, timezone

from sample_payloads import sample_forecast

from brweather_data.db import insert_weather_snapshot


class Cursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return (123,)


class Connection:
    def __init__(self):
        self.cursor_instance = Cursor()

    @contextmanager
    def cursor(self):
        yield self.cursor_instance

    def calls_into(self, table):
        return [p for sql, p in self.cursor_instance.calls if f"INSERT INTO {table} " in sql]


def test_insert_weather_snapshot_stores_current_fields():
    conn = Connection()
    payload = {
        "current": {
            "time": "2026-11-16T07:00",
            "temperature_2m": 30.6,
            "apparent_temperature": 33.8,
            "relative_humidity_2m": 60,
            "precipitation": 0.0,
            "weather_code": 0,
            "wind_speed_10m": 12.1,
            "wind_direction_10m": 170,
            "uv_index": 4.45,
        },
        "hourly": {"time": []},
        "daily": {"time": []},
    }

    snapshot_id = insert_weather_snapshot(conn, 21.0285, 105.8542, payload)

    sql, params = conn.cursor_instance.calls[0]
    assert snapshot_id == 123
    assert "current_uv_index" in sql
    assert params[5] == datetime(2026, 11, 16, 7, tzinfo=timezone.utc)  # valid_time, UTC
    assert params[6:] == (30.6, 33.8, 60, 0.0, 0, 12.1, 170, 4.45)


def test_snapshot_keeps_source_fetched_at_and_raw_link():
    conn = Connection()
    payload = sample_forecast()

    insert_weather_snapshot(conn, 21.0, 105.75, payload, raw_payload_id=77)

    (snap,) = conn.calls_into("weather_snapshots")
    lat, lon, fetched_at, source, raw_id, valid_time = snap[:6]
    assert (lat, lon, source, raw_id) == (21.0, 105.75, "open-meteo", 77)
    assert fetched_at == datetime(2026, 11, 20, 7, 10, tzinfo=timezone.utc)
    assert valid_time == datetime(2026, 11, 20, 7, tzinfo=timezone.utc)


def test_snapshot_stores_168_hours_and_7_days_with_rain_probability():
    conn = Connection()

    insert_weather_snapshot(conn, 21.0, 105.75, sample_forecast(), raw_payload_id=1)

    hours = conn.calls_into("weather_hourly")
    days = conn.calls_into("weather_daily")
    assert len(hours) == 168
    assert all(h[1].tzinfo == timezone.utc for h in hours)
    assert len(days) == 7
    day0 = days[0]
    assert str(day0[1]) == "2026-11-20"
    assert day0[2:7] == (27.0, 19.0, 0.0, 5, 1)  # max, min, rain sum, rain probability max, weather code
    assert day0[7].tzinfo == timezone.utc and day0[8].tzinfo == timezone.utc


def test_missing_column_in_response_is_stored_as_null_not_zero():
    conn = Connection()
    payload = sample_forecast(days=1)
    del payload["hourly"]["uv_index"]
    del payload["daily"]["precipitation_probability_max"]

    insert_weather_snapshot(conn, 21.0, 105.75, payload)

    assert all(h[10] is None for h in conn.calls_into("weather_hourly"))  # uv_index
    assert conn.calls_into("weather_daily")[0][5] is None
