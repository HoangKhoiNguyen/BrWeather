# PM2.5 baseline evaluation: Dragon

Scope: OpenAQ sensor 14581375, Dragon; AirGradient Open Air Generation 1, is_monitor=false. Role: REFERENCE_OBSERVATION_FOR_PROTOTYPE. One community sensor is not an official ground truth, reference-grade monitor, or representative of Hanoi.
License: CC BY 4.0. Attribution: srgillo via OpenAQ; link to https://creativecommons.org/licenses/by/4.0/ and disclose transformations.
Raw records: 4160; output hourly rows: 4320; usable for ML: 4153.
Quality flags: {'VALID': 4153, 'MISSING': 160, 'NEGATIVE_VALUE': 0, 'EXTREME_VALUE': 0, 'SUSPECT_ZERO_RUN': 7, 'DUPLICATE_TIMESTAMP': 0, 'NON_HOURLY_INTERVAL': 0}; raw SHA-256: a3e0f22db35c38f9a900577a101787a4ff25e486a19b055b556c28de22b602ee.
No missing-hour imputation, Open-Meteo, OpenWeather, or weather features were used. The seven suspect zero hours remain in the raw column and are excluded in scenario B.

## Time splits

- train: 2026-05-15T09:00:00+00:00 to 2026-09-01T00:00:00+00:00 (end exclusive).
- validation: 2026-09-01T00:00:00+00:00 to 2026-10-27T00:00:00+00:00 (end exclusive).
- test: 2026-10-27T00:00:00+00:00 to 2026-11-11T09:00:00+00:00 (end exclusive).

Baseline selected before test: **Persistence** by lowest 24h validation MAE on 1273 timestamps shared by all three models, scenario B. Comparable MAE: {'Persistence': 17.2445, 'Daily Seasonal Naive 24h': 17.2445, 'Weekly Seasonal Naive 168h': 27.9643}. Persistence and daily seasonal naive tie at 24h because both use observed(t); Persistence is the simpler benchmark.

## Validation and test metrics (scenario B)

| Split | Model | Horizon | Samples | Coverage | MAE | RMSE | Bias | Median AE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| validation | Persistence | 1h | 1308 | 97.39% | 6.8956 | 10.2439 | -0.0799 | 4.25 |
| validation | Persistence | 6h | 1298 | 97.01% | 18.2636 | 25.0613 | -0.3533 | 13.3 |
| validation | Persistence | 24h | 1273 | 96.44% | 17.2445 | 23.3907 | -0.231 | 12.6 |
| validation | Daily Seasonal Naive 24h | 1h | 1296 | 96.5% | 17.1619 | 23.2966 | -0.1296 | 12.6 |
| validation | Daily Seasonal Naive 24h | 6h | 1291 | 96.49% | 17.2072 | 23.3384 | -0.1363 | 12.6 |
| validation | Daily Seasonal Naive 24h | 24h | 1273 | 96.44% | 17.2445 | 23.3907 | -0.231 | 12.6 |
| validation | Weekly Seasonal Naive 168h | 1h | 1309 | 97.47% | 27.6373 | 37.4776 | -1.5581 | 20.1 |
| validation | Weekly Seasonal Naive 168h | 6h | 1304 | 97.46% | 27.6906 | 37.5374 | -1.599 | 20.2 |
| validation | Weekly Seasonal Naive 168h | 24h | 1286 | 97.42% | 27.9227 | 37.7687 | -1.7457 | 20.6 |
| test | Persistence | 1h | 357 | 97.01% | 5.9518 | 9.0419 | 0.3361 | 3.7 |
| test | Persistence | 6h | 347 | 95.59% | 16.2239 | 22.191 | 1.0821 | 11.9 |
| test | Persistence | 24h | 328 | 95.07% | 17.025 | 22.709 | 2.8201 | 12.45 |
| test | Daily Seasonal Naive 24h | 1h | 341 | 92.66% | 16.6997 | 22.4198 | 3.0018 | 12.3 |
| test | Daily Seasonal Naive 24h | 6h | 341 | 93.94% | 16.6997 | 22.4198 | 3.0018 | 12.3 |
| test | Daily Seasonal Naive 24h | 24h | 328 | 95.07% | 17.025 | 22.709 | 2.8201 | 12.45 |
| test | Weekly Seasonal Naive 168h | 1h | 324 | 88.04% | 25.8833 | 32.1278 | 13.008 | 22.15 |
| test | Weekly Seasonal Naive 168h | 6h | 319 | 87.88% | 25.8643 | 32.1035 | 13.6367 | 22.2 |
| test | Weekly Seasonal Naive 168h | 24h | 301 | 87.25% | 26.9213 | 32.9058 | 14.714 | 23.5 |

## Sensitivity to the suspect zero run

Scenario A keeps all seven zero hours as valid; scenario B excludes them from both features and targets. B was specified before evaluating metrics and is the primary result.

| Split | Model | Horizon | A samples / MAE | B samples / MAE |
|---|---|---:|---:|---:|
| validation | Persistence | 1h | 1308 / 6.8956 | 1308 / 6.8956 |
| validation | Persistence | 6h | 1298 / 18.2636 | 1298 / 18.2636 |
| validation | Persistence | 24h | 1273 / 17.2445 | 1273 / 17.2445 |
| validation | Daily Seasonal Naive 24h | 1h | 1296 / 17.1619 | 1296 / 17.1619 |
| validation | Daily Seasonal Naive 24h | 6h | 1291 / 17.2072 | 1291 / 17.2072 |
| validation | Daily Seasonal Naive 24h | 24h | 1273 / 17.2445 | 1273 / 17.2445 |
| validation | Weekly Seasonal Naive 168h | 1h | 1309 / 27.6373 | 1309 / 27.6373 |
| validation | Weekly Seasonal Naive 168h | 6h | 1304 / 27.6906 | 1304 / 27.6906 |
| validation | Weekly Seasonal Naive 168h | 24h | 1286 / 27.9227 | 1286 / 27.9227 |
| test | Persistence | 1h | 365 / 5.8219 | 357 / 5.9518 |
| test | Persistence | 6h | 360 / 15.6467 | 347 / 16.2239 |
| test | Persistence | 24h | 342 / 17.3374 | 328 / 17.025 |
| test | Daily Seasonal Naive 24h | 1h | 355 / 17.0135 | 341 / 16.6997 |
| test | Daily Seasonal Naive 24h | 6h | 355 / 17.0135 | 341 / 16.6997 |
| test | Daily Seasonal Naive 24h | 24h | 342 / 17.3374 | 328 / 17.025 |
| test | Weekly Seasonal Naive 168h | 1h | 331 / 26.1063 | 324 / 25.8833 |
| test | Weekly Seasonal Naive 168h | 6h | 326 / 26.0911 | 319 / 25.8643 |
| test | Weekly Seasonal Naive 168h | 24h | 308 / 27.1373 | 301 / 26.9213 |

These baseline results show feasibility on this sensor and window only. The final test was not used to choose the benchmark. Review sensor quality and evaluate longer seasonal coverage before claiming generalization or comparing a tree model.

![Test predictions](figures/pm25_baseline_predictions_test.png)
![Errors](figures/pm25_baseline_errors.png)
![Quality flags](figures/pm25_quality_flags.png)
