# OpenAQ Hanoi: 180-day ground truth gate

Run at 2026-11-11T09:30:41.531855+00:00; window 2026-05-15T09:00:00+00:00 to 2026-11-11T09:00:00+00:00 UTC.
Ground truth here means a reference observation for this project, not an absolute truth or a citywide estimate.
API requests: 21 total for this checkpoint; 0 this run; last remaining 43.

## Coverage and decisions

| Sensor | 30d | 90d | 180d | Longest gap (h) | Technical | License | Ground truth |
|---|---:|---:|---:|---:|---|---|---|
| 13502151 | 100.0% | 99.95% | 93.87% | 86 | TECHNICAL_CONDITIONAL | LICENSE_UNVERIFIED | GROUND_TRUTH_NOT_READY |
| 13502154 | 96.53% | 92.78% | 91.48% | 86 | TECHNICAL_CONDITIONAL | LICENSE_UNVERIFIED | GROUND_TRUTH_NOT_READY |
| 14581375 | 95.0% | 98.15% | 96.3% | 119 | TECHNICAL_CONDITIONAL | LICENSE_PASS_WITH_ATTRIBUTION | GROUND_TRUTH_NOT_READY |

## Monthly coverage

| Sensor | Month UTC | Complete month | Observed / expected | Coverage | Longest gap (h) |
|---|---|---|---:|---:|---:|
| 13502151 | 2026-05 | False | 396 / 399 | 99.25% | 3 |
| 13502151 | 2026-06 | True | 519 / 720 | 72.08% | 86 |
| 13502151 | 2026-07 | True | 684 / 744 | 91.94% | 45 |
| 13502151 | 2026-08 | True | 743 / 744 | 99.87% | 1 |
| 13502151 | 2026-09 | True | 720 / 720 | 100.0% | 0 |
| 13502151 | 2026-10 | True | 744 / 744 | 100.0% | 0 |
| 13502151 | 2026-11 | False | 249 / 249 | 100.0% | 0 |
| 13502154 | 2026-05 | False | 392 / 399 | 98.25% | 3 |
| 13502154 | 2026-06 | True | 603 / 720 | 83.75% | 86 |
| 13502154 | 2026-07 | True | 663 / 744 | 89.11% | 45 |
| 13502154 | 2026-08 | True | 653 / 744 | 87.77% | 44 |
| 13502154 | 2026-09 | True | 691 / 720 | 95.97% | 3 |
| 13502154 | 2026-10 | True | 723 / 744 | 97.18% | 3 |
| 13502154 | 2026-11 | False | 227 / 249 | 91.16% | 3 |
| 14581375 | 2026-05 | False | 398 / 399 | 99.75% | 1 |
| 14581375 | 2026-06 | True | 720 / 720 | 100.0% | 0 |
| 14581375 | 2026-07 | True | 625 / 744 | 84.01% | 119 |
| 14581375 | 2026-08 | True | 740 / 744 | 99.46% | 3 |
| 14581375 | 2026-09 | True | 720 / 720 | 100.0% | 0 |
| 14581375 | 2026-10 | True | 709 / 744 | 95.3% | 34 |
| 14581375 | 2026-11 | False | 248 / 249 | 99.6% | 1 |

## Constant runs of 6 hours or more

- Sensor 14581375: 2026-11-09T10:00:00+00:00 to 2026-11-09T16:00:00+00:00 UTC, 7 hours, value 0.0 µg/m³. Flag for review; not deleted.

## Comparison with saved 30-day raw data

- Sensor 13502151: {'status': 'COMPARED', 'overlap_start': '2026-10-12T09:00:00+00:00', 'overlap_end': '2026-11-11T09:00:00+00:00', 'matching_timestamps': 720, 'changed_values': 0, 'new_late_records': 0, 'old_records_absent_now': 0}
- Sensor 13502154: {'status': 'COMPARED', 'overlap_start': '2026-10-12T09:00:00+00:00', 'overlap_end': '2026-11-11T09:00:00+00:00', 'matching_timestamps': 695, 'changed_values': 0, 'new_late_records': 0, 'old_records_absent_now': 0}
- Sensor 14581375: {'status': 'COMPARED', 'overlap_start': '2026-10-12T09:00:00+00:00', 'overlap_end': '2026-11-11T09:00:00+00:00', 'matching_timestamps': 684, 'changed_values': 0, 'new_late_records': 0, 'old_records_absent_now': 0}

## License review

- Sensor 13502151: LICENSE_UNVERIFIED; provider Hanoi Air Quality Monitoring Network; owner Unknown Governmental Organization; license not in API metadata; terms missing; attribution not specified. Storage, analysis/training, and noncommercial app display: unverified.
- Sensor 13502154: LICENSE_UNVERIFIED; provider Hanoi Air Quality Monitoring Network; owner Unknown Governmental Organization; license not in API metadata; terms missing; attribution not specified. Storage, analysis/training, and noncommercial app display: unverified.
- Sensor 14581375: LICENSE_PASS_WITH_ATTRIBUTION; provider AirGradient; owner srgillo; license CC BY 4.0; terms https://creativecommons.org/licenses/by/4.0/; attribution srgillo. Storage, analysis/training, and noncommercial app display: supported by listed license.

OpenAQ requires credit to OpenAQ and compliance with upstream provider terms: https://docs.openaq.org/about/terms .
CC BY 4.0 requires credit, a link to the license, and a note of changes: https://creativecommons.org/licenses/by/4.0/ .

## Recommendation

Ground-truth-ready sensors: none.
TECHNICAL_PASS_180 sensors: none.
Provisional principal for further review: 13502151 (strong recent continuity, but an 86-hour gap and unverified license). Nearby check: 13502154 (same 86-hour gap, so not independent across that outage). Independent comparison candidate: 14581375 (licensed CC BY 4.0, but a 119-hour gap and a 7-hour zero run to review). None is approved as project ground truth yet.
Scope is these point locations and the measured time window; do not claim representation of all Hanoi.
Do not load 365 days yet: no sensor passes the 180-day technical gate. After explaining/excluding the long gaps and resolving permissions, check 365 days for seasonality. A window ending in November misses much of winter–spring; do not claim cross-season performance yet.

![Coverage](figures/openaq_coverage_30_90_180d.png)
![Monthly](figures/openaq_monthly_coverage.png)
![Timeline](figures/openaq_long_term_timeline.png)
