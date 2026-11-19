"""Audit 180 days of OpenAQ PM2.5 for three preselected Hanoi sensors."""

import csv
import gzip
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from audit_openaq_coverage import Client, dt, fetch_hours, save_json, summarize, HOUR
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "audit"
RAW = AUDIT / "openaq_hours_180d"
CHECKPOINT = AUDIT / "openaq_long_term_checkpoint.json"
SENSORS = (13502151, 13502154, 14581375)


def hours_in(records, start, end):
    result = {}
    for item in records:
        stamp = ((item.get("period") or {}).get("datetimeFrom") or {}).get("utc")
        value = item.get("value")
        if not stamp or not isinstance(value, (int, float)):
            continue
        moment = dt(stamp).replace(minute=0, second=0, microsecond=0)
        if start <= moment < end:
            result.setdefault(moment, value)
    return result


def runs(hours):
    spans = []
    ordered = sorted(hours)
    if not ordered:
        return spans
    first = last = ordered[0]
    value = hours[first]
    for moment in ordered[1:] + [None]:
        if moment is not None and moment-last == HOUR and hours[moment] == value:
            last = moment
            continue
        length = int((last-first)/HOUR) + 1
        if length >= 6:
            spans.append({"start": first.isoformat(), "end": last.isoformat(),
                          "hours": length, "value": value})
        if moment is not None:
            first = last = moment
            value = hours[moment]
    return spans


def month_bounds(start, end):
    cursor = start
    while cursor < end:
        next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1, hour=0)
        stop = min(next_month, end)
        yield cursor, stop, cursor.day == 1 and cursor.hour == 0 and stop == next_month
        cursor = stop


def compare_old(sensor_id, records, start, end):
    path = AUDIT / "openaq_hours_30d" / f"sensor_{sensor_id}.json.gz"
    if not path.exists():
        return {"status": "NO_OLD_RAW"}
    with gzip.open(path, "rt", encoding="utf-8") as file:
        old = json.load(file)
    old_start, old_end = dt(old["window_start"]), dt(old["window_end"])
    lo, hi = max(start, old_start), min(end, old_end)
    before = {dt(r["datetime"]).replace(minute=0, second=0, microsecond=0): r["value"]
              for r in old["records"] if r.get("value") is not None and lo <= dt(r["datetime"]) < hi}
    after = hours_in(records, lo, hi)
    shared = before.keys() & after.keys()
    return {"status": "COMPARED", "overlap_start": lo.isoformat(), "overlap_end": hi.isoformat(),
            "matching_timestamps": len(shared),
            "changed_values": sum(before[t] != after[t] for t in shared),
            "new_late_records": len(after.keys() - before.keys()),
            "old_records_absent_now": len(before.keys() - after.keys())}


def review_license(client, row, locations, cached):
    location_id = str(row["location_id"])
    location = cached.get(location_id) or locations[row["location_id"]]
    if not location.get("licenses"):
        location = client.get(f"/locations/{location_id}")["results"][0]
        cached[location_id] = location
    licenses = location.get("licenses") or []
    details = []
    for item in licenses:
        license_id = item.get("id")
        if license_id is not None:
            key = f"license:{license_id}"
            if key not in cached:
                cached[key] = client.get(f"/licenses/{license_id}")["results"][0]
            details.append(cached[key])
    supported = bool(licenses and details and all(
        x.get("modificationAllowed") and x.get("redistributionAllowed") for x in details))
    restricted = bool(details and any(
        x.get("modificationAllowed") is False or x.get("redistributionAllowed") is False for x in details))
    status = ("LICENSE_RESTRICTED" if restricted else
              "LICENSE_PASS_WITH_ATTRIBUTION" if supported and any(x.get("attributionRequired") for x in details) else
              "LICENSE_PASS" if supported else "LICENSE_UNVERIFIED")
    return {
        "sensor_id": row["sensor_id"], "location_id": row["location_id"],
        "provider": (location.get("provider") or {}).get("name"),
        "owner": (location.get("owner") or {}).get("name"),
        "license_status": status,
        "license_name": "; ".join(x.get("name", "") for x in details) or None,
        "license_url": "; ".join(x.get("sourceUrl", "") for x in details) or None,
        "attribution": "; ".join((x.get("attribution") or {}).get("name", "") for x in licenses) or None,
        "attribution_url": "; ".join((x.get("attribution") or {}).get("url") or "" for x in licenses) or None,
        "storage_allowed": supported, "analysis_training_allowed": supported,
        "noncommercial_app_display_allowed": supported,
        "historical_and_derived_storage_allowed": supported,
        "attribution_required": any(x.get("attributionRequired") for x in details) if details else None,
        "metadata": {"location_licenses": licenses, "license_details": details},
    }


def technical(long_row, monthly, unit):
    if not unit or unit not in ("µg/m³", "ug/m3", "μg/m³") or long_row["coverage_percent"] < 60 or long_row["latest_age_hours"] > 168:
        return "TECHNICAL_FAIL"
    full_month_low = any(m["full_month"] and m["coverage_percent"] < 70 for m in monthly)
    if (long_row["latest_age_hours"] > 72 or long_row["coverage_percent"] < 80 or
        full_month_low or long_row["longest_missing_gap_hours"] >= 48 or
        long_row["negative_value_count"] or long_row["extreme_value_count"] or
        long_row["longest_constant_run_hours"] > 24):
        return "TECHNICAL_CONDITIONAL"
    return "TECHNICAL_PASS_180"


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def charts(coverage, monthly, hourly, start, end):
    os.environ.setdefault("MPLCONFIGDIR", str(AUDIT / ".mplconfig"))
    (AUDIT / ".mplconfig").mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figdir = ROOT / "reports" / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4))
    for i, days in enumerate((30, 90, 180)):
        series = [next(r["coverage_percent"] for r in coverage if r["sensor_id"] == sensor and r["window_days"] == days) for sensor in SENSORS]
        ax.bar([j + (i-1)*.25 for j in range(3)], series, width=.24, label=f"{days} days")
    ax.set(xticks=range(3), xticklabels=[str(s) for s in SENSORS], ylim=(0, 100), ylabel="Coverage (%)", xlabel="Sensor ID")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figdir / "openaq_coverage_30_90_180d.png", dpi=150)
    plt.close(fig)

    months = sorted({r["year_month"] for r in monthly})
    fig, ax = plt.subplots(figsize=(11, 4))
    for sensor in SENSORS:
        by_month = {r["year_month"]: r["coverage_percent"] for r in monthly if r["sensor_id"] == sensor}
        ax.plot(months, [by_month.get(m) for m in months], marker="o", label=str(sensor))
    ax.set(ylim=(0, 100), ylabel="Coverage (%)", xlabel="UTC month")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(title="Sensor ID")
    fig.tight_layout()
    fig.savefig(figdir / "openaq_monthly_coverage.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 3.5))
    n = int((end-start)/HOUR)
    for i, sensor in enumerate(SENSORS):
        have = hourly[sensor]
        ax.broken_barh([(j, 1) for j in range(n) if start + j*HOUR in have], (i-.35, .7), facecolors="#287e69")
    ax.set(xlim=(0, n), ylim=(-.7, 2.7), yticks=range(3), yticklabels=[str(s) for s in SENSORS],
           xlabel="Hour from 180-day window start (UTC); white = missing", title="OpenAQ observed PM2.5 hours")
    fig.tight_layout()
    fig.savefig(figdir / "openaq_long_term_timeline.png", dpi=150)
    plt.close(fig)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    key = os.getenv("OPENAQ_API_KEY")
    if not key:
        raise RuntimeError("OPENAQ_API_KEY chưa được đặt trong .env")
    inventory = json.loads((AUDIT / "openaq_hanoi_sensor_inventory.json").read_text(encoding="utf-8"))
    by_sensor = {r["sensor_id"]: r for r in inventory["inventory"]}
    locations = {r["id"]: r for r in inventory["locations"]}
    now = datetime.now(timezone.utc)
    end = now.replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=180)
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8")) if CHECKPOINT.exists() and not args.force else {
        "window_start": start.isoformat(), "window_end": end.isoformat(),
        "completed": {}, "location_metadata": {}, "license_reviews": {},
    }
    start, end = dt(checkpoint["window_start"]), dt(checkpoint["window_end"])
    client = Client(key)
    RAW.mkdir(parents=True, exist_ok=True)
    for sensor_id in SENSORS:
        path = RAW / f"sensor_{sensor_id}.json.gz"
        sid = str(sensor_id)
        if sid in checkpoint["completed"] and path.exists() and not args.force:
            print(f"SKIP {sensor_id}: checkpoint complete")
            continue
        row = by_sensor[sensor_id]
        print(f"FETCH {sensor_id}: 180 days in 30-day chunks")
        before = client.calls
        try:
            license_review = review_license(client, row, locations, checkpoint["location_metadata"])
            records = []
            cursor = start
            while cursor < end:
                stop = min(cursor + timedelta(days=30), end)
                records.extend(fetch_hours(client, sensor_id, cursor, stop))
                cursor = stop
            with gzip.open(path, "wt", encoding="utf-8") as file:
                json.dump({"sensor_id": sensor_id, "location_id": row["location_id"],
                           "window_start": start.isoformat(), "window_end": end.isoformat(),
                           "license_review": license_review, "records": records}, file, ensure_ascii=False)
            checkpoint["completed"][sid] = {"raw_records": len(records), "api_request_count": client.calls-before}
            checkpoint["license_reviews"][sid] = license_review
            checkpoint["rate_limit_remaining"] = client.remaining
            save_json(CHECKPOINT, checkpoint)
            print(f"DONE {sensor_id}: {len(records)} raw records, {client.calls-before} requests")
        except (RuntimeError, KeyError, ValueError) as exc:
            checkpoint.setdefault("failures", {})[sid] = str(exc)
            save_json(CHECKPOINT, checkpoint)
            raise

    coverage = []
    monthly = []
    comparisons = {}
    constant_spans = {}
    hourly = {}
    decisions = {}
    for sensor_id in SENSORS:
        row = by_sensor[sensor_id]
        with gzip.open(RAW / f"sensor_{sensor_id}.json.gz", "rt", encoding="utf-8") as file:
            records = json.load(file)["records"]
        full_hours = hours_in(records, start, end)
        hourly[sensor_id] = full_hours
        constant_spans[sensor_id] = runs(full_hours)
        for days in (30, 90, 180):
            begin = end - timedelta(days=days)
            result, _, _ = summarize(row, records, begin, end, now, checkpoint["completed"][str(sensor_id)]["api_request_count"], "")
            coverage.append({"sensor_id": sensor_id, "window_days": days,
                             "first_observation": result["first_observation_in_window"],
                             "last_observation": result["last_observation_in_window"],
                             "active_days": len({t.date() for t in hours_in(records, begin, end)}),
                             **result})
        sensor_months = []
        for begin, stop, full in month_bounds(start, end):
            result, _, _ = summarize(row, records, begin, stop, now, 0, "")
            item = {"sensor_id": sensor_id, "year_month": begin.strftime("%Y-%m"),
                    "full_month": full, "observed_hours": result["unique_observed_hours"],
                    **{k: result[k] for k in ("expected_hours", "coverage_percent", "longest_missing_gap_hours",
                          "negative_value_count", "extreme_value_count", "longest_constant_run_hours")}}
            monthly.append(item)
            sensor_months.append(item)
        long_row = next(r for r in coverage if r["sensor_id"] == sensor_id and r["window_days"] == 180)
        tech = technical(long_row, sensor_months, row["unit"])
        license_status = checkpoint["license_reviews"][str(sensor_id)]["license_status"]
        gate = ("GROUND_TRUTH_READY" if tech == "TECHNICAL_PASS_180" and license_status in ("LICENSE_PASS", "LICENSE_PASS_WITH_ATTRIBUTION")
                else "TECHNICALLY_READY_LICENSE_BLOCKED" if tech == "TECHNICAL_PASS_180" else "GROUND_TRUTH_NOT_READY")
        decisions[sensor_id] = {"technical_status": tech, "license_status": license_status, "ground_truth_decision": gate}
        comparisons[sensor_id] = compare_old(sensor_id, records, start, end)

    coverage_path = AUDIT / "openaq_hanoi_coverage_long_term.csv"
    monthly_path = AUDIT / "openaq_hanoi_monthly_coverage.csv"
    license_path = AUDIT / "openaq_hanoi_license_review.csv"
    for item in coverage:
        item.update(decisions[item["sensor_id"]])
    write_csv(coverage_path, coverage, coverage[0].keys())
    write_csv(monthly_path, monthly, monthly[0].keys())
    reviews = [checkpoint["license_reviews"][str(s)] for s in SENSORS]
    write_csv(license_path, reviews, [k for k in reviews[0] if k != "metadata"])
    charts(coverage, monthly, hourly, start, end)

    report = ROOT / "reports" / "openaq_hanoi_ground_truth_decision.md"
    lines = ["# OpenAQ Hanoi: 180-day ground truth gate", "",
             f"Run at {now.isoformat()}; window {start.isoformat()} to {end.isoformat()} UTC.",
             "Ground truth here means a reference observation for this project, not an absolute truth or a citywide estimate.",
             f"API requests: {sum(x['api_request_count'] for x in checkpoint['completed'].values())} total for this checkpoint; {client.calls} this run; last remaining {client.remaining or checkpoint.get('rate_limit_remaining')}.",
             "", "## Coverage and decisions", "",
             "| Sensor | 30d | 90d | 180d | Longest gap (h) | Technical | License | Ground truth |",
             "|---|---:|---:|---:|---:|---|---|---|"]
    for sensor in SENSORS:
        items = {r["window_days"]: r for r in coverage if r["sensor_id"] == sensor}
        d = decisions[sensor]
        lines.append(f"| {sensor} | {items[30]['coverage_percent']}% | {items[90]['coverage_percent']}% | {items[180]['coverage_percent']}% | {items[180]['longest_missing_gap_hours']} | {d['technical_status']} | {d['license_status']} | {d['ground_truth_decision']} |")
    lines += ["", "## Monthly coverage", "", "| Sensor | Month UTC | Complete month | Observed / expected | Coverage | Longest gap (h) |",
              "|---|---|---|---:|---:|---:|"]
    for m in monthly:
        lines.append(f"| {m['sensor_id']} | {m['year_month']} | {m['full_month']} | {m['observed_hours']} / {m['expected_hours']} | {m['coverage_percent']}% | {m['longest_missing_gap_hours']} |")
    lines += ["", "## Constant runs of 6 hours or more", ""]
    for sensor in SENSORS:
        for run in constant_spans[sensor]:
            lines.append(f"- Sensor {sensor}: {run['start']} to {run['end']} UTC, {run['hours']} hours, value {run['value']} µg/m³. Flag for review; not deleted.")
    if not any(constant_spans.values()):
        lines.append("- None found.")
    lines += ["", "## Comparison with saved 30-day raw data", ""]
    for sensor in SENSORS:
        lines.append(f"- Sensor {sensor}: {comparisons[sensor]}")
    lines += ["", "## License review", ""]
    for review in reviews:
        lines.append(f"- Sensor {review['sensor_id']}: {review['license_status']}; provider {review['provider']}; owner {review['owner']}; license {review['license_name'] or 'not in API metadata'}; terms {review['license_url'] or 'missing'}; attribution {review['attribution'] or 'not specified'}. Storage, analysis/training, and noncommercial app display: {'supported by listed license' if review['storage_allowed'] else 'unverified'}.")
    lines += ["", "OpenAQ requires credit to OpenAQ and compliance with upstream provider terms: https://docs.openaq.org/about/terms .",
              "CC BY 4.0 requires credit, a link to the license, and a note of changes: https://creativecommons.org/licenses/by/4.0/ .",
              "", "## Recommendation", ""]
    ready = [s for s in SENSORS if decisions[s]["ground_truth_decision"] == "GROUND_TRUTH_READY"]
    technical_ready = [s for s in SENSORS if decisions[s]["technical_status"] == "TECHNICAL_PASS_180"]
    lines.append(f"Ground-truth-ready sensors: {ready or 'none'}.")
    lines.append(f"TECHNICAL_PASS_180 sensors: {technical_ready or 'none'}.")
    lines.append("Provisional principal for further review: 13502151 (strong recent continuity, but an 86-hour gap and unverified license). Nearby check: 13502154 (same 86-hour gap, so not independent across that outage). Independent comparison candidate: 14581375 (licensed CC BY 4.0, but a 119-hour gap and a 7-hour zero run to review). None is approved as project ground truth yet.")
    lines.append("Scope is these point locations and the measured time window; do not claim representation of all Hanoi.")
    lines.append("Do not load 365 days yet: no sensor passes the 180-day technical gate. After explaining/excluding the long gaps and resolving permissions, check 365 days for seasonality. A window ending in November misses much of winter–spring; do not claim cross-season performance yet.")
    lines += ["", "![Coverage](figures/openaq_coverage_30_90_180d.png)",
              "![Monthly](figures/openaq_monthly_coverage.png)",
              "![Timeline](figures/openaq_long_term_timeline.png)"]
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if any(decisions[s]["ground_truth_decision"] == "TECHNICALLY_READY_LICENSE_BLOCKED" for s in SENSORS):
        draft = ROOT / "reports" / "openaq_data_permission_request_draft.md"
        draft.write_text("""# Draft email — do not send automatically

Subject: Permission to use Hanoi PM2.5 observations in a noncommercial student project

Hello OpenAQ / data provider,

I am developing brWeather, a noncommercial educational project in Hanoi. May I store historical PM2.5 observations for the identified Hanoi sensors in PostgreSQL, analyze them, train and evaluate machine-learning models, and display observations and derived results in the learning app? May I retain both the historical data and derived outputs? Please tell me the applicable license, any restrictions, and the exact attribution required for OpenAQ and the original provider.

Thank you.
""", encoding="utf-8")
    print(f"Report: {report}; requests this run={client.calls}")
    for sensor in SENSORS:
        d = decisions[sensor]
        values = [next(r['coverage_percent'] for r in coverage if r['sensor_id'] == sensor and r['window_days'] == days) for days in (30, 90, 180)]
        print(sensor, values, d)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        print(f"Long-term audit failed: {exc}")
        raise SystemExit(1)
