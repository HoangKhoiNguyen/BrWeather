"""T5.1-2 (parameter table), T5.1-5 (pick 20 spread cases), T5.1-6 (review summary)."""
from datetime import datetime, timedelta, timezone

from brweather_data.jobs.anomaly_review import pick_cases, summarize, tune_table
from brweather_data.quality.synthetic_cases import build_cases

T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)


def test_tune_table_is_monotonic_in_threshold():
    cases = [c for c in build_cases() if c.case_id in ("single_spike", "regional_rise", "normal")]
    data = {i: (c.times, c.station) for i, c in enumerate(cases)}
    rows = tune_table(data, hours=48)
    assert len(rows) == 16
    by = {(r["threshold"], r["min_abs"]): r["events_per_station_week"] for r in rows}
    assert by[(3.5, 0.0)] >= by[(4.3, 15.0)] >= by[(5.0, 20.0)]
    assert by[(4.3, 15.0)] > 0


def _row(i, cat, station, hours_ago):
    return {"id": i, "category": cat, "station_id": station, "start_time": T0 - timedelta(hours=hours_ago)}


def test_pick_cases_spreads_over_categories_and_stations():
    rows = [_row(i, "needs_review", 1, i) for i in range(30)]           # one noisy station
    rows += [_row(100 + i, "data", 2, i) for i in range(3)]
    rows += [_row(200 + i, "environment", 3, i) for i in range(2)]
    picked = pick_cases(rows, 20)
    assert len(picked) == 20
    assert {r["category"] for r in picked} == {"needs_review", "data", "environment"}
    assert sum(r["station_id"] != 1 for r in picked) == 5               # every rarer case is included
    assert picked == sorted(picked, key=lambda r: r["start_time"])
    assert pick_cases(rows, 20) == picked                                # deterministic


def test_pick_cases_when_fewer_than_n():
    assert len(pick_cases([_row(1, "data", 1, 1)], 20)) == 1


def test_summary_of_a_filled_sheet():
    rows = [
        {"category": "data", "reviewer_is_anomaly": "đúng", "reviewer_category": "Có thể do lỗi đo"},
        {"category": "environment", "reviewer_is_anomaly": "đúng", "reviewer_category": "needs_review"},
        {"category": "needs_review", "reviewer_is_anomaly": "sai", "reviewer_category": ""},
        {"category": "data", "reviewer_is_anomaly": "", "reviewer_category": ""},
    ]
    s = summarize(rows)
    assert s == {"cases": 4, "reviewed": 3, "confirmed_anomaly": 2, "precision_pct": 66.7,
                 "category_agreement_pct": 50.0}
