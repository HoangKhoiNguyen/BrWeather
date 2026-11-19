"""Audit 30-day OpenAQ hourly PM2.5 coverage for recently active Hanoi sensors."""

import argparse
import csv
import gzip
import json
import os
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "audit"
RAW = AUDIT / "openaq_hours_30d"
CHECKPOINT = AUDIT / "openaq_coverage_checkpoint.json"
BASE = "https://api.openaq.org/v3"
HOUR = timedelta(hours=1)
FIELDS = (
    "sensor_id", "location_id", "location_name", "provider", "owner", "license_status",
    "unit", "inventory_datetime_first", "inventory_datetime_last", "window_start", "window_end",
    "latest_age_hours", "observed_records", "unique_observed_hours", "expected_hours",
    "coverage_percent", "missing_hours", "missing_percent", "duplicate_count",
    "duplicate_percent", "first_observation_in_window", "last_observation_in_window",
    "median_interval_hours", "longest_missing_gap_hours", "negative_value_count",
    "extreme_value_count", "constant_run_count", "longest_constant_run_hours",
    "api_request_count", "audit_status",
)


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


class Client:
    def __init__(self, key):
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = key
        self.calls = 0
        self.remaining = None
        self.last_call = 0.0

    def get(self, path, params=None):
        for attempt in range(4):
            if self.calls >= 1900:
                raise RuntimeError("Đã dùng 1.900 request; dừng để giữ dưới hạn mức giờ")
            time.sleep(max(0, 2.1 - (time.monotonic() - self.last_call)))
            self.last_call = time.monotonic()
            self.calls += 1
            try:
                response = self.session.get(BASE + path, params=params, timeout=30)
            except requests.RequestException as exc:
                if attempt == 3:
                    raise RuntimeError(f"Lỗi mạng: {type(exc).__name__}") from None
                time.sleep(2 ** attempt)
                continue
            self.remaining = response.headers.get("x-ratelimit-remaining", self.remaining)
            code = response.status_code
            if code in (401, 403):
                raise RuntimeError(f"HTTP {code}: khóa hoặc quyền truy cập không hợp lệ")
            if code in (408, 429) or code >= 500:
                if attempt == 3:
                    raise RuntimeError(f"HTTP {code}: hết lượt thử tại {path}")
                retry = response.headers.get("Retry-After")
                time.sleep(min(120, int(retry) if retry and retry.isdigit() else 2 ** (attempt + 1)))
                continue
            if code != 200:
                raise RuntimeError(f"HTTP {code} tại {path}")
            return response.json()
        raise RuntimeError("Hết lượt thử")


def fetch_hours(client, sensor_id, start, end):
    """Return every page; a full page alone never ends pagination."""
    records = []
    page = 1
    while True:
        data = client.get(f"/sensors/{sensor_id}/hours", {
            "datetime_from": start.isoformat(), "datetime_to": end.isoformat(),
            "limit": 1000, "page": page,
        })
        batch = data["results"]
        records.extend(batch)
        found = data.get("meta", {}).get("found")
        if not batch or (found is not None and len(records) >= int(found)) or len(batch) < 1000:
            return records
        page += 1


def classify(row, now):
    if not row["datetime_last"]:
        return "UNKNOWN"
    age = (now - dt(row["datetime_last"])).total_seconds() / 3600
    return "ACTIVE" if age <= 72 else "RECENT" if age <= 168 else "STALE"


def license_for(client, row, locations, cache):
    location = locations[row["location_id"]]
    licenses = location.get("licenses")
    if not licenses:
        if str(row["location_id"]) not in cache:
            cache[str(row["location_id"])] = client.get(f"/locations/{row['location_id']}")["results"][0]
        location = cache[str(row["location_id"])]
        licenses = location.get("licenses")
    terms = []
    for license_item in licenses or []:
        license_id = license_item.get("id")
        if license_id is not None:
            key = f"license:{license_id}"
            if key not in cache:
                cache[key] = client.get(f"/licenses/{license_id}")["results"][0]
            terms.append(cache[key])
    return "LICENSE_METADATA_PRESENT" if licenses else "LICENSE_UNVERIFIED", {
        "licenses": licenses, "provider": location.get("provider"),
        "owner": location.get("owner"), "terms": terms,
    }


def summarize(row, records, start, end, now, requests_used, license_status):
    hours = {}
    duplicate = negative = extreme = 0
    raw = []
    for item in records:
        period = item.get("period") or {}
        stamp = (period.get("datetimeFrom") or {}).get("utc")
        value = item.get("value")
        if not stamp:
            continue
        moment = dt(stamp)
        raw.append({
            "sensor_id": row["sensor_id"], "location_id": row["location_id"],
            "datetime": moment.isoformat(), "value": value, "unit": row["unit"],
            "coordinates": item.get("coordinates"), "provider": row["provider"],
            "owner": row["owner"], "payload": item,
        })
        if not start <= moment < end:
            continue
        hour = moment.replace(minute=0, second=0, microsecond=0)
        if hour in hours:
            duplicate += 1
        if isinstance(value, (int, float)):
            negative += value < 0
            extreme += value > 1000
            if hour not in hours:
                hours[hour] = value
    ordered = sorted(hours)
    expected = int((end - start) / HOUR)
    missing = expected - len(ordered)
    gaps = []
    previous = start - HOUR
    for hour in ordered + [end]:
        gaps.append(max(0, int((hour - previous) / HOUR) - 1))
        previous = hour
    intervals = [(b - a) / HOUR for a, b in zip(ordered, ordered[1:])]
    run_count = longest_run = run = 0
    previous_hour = previous_value = None
    for hour in ordered + [None]:
        value = hours.get(hour)
        if hour is not None and previous_hour is not None and hour - previous_hour == HOUR and value == previous_value:
            run += 1
        else:
            if run >= 6:
                run_count += 1
                longest_run = max(longest_run, run)
            run = 1 if hour is not None else 0
        previous_hour, previous_value = hour, value
    coverage = 100 * len(ordered) / expected
    age = (now - dt(row["datetime_last"])).total_seconds() / 3600
    severe = negative or extreme or run_count
    status = ("GOOD_30D" if age <= 72 and coverage >= 80 and row["unit"] and not severe
              else "USABLE_30D" if age <= 168 and coverage >= 60
              else "POOR_30D")
    result = {
        "sensor_id": row["sensor_id"], "location_id": row["location_id"],
        "location_name": row["location_name"], "provider": row["provider"], "owner": row["owner"],
        "license_status": license_status, "unit": row["unit"],
        "inventory_datetime_first": row["datetime_first"],
        "inventory_datetime_last": row["datetime_last"],
        "window_start": start.isoformat(), "window_end": end.isoformat(),
        "latest_age_hours": round(age, 2), "observed_records": len(raw),
        "unique_observed_hours": len(ordered), "expected_hours": expected,
        "coverage_percent": round(coverage, 2), "missing_hours": missing,
        "missing_percent": round(100 * missing / expected, 2),
        "duplicate_count": duplicate,
        "duplicate_percent": round(100 * duplicate / len(raw), 2) if raw else 0,
        "first_observation_in_window": ordered[0].isoformat() if ordered else None,
        "last_observation_in_window": ordered[-1].isoformat() if ordered else None,
        "median_interval_hours": statistics.median(intervals) if intervals else None,
        "longest_missing_gap_hours": max(gaps), "negative_value_count": negative,
        "extreme_value_count": extreme, "constant_run_count": run_count,
        "longest_constant_run_hours": longest_run, "api_request_count": requests_used,
        "audit_status": status,
    }
    return result, raw, ordered


def plot(rows, hours_by_sensor, start, end):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = ROOT / "reports" / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    labels = [str(r["sensor_id"]) for r in rows]
    fig, ax = plt.subplots(figsize=(9, max(3, len(rows) * .55)))
    ax.barh(labels, [r["coverage_percent"] for r in rows], color="#287e69")
    ax.set(xlim=(0, 100), xlabel="Coverage (%)", ylabel="OpenAQ sensor ID", title="PM2.5 coverage, last 30 days")
    fig.tight_layout()
    fig.savefig(figures / "openaq_coverage_30d.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, max(3, len(rows) * .55)))
    for y, row in enumerate(rows):
        present = hours_by_sensor.get(str(row["sensor_id"]), set())
        ax.broken_barh([(i, 1) for i in range(int((end-start)/HOUR)) if start + i*HOUR in present], (y-.35, .7), facecolors="#287e69")
    ax.set(xlim=(0, int((end-start)/HOUR)), ylim=(-.7, len(rows)-.3), yticks=range(len(rows)),
           yticklabels=labels, xlabel="Hour from window start (UTC); white = missing", title="Observed PM2.5 hours")
    fig.tight_layout()
    fig.savefig(figures / "openaq_timeline_30d.png", dpi=150)
    plt.close(fig)


def main():
    (AUDIT / ".mplconfig").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(AUDIT / ".mplconfig"))
    import matplotlib  # Check chart dependency before making API calls.
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-fetch selected sensors")
    args = parser.parse_args()
    inventory = json.loads((AUDIT / "openaq_hanoi_sensor_inventory.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    groups = {name: [r for r in inventory["inventory"] if classify(r, now) == name]
              for name in ("ACTIVE", "RECENT", "STALE", "UNKNOWN")}
    selected = groups["ACTIVE"][:10] if groups["ACTIVE"] else groups["RECENT"][:5]
    print("Groups:", {name: len(rows) for name, rows in groups.items()})
    print("Selected:", [(r["sensor_id"], r["location_name"]) for r in selected])
    if not selected:
        raise RuntimeError("Không có sensor ACTIVE hoặc RECENT để khảo sát")
    window_end = now.replace(minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(days=30)
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8")) if CHECKPOINT.exists() and not args.force else {
        "window_start": window_start.isoformat(), "window_end": window_end.isoformat(),
        "completed": {}, "license_metadata": {},
    }
    window_start, window_end = dt(checkpoint["window_start"]), dt(checkpoint["window_end"])
    load_dotenv(ROOT / ".env")
    key = os.getenv("OPENAQ_API_KEY")
    if not key:
        raise RuntimeError("OPENAQ_API_KEY chưa được đặt trong .env")
    client = Client(key)
    locations = {r["id"]: r for r in inventory["locations"]}
    RAW.mkdir(parents=True, exist_ok=True)
    for row in selected:
        sensor_id = str(row["sensor_id"])
        raw_path = RAW / f"sensor_{sensor_id}.json.gz"
        if sensor_id in checkpoint["completed"] and raw_path.exists() and not args.force:
            print(f"SKIP sensor {sensor_id}: checkpoint complete")
            continue
        before = client.calls
        try:
            license_status, metadata = license_for(client, row, locations, checkpoint["license_metadata"])
            records = fetch_hours(client, sensor_id, window_start, window_end)
            result, raw, _ = summarize(row, records, window_start, window_end, now,
                                       client.calls-before, license_status)
            with gzip.open(raw_path, "wt", encoding="utf-8") as file:
                json.dump({"sensor_id": row["sensor_id"], "location_id": row["location_id"],
                           "window_start": window_start.isoformat(), "window_end": window_end.isoformat(),
                           "license_metadata": metadata, "records": raw}, file, ensure_ascii=False)
            checkpoint["completed"][sensor_id] = result
            print(f"DONE sensor {sensor_id}: {result['coverage_percent']}% {result['audit_status']}")
        except (RuntimeError, KeyError, ValueError) as exc:
            print(f"FAILED sensor {sensor_id}: {exc}")
            checkpoint["completed"][sensor_id] = {"sensor_id": row["sensor_id"],
                "location_id": row["location_id"], "location_name": row["location_name"],
                "audit_status": "FAILED", "error": str(exc), "api_request_count": client.calls-before}
        checkpoint["rate_limit_remaining"] = client.remaining
        save_json(CHECKPOINT, checkpoint)

    rank = {"GOOD_30D": 0, "USABLE_30D": 1, "POOR_30D": 2, "FAILED": 3}
    rows = sorted(checkpoint["completed"].values(), key=lambda r: (
        rank[r["audit_status"]], -float(r.get("coverage_percent") or 0),
        float(r.get("latest_age_hours") or float("inf"))))
    total_requests = sum(r["api_request_count"] for r in rows)
    remaining = client.remaining if client.remaining is not None else checkpoint.get("rate_limit_remaining")
    csv_path = AUDIT / "openaq_hanoi_coverage_30d.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    save_json(AUDIT / "openaq_hanoi_coverage_30d.json", {
        "run_at": now.isoformat(), "groups": {k: len(v) for k, v in groups.items()},
        "selected_sensor_ids": [r["sensor_id"] for r in selected],
        "api_request_count_this_run": client.calls, "api_request_count_total": total_requests,
        "rate_limit_remaining": remaining,
        "rows": rows, "license_metadata": checkpoint["license_metadata"],
    })
    successful = [r for r in rows if r["audit_status"] != "FAILED"]
    hours_by_sensor = {}
    for row in successful:
        with gzip.open(RAW / f"sensor_{row['sensor_id']}.json.gz", "rt", encoding="utf-8") as file:
            raw = json.load(file)["records"]
        hours_by_sensor[str(row["sensor_id"])] = {dt(r["datetime"]).replace(minute=0, second=0, microsecond=0)
                                                      for r in raw if isinstance(r.get("value"), (int, float))}
    plot(successful, hours_by_sensor, window_start, window_end)
    report = ROOT / "reports" / "openaq_hanoi_coverage_30d.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# OpenAQ Hanoi PM2.5: 30-day coverage", "", f"Run at: {now.isoformat()}",
             f"Window UTC: {window_start.isoformat()} to {window_end.isoformat()}",
             f"Groups: { {k: len(v) for k, v in groups.items()} }",
             f"Selected sensors: {[r['sensor_id'] for r in selected]}",
             f"API requests: {total_requests} total, {client.calls} this run; last known remaining: {remaining}", "",
             "| Sensor | Location | Coverage | Latest age (h) | Missing | Longest gap (h) | Status | License |",
             "|---|---|---:|---:|---:|---:|---|---|"]
    for row in rows:
        lines.append(f"| {row['sensor_id']} | {row['location_name']} | {row.get('coverage_percent', '')} | {row.get('latest_age_hours', '')} | {row.get('missing_hours', '')} | {row.get('longest_missing_gap_hours', '')} | {row['audit_status']} | {row.get('license_status', '')} |")
    best = successful[0] if successful else None
    lines += ["", f"Best sensor: {best['sensor_id'] if best else 'none'}",
              "Recently updated but low coverage: " + ", ".join(str(r["sensor_id"]) for r in successful if r["latest_age_hours"] <= 72 and r["coverage_percent"] < 60),
              "Failed sensors: " + ", ".join(str(r["sensor_id"]) for r in rows if r["audit_status"] == "FAILED"),
              "License metadata absent means LICENSE_UNVERIFIED; check upstream terms before publication.",
              "Expand to 90/180 days only for GOOD_30D or USABLE_30D sensors after review.",
              "", "## License and attribution metadata", ""]
    for row in selected:
        location = checkpoint["license_metadata"].get(str(row["location_id"]), locations[row["location_id"]])
        licenses = location.get("licenses") or []
        if licenses:
            for item in licenses:
                terms = checkpoint["license_metadata"].get(f"license:{item['id']}", {})
                attribution = item.get("attribution") or {}
                lines.append(f"- Sensor {row['sensor_id']}: {item.get('name')} (ID {item['id']}); attribution: {attribution.get('name') or 'unknown'}; attribution URL: {attribution.get('url') or 'missing'}; terms: {terms.get('sourceUrl') or 'missing'}.")
        else:
            lines.append(f"- Sensor {row['sensor_id']}: LICENSE_UNVERIFIED; provider {row['provider']}; owner {row['owner']}.")
    lines += [
              "", "![Coverage](figures/openaq_coverage_30d.png)",
              "![Timeline](figures/openaq_timeline_30d.png)"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Reports: {csv_path}, {report}; requests={total_requests} total/{client.calls} this run, remaining={remaining}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        print(f"Audit failed: {exc}")
        raise SystemExit(1)
