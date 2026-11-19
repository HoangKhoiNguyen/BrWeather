"""Cache ERA5 historical weather at Dragon's recorded coordinates."""

import argparse
import csv
import gzip
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "weather"
CACHE = OUT / "openmeteo_dragon_era5_raw.json"
HOURLY = OUT / "openmeteo_dragon_era5_hourly.csv.gz"
METADATA = OUT / "openmeteo_dragon_era5_metadata.json"
URL = "https://archive-api.open-meteo.com/v1/archive"
VARS = ("temperature_2m", "relative_humidity_2m", "precipitation", "surface_pressure",
        "wind_speed_10m", "wind_direction_10m", "cloud_cover", "boundary_layer_height")


def get(params):
    for attempt in range(3):
        try:
            response = requests.get(URL, params=params, timeout=45)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 2:
                    raise RuntimeError(f"Open-Meteo HTTP {response.status_code}")
                time.sleep(2 ** attempt)
                continue
            if response.status_code != 200:
                raise RuntimeError(f"Open-Meteo HTTP {response.status_code}: {response.text[:200]}")
            payload = response.json()
            if payload.get("error"):
                raise RuntimeError(f"Open-Meteo: {payload.get('reason', 'API error')}")
            return payload
        except requests.RequestException as exc:
            if attempt == 2:
                raise RuntimeError(f"Open-Meteo network error: {type(exc).__name__}") from None
            time.sleep(2 ** attempt)
    raise RuntimeError("Open-Meteo retry limit reached")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-fetch weather rather than use cache")
    args = parser.parse_args()
    inventory = json.loads((ROOT / "data/audit/openaq_hanoi_sensor_inventory.json").read_text(encoding="utf-8"))
    dragon = next(r for r in inventory["inventory"] if r["sensor_id"] == 14581375)
    start = datetime(2026, 5, 15, 9, tzinfo=timezone.utc) - timedelta(hours=168)
    last_day = min(date(2026, 11, 11), datetime.now(timezone.utc).date() - timedelta(days=5))
    if last_day < start.date():
        raise RuntimeError("ERA5 archive is not yet available for the study period")
    OUT.mkdir(parents=True, exist_ok=True)
    cache = {"source": "Open-Meteo Historical Weather", "model": "ERA5",
             "endpoint": URL, "requested_coordinates": {"latitude": dragon["latitude"], "longitude": dragon["longitude"]},
             "timezone": "UTC", "variables": VARS, "chunks": {}}
    if CACHE.exists() and not args.force:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
        if cache["requested_coordinates"] != {"latitude": dragon["latitude"], "longitude": dragon["longitude"]}:
            raise RuntimeError("Cached coordinates do not match Dragon inventory")
        last_day = max(date.fromisoformat(key.split("/")[1]) for key in cache["chunks"])
    request_count = 0
    cursor = start.date()
    while cursor <= last_day:
        stop = min(cursor + timedelta(days=29), last_day)
        key = f"{cursor}/{stop}"
        if key not in cache["chunks"]:
            params = {"latitude": dragon["latitude"], "longitude": dragon["longitude"],
                      "start_date": cursor.isoformat(), "end_date": stop.isoformat(),
                      "hourly": ",".join(VARS), "timezone": "UTC", "models": "era5"}
            cache["chunks"][key] = {"request": params, "fetched_at": datetime.now(timezone.utc).isoformat(),
                                    "response": get(params)}
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            request_count += 1
            print(f"FETCH {key}")
        else:
            print(f"CACHE {key}")
        cursor = stop + timedelta(days=1)
    rows = {}
    units = {}
    grid = None
    for chunk in cache["chunks"].values():
        response = chunk["response"]
        units.update(response.get("hourly_units") or {})
        grid = {"latitude": response.get("latitude"), "longitude": response.get("longitude"),
                "elevation": response.get("elevation")}
        hourly = response["hourly"]
        for i, stamp in enumerate(hourly["time"]):
            moment = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
            if start <= moment < datetime.combine(last_day + timedelta(days=1), datetime.min.time(), timezone.utc):
                rows[moment.isoformat()] = {v: hourly.get(v, [None] * len(hourly["time"]))[i] for v in VARS}
    with gzip.open(HOURLY, "wt", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=("valid_time_utc", *VARS))
        writer.writeheader()
        for stamp in sorted(rows):
            writer.writerow({"valid_time_utc": stamp, **rows[stamp]})
    available = [stamp for stamp, values in rows.items() if any(value is not None for value in values.values())]
    metadata = {"source": cache["source"], "model": "ERA5 reanalysis", "endpoint": URL,
                "requested_coordinates": cache["requested_coordinates"], "selected_grid": grid,
                "timezone": "UTC", "temporal_resolution": "hourly", "spatial_resolution": "0.25 degree (~25 km)",
                "availability_delay": "about 5 days", "hourly_units": units,
                "first_valid_time": min(rows), "last_valid_time": max(rows),
                "last_available_valid_time": max(available),
                "all_null_hours": len(rows) - len(available),
                "fetched_at": max(chunk["fetched_at"] for chunk in cache["chunks"].values()),
                "prepared_at": datetime.now(timezone.utc).isoformat(),
                "request_count_this_run": request_count, "cached_chunks": len(cache["chunks"]),
                "license": "CC BY 4.0", "attribution": "Open-Meteo and ECMWF/Copernicus ERA5",
                "forecast_vintage_available_in_this_dataset": False}
    METADATA.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"weather_hours={len(rows)} requests={request_count} last={max(rows)}")


if __name__ == "__main__":
    main()
