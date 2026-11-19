"""Manual append-only OpenAQ hourly observation capture for Dragon."""

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from audit_openaq_coverage import Client
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/prospective/openaq_observation_snapshots"
SENSOR_ID = 14581375


def save_snapshot(pages, retrieved_at, output=OUT):
    fingerprint = {"schema_version": 2, "sensor_id": SENSOR_ID, "pages": pages}
    snapshot_id = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{snapshot_id}.json"
    if path.exists():
        return path, False
    existing_ids = set()
    for existing in output.glob("*.json"):
        saved = json.loads(existing.read_text(encoding="utf-8"))
        if saved.get("schema_version") == 2:
            existing_ids.update(row["observation_id"] for row in saved.get("records", []))
    records = []
    seen = set()
    for page_number, page in enumerate(pages, start=1):
        for item in page["results"]:
            moment = ((item.get("period") or {}).get("datetimeFrom") or {}).get("utc")
            if moment:
                parameter = (item.get("parameter") or {}).get("name")
                unit = (item.get("parameter") or {}).get("units")
                identity = {"sensor_id": SENSOR_ID, "measurement_time_utc": moment,
                            "parameter": parameter, "value": item.get("value"), "unit": unit}
                observation_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
                if observation_id in seen or observation_id in existing_ids:
                    continue
                seen.add(observation_id)
                records.append({"observation_id": observation_id, "sensor_id": SENSOR_ID,
                                "measurement_time_utc": moment, "parameter": parameter,
                                "pm2_5": item.get("value"), "unit": unit,
                                "source_flag": item.get("flagInfo"),
                                "retrieved_at": retrieved_at.isoformat(),
                                "source": "OpenAQ", "quality_flag": "PENDING_REVIEW",
                                "raw_page": page_number})
    try:
        with path.open("x", encoding="utf-8") as file:
            json.dump({"schema_version": 2, "snapshot_id": snapshot_id, "retrieved_at": retrieved_at.isoformat(),
                       "sensor_id": SENSOR_ID, "endpoint": f"/v3/sensors/{SENSOR_ID}/hours",
                       "records": records, "raw_pages": pages}, file, ensure_ascii=False)
        return path, True
    except FileExistsError:
        return path, False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="Capture recent Dragon hours now")
    args = parser.parse_args()
    if not args.sample:
        parser.error("Use --sample for manual capture; no scheduler is installed")
    load_dotenv(ROOT / ".env")
    key = os.getenv("OPENAQ_API_KEY")
    if not key:
        raise RuntimeError("OPENAQ_API_KEY is missing")
    client = Client(key)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=48)
    pages = []
    page = 1
    while True:
        payload = client.get(f"/sensors/{SENSOR_ID}/hours", {
            "datetime_from": start.isoformat(), "datetime_to": end.isoformat(),
            "limit": 1000, "page": page,
        })
        pages.append(payload)
        if len(payload["results"]) < 1000 or sum(len(x["results"]) for x in pages) >= int(payload.get("meta", {}).get("found") or 10**9):
            break
        page += 1
    path, created = save_snapshot(pages, datetime.now(timezone.utc))
    print(f"observation_snapshot={path.name} created={created} requests={client.calls}")


if __name__ == "__main__":
    main()
