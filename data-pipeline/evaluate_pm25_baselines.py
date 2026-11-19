"""Evaluate timestamp-safe PM2.5 baselines on Dragon reference observations."""

import csv
import gzip
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/dragon_pm25_reference_180d.csv.gz"
SUMMARY = ROOT / "data/processed/dragon_pm25_quality_summary.json"
OUT = ROOT / "data/modeling"
FIGURES = ROOT / "reports/figures"
HOUR = timedelta(hours=1)
MODELS = ("Persistence", "Daily Seasonal Naive 24h", "Weekly Seasonal Naive 168h")
HORIZONS = (1, 6, 24)
SPLITS = (
    ("train", datetime(2026, 5, 15, 9, tzinfo=timezone.utc), datetime(2026, 9, 1, tzinfo=timezone.utc)),
    ("validation", datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 10, 27, tzinfo=timezone.utc)),
    ("test", datetime(2026, 10, 27, tzinfo=timezone.utc), datetime(2026, 11, 11, 9, tzinfo=timezone.utc)),
)
PREDICTION_FIELDS = ("model_name", "sensor_id", "issued_at", "valid_time", "horizon_hours",
                     "split", "prediction", "observed", "absolute_error", "quality_scenario", "source_type")
METRIC_FIELDS = ("model_name", "split", "horizon_hours", "quality_scenario", "sample_count",
                 "possible_predictions", "coverage_of_possible_predictions_percent", "MAE", "RMSE",
                 "mean_error_bias", "median_absolute_error")


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def source_time(model, issued_at, horizon):
    if model == "Persistence":
        source = issued_at
    elif model == "Daily Seasonal Naive 24h":
        source = issued_at + (horizon - 24) * HOUR
    elif model == "Weekly Seasonal Naive 168h":
        source = issued_at + (horizon - 168) * HOUR
    else:
        raise ValueError(model)
    assert source <= issued_at, "Future feature leakage"
    return source


def usable(row, scenario):
    return row is not None and (row["quality_flag"] == "VALID" or
                                scenario == "A_KEEP_ZERO" and row["quality_flag"] == "SUSPECT_ZERO_RUN")


def evaluate_one(series, model, split, start, end, horizon, scenario):
    rows = []
    possible = 0
    issued = start
    while issued + horizon * HOUR < end:
        possible += 1
        valid = issued + horizon * HOUR
        feature = series.get(source_time(model, issued, horizon))
        target = series.get(valid)
        if usable(feature, scenario) and usable(target, scenario):
            prediction = feature["pm2_5"]
            observed = target["pm2_5"]
            rows.append({"model_name": model, "sensor_id": 14581375,
                         "issued_at": issued.isoformat(), "valid_time": valid.isoformat(),
                         "horizon_hours": horizon, "split": split, "prediction": prediction,
                         "observed": observed, "absolute_error": abs(prediction-observed),
                         "quality_scenario": scenario, "source_type": "REFERENCE_OBSERVATION"})
        issued += HOUR
    errors = [r["prediction"]-r["observed"] for r in rows]
    metric = {"model_name": model, "split": split, "horizon_hours": horizon,
              "quality_scenario": scenario, "sample_count": len(rows),
              "possible_predictions": possible,
              "coverage_of_possible_predictions_percent": round(100*len(rows)/possible, 2) if possible else 0,
              "MAE": round(statistics.mean(abs(e) for e in errors), 4) if errors else None,
              "RMSE": round(math.sqrt(statistics.mean(e*e for e in errors)), 4) if errors else None,
              "mean_error_bias": round(statistics.mean(errors), 4) if errors else None,
              "median_absolute_error": round(statistics.median(abs(e) for e in errors), 4) if errors else None}
    return rows, metric


def select_validation_baseline(predictions):
    """Select on the same valid 24h validation timestamps for all three models."""
    by_model = {model: {r["issued_at"]: r for r in predictions if
                         r["model_name"] == model and r["split"] == "validation" and
                         r["horizon_hours"] == 24 and r["quality_scenario"] == "B_EXCLUDE_ZERO"}
                for model in MODELS}
    common = set.intersection(*(set(rows) for rows in by_model.values()))
    if not common:
        raise RuntimeError("No common validation timestamps for 24h baseline selection")
    scores = {model: statistics.mean(by_model[model][t]["absolute_error"] for t in common)
              for model in MODELS}
    return min(scores, key=scores.get), scores, len(common)


def plot(predictions, metrics, selected):
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "data/audit/.mplconfig"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGURES.mkdir(parents=True, exist_ok=True)
    test = [r for r in predictions if r["model_name"] == selected and r["split"] == "test" and
            r["horizon_hours"] == 24 and r["quality_scenario"] == "B_EXCLUDE_ZERO"]
    fig, ax = plt.subplots(figsize=(12, 4))
    dates = [stamp(r["valid_time"]) for r in test]
    ax.scatter(dates, [r["observed"] for r in test], s=8, label="OpenAQ reference observation")
    ax.scatter(dates, [r["prediction"] for r in test], s=8, label=selected)
    ax.set(title="Dragon 24h test predictions (points; gaps stay empty)", ylabel="PM2.5 (ug/m3)", xlabel="Valid time UTC")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURES / "pm25_baseline_predictions_test.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    for i, split in enumerate(("validation", "test")):
        values = [next(r["MAE"] for r in metrics if r["model_name"] == model and r["split"] == split and
                       r["horizon_hours"] == 24 and r["quality_scenario"] == "B_EXCLUDE_ZERO") for model in MODELS]
        ax.bar([j + (i-.5)*.35 for j in range(3)], values, width=.34, label=split)
    ax.set(xticks=range(3), xticklabels=MODELS, ylabel="MAE (ug/m3)", title="24h baseline error; suspect zeros excluded")
    ax.tick_params(axis="x", rotation=10)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "pm25_baseline_errors.png", dpi=150)
    plt.close(fig)

    flags = json.loads(SUMMARY.read_text(encoding="utf-8"))["quality_flags"]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(list(flags), list(flags.values()), color="#287e69")
    ax.set(ylabel="Hourly rows", title="Dragon PM2.5 quality flags")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(FIGURES / "pm25_quality_flags.png", dpi=150)
    plt.close(fig)


def main():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    with gzip.open(DATA, "rt", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    series = {stamp(r["observation_time_utc"]):
              {"pm2_5": float(r["pm2_5"]) if r["pm2_5"] else None,
               "quality_flag": r["quality_flag"]} for r in rows}
    assert len(series) == len(rows)
    assert all(a[2] <= b[1] for a, b in zip(SPLITS, SPLITS[1:])), "Overlapping splits"
    predictions = []
    metrics = []
    for split, start, end in SPLITS[:2]:
        for model in MODELS:
            for horizon in HORIZONS:
                for scenario in ("A_KEEP_ZERO", "B_EXCLUDE_ZERO"):
                    result, metric = evaluate_one(series, model, split, start, end, horizon, scenario)
                    predictions.extend(result)
                    metrics.append(metric)
    selected, common_scores, common_n = select_validation_baseline(predictions)
    for split, start, end in SPLITS[2:]:  # Test is evaluated only after selection.
        for model in MODELS:
            for horizon in HORIZONS:
                for scenario in ("A_KEEP_ZERO", "B_EXCLUDE_ZERO"):
                    result, metric = evaluate_one(series, model, split, start, end, horizon, scenario)
                    predictions.extend(result)
                    metrics.append(metric)
    assert all(stamp(r["issued_at"]) < stamp(r["valid_time"]) for r in predictions)
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / "baseline_predictions.csv.gz", "wt", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=PREDICTION_FIELDS)
        writer.writeheader()
        writer.writerows(predictions)
    with (OUT / "baseline_metrics.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=METRIC_FIELDS)
        writer.writeheader()
        writer.writerows(metrics)
    plot(predictions, metrics, selected)

    report = ROOT / "reports/pm25_baseline_evaluation.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# PM2.5 baseline evaluation: Dragon", "",
             "Scope: OpenAQ sensor 14581375, Dragon; AirGradient Open Air Generation 1, is_monitor=false. Role: REFERENCE_OBSERVATION_FOR_PROTOTYPE. One community sensor is not an official ground truth, reference-grade monitor, or representative of Hanoi.",
             "License: CC BY 4.0. Attribution: srgillo via OpenAQ; link to https://creativecommons.org/licenses/by/4.0/ and disclose transformations.",
             f"Raw records: {summary['raw_records']}; output hourly rows: {summary['output_rows']}; usable for ML: {summary['usable_for_ml']}.",
             f"Quality flags: {summary['quality_flags']}; raw SHA-256: {summary['raw_sha256']}.",
             "No missing-hour imputation, Open-Meteo, OpenWeather, or weather features were used. The seven suspect zero hours remain in the raw column and are excluded in scenario B.",
             "", "## Time splits", ""]
    for name, start, end in SPLITS:
        lines.append(f"- {name}: {start.isoformat()} to {end.isoformat()} (end exclusive).")
    lines += ["", f"Baseline selected before test: **{selected}** by lowest 24h validation MAE on {common_n} timestamps shared by all three models, scenario B. Comparable MAE: { {k: round(v, 4) for k, v in common_scores.items()} }. Persistence and daily seasonal naive tie at 24h because both use observed(t); Persistence is the simpler benchmark.",
              "", "## Validation and test metrics (scenario B)", "",
              "| Split | Model | Horizon | Samples | Coverage | MAE | RMSE | Bias | Median AE |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for metric in metrics:
        if metric["split"] in ("validation", "test") and metric["quality_scenario"] == "B_EXCLUDE_ZERO":
            lines.append(f"| {metric['split']} | {metric['model_name']} | {metric['horizon_hours']}h | {metric['sample_count']} | {metric['coverage_of_possible_predictions_percent']}% | {metric['MAE']} | {metric['RMSE']} | {metric['mean_error_bias']} | {metric['median_absolute_error']} |")
    lines += ["", "## Sensitivity to the suspect zero run", "",
              "Scenario A keeps all seven zero hours as valid; scenario B excludes them from both features and targets. B was specified before evaluating metrics and is the primary result.",
              "", "| Split | Model | Horizon | A samples / MAE | B samples / MAE |",
              "|---|---|---:|---:|---:|"]
    for split in ("validation", "test"):
        for model in MODELS:
            for horizon in HORIZONS:
                a, b = [next(r for r in metrics if r["split"] == split and r["model_name"] == model and
                        r["horizon_hours"] == horizon and r["quality_scenario"] == scenario)
                        for scenario in ("A_KEEP_ZERO", "B_EXCLUDE_ZERO")]
                lines.append(f"| {split} | {model} | {horizon}h | {a['sample_count']} / {a['MAE']} | {b['sample_count']} / {b['MAE']} |")
    lines += ["", "These baseline results show feasibility on this sensor and window only. The final test was not used to choose the benchmark. Review sensor quality and evaluate longer seasonal coverage before claiming generalization or comparing a tree model.",
              "", "![Test predictions](figures/pm25_baseline_predictions_test.png)",
              "![Errors](figures/pm25_baseline_errors.png)",
              "![Quality flags](figures/pm25_quality_flags.png)"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Selected: {selected}; common validation timestamps: {common_n}")
    print(f"Predictions: {len(predictions)}; metrics rows: {len(metrics)}; report: {report}")


if __name__ == "__main__":
    main()
