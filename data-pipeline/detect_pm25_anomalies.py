"""Explainable PM2.5 data-quality checks and anomaly candidates for Dragon."""

import csv
import gzip
import hashlib
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/dragon_pm25_reference_180d.csv.gz"
BASELINES = ROOT / "data/modeling/baseline_predictions.csv.gz"
CONFIG_PATH = ROOT / "data-pipeline/anomaly_thresholds.json"
OUT = ROOT / "data/anomalies"
FIGURES = ROOT / "reports/figures"
HOUR = timedelta(hours=1)


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def severity_for_duration(hours, thresholds):
    severity = "INFO"
    for name in ("INFO", "WATCH", "WARNING", "CRITICAL"):
        if hours >= thresholds[name]:
            severity = name
    return severity


def stable_id(sensor_id, event_type, detector, start, end):
    value = f"{sensor_id}|{event_type}|{detector}|{start.isoformat()}|{end.isoformat()}"
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def event(event_type, category, severity, start, end, detector, config, **extra):
    return {"event_id": stable_id(config["sensor_id"], event_type, detector, start, end),
            "sensor_id": config["sensor_id"], "event_type": event_type, "category": category,
            "status": "PENDING_REVIEW" if category == "DATA_QUALITY" else "CANDIDATE",
            "severity": severity,
            "severity_scope": "DATA_QUALITY" if category == "DATA_QUALITY" else "DETECTION_CONFIDENCE",
            "start_time": start.isoformat(), "end_time": end.isoformat(),
            "duration_hours": int((end-start)/HOUR)+1, "observed_value": extra.get("observed_value"),
            "reference_value": extra.get("reference_value"), "score": extra.get("score"),
            "threshold": extra.get("threshold"), "detector": detector,
            "quality_context": extra.get("quality_context", "NONE"),
            "explanation": extra.get("explanation", ""),
            "created_at": extra.get("created_at"), "detector_version": config["detector_version"]}


def load_rows(path=DATA):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        row["time"] = utc(row["observation_time_utc"])
        try:
            row["value"] = float(row["pm2_5"]) if row["pm2_5"] != "" else None
        except ValueError:
            row["value"] = row["pm2_5"]
    return rows


def consecutive_groups(times):
    groups = []
    for moment in sorted(times):
        if groups and moment - groups[-1][-1] == HOUR:
            groups[-1].append(moment)
        else:
            groups.append([moment])
    return groups


def quality_events(rows, config, created_at):
    events = []
    missing = [r["time"] for r in rows if r["value"] is None or r.get("quality_flag") == "MISSING"]
    for group in consecutive_groups(missing):
        duration = len(group)
        events.append(event("MISSING_DATA", "DATA_QUALITY",
                            severity_for_duration(duration, config["missing_severity_hours"]),
                            group[0], group[-1], "missing_run", config,
                            threshold="1/2/6/24 hours", created_at=created_at,
                            explanation=f"{duration} consecutive hourly observations are missing"))

    counts = Counter(r["time"] for r in rows)
    invalid = defaultdict(list)
    for row in rows:
        reasons = []
        value = row["value"]
        if counts[row["time"]] > 1:
            reasons.append("DUPLICATE_TIMESTAMP")
        if row["time"].minute or row["time"].second or row["time"].microsecond:
            reasons.append("NON_HOURLY_INTERVAL")
        if row.get("unit") not in config["expected_unit_aliases"]:
            reasons.append("WRONG_UNIT")
        if value is not None and not isinstance(value, float):
            reasons.append("NON_NUMERIC")
        if isinstance(value, float) and (value < config["technical_min"] or value > config["technical_max"]):
            reasons.append("TECHNICAL_RANGE")
        for reason in reasons:
            invalid[reason].append(row)
    for reason, bad in invalid.items():
        for group in consecutive_groups(r["time"] for r in bad):
            values = [r["value"] for r in bad if r["time"] in group and isinstance(r["value"], float)]
            events.append(event("INVALID_VALUE", "DATA_QUALITY", "WARNING", group[0], group[-1],
                                reason.lower(), config, observed_value=max(values) if values else None,
                                threshold=f"{config['technical_min']}..{config['technical_max']}",
                                created_at=created_at, explanation=f"Technical validation failed: {reason}"))

    numeric = {r["time"]: r["value"] for r in rows if isinstance(r["value"], float)}
    zero_groups = consecutive_groups(t for t, value in numeric.items() if value == 0)
    for group in zero_groups:
        if len(group) >= config["zero_run_hours"]:
            events.append(event("SUSPECT_ZERO_RUN", "DATA_QUALITY", "WARNING", group[0], group[-1],
                                "zero_run", config, observed_value=0, threshold=config["zero_run_hours"],
                                created_at=created_at,
                                explanation="Consecutive raw zeros are a sensor-data issue; not a clean-air event"))

    valid = [(r["time"], r["value"]) for r in rows if r.get("quality_flag") == "VALID" and isinstance(r["value"], float)]
    flat_groups = []
    current = []
    for moment, value in valid:
        if current and (moment-current[-1][0] != HOUR or
                        max([x[1] for x in current] + [value])-min([x[1] for x in current] + [value]) > config["flatline_max_range"]):
            flat_groups.append(current)
            current = []
        current.append((moment, value))
    if current:
        flat_groups.append(current)
    for group in flat_groups:
        if len(group) >= config["flatline_min_hours"]:
            events.append(event("FLATLINE", "DATA_QUALITY", "WARNING", group[0][0], group[-1][0],
                                "rolling_range", config, observed_value=statistics.mean(x[1] for x in group),
                                threshold=config["flatline_max_range"], created_at=created_at,
                                explanation=f"Range <= {config['flatline_max_range']} for {len(group)} consecutive valid hours"))
    return events


def stale_event(observation_records, as_of_time, config, created_at):
    if not observation_records:
        return event("STALE_OBSERVATION", "DATA_QUALITY", "CRITICAL", as_of_time, as_of_time,
                     "latest_measurement_age", config, threshold=config["stale_after_hours"],
                     created_at=created_at, explanation="No prospective observation is available")
    latest = max(utc(row["measurement_time_utc"]) for row in observation_records)
    age = (as_of_time-latest)/HOUR
    if age <= config["stale_after_hours"]:
        return None
    return event("STALE_OBSERVATION", "DATA_QUALITY", "WARNING" if age < 24 else "CRITICAL",
                 latest+HOUR, as_of_time.replace(minute=0, second=0, microsecond=0),
                 "latest_measurement_age", config, score=round(age, 2),
                 threshold=config["stale_after_hours"], created_at=created_at,
                 explanation=f"Latest measurement is {age:.1f} hours old at the supplied as_of_time")


def past_robust_score(times, values, index, window, minimum):
    current = values[index]
    if current is None:
        return None, None
    by_time = {time: value for time, value in zip(times, values)}
    past = [by_time.get(times[index]-lag*HOUR) for lag in range(1, window+1)]
    valid = [value for value in past if isinstance(value, float)]
    if len(valid) < minimum:
        return None, None
    median = statistics.median(valid)
    mad = statistics.median(abs(value-median) for value in valid) or 1.0
    return (current-median)/(1.4826*mad), median


def fit_thresholds(rows, config):
    train_end = utc(config["split_boundaries_utc"]["train_end"])
    train = [r for r in rows if r["time"] < train_end and r.get("quality_flag") == "VALID" and isinstance(r["value"], float)]
    by_time = {r["time"]: r["value"] for r in train}
    changes = {}
    for lag in (1, 3):
        changes[str(lag)] = [abs(value-by_time[t-lag*HOUR]) for t, value in by_time.items() if t-lag*HOUR in by_time]
    robust = []
    times = [r["time"] for r in rows]
    values = [r["value"] if r.get("quality_flag") == "VALID" and isinstance(r["value"], float) else None for r in rows]
    for i, moment in enumerate(times):
        if moment >= train_end:
            break
        score, _ = past_robust_score(times, values, i, config["robust_window_hours"], config["robust_min_history"])
        if score is not None:
            robust.append(abs(score))
    residuals = changes["1"]
    return {"fit_split": "TRAIN_ONLY", "train_end": train_end.isoformat(),
            "rapid_change_abs_1h": float(np.quantile(changes["1"], config["rapid_change_quantile"])),
            "rapid_change_abs_3h": float(np.quantile(changes["3"], config["rapid_change_quantile"])),
            "robust_deviation_abs": float(np.quantile(robust, config["robust_score_quantile"])),
            "persistence_residual_abs_1h": float(np.quantile(residuals, config["persistence_residual_quantile"]))}


def merge_candidates(points, event_type, detector, config, created_at, threshold, quality_times):
    events = []
    for group in consecutive_groups({point["time"] for point in points}):
        selected = [point for point in points if point["time"] in group]
        strongest = max(selected, key=lambda x: abs(x["score"]))
        consensus = len({point["detector"] for point in selected})
        ratio = abs(strongest["score"])/threshold if threshold else 0
        severity = "CRITICAL" if ratio >= 3 or consensus >= 3 else "WARNING" if ratio >= 2 else "WATCH"
        near_quality = any(abs((moment-quality)/HOUR) <= config["quality_context_hours"]
                           for moment in group for quality in quality_times)
        events.append(event(event_type, "AIR_QUALITY_EVENT", severity, group[0], group[-1], detector,
                            config, observed_value=strongest["observed"], reference_value=strongest["reference"],
                            score=strongest["score"], threshold=threshold, created_at=created_at,
                            quality_context="WITHIN_24H_OF_DATA_QUALITY_EVENT" if near_quality else "NONE",
                            explanation="ANOMALY_CANDIDATE from a past-only detector; cause is unknown"))
    return events


def air_candidates(rows, thresholds, config, created_at, quality_events_list):
    valid_by_time = {r["time"]: r["value"] for r in rows if r.get("quality_flag") == "VALID" and isinstance(r["value"], float)}
    times = [r["time"] for r in rows]
    values = [valid_by_time.get(moment) for moment in times]
    quality_times = [utc(e["start_time"]) for e in quality_events_list] + [utc(e["end_time"]) for e in quality_events_list]
    events = []
    rapid_points = []
    for lag in (1, 3):
        threshold = thresholds[f"rapid_change_abs_{lag}h"]
        for moment, value in valid_by_time.items():
            past = valid_by_time.get(moment-lag*HOUR)
            if past is None:
                continue
            change = value-past
            if abs(change) > threshold:
                percent = 100*change/past if abs(past) >= config["rapid_change_percent_denominator_min"] else None
                rapid_points.append({"time": moment, "score": change/threshold, "observed": value,
                                     "reference": past, "detector": f"rapid_change_{lag}h",
                                     "raw_change": change, "percent": percent})
    events += merge_candidates(rapid_points, "RAPID_CHANGE", "rapid_change_1h_or_3h", config,
                               created_at, 1.0, quality_times)
    robust_points = []
    for i, moment in enumerate(times):
        score, median = past_robust_score(times, values, i, config["robust_window_hours"], config["robust_min_history"])
        if score is not None and abs(score) > thresholds["robust_deviation_abs"]:
            robust_points.append({"time": moment, "score": score, "observed": values[i],
                                  "reference": median, "detector": "robust_median_mad"})
    events += merge_candidates(robust_points, "ROBUST_DEVIATION", "robust_median_mad", config,
                               created_at, thresholds["robust_deviation_abs"], quality_times)

    persistence_points = []
    if BASELINES.exists():
        with gzip.open(BASELINES, "rt", encoding="utf-8", newline="") as file:
            predictions = [r for r in csv.DictReader(file) if r["model_name"] == "Persistence" and
                           r["horizon_hours"] == "1" and r["quality_scenario"] == "B_EXCLUDE_ZERO"]
        for row in predictions:
            valid_time = utc(row["valid_time"])
            if valid_time not in valid_by_time or float(row["observed"]) != valid_by_time[valid_time]:
                continue
            residual = float(row["observed"])-float(row["prediction"])
            if abs(residual) > thresholds["persistence_residual_abs_1h"]:
                persistence_points.append({"time": valid_time, "score": residual,
                                           "observed": float(row["observed"]),
                                           "reference": float(row["prediction"]),
                                           "detector": "persistence_residual_1h"})
    events += merge_candidates(persistence_points, "PERSISTENCE_RESIDUAL", "persistence_residual_1h",
                               config, created_at, thresholds["persistence_residual_abs_1h"], quality_times)
    return events


def plot(rows, events):
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "data/audit/.mplconfig"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGURES.mkdir(parents=True, exist_ok=True)
    valid = [r for r in rows if isinstance(r["value"], float)]
    fig, ax = plt.subplots(figsize=(13, 4))
    ax.scatter([r["time"] for r in valid], [r["value"] for r in valid], s=4, color="#287e69")
    colors = {"DATA_QUALITY": "#c65944", "AIR_QUALITY_EVENT": "#e69f00"}
    for item in events:
        ax.axvspan(utc(item["start_time"]), utc(item["end_time"])+HOUR, alpha=.18,
                   color=colors[item["category"]])
    ax.set(title="Dragon PM2.5 with candidate events; shaded intervals are not health alerts",
           ylabel="PM2.5 (ug/m3)", xlabel="UTC")
    fig.tight_layout()
    fig.savefig(FIGURES / "dragon_anomaly_timeline.png", dpi=150)
    plt.close(fig)

    counts = Counter(e["event_type"] for e in events)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(counts.keys(), counts.values())
    ax.set(ylabel="Merged candidate events", title="Dragon event count by type")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(FIGURES / "dragon_anomaly_event_counts.png", dpi=150)
    plt.close(fig)

    air = [e for e in events if e["category"] == "AIR_QUALITY_EVENT"]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.scatter([utc(e["start_time"]) for e in air], [abs(float(e["score"])) for e in air],
               s=12, c=["#4472c4" if e["event_type"] == "ROBUST_DEVIATION" else "#e69f00" for e in air])
    ax.set(ylabel="Absolute detector score (detector-specific)", xlabel="UTC",
           title="Candidate detector scores; scales are not directly comparable")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURES / "dragon_anomaly_scores.png", dpi=150)
    plt.close(fig)


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rows = load_rows()
    created_at = datetime.now(timezone.utc).isoformat()
    quality = quality_events(rows, config, created_at)
    prospective = sorted((ROOT / "data/prospective/openaq_observation_snapshots").glob("*.json"))
    if prospective:
        snapshot = max((json.loads(path.read_text(encoding="utf-8")) for path in prospective
                        if json.loads(path.read_text(encoding="utf-8")).get("schema_version") == 2),
                       key=lambda x: utc(x["retrieved_at"]), default=None)
        if snapshot:
            stale = stale_event(snapshot["records"], datetime.fromisoformat(created_at), config, created_at)
            if stale:
                quality.append(stale)
    thresholds = fit_thresholds(rows, config)
    air = air_candidates(rows, thresholds, config, created_at, quality)
    events = sorted(quality+air, key=lambda e: (e["start_time"], e["event_type"], e["detector"]))
    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(events[0].keys())
    with (OUT / "dragon_anomaly_events.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(events)
    (OUT / "dragon_anomaly_events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    overlaps = Counter()
    for i, left in enumerate(air):
        for right in air[i+1:]:
            if left["event_type"] != right["event_type"] and utc(left["start_time"]) <= utc(right["end_time"]) and utc(right["start_time"]) <= utc(left["end_time"]):
                overlaps[" & ".join(sorted((left["event_type"], right["event_type"])))] += 1
    known_types = ("MISSING_DATA", "STALE_OBSERVATION", "SUSPECT_ZERO_RUN", "FLATLINE",
                   "INVALID_VALUE", "RAPID_CHANGE", "ROBUST_DEVIATION", "PERSISTENCE_RESIDUAL")
    event_counts = Counter(e["event_type"] for e in events)
    train_end = utc(config["split_boundaries_utc"]["train_end"])
    validation_end = utc(config["split_boundaries_utc"]["validation_end"])
    by_split = Counter("train" if utc(e["start_time"]) < train_end else
                       "validation" if utc(e["start_time"]) < validation_end else "test" for e in air)
    summary = {"sensor_id": config["sensor_id"], "role": "REFERENCE_OBSERVATION_FOR_PROTOTYPE",
               "detector_version": config["detector_version"], "created_at": created_at,
               "thresholds": thresholds, "events_by_type": {kind: event_counts.get(kind, 0) for kind in known_types},
               "air_candidate_events_by_split": {split: by_split.get(split, 0) for split in ("train", "validation", "test")},
               "data_quality_events": sum(e["category"] == "DATA_QUALITY" for e in events),
               "air_quality_candidate_events": sum(e["category"] == "AIR_QUALITY_EVENT" for e in events),
               "affected_hours_by_type": {kind: len({t for e in events if e["event_type"] == kind
                   for t in (utc(e["start_time"])+i*HOUR for i in range(e["duration_hours"]))})
                   for kind in {e["event_type"] for e in events}},
               "detector_overlap_events": dict(overlaps),
               "air_events_near_quality": sum(e["category"] == "AIR_QUALITY_EVENT" and e["quality_context"] != "NONE" for e in events),
               "no_label_warning": "No confirmed anomaly labels; counts are candidates, not precision/recall evidence"}
    (OUT / "dragon_anomaly_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    plot(rows, events)

    report = ROOT / "reports/pm25_anomaly_detection_evaluation.md"
    prospective_path = ROOT / "data/prospective/collection_validation.json"
    prospective = json.loads(prospective_path.read_text(encoding="utf-8")) if prospective_path.exists() else None
    notable = sorted(events, key=lambda e: (e["severity"] != "CRITICAL", -e["duration_hours"]))[:12]
    lines = ["# Dragon PM2.5 anomaly candidate evaluation", "",
             "Scope: OpenAQ Dragon sensor 14581375, AirGradient Open Air Generation 1, is_monitor=false; REFERENCE_OBSERVATION_FOR_PROTOTYPE only. Events do not establish pollution cause or health risk.",
             f"Thresholds were fit on train only, ending {thresholds['train_end']}. Validation was used for inspection; the opened test did not select thresholds. Thresholds: {thresholds}.",
             "Rapid-change uses past 1h/3h values; robust deviation uses the previous 72 hours with at least 36 valid observations; Persistence residual requires prediction and quality-approved observation at the same valid_time. No detector reads future observations.",
             f"Merged events by type: {summary['events_by_type']}. Data quality={summary['data_quality_events']}; air-quality candidates={summary['air_quality_candidate_events']}; candidates near quality issues={summary['air_events_near_quality']}.",
             f"Affected hours by type: {summary['affected_hours_by_type']}. Detector overlap: {summary['detector_overlap_events']}.",
             "", "## Quality rules", "",
             f"Missing severity thresholds are centralized at {config['missing_severity_hours']} hours. Flatline requires at least {config['flatline_min_hours']} consecutive valid hours with range <= {config['flatline_max_range']} ug/m3. Zero run requires {config['zero_run_hours']} hours. Technical range is {config['technical_min']}..{config['technical_max']} ug/m3.",
             "The known seven-hour zero segment is SUSPECT_ZERO_RUN, DATA_QUALITY, PENDING_REVIEW. It is never emitted as an air-quality event and its source PM2.5 values are unchanged.",
             "", "## Prospective collection check", "",
             (f"Status={prospective['validation_status']}; observation snapshot rows={prospective['observation_count']}; new measurement timestamps after the frozen 180-day dataset={prospective['new_measurements_after_historical_dataset']}; joinable future weather hours={prospective['joinable_future_weather_hours']}; target-ready rows={prospective['target_ready_count']}; scoring={prospective['scoring_status']}."
              if prospective else "Prospective validation has not been run."),
             "All collected observations remain PENDING_REVIEW. Collection success does not authorize scoring before target arrival and quality review.",
             "", "## Notable candidates", "",
             "| Type | Category | Severity | Start | End | Hours | Detector | Context |",
             "|---|---|---|---|---|---:|---|---|"]
    for item in notable:
        lines.append(f"| {item['event_type']} | {item['category']} | {item['severity']} | {item['start_time']} | {item['end_time']} | {item['duration_hours']} | {item['detector']} | {item['quality_context']} |")
    lines += ["", "## Limitations", "",
              "There are no confirmed anomaly labels, so precision, recall, F1 and accuracy are not reported. Event counts do not measure detector quality. Thresholds are empirical train quantiles for one community sensor and 180 days. Detector overlap and proximity to data gaps require human review. Severity expresses data-quality impact or detection confidence, never AQI or health advice.",
              "", "![Timeline](figures/dragon_anomaly_timeline.png)",
              "![Counts](figures/dragon_anomaly_event_counts.png)",
              "![Scores](figures/dragon_anomaly_scores.png)"]
    report.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
