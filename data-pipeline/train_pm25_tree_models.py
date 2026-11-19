"""Offline Dragon tree-model ablation with validation-only selection."""

import csv
import gzip
import json
import math
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.pipeline import Pipeline

from evaluate_pm25_baselines import SPLITS

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/modeling/dragon_pm25_weather_features.csv.gz"
SCHEMA = ROOT / "data/modeling/dragon_pm25_weather_feature_schema.json"
OUT = ROOT / "data/modeling"
FIGURES = ROOT / "reports/figures"
SEED = 42
CONFIGS = {
    "RandomForest_depth8": (RandomForestRegressor, {"n_estimators": 60, "max_depth": 8, "min_samples_leaf": 3, "n_jobs": -1, "random_state": SEED}),
    "RandomForest_depth12": (RandomForestRegressor, {"n_estimators": 60, "max_depth": 12, "min_samples_leaf": 3, "n_jobs": -1, "random_state": SEED}),
    "HistGB_leaf15": (HistGradientBoostingRegressor, {"max_iter": 80, "max_leaf_nodes": 15, "learning_rate": 0.08, "random_state": SEED}),
    "HistGB_leaf31": (HistGradientBoostingRegressor, {"max_iter": 80, "max_leaf_nodes": 31, "learning_rate": 0.08, "random_state": SEED}),
}
PRED_FIELDS = ("sensor_id", "source_type", "ablation", "model_name", "split", "issued_at",
               "valid_time", "horizon_hours", "prediction", "persistence", "observed", "residual")
METRIC_FIELDS = ("ablation", "model_name", "split", "horizon_hours", "sample_count", "possible_predictions",
                 "forecast_availability_percent", "MAE", "RMSE", "median_absolute_error", "bias",
                 "persistence_MAE_same_timestamps", "improvement_pct")


def load_data():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    with gzip.open(DATA, "rt", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert all(datetime.fromisoformat(r["max_feature_time_utc"]) <= datetime.fromisoformat(r["issued_at"]) <
               datetime.fromisoformat(r["valid_time"]) for r in rows)
    return rows, schema


def matrix(rows, names):
    return np.array([[float(r[name]) if r[name] not in (None, "") else np.nan for name in names]
                     for r in rows], dtype=float)


def metrics(actual, predicted, persistence, possible):
    error = predicted-actual
    mae = float(np.mean(np.abs(error)))
    baseline_mae = float(np.mean(np.abs(persistence-actual)))
    return {"sample_count": len(actual), "possible_predictions": possible,
            "forecast_availability_percent": round(100*len(actual)/possible, 2) if possible else 0,
            "MAE": round(mae, 4), "RMSE": round(float(np.sqrt(np.mean(error**2))), 4),
            "median_absolute_error": round(float(np.median(np.abs(error))), 4),
            "bias": round(float(np.mean(error)), 4),
            "persistence_MAE_same_timestamps": round(baseline_mae, 4),
            "improvement_pct": round(100*(baseline_mae-mae)/baseline_mae, 2) if baseline_mae else None}


def make_pipeline(name):
    cls, params = CONFIGS[name]
    return Pipeline([("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                     ("model", cls(**params))])


def group(rows, split, horizon):
    return [r for r in rows if r["split"] == split and int(r["horizon_hours"]) == horizon]


def choose_by_validation(selected, ablations):
    return {h: {"ablation": min(ablations, key=lambda a: selected[(h, a)]["validation_MAE"]),
                "model_name": None} for h in (1, 6, 24)}


def predict_rows(rows, predictions, ablation, model_name):
    return [{"sensor_id": 14581375, "source_type": "REFERENCE_OBSERVATION_FOR_PROTOTYPE",
             "ablation": ablation, "model_name": model_name, "split": row["split"],
             "issued_at": row["issued_at"], "valid_time": row["valid_time"],
             "horizon_hours": int(row["horizon_hours"]), "prediction": float(prediction),
             "persistence": float(row["persistence"]), "observed": float(row["target_pm25"]),
             "residual": float(prediction)-float(row["target_pm25"])}
            for row, prediction in zip(rows, predictions)]


def plot(predictions, metrics_rows, importance, chosen):
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "data/audit/.mplconfig"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGURES.mkdir(parents=True, exist_ok=True)
    best = chosen[24]["ablation"]
    test = [r for r in predictions if r["split"] == "test" and r["horizon_hours"] == 24 and
            r["ablation"] == best and r["model_name"] != "Persistence"]
    dates = [datetime.fromisoformat(r["valid_time"]) for r in test]
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.scatter(dates, [r["observed"] for r in test], s=12, label="Dragon reference observation")
    ax.scatter(dates, [r["prediction"] for r in test], s=12, label="Selected tree")
    ax.set(title="24h test prediction; no line across missing hours", ylabel="PM2.5 (ug/m3)", xlabel="Valid time UTC")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURES / "pm25_weather_tree_test_predictions.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.scatter(dates, [r["residual"] for r in test], s=12)
    ax.axhline(0, color="black", linewidth=.7)
    ax.set(title="24h test residuals", ylabel="Prediction - observation (ug/m3)", xlabel="Valid time UTC")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURES / "pm25_weather_tree_residuals.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4))
    for i, split in enumerate(("validation", "test")):
        values = [next(r["MAE"] for r in metrics_rows if r["split"] == split and
                    r["horizon_hours"] == h and r["ablation"] == chosen[h]["ablation"] and
                    r["model_name"] != "Persistence") for h in (1, 6, 24)]
        baseline = [next(r["persistence_MAE_same_timestamps"] for r in metrics_rows if r["split"] == split and
                    r["horizon_hours"] == h and r["ablation"] == chosen[h]["ablation"] and
                    r["model_name"] != "Persistence") for h in (1, 6, 24)]
        x = np.arange(3) + (i-.5)*.38
        ax.bar(x-.09, values, width=.18, label=f"Tree {split}")
        ax.bar(x+.09, baseline, width=.18, label=f"Persistence {split}")
    ax.set(xticks=range(3), xticklabels=["1h", "6h", "24h"], ylabel="MAE (ug/m3)", title="Matched-timestamp MAE")
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(FIGURES / "pm25_weather_tree_mae.png", dpi=150)
    plt.close(fig)

    top = sorted(importance, key=lambda x: x["importance_mean"], reverse=True)[:15]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh([r["feature"] for r in reversed(top)], [r["importance_mean"] for r in reversed(top)])
    ax.set(xlabel="Validation MAE increase after permutation", title="Permutation importance (association, not causation)")
    fig.tight_layout()
    fig.savefig(FIGURES / "pm25_weather_tree_permutation_importance.png", dpi=150)
    plt.close(fig)


def main():
    rows, schema = load_data()
    selected = {}
    candidates = []
    predictions = []
    metrics_rows = []
    ablations = {"PM25_ONLY": schema["pm25_features"],
                 "PM25_WEATHER": schema["pm25_features"] + schema["weather_features"]}
    for horizon in (1, 6, 24):
        train = group(rows, "train", horizon)
        validation = group(rows, "validation", horizon)
        if not train or not validation:
            raise RuntimeError(f"Missing train/validation rows for {horizon}h")
        y_train = np.array([float(r["target_pm25"]) for r in train])
        y_val = np.array([float(r["target_pm25"]) for r in validation])
        for ablation, names in ablations.items():
            X_train, X_val = matrix(train, names), matrix(validation, names)
            for name in CONFIGS:
                pipeline = make_pipeline(name)
                pipeline.fit(X_train, y_train)  # The imputer is fit only here.
                val_prediction = pipeline.predict(X_val)
                result = metrics(y_val, val_prediction,
                                 np.array([float(r["persistence"]) for r in validation]), len(validation))
                candidates.append({"horizon_hours": horizon, "ablation": ablation, "model_name": name,
                                   "validation_MAE": result["MAE"], "sample_count": len(validation),
                                   "parameters": CONFIGS[name][1]})
                key = (horizon, ablation)
                if key not in selected or result["MAE"] < selected[key]["validation_MAE"]:
                    selected[key] = {"pipeline": pipeline, "name": name, "features": names,
                                     "validation_MAE": result["MAE"], "validation_predictions": val_prediction}
    # Lock every model and the best ablation per horizon using validation only.
    chosen = choose_by_validation(selected, ablations)
    for h in chosen:
        chosen[h]["model_name"] = selected[(h, chosen[h]["ablation"])]["name"]
    print("Validation-locked choices:", chosen)

    effective_end = datetime.fromisoformat(schema["effective_test_end_exclusive"])
    for horizon in (1, 6, 24):
        for ablation in ablations:
            item = selected[(horizon, ablation)]
            pipeline, names, name = item["pipeline"], item["features"], item["name"]
            artifact = OUT / f"dragon_{ablation.lower()}_{horizon}h.joblib"
            joblib.dump({"pipeline": pipeline, "features": names, "horizon_hours": horizon,
                         "ablation": ablation, "model_name": name, "seed": SEED,
                         "parameters": CONFIGS[name][1]}, artifact)
            for split in ("validation", "test"):
                part = group(rows, split, horizon)
                bounds = next((start, min(end, effective_end)) for name_, start, end in SPLITS if name_ == split)
                possible = max(0, int((bounds[1]-bounds[0]).total_seconds()/3600)-horizon)
                X = matrix(part, names)
                pred = pipeline.predict(X)
                baseline = np.array([float(r["persistence"]) for r in part])
                actual = np.array([float(r["target_pm25"]) for r in part])
                result = metrics(actual, pred, baseline, possible)
                metrics_rows.append({"ablation": ablation, "model_name": name, "split": split,
                                     "horizon_hours": horizon, **result})
                metrics_rows.append({"ablation": ablation, "model_name": "Persistence", "split": split,
                                     "horizon_hours": horizon, **metrics(actual, baseline, baseline, possible)})
                predictions.extend(predict_rows(part, pred, ablation, name))
                predictions.extend(predict_rows(part, baseline, ablation, "Persistence"))

    # Permutation importance uses validation data only, after the 24h choice is locked.
    ablation = chosen[24]["ablation"]
    item = selected[(24, ablation)]
    validation = group(rows, "validation", 24)[:250]
    X = matrix(validation, item["features"])
    y = np.array([float(r["target_pm25"]) for r in validation])
    pi = permutation_importance(item["pipeline"], X, y, scoring="neg_mean_absolute_error",
                                n_repeats=2, random_state=SEED, n_jobs=1)
    importance = [{"feature": name, "importance_mean": float(mean), "importance_std": float(std)}
                  for name, mean, std in zip(item["features"], pi.importances_mean, pi.importances_std)]

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "dragon_tree_model_candidates_validation.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=candidates[0].keys())
        writer.writeheader()
        writer.writerows(candidates)
    with (OUT / "dragon_tree_model_metrics.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=METRIC_FIELDS)
        writer.writeheader()
        writer.writerows(metrics_rows)
    with gzip.open(OUT / "dragon_tree_model_predictions.csv.gz", "wt", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=PRED_FIELDS)
        writer.writeheader()
        writer.writerows(predictions)
    with (OUT / "dragon_tree_model_permutation_importance.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=importance[0].keys())
        writer.writeheader()
        writer.writerows(importance)
    monthly = []
    for h in (1, 6, 24):
        ablation = chosen[h]["ablation"]
        model_name = chosen[h]["model_name"]
        for split in ("validation", "test"):
            months = sorted({r["valid_time"][:7] for r in predictions if r["split"] == split and
                             r["horizon_hours"] == h and r["ablation"] == ablation and r["model_name"] == model_name})
            for month in months:
                part = [r for r in predictions if r["split"] == split and r["horizon_hours"] == h and
                        r["ablation"] == ablation and r["model_name"] == model_name and r["valid_time"].startswith(month)]
                actual = np.array([r["observed"] for r in part])
                pred = np.array([r["prediction"] for r in part])
                baseline = np.array([r["persistence"] for r in part])
                monthly.append({"month_utc": month, "split": split, "horizon_hours": h,
                                "ablation": ablation, "model_name": model_name,
                                **metrics(actual, pred, baseline, len(part))})
    with (OUT / "dragon_tree_model_monthly_metrics.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=monthly[0].keys())
        writer.writeheader()
        writer.writerows(monthly)
    config = {"seed": SEED, "candidate_parameters": {k: v[1] for k, v in CONFIGS.items()},
              "selected_by_validation_only": {f"{h}h_{a}": {"model_name": selected[(h, a)]["name"],
                "validation_MAE": selected[(h, a)]["validation_MAE"]} for h in (1, 6, 24) for a in ablations},
              "chosen_ablation_by_validation_only": chosen,
              "forecast_ablation": "NOT_EVALUATED_NO_FORECAST_VINTAGE"}
    (OUT / "dragon_tree_model_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    plot(predictions, metrics_rows, importance, chosen)

    weather = json.loads((ROOT / "data/weather/openmeteo_dragon_era5_metadata.json").read_text(encoding="utf-8"))
    original_baseline = {int(r["horizon_hours"]): int(r["sample_count"]) for r in
        csv.DictReader((ROOT / "data/modeling/baseline_metrics.csv").open(encoding="utf-8")) if
        r["split"] == "test" and r["model_name"] == "Persistence" and r["quality_scenario"] == "B_EXCLUDE_ZERO"}
    lost_test = {h: original_baseline[h] - schema["sample_counts"]["test"][str(h)] for h in (1, 6, 24)}
    missing_weather = {split: sum(counts.values()) for split, counts in schema["missing_weather_by_feature_split"].items()}
    report = ROOT / "reports/pm25_weather_tree_model_evaluation.md"
    lines = ["# Dragon PM2.5 weather/tree offline evaluation", "",
             "Scope: OpenAQ Dragon sensor 14581375, AirGradient Open Air Generation 1, is_monitor=false; role REFERENCE_OBSERVATION_FOR_PROTOTYPE. No citywide or official-ground-truth claim.",
             f"Weather: Open-Meteo ERA5 reanalysis, {weather['endpoint']}, requested {weather['requested_coordinates']}, selected grid {weather['selected_grid']}, hourly UTC, {weather['spatial_resolution']}, about 5-day publication delay, CC BY 4.0; credit Open-Meteo and ECMWF/Copernicus ERA5.",
             "ERA5 values at or before issued_at are retrospective features; they may have been published days later. This experiment is not a deployable real-time forecast validation. No realized future weather was used. Historical forecast vintage was not verified/retrieved: PM25_WEATHER_FORECAST = NOT_EVALUATED_NO_FORECAST_VINTAGE.",
             f"ERA5 has {weather['all_null_hours']} all-null hours at the archive tail; last usable weather is {weather['last_available_valid_time']}. Test ends {schema['effective_test_end_exclusive']} instead of 2026-11-11T09:00:00+00:00; the dropped tail and 168h PM2.5-history requirements leave few 24h test samples.",
             f"Compared with the original quality-filtered Persistence test, the effective feature dataset has {lost_test} fewer test samples at 1/6/24h. These losses combine the ERA5 tail restriction and required PM2.5 lag/rolling history; they are not all weather missing values.",
             "168h PM2.5 rolling statistics use observed hours only when at least 135/168 are present, with a count feature; short 3/6/24h windows require every hour. No PM2.5 value is imputed.",
             f"Sample counts: {schema['sample_counts']}. Missing weather feature cells among retained samples: {missing_weather}; detailed counts by feature/split are in the feature schema. SimpleImputer is fit on train only.",
             f"Candidate hyperparameters and validation-only choices: {config['selected_by_validation_only']}. Seed {SEED}.",
             "", "## Matched-timestamp validation and test metrics", "",
             "Every model and Persistence row within a split/horizon uses identical timestamps. Availability is versus all hourly issue times in the effective split, before PM2.5 quality filtering.",
             "| Split | Horizon | Ablation | Model | N | Availability | MAE | RMSE | Median AE | Bias | Persistence MAE | Improvement |",
             "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in metrics_rows:
        if r["model_name"] != "Persistence":
            lines.append(f"| {r['split']} | {r['horizon_hours']}h | {r['ablation']} | {r['model_name']} | {r['sample_count']} | {r['forecast_availability_percent']}% | {r['MAE']} | {r['RMSE']} | {r['median_absolute_error']} | {r['bias']} | {r['persistence_MAE_same_timestamps']} | {r['improvement_pct']}% |")
    lines += ["", "## Validation-selected configuration by horizon", ""]
    for h in (1, 6, 24):
        c = chosen[h]
        test = next(r for r in metrics_rows if r["split"] == "test" and r["horizon_hours"] == h and
                    r["ablation"] == c["ablation"] and r["model_name"] != "Persistence")
        lines.append(f"- {h}h: {c['ablation']} / {c['model_name']}; test matched N={test['sample_count']}, MAE={test['MAE']}, Persistence={test['persistence_MAE_same_timestamps']}, improvement={test['improvement_pct']}%.")
    six = next(r for r in metrics_rows if r["split"] == "test" and r["horizon_hours"] == 6 and
               r["ablation"] == chosen[6]["ablation"] and r["model_name"] != "Persistence")
    lines.append("Proposal 6h criterion (>=10% test MAE improvement): " + ("PASS" if six["improvement_pct"] is not None and six["improvement_pct"] >= 10 else "FAIL") + ". This was checked only after validation selection; no test-based tuning was done.")
    lines += ["", "## Ablation and limitations", "",
              "PM25_ONLY and PM25_WEATHER use the same feature timestamps, targets and Persistence comparison. Their selected models differ only in whether current/past ERA5 features are available. Weather helps 24h validation MAE but worsens 24h test MAE on only 61 samples; it does not show stable benefit here. Weather feature association is not causation.",
              "Selected-model monthly metrics are in data/modeling/dragon_tree_model_monthly_metrics.csv. Validation permutation importance uses 250 validation rows and is an association measure, not causal evidence.",
              "This sensor has only 180 days and a short weather-covered test tail. ERA5 publication delay and OpenAQ observation arrival times mean real-time feature availability has not been established. Validate forecast vintage and a longer multi-season window before claims about operational performance or Hanoi as a whole.",
              "Official Open-Meteo Historical Weather documentation: https://open-meteo.com/en/docs/historical-weather-api ; noncommercial terms and CC BY 4.0: https://open-meteo.com/en/terms .",
              "", "![Test predictions](figures/pm25_weather_tree_test_predictions.png)",
              "![Residuals](figures/pm25_weather_tree_residuals.png)",
              "![MAE](figures/pm25_weather_tree_mae.png)",
              "![Validation permutation importance](figures/pm25_weather_tree_permutation_importance.png)"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report: {report}; selected={chosen}; 6h_test_improvement={six['improvement_pct']}%")


if __name__ == "__main__":
    main()
