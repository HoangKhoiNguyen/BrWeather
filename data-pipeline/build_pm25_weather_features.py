"""Build leakage-checked Dragon PM2.5 and past/current ERA5 features."""

import csv
import gzip
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evaluate_pm25_baselines import SPLITS, HOUR, stamp

ROOT = Path(__file__).resolve().parents[1]
WEATHER = ROOT / "data/weather/openmeteo_dragon_era5_hourly.csv.gz"
WEATHER_META = ROOT / "data/weather/openmeteo_dragon_era5_metadata.json"
PM = ROOT / "data/processed/dragon_pm25_reference_180d.csv.gz"
OUT = ROOT / "data/modeling"
PM_LAGS = (1, 3, 6, 24, 168)
PM_WINDOWS = (3, 6, 24, 168)
WEATHER_LAGS = (1, 3, 6, 24)
WEATHER_WINDOWS = (6, 24)
WEATHER_VARS = ("temperature_2m", "relative_humidity_2m", "precipitation", "surface_pressure",
                "wind_speed_10m", "cloud_cover", "boundary_layer_height", "wind_sin", "wind_cos")


def number(value):
    return float(value) if value not in (None, "") else None


def load_inputs():
    with gzip.open(PM, "rt", encoding="utf-8", newline="") as file:
        pm = {stamp(r["observation_time_utc"]): number(r["pm2_5_ml"])
              for r in csv.DictReader(file)}
    with gzip.open(WEATHER, "rt", encoding="utf-8", newline="") as file:
        weather = {}
        for row in csv.DictReader(file):
            direction = number(row["wind_direction_10m"])
            values = {v: number(row[v]) for v in WEATHER_VARS if v not in ("wind_sin", "wind_cos")}
            values["wind_sin"] = math.sin(math.radians(direction)) if direction is not None else None
            values["wind_cos"] = math.cos(math.radians(direction)) if direction is not None else None
            weather[stamp(row["valid_time_utc"])] = values
    meta = json.loads(WEATHER_META.read_text(encoding="utf-8"))
    return pm, weather, meta


def rolling(values):
    if any(v is None for v in values):
        return None
    return (sum(values)/len(values), min(values), max(values))


def features_at(issued, pm, weather):
    """Return features only if all requested PM2.5 history exists."""
    used_times = [issued]
    feature = {"pm25_current": pm.get(issued)}
    for lag in PM_LAGS:
        moment = issued - lag*HOUR
        used_times.append(moment)
        feature[f"pm25_lag_{lag}h"] = pm.get(moment)
    for window in PM_WINDOWS:
        times = [issued - i*HOUR for i in range(window)]
        used_times.extend(times)
        values = [pm.get(t) for t in times]
        observed = [v for v in values if v is not None]
        if len(observed) < (135 if window == 168 else window):
            return None
        feature[f"pm25_count_{window}h"] = len(observed)
        mean = sum(observed)/len(observed)
        feature[f"pm25_mean_{window}h"] = mean
        feature[f"pm25_std_{window}h"] = math.sqrt(sum((v-mean)**2 for v in observed)/len(observed))
        feature[f"pm25_min_{window}h"] = min(observed)
        feature[f"pm25_max_{window}h"] = max(observed)
    if any(value is None for value in feature.values()):
        return None
    for var in WEATHER_VARS:
        feature[f"weather_{var}_current"] = weather.get(issued, {}).get(var)
        for lag in WEATHER_LAGS:
            moment = issued - lag*HOUR
            used_times.append(moment)
            feature[f"weather_{var}_lag_{lag}h"] = weather.get(moment, {}).get(var)
        for window in WEATHER_WINDOWS:
            times = [issued-i*HOUR for i in range(window)]
            used_times.extend(times)
            result = rolling([weather.get(t, {}).get(var) for t in times])
            for name, value in zip(("mean", "min", "max"), result or (None, None, None)):
                feature[f"weather_{var}_{name}_{window}h"] = value
    feature["hour_sin"] = math.sin(2*math.pi*issued.hour/24)
    feature["hour_cos"] = math.cos(2*math.pi*issued.hour/24)
    feature["day_of_year_sin"] = math.sin(2*math.pi*issued.timetuple().tm_yday/365.25)
    feature["day_of_year_cos"] = math.cos(2*math.pi*issued.timetuple().tm_yday/365.25)
    feature["day_of_week"] = issued.weekday()
    feature["weekend"] = int(issued.weekday() >= 5)
    assert max(used_times) <= issued
    return feature


def main():
    pm, weather, meta = load_inputs()
    weather_end = stamp(meta["last_available_valid_time"]) + HOUR
    end = min(SPLITS[-1][2], weather_end)
    rows = []
    missing_weather = {}
    for split, start, split_end in SPLITS:
        stop = min(split_end, end)
        issued = start
        while issued < stop:
            feature = features_at(issued, pm, weather)
            if feature is not None:
                for horizon in (1, 6, 24):
                    valid = issued + horizon*HOUR
                    target = pm.get(valid) if valid < stop else None
                    if target is None:
                        continue
                    rows.append({"sensor_id": 14581375, "source_type": "REFERENCE_OBSERVATION_FOR_PROTOTYPE",
                                 "split": split, "issued_at": issued.isoformat(), "valid_time": valid.isoformat(),
                                 "horizon_hours": horizon, "target_pm25": target,
                                 "persistence": pm[issued], "max_feature_time_utc": issued.isoformat(), **feature})
            issued += HOUR
    if not rows:
        raise RuntimeError("No valid PM2.5/weather feature rows")
    pm_features = [key for key in rows[0] if key.startswith("pm25_") or key in
                   ("hour_sin", "hour_cos", "day_of_year_sin", "day_of_year_cos", "day_of_week", "weekend")]
    weather_features = [key for key in rows[0] if key.startswith("weather_")]
    for split, _, _ in SPLITS:
        part = [r for r in rows if r["split"] == split]
        missing_weather[split] = {name: sum(r[name] is None for r in part) for name in weather_features}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "dragon_pm25_weather_features.csv.gz"
    with gzip.open(path, "wt", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    schema = {"sensor_id": 14581375, "role": "REFERENCE_OBSERVATION_FOR_PROTOTYPE",
              "pm25_features": pm_features, "weather_features": weather_features,
              "weather_source": "Open-Meteo ERA5 reanalysis", "weather_endpoint": meta["endpoint"],
              "weather_available_through": meta["last_available_valid_time"],
              "effective_test_end_exclusive": end.isoformat(),
              "forecast_vintage_status": "NOT_EVALUATED_NO_FORECAST_VINTAGE",
              "weather_feature_rule": "valid_time <= issued_at; retrospective reanalysis proxy, not a proven real-time feed",
              "missing_weather_by_feature_split": missing_weather,
              "sample_counts": {split: {str(h): sum(r["split"] == split and r["horizon_hours"] == h for r in rows)
                                        for h in (1, 6, 24)} for split, _, _ in SPLITS}}
    (OUT / "dragon_pm25_weather_feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"feature_rows={len(rows)} test_end={end.isoformat()} sample_counts={schema['sample_counts']}")


if __name__ == "__main__":
    main()
