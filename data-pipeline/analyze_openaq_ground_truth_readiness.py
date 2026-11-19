"""Analyze saved 180-day OpenAQ observations without changing raw data."""

import csv
import gzip
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from audit_openaq_coverage import Client, dt, save_json, HOUR
from audit_openaq_long_term import SENSORS, hours_in, runs, write_csv
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "audit"
FIGURES = ROOT / "reports" / "figures"
CACHE = AUDIT / "openaq_readiness_metadata_cache.json"
LAGS = {"BASIC": (1, 3, 6, 24), "SEASONAL": (1, 3, 6, 24, 168)}
HORIZONS = (1, 6, 24)


def gaps(hours, start, end, sensor_id, location_name):
    """List every absent run, including leading and trailing hours."""
    result = []
    prior = start - HOUR
    prior_value = None
    for moment in sorted(hours) + [end]:
        gap_start = prior + HOUR
        gap_end = moment - HOUR
        length = int((moment-prior)/HOUR) - 1
        if length > 0:
            result.append({"sensor_id": sensor_id, "location_name": location_name,
                           "gap_start_utc": gap_start.isoformat(), "gap_end_utc": gap_end.isoformat(),
                           "duration_hours": length, "previous_value": prior_value,
                           "next_value": hours.get(moment), "year_month": gap_start.strftime("%Y-%m")})
        prior, prior_value = moment, hours.get(moment)
    return result


def sample_counts(hours, start, end, lags, horizon, suspect=frozenset()):
    """Mutually exclusive invalid reasons: lag, then target, then suspect."""
    counts = {"candidate_timestamps": 0, "valid_samples": 0,
              "invalid_due_to_missing_lag": 0, "invalid_due_to_missing_target": 0,
              "invalid_due_to_suspect_data": 0}
    by_month = defaultdict(int)
    t = start
    while t + horizon * HOUR < end:
        counts["candidate_timestamps"] += 1
        features = [t - lag * HOUR for lag in lags]
        target = t + horizon * HOUR
        if any(x not in hours for x in features):
            counts["invalid_due_to_missing_lag"] += 1
        elif target not in hours:
            counts["invalid_due_to_missing_target"] += 1
        elif target in suspect or any(x in suspect for x in features):
            counts["invalid_due_to_suspect_data"] += 1
        else:
            counts["valid_samples"] += 1
            by_month[t.strftime("%Y-%m")] += 1
        t += HOUR
    counts["valid_sample_percent"] = round(100 * counts["valid_samples"] / counts["candidate_timestamps"], 2) if counts["candidate_timestamps"] else 0
    return counts, dict(by_month)


def anomaly_counts(hours, start, end, window):
    total = int((end-start)/HOUR)
    eligible = sum(t in hours and all(t - lag*HOUR in hours for lag in range(1, window+1))
                   for t in (start + i*HOUR for i in range(total)))
    return {"eligible_points": eligible, "ineligible_due_to_gap": total-eligible,
            "eligible_percent": round(100*eligible/total, 2)}


def request_metadata(client, cache, path, params=None):
    key = path + "?" + json.dumps(params or {}, sort_keys=True)
    if key not in cache["responses"]:
        cache["responses"][key] = client.get(path, params)
        cache["requests"].append({"path": path, "params": params or {}, "purpose": "targeted provenance/zero-run check"})
        save_json(CACHE, cache)
    return cache["responses"][key]


def instrument_review(client, cache, inventory):
    locations = {r["id"]: r for r in inventory["locations"]}
    rows = []
    for sensor_id in SENSORS:
        row = next(r for r in inventory["inventory"] if r["sensor_id"] == sensor_id)
        location = locations[row["location_id"]]
        instruments = []
        for item in location.get("instruments") or []:
            detail = request_metadata(client, cache, f"/instruments/{item['id']}")["results"][0]
            instruments.append(detail)
        described = bool(instruments and all(x.get("name") and (x.get("manufacturer") or {}).get("name") for x in instruments))
        generic = any("Unknown" in (x.get("manufacturer") or {}).get("name", "") or x.get("name") == "Government Monitor" for x in instruments)
        status = "INSTRUMENT_VERIFIED" if described and not generic else "INSTRUMENT_PARTIALLY_DESCRIBED" if instruments else "INSTRUMENT_UNVERIFIED"
        rows.append({"sensor_id": sensor_id, "location": row["location_name"],
                     "latitude": row["latitude"], "longitude": row["longitude"],
                     "is_mobile": row["is_mobile"], "is_monitor": row["is_monitor"],
                     "provider": row["provider"], "owner": row["owner"],
                     "instrument_manufacturer": "; ".join((x.get("manufacturer") or {}).get("name", "") for x in instruments) or None,
                     "instrument_model": "; ".join(x.get("name", "") for x in instruments) or None,
                     "instrument_type": "; ".join("monitor" if x.get("isMonitor") else "sensor" for x in instruments) or None,
                     "license": row["license"],
                     "attribution": "; ".join((x.get("attribution") or {}).get("name", "") for x in location.get("licenses") or []) or None,
                     "metadata_source": "OpenAQ inventory location + /v3/instruments/{id}",
                     "instrument_status": status})
    return rows


def plot(gap_rows, sample_rows, start, end):
    os.environ.setdefault("MPLCONFIGDIR", str(AUDIT / ".mplconfig"))
    (AUDIT / ".mplconfig").mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 3.5))
    for i, sensor in enumerate(SENSORS):
        bars = []
        for gap in gap_rows:
            if gap["sensor_id"] == sensor and gap["duration_hours"] >= 3:
                bars.append(((dt(gap["gap_start_utc"])-start)/HOUR, gap["duration_hours"]))
        ax.broken_barh(bars, (i-.35, .7), facecolors="#c65944")
    ax.set(xlim=(0, (end-start)/HOUR), ylim=(-.7, 2.7), yticks=range(3),
           yticklabels=[str(s) for s in SENSORS], xlabel="Hour from window start (UTC); red = missing >=3h",
           title="OpenAQ PM2.5 gap comparison")
    fig.tight_layout()
    fig.savefig(FIGURES / "openaq_gap_comparison.png", dpi=150)
    plt.close(fig)

    months = sorted({m for r in sample_rows for m in r["valid_samples_by_month"]})
    fig, ax = plt.subplots(figsize=(11, 4))
    for sensor in SENSORS:
        row = next(r for r in sample_rows if r["sensor_id"] == sensor and r["lag_set"] == "BASIC"
                   and r["horizon_hours"] == 24 and r["scenario"] == "EXCLUDE_SUSPECT")
        ax.plot(months, [row["valid_samples_by_month"].get(m, 0) for m in months], marker="o", label=str(sensor))
    ax.set(xlabel="UTC month of feature timestamp", ylabel="Valid 24h samples",
           title="PM2.5 24h target samples, basic lags, suspect zeros excluded")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(title="Sensor ID")
    fig.tight_layout()
    fig.savefig(FIGURES / "openaq_valid_ml_samples_by_month.png", dpi=150)
    plt.close(fig)


def main():
    inventory = json.loads((AUDIT / "openaq_hanoi_sensor_inventory.json").read_text(encoding="utf-8"))
    long_checkpoint = json.loads((AUDIT / "openaq_long_term_checkpoint.json").read_text(encoding="utf-8"))
    start, end = dt(long_checkpoint["window_start"]), dt(long_checkpoint["window_end"])
    raw = {}
    hours = {}
    names = {}
    for sensor_id in SENSORS:
        with gzip.open(AUDIT / "openaq_hours_180d" / f"sensor_{sensor_id}.json.gz", "rt", encoding="utf-8") as file:
            raw[sensor_id] = json.load(file)["records"]
        hours[sensor_id] = hours_in(raw[sensor_id], start, end)
        names[sensor_id] = next(r["location_name"] for r in inventory["inventory"] if r["sensor_id"] == sensor_id)
    gap_rows = [g for sensor in SENSORS for g in gaps(hours[sensor], start, end, sensor, names[sensor])]
    write_csv(AUDIT / "openaq_gap_analysis.csv", [g for g in gap_rows if g["duration_hours"] >= 3],
              ("sensor_id", "location_name", "gap_start_utc", "gap_end_utc", "duration_hours",
               "previous_value", "next_value", "year_month"))

    dragon_runs = [r for r in runs(hours[14581375]) if r["value"] == 0]
    zero_groups = []
    for moment in sorted(t for t, value in hours[14581375].items() if value == 0):
        if zero_groups and moment - zero_groups[-1][-1] == HOUR:
            zero_groups[-1].append(moment)
        else:
            zero_groups.append([moment])
    suspect = {t for run in dragon_runs for t in
               (dt(run["start"]) + i*HOUR for i in range(run["hours"]))}
    sample_rows = []
    for sensor in SENSORS:
        for lag_name, lags in LAGS.items():
            for horizon in HORIZONS:
                for scenario in ("KEEP_SUSPECT", "EXCLUDE_SUSPECT"):
                    counts, monthly = sample_counts(hours[sensor], start, end, lags, horizon,
                                                     suspect if sensor == 14581375 and scenario == "EXCLUDE_SUSPECT" else frozenset())
                    sample_rows.append({"sensor_id": sensor, "location_name": names[sensor], "lag_set": lag_name,
                                        "horizon_hours": horizon, "scenario": scenario, **counts,
                                        "valid_samples_by_month": monthly})
    write_csv(AUDIT / "openaq_ml_sample_readiness.csv", [
        {**r, "valid_samples_by_month": json.dumps(r["valid_samples_by_month"])} for r in sample_rows],
              [k for k in sample_rows[0] if k != "valid_samples_by_month"] + ["valid_samples_by_month"])
    anomaly_rows = [{"sensor_id": sensor, "rolling_window_hours": window,
                     **anomaly_counts(hours[sensor], start, end, window)}
                    for sensor in SENSORS for window in (24, 168)]
    write_csv(AUDIT / "openaq_anomaly_window_readiness.csv", anomaly_rows, anomaly_rows[0].keys())

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"responses": {}, "requests": []}
    load_dotenv(ROOT / ".env")
    key = os.getenv("OPENAQ_API_KEY")
    if not key:
        raise RuntimeError("OPENAQ_API_KEY chưa được đặt trong .env")
    client = Client(key)
    instruments = instrument_review(client, cache, inventory)
    write_csv(AUDIT / "openaq_instrument_review.csv", instruments, instruments[0].keys())
    zero_start = datetime(2026, 11, 9, 4, tzinfo=timezone.utc)
    zero_end = datetime(2026, 11, 9, 18, tzinfo=timezone.utc)
    params = {"datetime_from": zero_start.isoformat(), "datetime_to": zero_end.isoformat(), "limit": 1000, "page": 1}
    pm1 = request_metadata(client, cache, "/sensors/14581374/hours", params)["results"]
    humidity = request_metadata(client, cache, "/sensors/14581376/hours", params)["results"]
    flags = request_metadata(client, cache, "/sensors/14581375/flags", params)["results"]

    plot(gap_rows, sample_rows, start, end)
    hanoi_a = {t for t in (start+i*HOUR for i in range(int((end-start)/HOUR))) if t not in hours[13502151]}
    hanoi_b = {t for t in (start+i*HOUR for i in range(int((end-start)/HOUR))) if t not in hours[13502154]}
    shared = len(hanoi_a & hanoi_b)
    union = len(hanoi_a | hanoi_b)
    shared_gap_start = datetime(2026, 6, 25, 14, tzinfo=timezone.utc)
    dragon_during_shared_gap = sum(shared_gap_start + i*HOUR in hours[14581375] for i in range(86))
    split_train = datetime(2026, 9, 1, tzinfo=timezone.utc)
    split_test = datetime(2026, 10, 27, tzinfo=timezone.utc)
    splits = {"train": (start, split_train), "validation": (split_train, split_test), "test": (split_test, end)}
    split_counts = {sensor: {name: {h: sample_counts(hours[sensor], a, b, LAGS["BASIC"], h,
                        suspect if sensor == 14581375 else frozenset())[0]["valid_samples"]
                        for h in HORIZONS} for name, (a, b) in splits.items()} for sensor in SENSORS}
    license_reviews = {int(r["sensor_id"]): r for r in csv.DictReader(open(AUDIT / "openaq_hanoi_license_review.csv", encoding="utf-8"))}
    statuses = {}
    for sensor in SENSORS:
        valid24 = next(r["valid_samples"] for r in sample_rows if r["sensor_id"] == sensor and r["lag_set"] == "BASIC"
                       and r["horizon_hours"] == 24 and r["scenario"] == "EXCLUDE_SUSPECT")
        longest = max((g["duration_hours"] for g in gap_rows if g["sensor_id"] == sensor), default=0)
        has_split = all(split_counts[sensor][part][24] >= 100 for part in splits)
        tech = ("TECHNICAL_NOT_READY" if not has_split or valid24 < 1000 else
                "TECHNICAL_LIMITED" if valid24 < 2000 else
                "TECHNICAL_USABLE_WITH_GAPS" if longest >= 48 or (sensor == 14581375 and suspect) else
                "TECHNICAL_READY")
        license_status = license_reviews[sensor]["license_status"]
        instrument_status = next(r["instrument_status"] for r in instruments if r["sensor_id"] == sensor)
        decision = ("GROUND_TRUTH_READY" if tech == "TECHNICAL_READY" and license_status in ("LICENSE_PASS", "LICENSE_PASS_WITH_ATTRIBUTION") and instrument_status == "INSTRUMENT_VERIFIED" else
                    "TECHNICALLY_READY_LICENSE_BLOCKED" if tech == "TECHNICAL_READY" and license_status == "LICENSE_UNVERIFIED" else
                    "TECHNICALLY_READY_INSTRUMENT_UNVERIFIED" if tech == "TECHNICAL_READY" and instrument_status == "INSTRUMENT_UNVERIFIED" else
                    "USABLE_FOR_PROTOTYPE" if tech == "TECHNICAL_USABLE_WITH_GAPS" else "GROUND_TRUTH_NOT_READY")
        statuses[sensor] = (tech, license_status, instrument_status, decision)

    report = ROOT / "reports" / "openaq_ground_truth_readiness_final.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# OpenAQ reference-observation readiness", "", f"Window: {start.isoformat()} to {end.isoformat()} UTC.",
             "This is point-sensor evidence for a project, not absolute truth or an estimate for all Hanoi.",
             f"Supplemental API requests this run: {client.calls}; cached request log: {len(cache['requests'])} entries.",
             "No /hours request was made for the three PM2.5 sensors; saved 180-day raw files were used.", "",
             "## Gap inventory", "", "All gaps of 3+ hours are in data/audit/openaq_gap_analysis.csv; filter duration_hours >= 6, 24, or 48 for larger gaps.",
             f"Hanoi sensors missing-hour intersection: {shared} hours; union: {union} hours; intersection/union: {round(100*shared/union, 2) if union else 0}%.",
             f"Provider/owner: {instruments[0]['provider']} / {instruments[0]['owner']} and {instruments[1]['provider']} / {instruments[1]['owner']}."]
    for sensor in SENSORS:
        major = sorted((g for g in gap_rows if g["sensor_id"] == sensor and g["duration_hours"] >= 24),
                       key=lambda g: -g["duration_hours"])
        counts = {threshold: sum(g["sensor_id"] == sensor and g["duration_hours"] >= threshold for g in gap_rows) for threshold in (3, 6, 24, 48)}
        lines.append(f"- Sensor {sensor}: gap counts >=3/6/24/48h = {counts[3]}/{counts[6]}/{counts[24]}/{counts[48]}.")
        for gap in major:
            lines.append(f"  - {gap['gap_start_utc']} to {gap['gap_end_utc']}: {gap['duration_hours']}h; before {gap['previous_value']}, after {gap['next_value']} µg/m³.")
    lines.append(f"The 86-hour gaps of the two Hanoi-network sensors match exactly, and provider/owner metadata match. This is consistent with a shared upstream interruption, not proof of its cause. Dragon has {dragon_during_shared_gap}/86 observed hours during that interval. Values before/after long gaps differ, but the intervening air quality is unknown; a reset cannot be inferred from these two endpoints alone.")
    lines += ["", "## Dragon zero run", ""]
    for run in dragon_runs:
        before = hours[14581375].get(dt(run["start"])-HOUR)
        after = hours[14581375].get(dt(run["end"])+HOUR)
        lines.append(f"- {run['start']} to {run['end']}: {run['hours']} records, raw value {run['value']} µg/m³; before {before}, after {after}; status SUSPECT_ZERO_RUN.")
    lines.append("- All contiguous raw zero groups: " + "; ".join(f"{group[0].isoformat()} to {group[-1].isoformat()} ({len(group)}h)" for group in zero_groups) + ".")
    pm1_zero = sum(r.get("value") == 0 and dt(r["period"]["datetimeFrom"]["utc"]) in suspect for r in pm1)
    humidity_present = sum(dt(r["period"]["datetimeFrom"]["utc"]) in suspect and r.get("value") is not None for r in humidity)
    lines.append(f"- Targeted PM1: {pm1_zero}/7 zero during the 7-hour PM2.5 run; humidity: {humidity_present}/7 values present. OpenAQ sensor flags: {len(flags)}. Raw PM2.5 flagInfo.hasFlags is false for these zero hours. Hourly timestamps are consecutive. The particle channels may share a problem, but these checks do not prove the cause; retain SUSPECT_ZERO_RUN.")
    lines += ["", "## Instrument and provenance", ""]
    for item in instruments:
        lines.append(f"- {item['sensor_id']}: {item['instrument_model']} / {item['instrument_manufacturer']}; {item['instrument_status']}; provider {item['provider']}; owner {item['owner']}; is_monitor={item['is_monitor']}. OpenAQ instrument metadata does not prove reference-grade performance.")
    lines += ["", "## Valid ML sample counts", "", "Rows below are BASIC/SEASONAL × 1/6/24h; each cell is KEEP_SUSPECT / EXCLUDE_SUSPECT. Full details and reasons for exclusions are in the CSV.", "",
              "| Sensor | Lags | 1h | 6h | 24h |", "|---|---|---:|---:|---:|"]
    for sensor in SENSORS:
        for lag in LAGS:
            values = []
            for horizon in HORIZONS:
                a, b = [next(r["valid_samples"] for r in sample_rows if r["sensor_id"] == sensor and r["lag_set"] == lag and r["horizon_hours"] == horizon and r["scenario"] == scenario) for scenario in ("KEEP_SUSPECT", "EXCLUDE_SUSPECT")]
                values.append(f"{a} / {b}")
            lines.append(f"| {sensor} | {lag} | {' | '.join(values)} |")
    months = sorted({m for r in sample_rows for m in r["valid_samples_by_month"]})
    lines += ["", "### Valid BASIC 24h samples by month (suspect zero run excluded)", "",
              "| Sensor | " + " | ".join(months) + " |",
              "|---|" + "---:|" * len(months)]
    for sensor in SENSORS:
        by_month = next(r["valid_samples_by_month"] for r in sample_rows if r["sensor_id"] == sensor and r["lag_set"] == "BASIC" and r["horizon_hours"] == 24 and r["scenario"] == "EXCLUDE_SUSPECT")
        lines.append(f"| {sensor} | " + " | ".join(str(by_month.get(m, 0)) for m in months) + " |")
    lines += ["", "## Anomaly rolling-window readiness", "", "| Sensor | 24h eligible | 168h eligible |", "|---|---:|---:|"]
    for sensor in SENSORS:
        a, b = [next(r["eligible_points"] for r in anomaly_rows if r["sensor_id"] == sensor and r["rolling_window_hours"] == w) for w in (24, 168)]
        lines.append(f"| {sensor} | {a} | {b} |")
    lines += ["", "## Time-ordered split proposal", "",
              "Use feature timestamps within each interval; targets must also fall inside that interval. Lag history may precede an interval because it is already known at prediction time. Keep the final test untouched during model choice.",
              f"Train: {start.isoformat()} to {split_train.isoformat()}; validation: {split_train.isoformat()} to {split_test.isoformat()}; test: {split_test.isoformat()} to {end.isoformat()} (end exclusive).",
              "", "| Sensor | Split | 1h | 6h | 24h |", "|---|---|---:|---:|---:|"]
    for sensor in SENSORS:
        for part in splits:
            values = split_counts[sensor][part]
            lines.append(f"| {sensor} | {part} | {values[1]} | {values[6]} | {values[24]} |")
    lines += ["", "## Decision", "", "| Sensor | Technical | License | Instrument | Overall |",
              "|---|---|---|---|---|"]
    for sensor in SENSORS:
        lines.append(f"| {sensor} | {' | '.join(statuses[sensor])} |")
    lines += ["", "The test begins after Dragon's 34-hour October gap. Its 7-hour November zero run remains flagged and is excluded from the conservative sample counts; keep the test untouched during model choice.",
              "The numerical sample thresholds are provisional for this learning project; no model was trained. USABLE_FOR_PROTOTYPE means internal analysis only when license is unverified. Long gaps and Dragon's zero run still need review. LICENSE_UNVERIFIED blocks publication and redistribution of the Hanoi-network observations pending provider confirmation.",
              "Source metadata: OpenAQ inventory and targeted /v3/instruments/{id}, /v3/sensors/{id}/hours, /v3/sensors/{id}/flags requests; API docs: https://docs.openaq.org/ .",
              "", "## Supplemental API request log", ""]
    for item in cache["requests"]:
        lines.append(f"- {item['path']} {item['params']}: {item['purpose']}")
    lines += ["", "![Gaps](figures/openaq_gap_comparison.png)",
              "![Valid samples](figures/openaq_valid_ml_samples_by_month.png)"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    draft = ROOT / "reports" / "openaq_permission_request_draft.md"
    draft.write_text("""# Drafts only — do not send automatically

## To OpenAQ

Subject: Permission and provider contact for Hanoi PM2.5 data in a noncommercial student project

Hello OpenAQ team,

I am developing brWeather, a noncommercial educational project in Hanoi. For locations 4946812 and 4946813, sensors 13502151 and 13502154, the API does not show license metadata. Could you identify the original data owner, an official contact channel, applicable license, and required attribution? May we download and retain raw and historical observations in PostgreSQL, analyze them statistically, use them as reference observations to train and evaluate ML models, display current and historical values in our learning app, publish charts and derived metrics, and retain the data and outputs after the project ends? Are there restrictions on any of these uses?

Thank you.

## To the Hanoi data provider / owner (send only after verifying an official contact)

Subject: Request for permission to use two Hanoi PM2.5 station datasets for brWeather

Hello,

We are building brWeather as a noncommercial student project. OpenAQ lists your Hanoi PM2.5 data for locations 4946812 and 4946813. May we download and store raw and historical observations internally in PostgreSQL, conduct statistical analysis, use the data as reference observations for ML training and evaluation, display current and historical measurements in the app, publish charts and derived indicators, and retain the raw data and results after the project ends? Please specify the license, attribution text and links, and any restrictions. We will not treat a lack of reply as permission.

Thank you.
""", encoding="utf-8")
    print(f"Report: {report}; supplemental requests this run={client.calls}")
    print("Hanoi shared missing hours:", shared, "intersection/union %:", round(100*shared/union, 2) if union else 0)
    for sensor in SENSORS:
        print(sensor, statuses[sensor], "BASIC 24h samples:", next(r["valid_samples"] for r in sample_rows if r["sensor_id"]==sensor and r["lag_set"]=="BASIC" and r["horizon_hours"]==24 and r["scenario"]=="EXCLUDE_SUSPECT"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        print(f"Readiness analysis failed: {exc}")
        raise SystemExit(1)
