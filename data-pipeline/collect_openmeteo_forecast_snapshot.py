"""Append-only Open-Meteo weather forecast snapshots for prospective evaluation."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/prospective/openmeteo_snapshots"
URL = "https://api.open-meteo.com/v1/forecast"
VARIABLES = ("temperature_2m", "relative_humidity_2m", "precipitation", "surface_pressure",
             "wind_speed_10m", "wind_direction_10m", "cloud_cover", "boundary_layer_height")


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def usable_at(snapshot, issued_at, valid_time):
    retrieved = datetime.fromisoformat(snapshot["retrieved_at"])
    return retrieved <= issued_at < valid_time and valid_time.isoformat() in {
        row["valid_time"] for row in snapshot["forecast_hours"]}


def save_snapshot(response, retrieved_at, params, output=OUT):
    if response.get("utc_offset_seconds") != 0:
        raise ValueError("Snapshot must use UTC")
    if any("\ufffd" in str(unit) for unit in (response.get("hourly_units") or {}).values()):
        raise ValueError("Forecast units were not decoded as UTF-8")
    hourly = response["hourly"]
    fingerprint = {"latitude": response.get("latitude"), "longitude": response.get("longitude"),
                   "hourly": hourly, "hourly_units": response.get("hourly_units")}
    snapshot_id = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{snapshot_id}.json"
    if path.exists():
        return path, False
    future = []
    for i, value in enumerate(hourly["time"]):
        valid = utc(value)
        if valid <= retrieved_at:
            continue
        future.append({"valid_time": valid.isoformat(),
                       **{name: hourly.get(name, [None] * len(hourly["time"]))[i] for name in VARIABLES}})
    if not future:
        raise ValueError("No future forecast hours in response")
    snapshot = {"snapshot_id": snapshot_id, "retrieved_at": retrieved_at.isoformat(),
                "requested_coordinates": {"latitude": params["latitude"], "longitude": params["longitude"]},
                "grid_coordinates": {"latitude": response.get("latitude"), "longitude": response.get("longitude")},
                "endpoint": URL, "request_params": params, "provider_model": response.get("model"),
                "provider_issue_time": None, "issue_time_evidence": "retrieved_at only; provider run time unavailable",
                "timezone": "UTC", "units": response.get("hourly_units"),
                "source": "Open-Meteo Weather Forecast API", "license": "CC BY 4.0",
                "attribution": "Open-Meteo and underlying weather model provider",
                "forecast_hours": future, "raw_response": response}
    try:
        with path.open("x", encoding="utf-8") as file:
            json.dump(snapshot, file, ensure_ascii=False, indent=2)
        return path, True
    except FileExistsError:
        return path, False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="Fetch one forecast snapshot now")
    args = parser.parse_args()
    if not args.sample:
        parser.error("Use --sample for a manual snapshot; no scheduler is installed")
    inventory = json.loads((ROOT / "data/audit/openaq_hanoi_sensor_inventory.json").read_text(encoding="utf-8"))
    dragon = next(row for row in inventory["inventory"] if row["sensor_id"] == 14581375)
    params = {"latitude": dragon["latitude"], "longitude": dragon["longitude"],
              "timezone": "UTC", "hourly": ",".join(VARIABLES), "forecast_hours": 48}
    try:
        response = requests.get(URL, params=params, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Open-Meteo HTTP {response.status_code}")
        response.encoding = "utf-8"
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(f"Open-Meteo: {payload.get('reason', 'API error')}")
    except requests.RequestException as exc:
        raise RuntimeError(f"Open-Meteo network error: {type(exc).__name__}") from None
    retrieved_at = datetime.now(timezone.utc)
    path, created = save_snapshot(payload, retrieved_at, params)
    print(f"snapshot={path.name} created={created} future_hours={len(json.loads(path.read_text(encoding='utf-8'))['forecast_hours'])}")


if __name__ == "__main__":
    main()
