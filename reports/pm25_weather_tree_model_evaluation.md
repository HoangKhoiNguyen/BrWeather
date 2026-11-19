# Dragon PM2.5 weather/tree offline evaluation

Scope: OpenAQ Dragon sensor 14581375, AirGradient Open Air Generation 1, is_monitor=false; role REFERENCE_OBSERVATION_FOR_PROTOTYPE. No citywide or official-ground-truth claim.
Weather: Open-Meteo ERA5 reanalysis, https://archive-api.open-meteo.com/v1/archive, requested {'latitude': 20.9933, 'longitude': 105.9441}, selected grid {'latitude': 21.0, 'longitude': 106.0, 'elevation': 6.0}, hourly UTC, 0.25 degree (~25 km), about 5-day publication delay, CC BY 4.0; credit Open-Meteo and ECMWF/Copernicus ERA5.
ERA5 values at or before issued_at are retrospective features; they may have been published days later. This experiment is not a deployable real-time forecast validation. No realized future weather was used. Historical forecast vintage was not verified/retrieved: PM25_WEATHER_FORECAST = NOT_EVALUATED_NO_FORECAST_VINTAGE.
ERA5 has 24 all-null hours at the archive tail; last usable weather is 2026-11-05T23:00:00+00:00. Test ends 2026-11-06T00:00:00+00:00 instead of 2026-11-11T09:00:00+00:00; the dropped tail and 168h PM2.5-history requirements leave few 24h test samples.
Compared with the original quality-filtered Persistence test, the effective feature dataset has {1: 273, 6: 268, 24: 267} fewer test samples at 1/6/24h. These losses combine the ERA5 tail restriction and required PM2.5 lag/rolling history; they are not all weather missing values.
168h PM2.5 rolling statistics use observed hours only when at least 135/168 are present, with a count feature; short 3/6/24h windows require every hour. No PM2.5 value is imputed.
Sample counts: {'train': {'1': 2091, '6': 2079, '24': 2043}, 'validation': {'1': 1296, '6': 1291, '24': 1273}, 'test': {'1': 84, '6': 79, '24': 61}}. Missing weather feature cells among retained samples: {'train': 0, 'validation': 0, 'test': 0}; detailed counts by feature/split are in the feature schema. SimpleImputer is fit on train only.
Candidate hyperparameters and validation-only choices: {'1h_PM25_ONLY': {'model_name': 'RandomForest_depth8', 'validation_MAE': 7.5927}, '1h_PM25_WEATHER': {'model_name': 'RandomForest_depth8', 'validation_MAE': 7.7778}, '6h_PM25_ONLY': {'model_name': 'RandomForest_depth8', 'validation_MAE': 15.839}, '6h_PM25_WEATHER': {'model_name': 'HistGB_leaf15', 'validation_MAE': 16.4414}, '24h_PM25_ONLY': {'model_name': 'RandomForest_depth8', 'validation_MAE': 17.6524}, '24h_PM25_WEATHER': {'model_name': 'RandomForest_depth8', 'validation_MAE': 15.601}}. Seed 42.

## Matched-timestamp validation and test metrics

Every model and Persistence row within a split/horizon uses identical timestamps. Availability is versus all hourly issue times in the effective split, before PM2.5 quality filtering.
| Split | Horizon | Ablation | Model | N | Availability | MAE | RMSE | Median AE | Bias | Persistence MAE | Improvement |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| validation | 1h | PM25_ONLY | RandomForest_depth8 | 1296 | 96.5% | 7.5927 | 11.477 | 4.8641 | -2.0033 | 6.8915 | -10.17% |
| test | 1h | PM25_ONLY | RandomForest_depth8 | 84 | 35.15% | 6.8437 | 9.2638 | 4.5962 | 0.0915 | 6.0679 | -12.79% |
| validation | 1h | PM25_WEATHER | RandomForest_depth8 | 1296 | 96.5% | 7.7778 | 11.799 | 5.0491 | -1.056 | 6.8915 | -12.86% |
| test | 1h | PM25_WEATHER | RandomForest_depth8 | 84 | 35.15% | 7.0592 | 9.1037 | 5.8023 | 2.4998 | 6.0679 | -16.34% |
| validation | 6h | PM25_ONLY | RandomForest_depth8 | 1291 | 96.49% | 15.839 | 22.4916 | 11.6395 | -2.551 | 18.1861 | 12.91% |
| test | 6h | PM25_ONLY | RandomForest_depth8 | 79 | 33.76% | 14.8472 | 18.5361 | 12.5763 | 4.2681 | 14.8177 | -0.2% |
| validation | 6h | PM25_WEATHER | HistGB_leaf15 | 1291 | 96.49% | 16.4414 | 22.3852 | 12.5942 | 0.5273 | 18.1861 | 9.59% |
| test | 6h | PM25_WEATHER | HistGB_leaf15 | 79 | 33.76% | 16.6497 | 20.0265 | 15.6887 | 12.2445 | 14.8177 | -12.36% |
| validation | 24h | PM25_ONLY | RandomForest_depth8 | 1273 | 96.44% | 17.6524 | 25.4632 | 12.0435 | -8.5375 | 17.2445 | -2.37% |
| test | 24h | PM25_ONLY | RandomForest_depth8 | 61 | 28.24% | 16.8904 | 20.3578 | 13.0391 | 2.7311 | 18.2902 | 7.65% |
| validation | 24h | PM25_WEATHER | RandomForest_depth8 | 1273 | 96.44% | 15.601 | 21.5787 | 11.0968 | -3.8679 | 17.2445 | 9.53% |
| test | 24h | PM25_WEATHER | RandomForest_depth8 | 61 | 28.24% | 19.4449 | 22.4932 | 18.5509 | 7.5973 | 18.2902 | -6.31% |

## Validation-selected configuration by horizon

- 1h: PM25_ONLY / RandomForest_depth8; test matched N=84, MAE=6.8437, Persistence=6.0679, improvement=-12.79%.
- 6h: PM25_ONLY / RandomForest_depth8; test matched N=79, MAE=14.8472, Persistence=14.8177, improvement=-0.2%.
- 24h: PM25_WEATHER / RandomForest_depth8; test matched N=61, MAE=19.4449, Persistence=18.2902, improvement=-6.31%.
Proposal 6h criterion (>=10% test MAE improvement): FAIL. This was checked only after validation selection; no test-based tuning was done.

## Ablation and limitations

PM25_ONLY and PM25_WEATHER use the same feature timestamps, targets and Persistence comparison. Their selected models differ only in whether current/past ERA5 features are available. Weather helps 24h validation MAE but worsens 24h test MAE on only 61 samples; it does not show stable benefit here. Weather feature association is not causation.
Selected-model monthly metrics are in data/modeling/dragon_tree_model_monthly_metrics.csv. Validation permutation importance uses 250 validation rows and is an association measure, not causal evidence.
This sensor has only 180 days and a short weather-covered test tail. ERA5 publication delay and OpenAQ observation arrival times mean real-time feature availability has not been established. Validate forecast vintage and a longer multi-season window before claims about operational performance or Hanoi as a whole.
Official Open-Meteo Historical Weather documentation: https://open-meteo.com/en/docs/historical-weather-api ; noncommercial terms and CC BY 4.0: https://open-meteo.com/en/terms .

![Test predictions](figures/pm25_weather_tree_test_predictions.png)
![Residuals](figures/pm25_weather_tree_residuals.png)
![MAE](figures/pm25_weather_tree_mae.png)
![Validation permutation importance](figures/pm25_weather_tree_permutation_importance.png)
