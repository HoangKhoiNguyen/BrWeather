"""Prepare Dragon PM2.5 reference observations without modifying OpenAQ raw data."""

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/audit/openaq_hours_180d/sensor_14581375.json.gz"
OUT = ROOT / "data/processed"
HOUR = timedelta(hours=1)
ZERO_START = datetime(2026, 11, 9, 10, tzinfo=timezone.utc)
ZERO_END = datetime(2026, 11, 9, 16, tzinfo=timezone.utc)
FIELDS = ("sensor_id", "location_id", "location_name", "observation_time_utc",
          "pm2_5", "pm2_5_ml", "unit", "source_provider", "source_type", "license",
          "attribution", "quality_flag", "usable_for_analysis", "usable_for_ml", "quality_reason")


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def prepare(records, start, end):
    by_time = defaultdict(list)
    for item in records:
        period = item.get("period") or {}
        raw_time = (period.get("datetimeFrom") or {}).get("utc")
        if raw_time:
            moment = stamp(raw_time)
            if start <= moment < end:
                by_time[moment].append(item)
    rows = []
    missing = duplicates = 0
    times = sorted(set(by_time) | {start + i*HOUR for i in range(int((end-start)/HOUR))})
    for moment in times:
        items = by_time.get(moment, [])
        item = items[0] if items else None
        value = item.get("value") if item else None
        period = (item or {}).get("period") or {}
        duplicate = len(items) > 1
        non_hourly = bool(item and (moment.minute or moment.second or moment.microsecond or
                                   period.get("label") != "1hour" or period.get("interval") != "01:00:00"))
        if not item or value is None:
            flag, reason = "MISSING", "No OpenAQ hourly value"
            missing += 1
        elif duplicate:
            flag, reason = "DUPLICATE_TIMESTAMP", f"{len(items)} raw records share this timestamp"
            duplicates += len(items)-1
        elif non_hourly:
            flag, reason = "NON_HOURLY_INTERVAL", "Raw period is not one UTC hour"
        elif value < 0:
            flag, reason = "NEGATIVE_VALUE", "PM2.5 is below zero"
        elif value > 1000:
            flag, reason = "EXTREME_VALUE", "PM2.5 exceeds 1000 ug/m3"
        elif ZERO_START <= moment <= ZERO_END and value == 0:
            flag, reason = "SUSPECT_ZERO_RUN", "Seven consecutive raw PM2.5 zeros; PM1 also zero"
        else:
            flag, reason = "VALID", ""
        usable_analysis = flag in ("VALID", "SUSPECT_ZERO_RUN", "EXTREME_VALUE")
        usable_ml = flag == "VALID"
        rows.append({"sensor_id": 14581375, "location_id": 6123215,
                     "location_name": "Dragon", "observation_time_utc": moment.isoformat(),
                     "pm2_5": value, "pm2_5_ml": value if usable_ml else None,
                     "unit": "µg/m³", "source_provider": "OpenAQ",
                     "source_type": "REFERENCE_OBSERVATION", "license": "CC BY 4.0",
                     "attribution": "srgillo via OpenAQ", "quality_flag": flag,
                     "usable_for_analysis": usable_analysis, "usable_for_ml": usable_ml,
                     "quality_reason": reason})
    assert len({r["observation_time_utc"] for r in rows}) == len(rows)
    return rows, duplicates, missing


def main():
    raw_bytes = RAW.read_bytes()
    digest_before = hashlib.sha256(raw_bytes).hexdigest()
    payload = json.loads(gzip.decompress(raw_bytes))
    start, end = stamp(payload["window_start"]), stamp(payload["window_end"])
    rows, duplicates, missing = prepare(payload["records"], start, end)
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / "dragon_pm25_reference_180d.csv.gz", "wt", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(r["quality_flag"] for r in rows)
    summary = {"sensor_id": 14581375, "source_type": "REFERENCE_OBSERVATION",
               "window_start": start.isoformat(), "window_end": end.isoformat(),
               "raw_records": len(payload["records"]), "output_rows": len(rows),
               "usable_for_ml": sum(r["usable_for_ml"] for r in rows),
               "duplicate_raw_records": duplicates, "missing_hours": missing,
               "quality_flags": {name: counts.get(name, 0) for name in
                   ("VALID", "MISSING", "NEGATIVE_VALUE", "EXTREME_VALUE",
                    "SUSPECT_ZERO_RUN", "DUPLICATE_TIMESTAMP", "NON_HOURLY_INTERVAL")},
               "raw_sha256": digest_before}
    (OUT / "dragon_pm25_quality_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    assert hashlib.sha256(RAW.read_bytes()).hexdigest() == digest_before
    print(summary)


if __name__ == "__main__":
    main()
