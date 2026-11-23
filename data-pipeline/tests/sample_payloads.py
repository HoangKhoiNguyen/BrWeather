"""Open-Meteo forecast payload with every field brWeather requests, shaped like the real API response.

Values are synthetic (labelled sample data); only the structure matters for the tests.
"""
from datetime import datetime, timedelta, timezone

from brweather_data.connectors.open_meteo import CURRENT_WEATHER, DAILY_WEATHER, HOURLY_WEATHER

START = datetime(2026, 11, 20, tzinfo=timezone.utc)  # Open-Meteo starts at 00:00 UTC of the first day


def _naive(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M")


def sample_forecast(start: datetime = START, days: int = 7) -> dict:
    hours = [start + timedelta(hours=i) for i in range(24 * days)]
    hourly = {"time": [_naive(t) for t in hours]}
    for i, name in enumerate(HOURLY_WEATHER):
        hourly[name] = [round(10 + i + (h % 24) / 4, 2) for h in range(len(hours))]
    hourly["weather_code"] = [3] * len(hours)

    day_list = [(start + timedelta(days=d)).date() for d in range(days)]
    daily = {"time": [d.isoformat() for d in day_list]}
    daily["temperature_2m_max"] = [27.0 + d for d in range(days)]
    daily["temperature_2m_min"] = [19.0 + d for d in range(days)]
    daily["precipitation_sum"] = [0.0, 1.2, 5.4, 0.0, 0.3, 12.0, 0.0][:days]
    daily["precipitation_probability_max"] = [5, 40, 80, 10, 30, 90, 0][:days]
    daily["weather_code"] = [1, 61, 63, 2, 51, 65, 0][:days]
    daily["sunrise"] = [_naive(datetime.combine(d, datetime.min.time()) - timedelta(minutes=45)) for d in day_list]
    daily["sunset"] = [_naive(datetime.combine(d, datetime.min.time()) + timedelta(hours=10, minutes=20))
                       for d in day_list]
    assert set(daily) - {"time"} == set(DAILY_WEATHER)

    current = {"time": _naive(start + timedelta(hours=7)), "interval": 900}
    current.update({name: 1.0 for name in CURRENT_WEATHER})
    return {
        "latitude": 21.0,
        "longitude": 105.75,
        "timezone": "UTC",
        "timezone_abbreviation": "UTC",
        "utc_offset_seconds": 0,
        "current": current,
        "hourly": hourly,
        "daily": daily,
        "brweather_meta": {
            "source": "Open-Meteo",
            "source_type": "MODEL",
            "fetched_at": (start + timedelta(hours=7, minutes=10)).isoformat(),
        },
    }
