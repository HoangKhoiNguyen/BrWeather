# OpenAQ reference-observation readiness

Window: 2026-05-15T09:00:00+00:00 to 2026-11-11T09:00:00+00:00 UTC.
This is point-sensor evidence for a project, not absolute truth or an estimate for all Hanoi.
Supplemental API requests this run: 0; cached request log: 5 entries.
No /hours request was made for the three PM2.5 sensors; saved 180-day raw files were used.

## Gap inventory

All gaps of 3+ hours are in data/audit/openaq_gap_analysis.csv; filter duration_hours >= 6, 24, or 48 for larger gaps.
Hanoi sensors missing-hour intersection: 162 hours; union: 471 hours; intersection/union: 34.39%.
Provider/owner: Hanoi Air Quality Monitoring Network / Unknown Governmental Organization and Hanoi Air Quality Monitoring Network / Unknown Governmental Organization.
- Sensor 13502151: gap counts >=3/6/24/48h = 14/12/2/1.
  - 2026-06-25T14:00:00+00:00 to 2026-06-29T03:00:00+00:00: 86h; before 29.2, after 19.4 µg/m³.
  - 2026-07-29T11:00:00+00:00 to 2026-07-31T07:00:00+00:00: 45h; before 20.4, after 29.0 µg/m³.
- Sensor 13502154: gap counts >=3/6/24/48h = 15/7/3/1.
  - 2026-06-25T14:00:00+00:00 to 2026-06-29T03:00:00+00:00: 86h; before 44.6, after 56.6 µg/m³.
  - 2026-07-29T11:00:00+00:00 to 2026-07-31T07:00:00+00:00: 45h; before 28.2, after 21.7 µg/m³.
  - 2026-08-29T17:00:00+00:00 to 2026-08-31T12:00:00+00:00: 44h; before 17.3, after 15.3 µg/m³.
- Sensor 14581375: gap counts >=3/6/24/48h = 3/2/2/1.
  - 2026-07-01T01:00:00+00:00 to 2026-07-05T23:00:00+00:00: 119h; before 35.4, after 2.1 µg/m³.
  - 2026-10-25T01:00:00+00:00 to 2026-10-26T10:00:00+00:00: 34h; before 68.6, after 53.1 µg/m³.
The 86-hour gaps of the two Hanoi-network sensors match exactly, and provider/owner metadata match. This is consistent with a shared upstream interruption, not proof of its cause. Dragon has 86/86 observed hours during that interval. Values before/after long gaps differ, but the intervening air quality is unknown; a reset cannot be inferred from these two endpoints alone.

## Dragon zero run

- 2026-11-09T10:00:00+00:00 to 2026-11-09T16:00:00+00:00: 7 records, raw value 0.0 µg/m³; before 0.1, after 0.1; status SUSPECT_ZERO_RUN.
- All contiguous raw zero groups: 2026-05-25T07:00:00+00:00 to 2026-05-25T07:00:00+00:00 (1h); 2026-07-18T17:00:00+00:00 to 2026-07-18T17:00:00+00:00 (1h); 2026-07-30T21:00:00+00:00 to 2026-07-30T21:00:00+00:00 (1h); 2026-11-08T20:00:00+00:00 to 2026-11-08T23:00:00+00:00 (4h); 2026-11-09T05:00:00+00:00 to 2026-11-09T08:00:00+00:00 (4h); 2026-11-09T10:00:00+00:00 to 2026-11-09T16:00:00+00:00 (7h).
- Targeted PM1: 7/7 zero during the 7-hour PM2.5 run; humidity: 7/7 values present. OpenAQ sensor flags: 0. Raw PM2.5 flagInfo.hasFlags is false for these zero hours. Hourly timestamps are consecutive. The particle channels may share a problem, but these checks do not prove the cause; retain SUSPECT_ZERO_RUN.

## Instrument and provenance

- 13502151: Government Monitor / Unknown Governmental Organization; INSTRUMENT_PARTIALLY_DESCRIBED; provider Hanoi Air Quality Monitoring Network; owner Unknown Governmental Organization; is_monitor=True. OpenAQ instrument metadata does not prove reference-grade performance.
- 13502154: Government Monitor / Unknown Governmental Organization; INSTRUMENT_PARTIALLY_DESCRIBED; provider Hanoi Air Quality Monitoring Network; owner Unknown Governmental Organization; is_monitor=True. OpenAQ instrument metadata does not prove reference-grade performance.
- 14581375: AirGradient Open Air Generation 1 (O-1PST) / AirGradient; INSTRUMENT_VERIFIED; provider AirGradient; owner srgillo; is_monitor=False. OpenAQ instrument metadata does not prove reference-grade performance.

## Valid ML sample counts

Rows below are BASIC/SEASONAL × 1/6/24h; each cell is KEEP_SUSPECT / EXCLUDE_SUSPECT. Full details and reasons for exclusions are in the CSV.

| Sensor | Lags | 1h | 6h | 24h |
|---|---|---:|---:|---:|
| 13502151 | BASIC | 3853 / 3853 | 3798 / 3798 | 3774 / 3774 |
| 13502151 | SEASONAL | 3498 / 3498 | 3444 / 3444 | 3423 / 3423 |
| 13502154 | BASIC | 3343 / 3343 | 3333 / 3333 | 3307 / 3307 |
| 13502154 | SEASONAL | 2946 / 2946 | 2934 / 2934 | 2910 / 2910 |
| 14581375 | BASIC | 4064 / 4043 | 4048 / 4022 | 3994 / 3975 |
| 14581375 | SEASONAL | 3765 / 3744 | 3749 / 3723 | 3695 / 3676 |

### Valid BASIC 24h samples by month (suspect zero run excluded)

| Sensor | 2026-05 | 2026-06 | 2026-07 | 2026-08 | 2026-09 | 2026-10 | 2026-11 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 13502151 | 361 | 387 | 606 | 731 | 720 | 744 | 225 |
| 13502154 | 342 | 509 | 526 | 517 | 595 | 660 | 158 |
| 14581375 | 371 | 697 | 600 | 725 | 720 | 657 | 205 |

## Anomaly rolling-window readiness

| Sensor | 24h eligible | 168h eligible |
|---|---:|---:|
| 13502151 | 3730 | 2713 |
| 13502154 | 2240 | 318 |
| 14581375 | 3993 | 3306 |

## Time-ordered split proposal

Use feature timestamps within each interval; targets must also fall inside that interval. Lag history may precede an interval because it is already known at prediction time. Keep the final test untouched during model choice.
Train: 2026-05-15T09:00:00+00:00 to 2026-09-01T00:00:00+00:00; validation: 2026-09-01T00:00:00+00:00 to 2026-10-27T00:00:00+00:00; test: 2026-10-27T00:00:00+00:00 to 2026-11-11T09:00:00+00:00 (end exclusive).

| Sensor | Split | 1h | 6h | 24h |
|---|---|---:|---:|---:|
| 13502151 | train | 2140 | 2085 | 2061 |
| 13502151 | validation | 1343 | 1338 | 1320 |
| 13502151 | test | 368 | 363 | 345 |
| 13502154 | train | 1929 | 1914 | 1894 |
| 13502154 | validation | 1132 | 1132 | 1117 |
| 13502154 | test | 281 | 281 | 272 |
| 14581375 | train | 2416 | 2405 | 2369 |
| 14581375 | validation | 1296 | 1291 | 1273 |
| 14581375 | test | 330 | 320 | 309 |

## Decision

| Sensor | Technical | License | Instrument | Overall |
|---|---|---|---|---|
| 13502151 | TECHNICAL_USABLE_WITH_GAPS | LICENSE_UNVERIFIED | INSTRUMENT_PARTIALLY_DESCRIBED | USABLE_FOR_PROTOTYPE |
| 13502154 | TECHNICAL_USABLE_WITH_GAPS | LICENSE_UNVERIFIED | INSTRUMENT_PARTIALLY_DESCRIBED | USABLE_FOR_PROTOTYPE |
| 14581375 | TECHNICAL_USABLE_WITH_GAPS | LICENSE_PASS_WITH_ATTRIBUTION | INSTRUMENT_VERIFIED | USABLE_FOR_PROTOTYPE |

The test begins after Dragon's 34-hour October gap. Its 7-hour November zero run remains flagged and is excluded from the conservative sample counts; keep the test untouched during model choice.
The numerical sample thresholds are provisional for this learning project; no model was trained. USABLE_FOR_PROTOTYPE means internal analysis only when license is unverified. Long gaps and Dragon's zero run still need review. LICENSE_UNVERIFIED blocks publication and redistribution of the Hanoi-network observations pending provider confirmation.
Source metadata: OpenAQ inventory and targeted /v3/instruments/{id}, /v3/sensors/{id}/hours, /v3/sensors/{id}/flags requests; API docs: https://docs.openaq.org/ .

## Supplemental API request log

- /instruments/2 {}: targeted provenance/zero-run check
- /instruments/24 {}: targeted provenance/zero-run check
- /sensors/14581374/hours {'datetime_from': '2026-11-09T04:00:00+00:00', 'datetime_to': '2026-11-09T18:00:00+00:00', 'limit': 1000, 'page': 1}: targeted provenance/zero-run check
- /sensors/14581376/hours {'datetime_from': '2026-11-09T04:00:00+00:00', 'datetime_to': '2026-11-09T18:00:00+00:00', 'limit': 1000, 'page': 1}: targeted provenance/zero-run check
- /sensors/14581375/flags {'datetime_from': '2026-11-09T04:00:00+00:00', 'datetime_to': '2026-11-09T18:00:00+00:00', 'limit': 1000, 'page': 1}: targeted provenance/zero-run check

![Gaps](figures/openaq_gap_comparison.png)
![Valid samples](figures/openaq_valid_ml_samples_by_month.png)
