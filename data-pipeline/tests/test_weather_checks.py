"""T1.2-1 (24 continuous UTC hours) and T1.3-1 (7 days with every daily field)."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from sample_payloads import START, sample_forecast

from brweather_data.connectors.open_meteo import DAILY_WEATHER, fetch_weather
from brweather_data.quality.weather_checks import check_daily, check_hourly_window

NOW = START + timedelta(hours=7, minutes=10)


def test_complete_payload_has_24_continuous_hours_from_now():
    result = check_hourly_window(sample_forecast(), NOW)
    assert result.ok, result.issues
    assert result.found == result.expected == 24


def test_window_across_midnight_utc_is_continuous():
    late = START + timedelta(hours=22, minutes=30)  # 22:30 UTC: window runs into the next UTC day
    result = check_hourly_window(sample_forecast(), late)
    assert result.ok and result.found == 24


def test_missing_hour_is_reported():
    payload = sample_forecast()
    i = payload["hourly"]["time"].index("2026-11-20T10:00")
    for values in payload["hourly"].values():
        del values[i]
    result = check_hourly_window(payload, NOW)
    assert not result.ok
    assert result.found == 23
    assert "missing_hour:2026-11-20T10:00:00+00:00" in result.issues


def test_non_utc_payload_is_reported():
    payload = sample_forecast()
    payload["timezone"], payload["utc_offset_seconds"] = "Asia/Bangkok", 25200
    assert any(i.startswith("timezone_not_utc") for i in check_hourly_window(payload, NOW).issues)


def test_missing_field_and_all_null_field_are_reported():
    payload = sample_forecast()
    del payload["hourly"]["uv_index"]
    payload["hourly"]["precipitation_probability"] = [None] * len(payload["hourly"]["time"])
    issues = check_hourly_window(payload, NOW).issues
    assert "missing_field:uv_index" in issues
    assert "all_null:precipitation_probability" in issues


def test_single_null_value_is_allowed():
    payload = sample_forecast()
    payload["hourly"]["temperature_2m"][9] = None
    assert check_hourly_window(payload, NOW).ok


def test_duplicate_and_unsorted_times_are_reported():
    payload = sample_forecast()
    times = payload["hourly"]["time"]
    times[8], times[9] = times[9], times[8]
    assert "not_sorted" in check_hourly_window(payload, NOW).issues
    payload = sample_forecast()
    payload["hourly"]["time"][9] = payload["hourly"]["time"][8]
    assert "duplicate_time" in check_hourly_window(payload, NOW).issues


def test_naive_start_is_rejected():
    with pytest.raises(ValueError):
        check_hourly_window(sample_forecast(), datetime(2026, 11, 20, 7))


def test_daily_has_seven_complete_days():
    result = check_daily(sample_forecast())
    assert result.ok, result.issues
    assert result.found == result.expected == 7


def test_daily_missing_day_and_null_value_are_reported():
    payload = sample_forecast(days=6)
    payload["daily"]["precipitation_probability_max"][2] = None
    result = check_daily(payload, first_day=date(2026, 11, 20))
    assert "missing_day:2026-11-26" in result.issues
    assert "null_value:precipitation_probability_max:2026-11-22" in result.issues


def test_daily_max_below_min_is_reported():
    payload = sample_forecast()
    payload["daily"]["temperature_2m_max"][0] = 10.0
    assert "max_below_min:2026-11-20" in check_daily(payload).issues


@patch("brweather_data.connectors.open_meteo.requests.get")
def test_fetch_weather_requests_every_daily_field_for_7_days(mock_get):
    response = Mock()
    response.json.return_value = sample_forecast()
    mock_get.return_value = response

    payload = fetch_weather(21.0285, 105.8542)

    params = mock_get.call_args.kwargs["params"]
    assert params["forecast_days"] == 7
    requested = set(params["daily"].split(","))
    assert requested == set(DAILY_WEATHER)
    assert {"temperature_2m_max", "temperature_2m_min", "precipitation_sum", "precipitation_probability_max",
            "weather_code", "sunrise", "sunset"} <= requested
    assert check_daily(payload).ok
    assert datetime.fromisoformat(payload["brweather_meta"]["fetched_at"]).tzinfo == timezone.utc
