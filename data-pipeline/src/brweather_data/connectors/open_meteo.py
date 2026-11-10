"""Open-Meteo clients (no API key). Free for non-commercial use under 10,000 calls/day; attribution required."""
import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

CURRENT_WEATHER = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
    "wind_direction_10m",
]
HOURLY_WEATHER = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "precipitation_probability",
    "weather_code",
    "wind_speed_10m",
    "wind_direction_10m",
    "uv_index",
    "boundary_layer_height",
]
DAILY_WEATHER = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "weather_code",
    "sunrise",
    "sunset",
]


def fetch_weather(lat: float, lon: float, forecast_days: int = 7) -> dict:
    """Current conditions, hourly and daily forecast. Times are UTC; wind in km/h."""
    resp = requests.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": ",".join(CURRENT_WEATHER),
            "hourly": ",".join(HOURLY_WEATHER),
            "daily": ",".join(DAILY_WEATHER),
            "timezone": "UTC",
            "forecast_days": forecast_days,
            "wind_speed_unit": "kmh",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_modelled_pm25(lat: float, lon: float, past_days: int = 1) -> dict:
    """Modelled PM2.5 (CAMS, ~45 km grid). Always label it as modelled data, never as a measurement."""
    resp = requests.get(
        AIR_QUALITY_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "pm2_5",
            "timezone": "UTC",
            "past_days": past_days,
            "forecast_days": 1,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
