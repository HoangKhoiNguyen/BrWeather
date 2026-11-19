# Dragon PM2.5 model stability and prospective plan

Opened original test remains unchanged: RF was 12.79%, 0.20%, and 6.31% worse than Persistence at 1/6/24h. The 6h >=10% improvement criterion failed. No test-based selection or retuning was done.
Dragon is one OpenAQ AirGradient Open Air Generation 1 sensor (is_monitor=false), not official ground truth or representative of Hanoi.

## Distribution drift

Stats include count, missing rate, mean, std, median, p10/p25/p75/p90, min and max for train, validation and test in data/modeling/pm25_stability_drift.csv. They describe the selected feature rows, so sample selection itself may affect distributions.
SMD = (test mean - validation mean) / pooled standard deviation. Absolute SMD >=0.5 is flagged as a notable distribution difference, not a causal explanation.
| Feature | Validation mean | Test mean | SMD | Flag |
|---|---:|---:|---:|---|
| weather_surface_pressure_current | 1011.3695 | 1013.9536 | 0.952 | True |
| pm25_mean_24h | 46.0621 | 32.8001 | -0.873 | True |
| weather_wind_sin_current | 0.3661 | 0.6707 | 0.8295 | True |
| weather_relative_humidity_2m_current | 77.1019 | 85.369 | 0.7096 | True |
| pm25_lag_168h | 44.767 | 63.5488 | 0.7081 | True |
| pm25_current | 46.1135 | 32.0071 | -0.6501 | True |
| weather_wind_cos_current | -0.0032 | -0.4454 | -0.6423 | True |
| pm25_lag_1h | 46.0915 | 32.2774 | -0.6395 | True |
| weather_cloud_cover_current | 38.6119 | 57.7143 | 0.5941 | True |
| pm25_lag_24h | 46.0046 | 33.8786 | -0.5811 | True |

## Residual diagnosis

Per-timestamp residuals include hour, PM2.5 band, weather, wind direction, rain, and rapid rise/fall labels. These are associations, not causes.
- 1h test: N=84, model MAE=6.84, Persistence MAE=6.07; model better at 32/84 timestamps; model bias=0.09; five largest errors contribute 22.0% of total absolute error. Largest-error valid times: ['2026-11-05T22:00:00+00:00', '2026-11-03T20:00:00+00:00', '2026-11-04T20:00:00+00:00', '2026-11-05T18:00:00+00:00', '2026-11-05T20:00:00+00:00'].
- 6h test: N=79, model MAE=14.85, Persistence MAE=14.82; model better at 40/79 timestamps; model bias=4.27; five largest errors contribute 16.5% of total absolute error. Largest-error valid times: ['2026-11-04T14:00:00+00:00', '2026-11-04T18:00:00+00:00', '2026-11-04T19:00:00+00:00', '2026-11-04T13:00:00+00:00', '2026-11-04T17:00:00+00:00'].
- 24h test: N=61, model MAE=19.44, Persistence MAE=18.29; model better at 27/61 timestamps; model bias=7.60; five largest errors contribute 18.6% of total absolute error. Largest-error valid times: ['2026-11-04T19:00:00+00:00', '2026-11-03T20:00:00+00:00', '2026-11-05T23:00:00+00:00', '2026-11-05T02:00:00+00:00', '2026-11-03T21:00:00+00:00'].

Selected 24h test residual groups with at least 10 samples; all hour/weather/rain/episode groups are in data/modeling/pm25_stability_residual_groups.csv.
| Group | N | Model MAE | Persistence MAE | Model bias |
|---|---:|---:|---:|---:|
| pm25_band=MID | 39 | 14.542 | 13.6154 | 6.4268 |
| pm25_band=LOW | 16 | 25.9935 | 23.3562 | 25.9935 |
| rain_category=RAIN | 22 | 20.9525 | 18.1545 | -2.0099 |
| rain_category=DRY | 39 | 18.5945 | 18.3667 | 13.0167 |
| episode=OTHER | 29 | 13.263 | 6.3379 | 8.526 |
| episode=RAPID_RISE | 11 | 26.606 | 30.6273 | -26.606 |
| episode=RAPID_FALL | 21 | 24.2307 | 28.3333 | 24.2307 |

## Walk-forward within original train + validation only

Four non-overlapping validation folds. Each fold trains on earlier rows; the latest training target is before validation start minus 24h. Imputer is fit within each fold's train. No original test row is in a fold.
| Horizon | Ablation | Model | Fold MAEs | Mean ± SD | Folds beating Persistence |
|---:|---|---|---|---:|---:|
| 1h | PM25_ONLY | RandomForest_depth8 | [6.9446, 5.9385, 6.545, 8.4311] | 6.96 ± 0.92 | 0/4 |
| 1h | PM25_ONLY | HistGB_leaf15 | [7.2912, 6.3761, 6.5233, 8.2997] | 7.12 ± 0.76 | 0/4 |
| 1h | PM25_WEATHER | RandomForest_depth8 | [6.9979, 6.1719, 6.4889, 8.2359] | 6.97 ± 0.79 | 0/4 |
| 1h | PM25_WEATHER | HistGB_leaf15 | [7.3268, 6.6026, 6.4034, 8.3269] | 7.16 ± 0.75 | 0/4 |
| 6h | PM25_ONLY | RandomForest_depth8 | [15.2155, 15.0453, 14.4137, 17.745] | 15.60 ± 1.27 | 3/4 |
| 6h | PM25_ONLY | HistGB_leaf15 | [15.2195, 15.213, 14.7769, 19.2116] | 16.11 ± 1.80 | 3/4 |
| 6h | PM25_WEATHER | RandomForest_depth8 | [14.8457, 14.9049, 15.2252, 17.0845] | 15.52 ± 0.92 | 4/4 |
| 6h | PM25_WEATHER | HistGB_leaf15 | [15.4272, 15.0434, 14.3501, 16.9381] | 15.44 ± 0.95 | 3/4 |
| 24h | PM25_ONLY | RandomForest_depth8 | [14.7917, 17.1453, 14.3809, 20.8813] | 16.80 ± 2.58 | 3/4 |
| 24h | PM25_ONLY | HistGB_leaf15 | [14.8433, 18.2695, 16.3589, 19.6108] | 17.27 ± 1.82 | 1/4 |
| 24h | PM25_WEATHER | RandomForest_depth8 | [14.7879, 20.5013, 12.9372, 17.1439] | 16.34 ± 2.83 | 3/4 |
| 24h | PM25_WEATHER | HistGB_leaf15 | [14.1362, 20.2212, 13.9332, 17.7529] | 16.51 ± 2.63 | 3/4 |

## Diagnosis and decision

- 1h RF weather beats RF PM25-only on 2/4 folds.
- 6h RF weather beats RF PM25-only on 3/4 folds.
- 24h RF weather beats RF PM25-only on 3/4 folds.
- The opened test is small (84/79/61 samples at 1/6/24h) and has notable PM2.5 and weather distribution differences from validation. At 24h the model overpredicts by 7.60 ug/m3; its five largest errors account for 18.6% of total error, so no single outlier alone explains failure. Fold performance varies, especially at 24h. These are plausible contributors, not proven causes.
- Although 6h RF with weather beats Persistence on four earlier folds, the validation-selected 6h PM25-only model failed on the opened test. Do not reselect using test; Persistence remains the accepted main benchmark.
- Weather does not improve consistently across horizons and folds. More model complexity is not justified by the current evidence.

## Prospective collection plan

The sample Open-Meteo snapshot is append-only and records retrieval UTC, requested/grid coordinates, endpoint, parameters, units, future valid times, raw response and SHA-256 ID. The API response does not provide a model run or provider issue time, so retrieved_at is the evidence of availability in our system.
Sample snapshot: b59b1aa7bed96c9bef9bd0d91e839dffacf1e77fbfb61b97854968f872ab8fe9; retrieved_at=2026-11-12T03:21:32.405601+00:00; future hours=47; provider issue time=None.
A future join is allowed only when retrieved_at <= issued_at < valid_time; never reconstruct a snapshot from realized historical weather.
The current OpenAQClient.hourly yields only (UTC hour, value). It does not preserve raw flagInfo, retrieval time or raw payload. A separate manual append-only script, data-pipeline/collect_openaq_observation_snapshot.py, has been created but not run in this step. It preserves sensor_id, measurement UTC, value, unit, flags, retrieved_at and raw response; new records are PENDING_REVIEW, never default VALID.
The proposed prospective schema is data/prospective/prospective_evaluation_schema.json. Start with manual weather and observation captures about hourly, respecting provider update rates and API limits. Review after 30 days; prefer 60–90 days for stability. No scheduler or production API is installed.
Open-Meteo documentation: https://open-meteo.com/en/docs ; free noncommercial terms and CC BY 4.0: https://open-meteo.com/en/terms .

![Drift](figures/pm25_stability_drift.png)
![Residuals](figures/pm25_stability_residuals.png)
![Walk forward](figures/pm25_stability_walk_forward_mae.png)
