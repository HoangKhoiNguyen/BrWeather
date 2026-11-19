from contextlib import contextmanager

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
    assert params[3:] == (30.6, 33.8, 60, 0.0, 0, 12.1, 170, 4.45)
