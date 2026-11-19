# Dragon PM2.5 anomaly candidate evaluation

Scope: OpenAQ Dragon sensor 14581375, AirGradient Open Air Generation 1, is_monitor=false; REFERENCE_OBSERVATION_FOR_PROTOTYPE only. Events do not establish pollution cause or health risk.
Thresholds were fit on train only, ending 2026-09-01T00:00:00+00:00. Validation was used for inspection; the opened test did not select thresholds. Thresholds: {'fit_split': 'TRAIN_ONLY', 'train_end': '2026-09-01T00:00:00+00:00', 'rapid_change_abs_1h': 33.846000000000004, 'rapid_change_abs_3h': 60.25799999999999, 'robust_deviation_abs': 4.276298074795428, 'persistence_residual_abs_1h': 33.846000000000004}.
Rapid-change uses past 1h/3h values; robust deviation uses the previous 72 hours with at least 36 valid observations; Persistence residual requires prediction and quality-approved observation at the same valid_time. No detector reads future observations.
Merged events by type: {'MISSING_DATA': 7, 'STALE_OBSERVATION': 0, 'SUSPECT_ZERO_RUN': 1, 'FLATLINE': 0, 'INVALID_VALUE': 0, 'RAPID_CHANGE': 51, 'ROBUST_DEVIATION': 23, 'PERSISTENCE_RESIDUAL': 39}. Data quality=8; air-quality candidates=113; candidates near quality issues=2.
Affected hours by type: {'PERSISTENCE_RESIDUAL': 45, 'MISSING_DATA': 160, 'RAPID_CHANGE': 78, 'ROBUST_DEVIATION': 49, 'SUSPECT_ZERO_RUN': 7}. Detector overlap: {'PERSISTENCE_RESIDUAL & RAPID_CHANGE': 39, 'RAPID_CHANGE & ROBUST_DEVIATION': 7, 'PERSISTENCE_RESIDUAL & ROBUST_DEVIATION': 6}.

## Quality rules

Missing severity thresholds are centralized at {'INFO': 1, 'WATCH': 2, 'WARNING': 6, 'CRITICAL': 24} hours. Flatline requires at least 8 consecutive valid hours with range <= 0.1 ug/m3. Zero run requires 6 hours. Technical range is 0.0..1000.0 ug/m3.
The known seven-hour zero segment is SUSPECT_ZERO_RUN, DATA_QUALITY, PENDING_REVIEW. It is never emitted as an air-quality event and its source PM2.5 values are unchanged.

## Prospective collection check

Status=PASS_COLLECTION_NOT_SCORING; observation snapshot rows=47; new measurement timestamps after the frozen 180-day dataset=17; joinable future weather hours=47; target-ready rows=0; scoring=NOT_SCORABLE_TARGET_NOT_ARRIVED_OR_PENDING_REVIEW.
All collected observations remain PENDING_REVIEW. Collection success does not authorize scoring before target arrival and quality review.

## Notable candidates

| Type | Category | Severity | Start | End | Hours | Detector | Context |
|---|---|---|---|---|---:|---|---|
| MISSING_DATA | DATA_QUALITY | CRITICAL | 2026-07-01T01:00:00+00:00 | 2026-07-05T23:00:00+00:00 | 119 | missing_run | NONE |
| MISSING_DATA | DATA_QUALITY | CRITICAL | 2026-10-25T01:00:00+00:00 | 2026-10-26T10:00:00+00:00 | 34 | missing_run | NONE |
| RAPID_CHANGE | AIR_QUALITY_EVENT | CRITICAL | 2026-06-15T12:00:00+00:00 | 2026-06-15T15:00:00+00:00 | 4 | rapid_change_1h_or_3h | NONE |
| PERSISTENCE_RESIDUAL | AIR_QUALITY_EVENT | CRITICAL | 2026-06-15T12:00:00+00:00 | 2026-06-15T14:00:00+00:00 | 3 | persistence_residual_1h | NONE |
| SUSPECT_ZERO_RUN | DATA_QUALITY | WARNING | 2026-11-09T10:00:00+00:00 | 2026-11-09T16:00:00+00:00 | 7 | zero_run | NONE |
| RAPID_CHANGE | AIR_QUALITY_EVENT | WARNING | 2026-06-04T11:00:00+00:00 | 2026-06-04T16:00:00+00:00 | 6 | rapid_change_1h_or_3h | NONE |
| RAPID_CHANGE | AIR_QUALITY_EVENT | WARNING | 2026-05-27T12:00:00+00:00 | 2026-05-27T16:00:00+00:00 | 5 | rapid_change_1h_or_3h | NONE |
| ROBUST_DEVIATION | AIR_QUALITY_EVENT | WATCH | 2026-06-03T20:00:00+00:00 | 2026-06-03T23:00:00+00:00 | 4 | robust_median_mad | NONE |
| ROBUST_DEVIATION | AIR_QUALITY_EVENT | WATCH | 2026-07-20T14:00:00+00:00 | 2026-07-20T17:00:00+00:00 | 4 | robust_median_mad | NONE |
| ROBUST_DEVIATION | AIR_QUALITY_EVENT | WATCH | 2026-09-21T23:00:00+00:00 | 2026-09-22T02:00:00+00:00 | 4 | robust_median_mad | NONE |
| ROBUST_DEVIATION | AIR_QUALITY_EVENT | WATCH | 2026-10-26T21:00:00+00:00 | 2026-10-27T00:00:00+00:00 | 4 | robust_median_mad | WITHIN_24H_OF_DATA_QUALITY_EVENT |
| ROBUST_DEVIATION | AIR_QUALITY_EVENT | WATCH | 2026-10-27T22:00:00+00:00 | 2026-10-28T01:00:00+00:00 | 4 | robust_median_mad | NONE |

## Limitations

There are no confirmed anomaly labels, so precision, recall, F1 and accuracy are not reported. Event counts do not measure detector quality. Thresholds are empirical train quantiles for one community sensor and 180 days. Detector overlap and proximity to data gaps require human review. Severity expresses data-quality impact or detection confidence, never AQI or health advice.

![Timeline](figures/dragon_anomaly_timeline.png)
![Counts](figures/dragon_anomaly_event_counts.png)
![Scores](figures/dragon_anomaly_scores.png)
