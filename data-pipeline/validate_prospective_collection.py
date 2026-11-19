"""Validate append-only weather/observation snapshots before prospective scoring."""

import json
import csv
import gzip
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEATHER_DIR = ROOT / "data/prospective/openmeteo_snapshots"
OBS_DIR = ROOT / "data/prospective/openaq_observation_snapshots"
OUT = ROOT / "data/prospective/collection_validation.json"


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def validate(weather_files=WEATHER_DIR, observation_files=OBS_DIR):
    weather = [json.loads(path.read_text(encoding="utf-8")) for path in weather_files.glob("*.json")]
    observations = [json.loads(path.read_text(encoding="utf-8")) for path in observation_files.glob("*.json")]
    if not weather or not observations:
        raise RuntimeError("Both weather and observation snapshots are required")
    weather_snapshot = max(weather, key=lambda x: utc(x["retrieved_at"]))
    observation_snapshot = max((x for x in observations if x.get("schema_version") == 2),
                               key=lambda x: utc(x["retrieved_at"]), default=None)
    if observation_snapshot is None:
        raise RuntimeError("No schema-version-2 observation snapshot")
    weather_retrieved = utc(weather_snapshot["retrieved_at"])
    observation_retrieved = utc(observation_snapshot["retrieved_at"])
    forecast_times = [utc(row["valid_time"]) for row in weather_snapshot["forecast_hours"]]
    measurement_times = [utc(row["measurement_time_utc"]) for row in observation_snapshot["records"]]
    issued_at = max(weather_retrieved, observation_retrieved)
    joinable = [time for time in forecast_times if issued_at < time]
    observation_ids = [row["observation_id"] for snapshot in observations if snapshot.get("schema_version") == 2
                       for row in snapshot["records"]]
    target_ready = [row for row in observation_snapshot["records"]
                    if utc(row["measurement_time_utc"]) > issued_at and row["quality_flag"] == "VALID"]
    with gzip.open(ROOT / "data/processed/dragon_pm25_reference_180d.csv.gz", "rt", encoding="utf-8", newline="") as file:
        historical_times = {utc(row["observation_time_utc"]) for row in csv.DictReader(file)}
    new_measurements = {utc(row["measurement_time_utc"]) for row in observation_snapshot["records"]} - historical_times
    checks = {
        "weather_retrieved_at_utc": weather_retrieved.utcoffset().total_seconds() == 0,
        "forecast_strictly_future_at_retrieval": all(time > weather_retrieved for time in forecast_times),
        "observation_sensor_id_correct": observation_snapshot["sensor_id"] == 14581375,
        "observation_measurement_times_utc": all(time.utcoffset().total_seconds() == 0 for time in measurement_times),
        "observation_retrieved_at_utc": observation_retrieved.utcoffset().total_seconds() == 0,
        "observation_units_present": all(bool(row.get("unit")) for row in observation_snapshot["records"]),
        "observation_source_present": all(row.get("source") == "OpenAQ" for row in observation_snapshot["records"]),
        "observation_raw_saved": bool(observation_snapshot.get("raw_pages")),
        "observations_pending_review": all(row.get("quality_flag") == "PENDING_REVIEW" for row in observation_snapshot["records"]),
        "stable_observation_ids_unique": len(observation_ids) == len(set(observation_ids)),
        "prospective_weather_join_available": bool(joinable),
    }
    result = {"validated_at": datetime.now(timezone.utc).isoformat(),
              "weather_snapshot_id": weather_snapshot["snapshot_id"],
              "observation_snapshot_id": observation_snapshot["snapshot_id"],
              "observation_count": len(observation_snapshot["records"]),
              "new_measurements_after_historical_dataset": len(new_measurements),
              "unique_observation_count_across_v2_snapshots": len(set(observation_ids)),
              "issued_at_candidate": issued_at.isoformat(),
              "joinable_future_weather_hours": len(joinable),
              "target_ready_count": len(target_ready),
              "scoring_status": "NOT_SCORABLE_TARGET_NOT_ARRIVED_OR_PENDING_REVIEW",
              "checks": checks}
    if not all(checks.values()):
        result["validation_status"] = "FAIL"
    else:
        result["validation_status"] = "PASS_COLLECTION_NOT_SCORING"
    return result


def main():
    result = validate()
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["validation_status"].startswith("PASS") else 1)


if __name__ == "__main__":
    main()
