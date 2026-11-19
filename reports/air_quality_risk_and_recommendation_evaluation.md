# Dragon air-quality assessment and recommendation prototype

The module does not publish VN_AQI. Dragon is an AirGradient Open Air Generation 1 community sensor with is_monitor=false; statutory station/data QA/QC required by Decision 1459/QĐ-TCMT is not established.
Official reference: {'title': 'Hướng dẫn kỹ thuật tính toán và công bố chỉ số chất lượng không khí Việt Nam (VN_AQI)', 'issuer': 'Tổng cục Môi trường, Bộ Tài nguyên và Môi trường', 'decision': '1459/QĐ-TCMT', 'issued_date': '2019-11-12', 'url': 'https://vea.mae.gov.vn/Data/files/QD%201459%20TCMT%20ngay%2012_11_2019%20AQI%281%29.pdf', 'scope': 'VN_AQI from quality-controlled data of continuous automatic ambient-air monitoring stations', 'pm25_hourly_method': '12-hour Nowcast; at least 2 of the latest 3 hourly values must exist', 'uncertainty': 'Current continued legal status was not independently established beyond the official agency-hosted document; applicability to this community sensor is not demonstrated.'}. Accessed 2026-11-12. Official VN_AQI names/colors and PM2.5 breakpoints are retained in the policy for traceability but are not applied as VN_AQI to Dragon. The current method is PROVISIONAL_PM25_CONCENTRATION_STATUS and emits no AQI number.
Observed concentration uses a past/current 12-hour Nowcast-like window. Official minimum: 2 of the latest 3 hours. Internal conservative gate: at least 9/12 valid hours (75.0%). Missing and SUSPECT_ZERO_RUN values are excluded; no future value is read.
Assessments=16826; by type={'OBSERVED_RETROSPECTIVE': 4320, 'FORECAST_PROTOTYPE': 12459, 'OBSERVED_PROSPECTIVE_PENDING_REVIEW': 47}; availability={'INSUFFICIENT_DATA': 33, 'AVAILABLE': 16579, 'SUPPRESSED_DATA_QUALITY': 168, 'PENDING_REVIEW': 46}; suppressed/insufficient reasons={'INSUFFICIENT_COVERAGE': 33, 'MISSING_DATA': 161, 'SUSPECT_ZERO_RUN': 7, 'PENDING_REVIEW': 46}; anomaly-candidate-linked assessments=464.
Availability by assessment type: {'OBSERVED_RETROSPECTIVE': {'INSUFFICIENT_DATA': 33, 'AVAILABLE': 4120, 'SUPPRESSED_DATA_QUALITY': 167}, 'FORECAST_PROTOTYPE': {'AVAILABLE': 12459}, 'OBSERVED_PROSPECTIVE_PENDING_REVIEW': {'PENDING_REVIEW': 46, 'SUPPRESSED_DATA_QUALITY': 1}}.
Data-quality events suppress assessment. Air-quality anomaly candidates add evidence only and never raise the concentration status or health recommendation.
Persistence forecasts are issued at the last valid observation for 1/6/24h, are marked FORECAST_PROTOTYPE and PROTOTYPE_ONLY, and are not official future AQI.
Recommendation occurrences for default GENERAL audience: {'MONITOR_GENERAL_V1': 11775, 'ADJUST_OUTDOOR_GENERAL_V1': 4804, 'SEEK_HELP_SEVERE_SYMPTOMS_V1': 1641}. The catalog also contains the sourced SENSITIVE_GROUP rule. Every emitted recommendation has an official WHO source and disclaimer. Excluded: ['Medication changes are excluded', 'Diagnosis is excluded', 'Respirator advice is excluded because individual fit and medical considerations are outside this prototype', 'No recommendation is emitted when assessment is suppressed or pending review'].
Prospective PENDING_REVIEW records=47. They create audit assessments that remain PENDING_REVIEW or are suppressed by an overlapping data-quality event; they have no status/recommendation and no Persistence forecast.

## Sources and uncertainty

- Decision 1459/QĐ-TCMT, Tổng cục Môi trường, 12/11/2019: https://vea.mae.gov.vn/Data/files/QD%201459%20TCMT%20ngay%2012_11_2019%20AQI%281%29.pdf
- QCVN 05:2023/BTNMT, Bộ Tài nguyên và Môi trường, reviewed as ambient-air concentration context and not used as the AQI formula: https://cem.gov.vn/storage/documents/66cf004657629qcvn-052023btnmt.pdf
- WHO personal interventions and risk communication, accessed 12/11/2026: https://www.who.int/news-room/questions-and-answers/item/air-pollution-personal-interventions-and-risk-communication
- Uncertainty: applicability and legal/current status are not independently proven for Dragon; advice is generic and individual effects vary.

![Status timeline](figures/dragon_assessment_status_timeline.png)
![Coverage and suppression](figures/dragon_assessment_coverage_suppression.png)
