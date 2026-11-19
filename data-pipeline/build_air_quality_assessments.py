"""Build retrospective and Persistence prototype assessments for Dragon."""

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/dragon_pm25_reference_180d.csv.gz"
EVENTS = ROOT / "data/anomalies/dragon_anomaly_events.json"
AIR_POLICY = ROOT / "data-pipeline/air_quality_policy.json"
REC_POLICY = ROOT / "data-pipeline/recommendation_policy.json"
OUT = ROOT / "data/assessments"
FIGURES = ROOT / "reports/figures"
HOUR = timedelta(hours=1)
HORIZONS = (1, 6, 24)


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def stable_id(*parts):
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:24]


def provisional_status(value, policy):
    if value is None or value < 0:
        return None
    for band in policy["provisional_bands"]:
        low_ok = value >= band.get("min_inclusive", -math.inf) if "min_inclusive" in band else value > band["min_exclusive"]
        high_ok = band["max_inclusive"] is None or value <= band["max_inclusive"]
        if low_ok and high_ok:
            return band["status"]
    return None


def nowcast(window):
    """Decision 1459 PM2.5 Nowcast over newest-to-oldest hourly values."""
    valid = [value for value in window if value is not None]
    if not valid:
        return None
    maximum = max(valid)
    weight = max(0.5, min(valid)/maximum) if maximum > 0 else 1.0
    weighted = [(weight**i, value) for i, value in enumerate(window) if value is not None]
    if weight == 0.5:
        return sum(w*value for w, value in weighted)
    return sum(w*value for w, value in weighted)/sum(w for w, _ in weighted)


def coverage_window(by_time, valid_time, policy):
    times = [valid_time-i*HOUR for i in range(policy["averaging_period_hours"])]
    values = [by_time.get(moment) for moment in times]
    valid_hours = sum(value is not None for value in values)
    latest_valid = sum(value is not None for value in values[:3])
    coverage = 100*valid_hours/len(values)
    eligible = (latest_valid >= policy["minimum_valid_latest_3_hours"] and
                valid_hours >= policy["minimum_valid_hours"] and
                coverage >= policy["minimum_coverage_pct"])
    return {"window_start": times[-1].isoformat(), "window_end": valid_time.isoformat(),
            "valid_hours": valid_hours, "expected_hours": len(values),
            "coverage_pct": round(coverage, 2), "latest_3_valid_hours": latest_valid,
            "eligible": eligible, "values_newest_first": values}


def linked_events(events, timestamp):
    linked = [item for item in events if utc(item["start_time"]) <= timestamp <= utc(item["end_time"])]
    groups = defaultdict(list)
    for item in linked:
        key = "DATA_QUALITY" if item["category"] == "DATA_QUALITY" else "ANOMALY_CANDIDATE"
        groups[key].append({field: item[field] for field in
                            ("event_id", "event_type", "category", "status", "severity", "detector", "quality_context")})
    return linked, [{"group": key, "evidence": value} for key, value in groups.items()]


def recommendations(status, availability, audience, policy):
    if availability != "AVAILABLE" or status is None:
        return []
    output = []
    for item in policy["recommendations"]:
        if status not in item["trigger_statuses"] or item["audience"] not in (audience, "ALL"):
            continue
        source = policy["sources"].get(item["source_reference"])
        if not source:
            continue
        output.append({"recommendation_id": item["recommendation_id"], "audience": item["audience"],
                       "trigger_status": status, "message": item["message"],
                       "source_reference": {"id": item["source_reference"], **source},
                       "disclaimer": policy["disclaimer"], "language": policy["language"],
                       "version": policy["version"]})
    return output


def base_assessment(kind, issued, valid, horizon, policy, created_at):
    scope = policy["sensor_scope"]
    return {"assessment_id": stable_id(scope["sensor_id"], kind, issued.isoformat(), valid.isoformat(), horizon),
            "sensor_id": scope["sensor_id"], "location_name": scope["location_name"],
            "latitude": scope["latitude"], "longitude": scope["longitude"],
            "assessment_type": kind, "issued_at": issued.isoformat(), "valid_time": valid.isoformat(),
            "horizon_hours": horizon, "pm25_value": None, "pm25_unit": "µg/m³",
            "averaging_period": None, "air_quality_method": policy["method"],
            "air_quality_status": None, "assessment_availability": "INSUFFICIENT_DATA",
            "data_quality_status": "MISSING", "data_coverage": None, "stale": False,
            "anomaly_status": "NONE", "anomaly_candidate_present": False,
            "anomaly_event_ids": [], "anomaly_groups": [], "forecast_model": None,
            "forecast_confidence": "NOT_AVAILABLE", "recommendations": [],
            "source": "OpenAQ", "attribution": "srgillo via OpenAQ; CC BY 4.0",
            "limitations": ["One AirGradient community sensor; is_monitor=false",
                            "Not official VN_AQI, not reference-grade, not representative of Hanoi"],
            "created_at": created_at, "policy_version": policy["policy_version"]}


def gate(row, as_of_time, policy, prospective=False):
    if int(row.get("sensor_id", 14581375)) != policy["sensor_scope"]["sensor_id"]:
        return "SUPPRESSED_DATA_QUALITY", "INVALID", False
    if row.get("unit") not in policy["accepted_units"]:
        return "SUPPRESSED_DATA_QUALITY", "INVALID", False
    quality = row.get("quality_flag", "INVALID")
    if quality == "PENDING_REVIEW":
        return "PENDING_REVIEW", quality, False
    if quality == "MISSING":
        return "INSUFFICIENT_DATA", quality, False
    if quality in ("SUSPECT_ZERO_RUN", "INVALID", "NEGATIVE_VALUE", "EXTREME_VALUE"):
        return "SUPPRESSED_DATA_QUALITY", quality, False
    observation_time = utc(row.get("observation_time_utc") or row["measurement_time_utc"])
    stale = prospective and as_of_time-observation_time > timedelta(hours=policy["stale_after_hours"])
    return ("STALE_DATA", "STALE", True) if stale else ("AVAILABLE", "VALID", False)


def observed_assessment(row, by_time, events, policy, rec_policy, audience, created_at,
                        as_of_time=None, prospective=False):
    valid_time = utc(row.get("observation_time_utc") or row["measurement_time_utc"])
    issued = utc(row.get("retrieved_at", valid_time.isoformat())) if prospective else valid_time
    result = base_assessment("OBSERVED_PROSPECTIVE_PENDING_REVIEW" if prospective else "OBSERVED_RETROSPECTIVE",
                             issued, valid_time, 0, policy, created_at)
    availability, quality, stale = gate(row, as_of_time or valid_time, policy, prospective)
    result.update(assessment_availability=availability, data_quality_status=quality, stale=stale)
    linked, groups = linked_events(events, valid_time)
    quality_events = [item for item in linked if item["category"] == "DATA_QUALITY"]
    if quality_events:
        result.update(assessment_availability="SUPPRESSED_DATA_QUALITY",
                      data_quality_status=quality_events[0]["event_type"])
    result["anomaly_event_ids"] = [item["event_id"] for item in linked]
    result["anomaly_groups"] = groups
    air_events = [item for item in linked if item["category"] == "AIR_QUALITY_EVENT"]
    result["anomaly_candidate_present"] = bool(air_events)
    result["anomaly_status"] = "ANOMALY_CANDIDATE_PRESENT" if air_events else "NONE"
    if result["assessment_availability"] != "AVAILABLE":
        return result
    coverage = coverage_window(by_time, valid_time, policy)
    result["data_coverage"] = {key: value for key, value in coverage.items() if key != "values_newest_first"}
    result["averaging_period"] = "12h Nowcast-like, past/current observations only"
    if not coverage["eligible"]:
        result["assessment_availability"] = "INSUFFICIENT_DATA"
        result["data_quality_status"] = "INSUFFICIENT_COVERAGE"
        return result
    concentration = nowcast(coverage["values_newest_first"])
    result["pm25_value"] = round(concentration, 3)
    result["air_quality_status"] = provisional_status(concentration, policy)
    result["recommendations"] = recommendations(result["air_quality_status"], "AVAILABLE", audience, rec_policy)
    return result


def forecast_assessment(row, events, horizon, policy, rec_policy, audience, created_at):
    issued = utc(row["observation_time_utc"])
    valid = issued+horizon*HOUR
    result = base_assessment("FORECAST_PROTOTYPE", issued, valid, horizon, policy, created_at)
    availability, quality, stale = gate(row, issued, policy)
    linked, groups = linked_events(events, issued)  # only evidence known at issuance
    quality_events = [item for item in linked if item["category"] == "DATA_QUALITY"]
    if quality_events:
        availability, quality = "SUPPRESSED_DATA_QUALITY", quality_events[0]["event_type"]
    result.update(assessment_availability=availability, data_quality_status=quality, stale=stale,
                  anomaly_event_ids=[item["event_id"] for item in linked], anomaly_groups=groups,
                  anomaly_candidate_present=any(item["category"] == "AIR_QUALITY_EVENT" for item in linked),
                  anomaly_status="ANOMALY_CANDIDATE_PRESENT" if any(item["category"] == "AIR_QUALITY_EVENT" for item in linked) else "NONE",
                  forecast_model="PERSISTENCE", forecast_confidence="PROTOTYPE_ONLY",
                  averaging_period="instantaneous hourly concentration carried forward",
                  data_coverage={"input_observation_hours": 1, "expected_hours": 1,
                                 "coverage_pct": 100 if availability == "AVAILABLE" else 0})
    if availability != "AVAILABLE":
        result["forecast_confidence"] = "NOT_AVAILABLE"
        return result
    value = float(row["pm2_5_ml"])
    result["pm25_value"] = value
    result["air_quality_status"] = provisional_status(value, policy)
    result["recommendations"] = recommendations(result["air_quality_status"], "AVAILABLE", audience, rec_policy)
    result["limitations"].append("Persistence benchmark repeats the last valid hourly observation; not an official future AQI")
    return result


def write_csv(path, rows):
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                             for key, value in row.items()})


def plot(assessments):
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "data/audit/.mplconfig"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGURES.mkdir(parents=True, exist_ok=True)
    observed = [item for item in assessments if item["assessment_type"] == "OBSERVED_RETROSPECTIVE"]
    available = [item for item in observed if item["assessment_availability"] == "AVAILABLE"]
    status_order = ["PROVISIONAL_LOW", "PROVISIONAL_MODERATE", "PROVISIONAL_ELEVATED",
                    "PROVISIONAL_HIGH", "PROVISIONAL_VERY_HIGH", "PROVISIONAL_EXTREME",
                    "PROVISIONAL_ABOVE_SCALE"]
    fig, ax = plt.subplots(figsize=(13, 4))
    ax.scatter([utc(item["valid_time"]) for item in available],
               [status_order.index(item["air_quality_status"]) for item in available], s=3)
    ax.set(yticks=range(len(status_order)), yticklabels=status_order,
           xlabel="UTC", title="Retrospective provisional PM2.5 concentration status")
    fig.tight_layout()
    fig.savefig(FIGURES / "dragon_assessment_status_timeline.png", dpi=150)
    plt.close(fig)

    coverages = [item["data_coverage"]["coverage_pct"] for item in observed if item["data_coverage"]]
    suppressed = Counter(item["assessment_availability"] for item in observed)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].hist(coverages, bins=20)
    axes[0].set(title="Observed Nowcast-window coverage", xlabel="Coverage (%)", ylabel="Assessments")
    axes[1].bar(suppressed.keys(), suppressed.values())
    axes[1].set(title="Observed assessment availability", ylabel="Assessments")
    axes[1].tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(FIGURES / "dragon_assessment_coverage_suppression.png", dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", help="UTC time for prospective stale checks")
    parser.add_argument("--audience", choices=("GENERAL", "SENSITIVE_GROUP"), default="GENERAL")
    args = parser.parse_args()
    policy = json.loads(AIR_POLICY.read_text(encoding="utf-8"))
    rec_policy = json.loads(REC_POLICY.read_text(encoding="utf-8"))
    events = json.loads(EVENTS.read_text(encoding="utf-8"))
    with gzip.open(DATA, "rt", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    by_time = {utc(row["observation_time_utc"]): float(row["pm2_5_ml"])
               for row in rows if row["pm2_5_ml"] != "" and row["quality_flag"] == "VALID"}
    created_at = datetime.now(timezone.utc).isoformat()
    assessments = []
    for row in rows:
        assessments.append(observed_assessment(row, by_time, events, policy, rec_policy,
                                               args.audience, created_at))
        if row["quality_flag"] == "VALID" and row["pm2_5_ml"] != "":
            assessments.extend(forecast_assessment(row, events, horizon, policy, rec_policy,
                                                   args.audience, created_at) for horizon in HORIZONS)
    as_of = utc(args.as_of) if args.as_of else datetime.now(timezone.utc)
    snapshots = sorted((ROOT / "data/prospective/openaq_observation_snapshots").glob("*.json"))
    prospective_records = {}
    for path in snapshots:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if snapshot.get("schema_version") != 2:
            continue
        for row in snapshot["records"]:
            prospective_records.setdefault(row["observation_id"], row)
    assessments.extend(observed_assessment(row, {}, events, policy, rec_policy, args.audience,
                                           created_at, as_of, True) for row in prospective_records.values())
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "dragon_air_quality_assessments.csv", assessments)
    (OUT / "dragon_air_quality_assessments.json").write_text(json.dumps(assessments, ensure_ascii=False), encoding="utf-8")
    required = list(base_assessment("X", datetime.now(timezone.utc), datetime.now(timezone.utc), 0,
                                    policy, created_at).keys())
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema",
              "title": "Dragon air-quality assessment", "type": "object",
              "required": required, "additionalProperties": False,
              "properties": {
                  "assessment_id": {"type": "string"}, "sensor_id": {"const": 14581375},
                  "location_name": {"const": "Dragon"}, "latitude": {"type": "number"},
                  "longitude": {"type": "number"},
                  "assessment_type": {"enum": ["OBSERVED_RETROSPECTIVE", "FORECAST_PROTOTYPE",
                                                   "OBSERVED_PROSPECTIVE_PENDING_REVIEW"]},
                  "issued_at": {"type": "string", "format": "date-time"},
                  "valid_time": {"type": "string", "format": "date-time"},
                  "horizon_hours": {"enum": [0, 1, 6, 24]},
                  "pm25_value": {"type": ["number", "null"]}, "pm25_unit": {"const": "µg/m³"},
                  "averaging_period": {"type": ["string", "null"]},
                  "air_quality_method": {"const": "PROVISIONAL_PM25_CONCENTRATION_STATUS"},
                  "air_quality_status": {"type": ["string", "null"]},
                  "assessment_availability": {"enum": ["AVAILABLE", "INSUFFICIENT_DATA",
                                                           "SUPPRESSED_DATA_QUALITY", "PENDING_REVIEW", "STALE_DATA"]},
                  "data_quality_status": {"type": "string"},
                  "data_coverage": {"type": ["object", "null"]}, "stale": {"type": "boolean"},
                  "anomaly_status": {"type": "string"}, "anomaly_candidate_present": {"type": "boolean"},
                  "anomaly_event_ids": {"type": "array", "items": {"type": "string"}},
                  "anomaly_groups": {"type": "array"}, "forecast_model": {"type": ["string", "null"]},
                  "forecast_confidence": {"enum": ["NOT_AVAILABLE", "LOW", "LIMITED", "PROTOTYPE_ONLY"]},
                  "recommendations": {"type": "array"}, "source": {"type": "string"},
                  "attribution": {"type": "string"}, "limitations": {"type": "array"},
                  "created_at": {"type": "string"}, "policy_version": {"type": "string"}
              },
              "concepts_kept_separate": ["data_quality_status", "assessment_availability",
                                          "air_quality_status", "anomaly_status", "forecast_confidence"],
              "policy_version": policy["policy_version"], "vn_aqi": False,
              "air_quality_method": policy["method"]}
    (OUT / "dragon_air_quality_assessment_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    recommendation_occurrences = Counter(item["recommendation_id"] for assessment in assessments
                                         for item in assessment["recommendations"])
    catalog = [{**item, "source_reference": {"id": item["source_reference"],
                **rec_policy["sources"][item["source_reference"]]},
                "disclaimer": rec_policy["disclaimer"], "language": rec_policy["language"],
                "version": rec_policy["version"]} for item in rec_policy["recommendations"]]
    (OUT / "dragon_recommendations.json").write_text(json.dumps({"catalog": catalog,
        "occurrences_in_default_general_assessments": dict(recommendation_occurrences),
        "excluded_topics": rec_policy["excluded_topics"], "policy_version": rec_policy["version"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    plot(assessments)

    counts = Counter(item["assessment_availability"] for item in assessments)
    types = Counter(item["assessment_type"] for item in assessments)
    reasons = Counter(item["data_quality_status"] for item in assessments if item["assessment_availability"] != "AVAILABLE")
    linked = sum(item["anomaly_candidate_present"] for item in assessments)
    by_type_availability = {kind: dict(Counter(item["assessment_availability"] for item in assessments
                                                if item["assessment_type"] == kind)) for kind in types}
    report = ROOT / "reports/air_quality_risk_and_recommendation_evaluation.md"
    lines = ["# Dragon air-quality assessment and recommendation prototype", "",
             "The module does not publish VN_AQI. Dragon is an AirGradient Open Air Generation 1 community sensor with is_monitor=false; statutory station/data QA/QC required by Decision 1459/QĐ-TCMT is not established.",
             f"Official reference: {policy['official_reference']}. Accessed {policy['accessed_date']}. Official VN_AQI names/colors and PM2.5 breakpoints are retained in the policy for traceability but are not applied as VN_AQI to Dragon. The current method is {policy['method']} and emits no AQI number.",
             f"Observed concentration uses a past/current 12-hour Nowcast-like window. Official minimum: 2 of the latest 3 hours. Internal conservative gate: at least {policy['minimum_valid_hours']}/12 valid hours ({policy['minimum_coverage_pct']}%). Missing and SUSPECT_ZERO_RUN values are excluded; no future value is read.",
             f"Assessments={len(assessments)}; by type={dict(types)}; availability={dict(counts)}; suppressed/insufficient reasons={dict(reasons)}; anomaly-candidate-linked assessments={linked}.",
             f"Availability by assessment type: {by_type_availability}.",
             "Data-quality events suppress assessment. Air-quality anomaly candidates add evidence only and never raise the concentration status or health recommendation.",
             "Persistence forecasts are issued at the last valid observation for 1/6/24h, are marked FORECAST_PROTOTYPE and PROTOTYPE_ONLY, and are not official future AQI.",
             f"Recommendation occurrences for default GENERAL audience: {dict(recommendation_occurrences)}. The catalog also contains the sourced SENSITIVE_GROUP rule. Every emitted recommendation has an official WHO source and disclaimer. Excluded: {rec_policy['excluded_topics']}.",
             f"Prospective PENDING_REVIEW records={len(prospective_records)}. They create audit assessments that remain PENDING_REVIEW or are suppressed by an overlapping data-quality event; they have no status/recommendation and no Persistence forecast.",
             "", "## Sources and uncertainty", "",
             "- Decision 1459/QĐ-TCMT, Tổng cục Môi trường, 12/11/2019: https://vea.mae.gov.vn/Data/files/QD%201459%20TCMT%20ngay%2012_11_2019%20AQI%281%29.pdf",
             "- QCVN 05:2023/BTNMT, Bộ Tài nguyên và Môi trường, reviewed as ambient-air concentration context and not used as the AQI formula: https://cem.gov.vn/storage/documents/66cf004657629qcvn-052023btnmt.pdf",
             "- WHO personal interventions and risk communication, accessed 12/11/2026: https://www.who.int/news-room/questions-and-answers/item/air-pollution-personal-interventions-and-risk-communication",
             "- Uncertainty: applicability and legal/current status are not independently proven for Dragon; advice is generic and individual effects vary.",
             "", "![Status timeline](figures/dragon_assessment_status_timeline.png)",
             "![Coverage and suppression](figures/dragon_assessment_coverage_suppression.png)"]
    report.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps({"assessments": len(assessments), "types": dict(types),
                      "availability": dict(counts), "reasons": dict(reasons),
                      "recommendations": dict(recommendation_occurrences)}, indent=2))


if __name__ == "__main__":
    main()
