"""Diagnose the opened test and walk forward only within old train/validation data."""

import csv
import gzip
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.stats import wasserstein_distance
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from train_pm25_tree_models import matrix, metrics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/modeling"
FIGURES = ROOT / "reports/figures"
SEED = 42
FOLDS = (
    ("F1", "2026-07-15T00:00:00+00:00", "2026-08-01T00:00:00+00:00"),
    ("F2", "2026-08-15T00:00:00+00:00", "2026-09-01T00:00:00+00:00"),
    ("F3", "2026-09-15T00:00:00+00:00", "2026-10-01T00:00:00+00:00"),
    ("F4", "2026-10-01T00:00:00+00:00", "2026-10-27T00:00:00+00:00"),
)
MODELS = {
    "RandomForest_depth8": (RandomForestRegressor, {"n_estimators": 60, "max_depth": 8,
                                                   "min_samples_leaf": 3, "n_jobs": -1, "random_state": SEED}),
    "HistGB_leaf15": (HistGradientBoostingRegressor, {"max_iter": 80, "max_leaf_nodes": 15,
                                                       "learning_rate": 0.08, "random_state": SEED}),
}


def read_rows():
    with gzip.open(DATA / "dragon_pm25_weather_features.csv.gz", "rt", encoding="utf-8", newline="") as file:
        features = list(csv.DictReader(file))
    with gzip.open(DATA / "dragon_tree_model_predictions.csv.gz", "rt", encoding="utf-8", newline="") as file:
        predictions = list(csv.DictReader(file))
    schema = json.loads((DATA / "dragon_pm25_weather_feature_schema.json").read_text(encoding="utf-8"))
    chosen = json.loads((DATA / "dragon_tree_model_config.json").read_text(encoding="utf-8"))["chosen_ablation_by_validation_only"]
    return features, predictions, schema, chosen


def stats(values):
    valid = np.array([v for v in values if v is not None], dtype=float)
    if not len(valid):
        return {"count": 0, "missing_rate": 1.0, **{x: None for x in
                ("mean", "std", "median", "p10", "p25", "p75", "p90", "min", "max")}}
    return {"count": len(valid), "missing_rate": round(1-len(valid)/len(values), 4),
            "mean": round(float(np.mean(valid)), 4), "std": round(float(np.std(valid)), 4),
            "median": round(float(np.median(valid)), 4),
            "p10": round(float(np.percentile(valid, 10)), 4),
            "p25": round(float(np.percentile(valid, 25)), 4),
            "p75": round(float(np.percentile(valid, 75)), 4),
            "p90": round(float(np.percentile(valid, 90)), 4),
            "min": round(float(np.min(valid)), 4), "max": round(float(np.max(valid)), 4)}


def drift(features, names):
    unique = {split: {r["issued_at"]: r for r in features if r["split"] == split and
                       r["horizon_hours"] == "1"} for split in ("train", "validation", "test")}
    output = []
    for name in names:
        arrays = {split: [float(r[name]) if r[name] not in (None, "") else None
                          for r in rows.values()] for split, rows in unique.items()}
        summary = {split: stats(values) for split, values in arrays.items()}
        val, test = summary["validation"], summary["test"]
        pooled = math.sqrt((val["std"]**2 + test["std"]**2)/2) if val["std"] is not None and test["std"] is not None else 0
        smd = (test["mean"]-val["mean"])/pooled if pooled else 0
        for split in unique:
            output.append({"feature": name, "split": split, **summary[split],
                           "validation_minus_test_mean": round(val["mean"]-test["mean"], 4) if val["mean"] is not None and test["mean"] is not None else None,
                           "smd_test_vs_validation": round(smd, 4),
                           "large_drift_flag": abs(smd) >= .5})
    return output


def full_pm_drift():
    from evaluate_pm25_baselines import SPLITS
    with gzip.open(ROOT / "data/processed/dragon_pm25_reference_180d.csv.gz", "rt", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    arrays = {split: [float(r["pm2_5_ml"]) if r["pm2_5_ml"] else None for r in rows
                      if start <= datetime.fromisoformat(r["observation_time_utc"]) < end]
              for split, start, end in SPLITS}
    summaries = {split: stats(values) for split, values in arrays.items()}
    val, test = summaries["validation"], summaries["test"]
    pooled = math.sqrt((val["std"]**2 + test["std"]**2)/2)
    smd = (test["mean"]-val["mean"])/pooled if pooled else 0
    return [{"feature": "pm2_5_ml_full_window", "split": split, **summaries[split],
             "validation_minus_test_mean": round(val["mean"]-test["mean"], 4),
             "smd_test_vs_validation": round(smd, 4), "large_drift_flag": abs(smd) >= .5}
            for split in ("train", "validation", "test")]


def residuals(features, predictions, chosen):
    by_feature = {(r["issued_at"], r["horizon_hours"]): r for r in features}
    rows = []
    for horizon in (1, 6, 24):
        ablation = chosen[str(horizon)]["ablation"]
        model = chosen[str(horizon)]["model_name"]
        for prediction in predictions:
            if prediction["split"] not in ("validation", "test") or prediction["horizon_hours"] != str(horizon) or prediction["ablation"] != ablation or prediction["model_name"] != model:
                continue
            feature = by_feature[(prediction["issued_at"], prediction["horizon_hours"])]
            observed = float(prediction["observed"])
            current = float(feature["pm25_current"])
            pred = float(prediction["prediction"])
            baseline = float(prediction["persistence"])
            temperature = float(feature["weather_temperature_2m_current"])
            humidity = float(feature["weather_relative_humidity_2m_current"])
            wind = float(feature["weather_wind_speed_10m_current"])
            direction = math.degrees(math.atan2(float(feature["weather_wind_sin_current"]),
                                                float(feature["weather_wind_cos_current"]))) % 360
            rain = float(feature["weather_precipitation_current"])
            change = observed-current
            rows.append({"split": prediction["split"], "horizon_hours": horizon,
                         "issued_at": prediction["issued_at"], "valid_time": prediction["valid_time"],
                         "hour_utc": datetime.fromisoformat(prediction["issued_at"]).hour,
                         "pm25_band": "LOW" if observed < 15 else "MID" if observed < 55 else "HIGH",
                         "temperature_2m": temperature, "relative_humidity_2m": humidity,
                         "wind_speed_10m": wind, "wind_direction_deg": direction,
                         "rain_category": "RAIN" if rain > 0 else "DRY",
                         "episode": "RAPID_RISE" if change >= 15 else "RAPID_FALL" if change <= -15 else "OTHER",
                         "observed": observed, "model_prediction": pred, "persistence_prediction": baseline,
                         "model_residual": pred-observed, "persistence_residual": baseline-observed,
                         "model_absolute_error": abs(pred-observed), "persistence_absolute_error": abs(baseline-observed),
                         "model_better": abs(pred-observed) < abs(baseline-observed)})
    return rows


def residual_groups(rows):
    output = []
    categories = {
        "hour_utc": lambda r: str(r["hour_utc"]),
        "pm25_band": lambda r: r["pm25_band"],
        "temperature_band": lambda r: "<20C" if r["temperature_2m"] < 20 else "20-27C" if r["temperature_2m"] < 27 else ">=27C",
        "humidity_band": lambda r: "<60%" if r["relative_humidity_2m"] < 60 else "60-80%" if r["relative_humidity_2m"] < 80 else ">=80%",
        "wind_speed_band": lambda r: "<2kmh" if r["wind_speed_10m"] < 2 else "2-5kmh" if r["wind_speed_10m"] < 5 else ">=5kmh",
        "wind_direction_quadrant": lambda r: ("N" if r["wind_direction_deg"] >= 315 or r["wind_direction_deg"] < 45 else
                                               "E" if r["wind_direction_deg"] < 135 else "S" if r["wind_direction_deg"] < 225 else "W"),
        "rain_category": lambda r: r["rain_category"],
        "episode": lambda r: r["episode"],
    }
    for split in ("validation", "test"):
        for horizon in (1, 6, 24):
            part = [r for r in rows if r["split"] == split and r["horizon_hours"] == horizon]
            for kind, classify in categories.items():
                groups = defaultdict(list)
                for row in part:
                    groups[classify(row)].append(row)
                for label, subset in groups.items():
                    output.append({"split": split, "horizon_hours": horizon, "group_type": kind,
                                   "group_value": label, "sample_count": len(subset),
                                   "model_MAE": round(statistics.mean(r["model_absolute_error"] for r in subset), 4),
                                   "persistence_MAE": round(statistics.mean(r["persistence_absolute_error"] for r in subset), 4),
                                   "model_bias": round(statistics.mean(r["model_residual"] for r in subset), 4),
                                   "model_better_count": sum(r["model_better"] for r in subset)})
    return output


def fold_rows(features, fold, horizon):
    name, start_str, end_str = fold
    start, end = datetime.fromisoformat(start_str), datetime.fromisoformat(end_str)
    embargo = start - timedelta(hours=24)
    train = [r for r in features if r["split"] in ("train", "validation") and
             r["horizon_hours"] == str(horizon) and datetime.fromisoformat(r["valid_time"]) < embargo]
    validation = [r for r in features if r["split"] in ("train", "validation") and
                  r["horizon_hours"] == str(horizon) and start <= datetime.fromisoformat(r["issued_at"]) and
                  datetime.fromisoformat(r["valid_time"]) < end]
    assert train and validation
    assert max(datetime.fromisoformat(r["valid_time"]) for r in train) < embargo <= start
    assert max(datetime.fromisoformat(r["valid_time"]) for r in validation) < datetime(2026, 10, 27, tzinfo=timezone.utc)
    return train, validation


def walk_forward(features, schema):
    results = []
    for horizon in (1, 6, 24):
        for fold in FOLDS:
            train, validation = fold_rows(features, fold, horizon)
            actual = np.array([float(r["target_pm25"]) for r in validation])
            persistence = np.array([float(r["persistence"]) for r in validation])
            baseline_mae = float(np.mean(np.abs(persistence-actual)))
            for ablation, names in (("PM25_ONLY", schema["pm25_features"]),
                                    ("PM25_WEATHER", schema["pm25_features"]+schema["weather_features"])):
                X_train, X_val = matrix(train, names), matrix(validation, names)
                y_train = np.array([float(r["target_pm25"]) for r in train])
                for model_name, (cls, params) in MODELS.items():
                    pipeline = Pipeline([("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                                         ("model", cls(**params))])
                    pipeline.fit(X_train, y_train)
                    pred = pipeline.predict(X_val)
                    score = metrics(actual, pred, persistence, len(validation))
                    results.append({"fold": fold[0], "train_end_target_before": (datetime.fromisoformat(fold[1])-timedelta(hours=24)).isoformat(),
                                    "validation_start": fold[1], "validation_end": fold[2],
                                    "horizon_hours": horizon, "ablation": ablation, "model_name": model_name,
                                    "sample_count": len(validation), "model_MAE": score["MAE"],
                                    "persistence_MAE_same_timestamps": round(baseline_mae, 4),
                                    "improvement_pct": score["improvement_pct"]})
    return results


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def charts(drift_rows, residual_rows, folds):
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "data/audit/.mplconfig"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGURES.mkdir(parents=True, exist_ok=True)
    drift_top = sorted((r for r in drift_rows if r["split"] == "test"),
                       key=lambda r: abs(r["smd_test_vs_validation"]), reverse=True)[:12]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh([r["feature"] for r in reversed(drift_top)], [r["smd_test_vs_validation"] for r in reversed(drift_top)])
    ax.axvline(.5, color="red", linestyle="--", linewidth=.7)
    ax.axvline(-.5, color="red", linestyle="--", linewidth=.7)
    ax.set(xlabel="Standardized mean difference: test vs validation", title="Feature drift (selected sample rows)")
    fig.tight_layout()
    fig.savefig(FIGURES / "pm25_stability_drift.png", dpi=150)
    plt.close(fig)

    test = sorted((r for r in residual_rows if r["split"] == "test" and r["horizon_hours"] == 24), key=lambda r: r["valid_time"])
    fig, ax = plt.subplots(figsize=(11, 4))
    dates = [datetime.fromisoformat(r["valid_time"]) for r in test]
    ax.scatter(dates, [r["model_residual"] for r in test], s=12, label="Tree")
    ax.scatter(dates, [r["persistence_residual"] for r in test], s=12, label="Persistence")
    ax.axhline(0, color="black", linewidth=.7)
    ax.set(xlabel="Valid time UTC", ylabel="Prediction - observation (ug/m3)", title="24h test residuals; gaps unconnected")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURES / "pm25_stability_residuals.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    for ablation in ("PM25_ONLY", "PM25_WEATHER"):
        for model in MODELS:
            part = [r for r in folds if r["horizon_hours"] == 24 and r["ablation"] == ablation and r["model_name"] == model]
            ax.plot([r["fold"] for r in part], [r["model_MAE"] for r in part], marker="o", label=f"{ablation} {model}")
    base = [r for r in folds if r["horizon_hours"] == 24 and r["ablation"] == "PM25_ONLY" and r["model_name"] == "RandomForest_depth8"]
    ax.plot([r["fold"] for r in base], [r["persistence_MAE_same_timestamps"] for r in base], color="black", linestyle="--", label="Persistence")
    ax.set(ylabel="MAE (ug/m3)", xlabel="Walk-forward fold", title="24h MAE by fold")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGURES / "pm25_stability_walk_forward_mae.png", dpi=150)
    plt.close(fig)


def main():
    features, predictions, schema, chosen = read_rows()
    names = ["pm25_current", "pm25_lag_1h", "pm25_lag_24h", "pm25_lag_168h",
             "pm25_mean_24h", "pm25_mean_168h", "pm25_std_24h", "pm25_count_168h",
             "weather_temperature_2m_current", "weather_relative_humidity_2m_current",
             "weather_precipitation_current", "weather_surface_pressure_current",
             "weather_wind_speed_10m_current", "weather_wind_sin_current", "weather_wind_cos_current",
             "weather_cloud_cover_current", "weather_boundary_layer_height_current"]
    drift_rows = drift(features, names) + full_pm_drift()
    residual_rows = residuals(features, predictions, chosen)
    grouped_residuals = residual_groups(residual_rows)
    folds = walk_forward(features, schema)
    write_csv(DATA / "pm25_stability_drift.csv", drift_rows)
    write_csv(DATA / "pm25_stability_residuals.csv", residual_rows)
    write_csv(DATA / "pm25_stability_residual_groups.csv", grouped_residuals)
    write_csv(DATA / "pm25_stability_walk_forward.csv", folds)
    charts(drift_rows, residual_rows, folds)

    report = ROOT / "reports/pm25_model_stability_and_prospective_plan.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    snapshots = sorted((ROOT / "data/prospective/openmeteo_snapshots").glob("*.json"))
    sample_snapshot = json.loads(snapshots[-1].read_text(encoding="utf-8")) if snapshots else None
    top_drift = sorted((r for r in drift_rows if r["split"] == "test"),
                       key=lambda r: abs(r["smd_test_vs_validation"]), reverse=True)[:10]
    lines = ["# Dragon PM2.5 model stability and prospective plan", "",
             "Opened original test remains unchanged: RF was 12.79%, 0.20%, and 6.31% worse than Persistence at 1/6/24h. The 6h >=10% improvement criterion failed. No test-based selection or retuning was done.",
             "Dragon is one OpenAQ AirGradient Open Air Generation 1 sensor (is_monitor=false), not official ground truth or representative of Hanoi.",
             "", "## Distribution drift", "",
             "Stats include count, missing rate, mean, std, median, p10/p25/p75/p90, min and max for train, validation and test in data/modeling/pm25_stability_drift.csv. They describe the selected feature rows, so sample selection itself may affect distributions.",
             "SMD = (test mean - validation mean) / pooled standard deviation. Absolute SMD >=0.5 is flagged as a notable distribution difference, not a causal explanation.",
             "| Feature | Validation mean | Test mean | SMD | Flag |", "|---|---:|---:|---:|---|"]
    for r in top_drift:
        val = next(x for x in drift_rows if x["feature"] == r["feature"] and x["split"] == "validation")
        lines.append(f"| {r['feature']} | {val['mean']} | {r['mean']} | {r['smd_test_vs_validation']} | {r['large_drift_flag']} |")
    lines += ["", "## Residual diagnosis", "",
              "Per-timestamp residuals include hour, PM2.5 band, weather, wind direction, rain, and rapid rise/fall labels. These are associations, not causes."]
    for horizon in (1, 6, 24):
        part = [r for r in residual_rows if r["split"] == "test" and r["horizon_hours"] == horizon]
        if not part:
            continue
        model_mae = statistics.mean(r["model_absolute_error"] for r in part)
        baseline_mae = statistics.mean(r["persistence_absolute_error"] for r in part)
        bias = statistics.mean(r["model_residual"] for r in part)
        better = sum(r["model_better"] for r in part)
        top = sorted(part, key=lambda r: r["model_absolute_error"], reverse=True)[:5]
        share = 100*sum(r["model_absolute_error"] for r in top)/sum(r["model_absolute_error"] for r in part)
        lines.append(f"- {horizon}h test: N={len(part)}, model MAE={model_mae:.2f}, Persistence MAE={baseline_mae:.2f}; model better at {better}/{len(part)} timestamps; model bias={bias:.2f}; five largest errors contribute {share:.1f}% of total absolute error. Largest-error valid times: {[r['valid_time'] for r in top]}.")
    lines += ["", "Selected 24h test residual groups with at least 10 samples; all hour/weather/rain/episode groups are in data/modeling/pm25_stability_residual_groups.csv.",
              "| Group | N | Model MAE | Persistence MAE | Model bias |", "|---|---:|---:|---:|---:|"]
    for r in grouped_residuals:
        if r["split"] == "test" and r["horizon_hours"] == 24 and r["sample_count"] >= 10 and r["group_type"] in ("pm25_band", "episode", "rain_category"):
            lines.append(f"| {r['group_type']}={r['group_value']} | {r['sample_count']} | {r['model_MAE']} | {r['persistence_MAE']} | {r['model_bias']} |")
    lines += ["", "## Walk-forward within original train + validation only", "",
              "Four non-overlapping validation folds. Each fold trains on earlier rows; the latest training target is before validation start minus 24h. Imputer is fit within each fold's train. No original test row is in a fold.",
              "| Horizon | Ablation | Model | Fold MAEs | Mean ± SD | Folds beating Persistence |",
              "|---:|---|---|---|---:|---:|"]
    for horizon in (1, 6, 24):
        for ablation in ("PM25_ONLY", "PM25_WEATHER"):
            for model in MODELS:
                part = [r for r in folds if r["horizon_hours"] == horizon and r["ablation"] == ablation and r["model_name"] == model]
                maes = [r["model_MAE"] for r in part]
                wins = sum(r["model_MAE"] < r["persistence_MAE_same_timestamps"] for r in part)
                lines.append(f"| {horizon}h | {ablation} | {model} | {maes} | {statistics.mean(maes):.2f} ± {statistics.pstdev(maes):.2f} | {wins}/4 |")
    lines += ["", "## Diagnosis and decision", ""]
    for horizon in (1, 6, 24):
        plain = {r["fold"]: r["model_MAE"] for r in folds if r["horizon_hours"] == horizon and r["ablation"] == "PM25_ONLY" and r["model_name"] == "RandomForest_depth8"}
        weather = {r["fold"]: r["model_MAE"] for r in folds if r["horizon_hours"] == horizon and r["ablation"] == "PM25_WEATHER" and r["model_name"] == "RandomForest_depth8"}
        lines.append(f"- {horizon}h RF weather beats RF PM25-only on {sum(weather[k] < plain[k] for k in plain)}/4 folds.")
    lines += ["- The opened test is small (84/79/61 samples at 1/6/24h) and has notable PM2.5 and weather distribution differences from validation. At 24h the model overpredicts by 7.60 ug/m3; its five largest errors account for 18.6% of total error, so no single outlier alone explains failure. Fold performance varies, especially at 24h. These are plausible contributors, not proven causes.",
              "- Although 6h RF with weather beats Persistence on four earlier folds, the validation-selected 6h PM25-only model failed on the opened test. Do not reselect using test; Persistence remains the accepted main benchmark.",
              "- Weather does not improve consistently across horizons and folds. More model complexity is not justified by the current evidence."]
    lines += ["", "## Prospective collection plan", "",
              "The sample Open-Meteo snapshot is append-only and records retrieval UTC, requested/grid coordinates, endpoint, parameters, units, future valid times, raw response and SHA-256 ID. The API response does not provide a model run or provider issue time, so retrieved_at is the evidence of availability in our system.",
              f"Sample snapshot: {sample_snapshot['snapshot_id'] if sample_snapshot else 'none'}; retrieved_at={sample_snapshot['retrieved_at'] if sample_snapshot else 'none'}; future hours={len(sample_snapshot['forecast_hours']) if sample_snapshot else 0}; provider issue time={sample_snapshot['provider_issue_time'] if sample_snapshot else 'unknown'}.",
              "A future join is allowed only when retrieved_at <= issued_at < valid_time; never reconstruct a snapshot from realized historical weather.",
              "The current OpenAQClient.hourly yields only (UTC hour, value). It does not preserve raw flagInfo, retrieval time or raw payload. A separate manual append-only script, data-pipeline/collect_openaq_observation_snapshot.py, has been created but not run in this step. It preserves sensor_id, measurement UTC, value, unit, flags, retrieved_at and raw response; new records are PENDING_REVIEW, never default VALID.",
              "The proposed prospective schema is data/prospective/prospective_evaluation_schema.json. Start with manual weather and observation captures about hourly, respecting provider update rates and API limits. Review after 30 days; prefer 60–90 days for stability. No scheduler or production API is installed.",
              "Open-Meteo documentation: https://open-meteo.com/en/docs ; free noncommercial terms and CC BY 4.0: https://open-meteo.com/en/terms .",
              "", "![Drift](figures/pm25_stability_drift.png)",
              "![Residuals](figures/pm25_stability_residuals.png)",
              "![Walk forward](figures/pm25_stability_walk_forward_mae.png)"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"drift={len(drift_rows)} residuals={len(residual_rows)} folds={len(folds)} report={report}")


if __name__ == "__main__":
    main()
