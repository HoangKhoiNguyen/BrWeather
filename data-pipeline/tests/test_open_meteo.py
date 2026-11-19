from datetime import datetime
from unittest.mock import Mock, patch

from brweather_data.connectors.open_meteo import CURRENT_WEATHER, fetch_weather


CURRENT_FIELDS = {
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "uv_index",
    "weather_code",
}


@patch("brweather_data.connectors.open_meteo.requests.get")
def test_fetch_weather_returns_complete_current_payload(mock_get):
    response = Mock()
    response.json.return_value = {
        "current_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
            "apparent_temperature": "°C",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
            "wind_speed_10m": "km/h",
            "wind_direction_10m": "°",
            "uv_index": "",
            "weather_code": "wmo code",
        },
        "current": {
            "time": "2026-11-16T06:00",
            "interval": 900,
            "temperature_2m": 25.1,
            "apparent_temperature": 26.0,
            "relative_humidity_2m": 71,
            "precipitation": 0.0,
            "wind_speed_10m": 8.2,
            "wind_direction_10m": 45,
            "uv_index": 4.3,
            "weather_code": 2,
        },
        "hourly": {"time": []},
        "daily": {"time": []},
    }
    mock_get.return_value = response

    payload = fetch_weather(21.0285, 105.8542)

    response.raise_for_status.assert_called_once_with()
    params = mock_get.call_args.kwargs["params"]
    assert set(params["current"].split(",")) == CURRENT_FIELDS == set(CURRENT_WEATHER)
    assert params["timezone"] == "UTC"
    assert params["wind_speed_unit"] == "kmh"
    assert CURRENT_FIELDS <= payload["current"].keys()
    assert payload["current_units"]["temperature_2m"] == "°C"
    assert payload["current_units"]["relative_humidity_2m"] == "%"
    assert payload["current_units"]["precipitation"] == "mm"
    assert payload["current_units"]["wind_speed_10m"] == "km/h"
    assert payload["brweather_meta"]["source"] == "Open-Meteo"
    assert payload["brweather_meta"]["source_type"] == "MODEL"
    assert datetime.fromisoformat(payload["brweather_meta"]["fetched_at"]).utcoffset().total_seconds() == 0


@patch("brweather_data.connectors.open_meteo.requests.get")
def test_fetch_weather_keeps_missing_current_value_as_null(mock_get):
    response = Mock()
    response.json.return_value = {
        "current": {field: None for field in CURRENT_FIELDS},
        "current_units": {},
        "hourly": {"time": []},
        "daily": {"time": []},
    }
    mock_get.return_value = response

    payload = fetch_weather(21.0285, 105.8542)

    assert payload["current"]["uv_index"] is None
    assert payload["current"]["weather_code"] is None
