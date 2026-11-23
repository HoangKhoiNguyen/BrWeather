"""T5.1-1 (past-only detection, events), T5.2-1 (classification), T5.2-2 (labelled synthetic cases)."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from brweather_data.jobs.detect_anomalies import analyse, to_series
from brweather_data.ml.anomaly import LIVE_THRESHOLD, MIN_ABS_DEVIATION, detect_events, flag_hours
from brweather_data.quality.anomaly_classifier import CATEGORY_LABELS, StationSeries, describe, fmt_number
from brweather_data.quality.synthetic_cases import EVENT_AT, build_cases, to_json

T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)


def _run(case):
    times = case.times
    flags = {times[i]: f for i, f in case.flags.items()}
    values = [None if v is not None and flags.get(times[i]) == "out_of_range" else v
              for i, v in enumerate(case.station)]
    station = StationSeries({times[i]: v for i, v in enumerate(case.station)}, flags)
    neighbours = {nid: StationSeries({times[i]: v for i, v in enumerate(vals)})
                  for nid, vals in case.neighbours.items()}
    return analyse(times, values, station, neighbours, first_index=72)


# ---------------------------------------------------------------- T5.2-2 + T5.2-1: every labelled case
@pytest.mark.parametrize("case", build_cases(), ids=lambda c: c.case_id)
def test_synthetic_case(case):
    results = _run(case)
    if not case.expected_event:
        assert results == []
        return
    assert len(results) == 1, [(e.start, c.category) for e, c in results]
    event, classification = results[0]
    assert event.start == case.times[EVENT_AT]
    assert (classification.category, classification.reason) == (case.expected_category, case.expected_reason)


def test_synthetic_set_covers_the_three_error_kinds_and_every_category():
    cases = build_cases()
    reasons = {c.expected_reason for c in cases}
    assert {"flatline", "isolated_spike", "after_signal_gap"} <= reasons        # đứng yên, nhảy vọt, mất tín hiệu
    assert {c.expected_category for c in cases if c.expected_event} == set(CATEGORY_LABELS)
    assert len({c.case_id for c in cases}) == len(cases)


def test_synthetic_export_is_labelled_and_json_serialisable():
    data = to_json(build_cases())
    text = json.dumps(data, ensure_ascii=False)
    assert all(d["synthetic"] is True for d in data)
    assert all(len(d["station"]["values"]) == len(d["times_utc"]) for d in data)
    assert "Đứng yên" in text


# ---------------------------------------------------------------- detector properties
def _flat(n, base=30.0):
    return [base + (i % 4) for i in range(n)]


def test_detection_only_looks_at_the_past():
    values = _flat(100)
    values[90] = 150.0
    before = [f.index for f in flag_hours(values, 72)]
    values[95:] = [999.0] * 5                      # change the future
    after = [f.index for f in flag_hours(values, 72) if f.index < 95]
    assert before == after == [90]


def test_needs_enough_history():
    values = _flat(40)
    values[30] = 200.0                             # only 30 past values (< 36): not judged
    values[39] = 200.0                             # 39 past values: judged
    assert [f.index for f in flag_hours(values)] == [39]


def test_small_absolute_change_in_clean_air_is_not_an_anomaly():
    values = [5.0, 5.1] * 40
    values[78] = 5.0 + MIN_ABS_DEVIATION - 1       # huge z (tiny MAD) but only 14 µg/m³
    assert flag_hours(values, 72) == []
    values[78] = 5.0 + MIN_ABS_DEVIATION + 1
    assert [f.index for f in flag_hours(values, 72)] == [78]
    assert abs(flag_hours(values, 72)[0].z) > LIVE_THRESHOLD


def test_events_merge_short_gaps_and_split_on_direction():
    times = [T0 + timedelta(hours=h) for h in range(100)]
    values = _flat(100)
    values[80], values[81], values[83] = 120.0, 125.0, 118.0     # one-hour gap at 82 -> one event
    values[90] = 1.0                                              # a drop, needs |dev| >= 15: 30 -> 1
    events = detect_events(times, values, 72)
    assert [(e.direction, e.duration_hours) for e in events] == [("up", 4), ("down", 1)]
    assert events[0].peak_value == 125.0 and events[0].peak_time == times[81]
    assert events[0].hours == [times[80], times[81], times[83]]


def test_to_series_keeps_flatline_but_drops_out_of_range():
    h = [T0 + timedelta(hours=i) for i in range(3)]
    times, values, series = to_series([(h[0], 30.0, "ok"), (h[1], 1500.0, "out_of_range"), (h[2], 30.0, "flatline")])
    assert values == [30.0, None, 30.0]
    assert series.flags == {h[0]: "ok", h[1]: "out_of_range", h[2]: "flatline"}


# ---------------------------------------------------------------- texts
def test_description_uses_only_event_numbers_and_states_category():
    case = next(c for c in build_cases() if c.case_id == "regional_rise")
    event, classification = _run(case)[0]
    text = describe(event, classification)
    assert text.startswith("PM2.5 tăng bất thường lên ")
    assert fmt_number(event.peak_value) in text and fmt_number(event.baseline) in text
    assert "kéo dài 6 giờ" in text and "biến động thật" in text
    for word in ("do giao thông", "do đốt", "nguyên nhân"):
        assert word not in text                    # never claims a cause (US5.2)


@pytest.mark.parametrize("v, s", [(42.0, "42"), (48.25, "48,2"), (48.26, "48,3"), (0.04, "0")])
def test_fmt_number(v, s):
    assert fmt_number(v) == s


def test_exported_fixture_matches_generator():
    """tests/fixtures/anomaly_synthetic_cases.json is regenerated with:
    python -m brweather_data.quality.synthetic_cases tests/fixtures/anomaly_synthetic_cases.json"""
    from pathlib import Path
    stored = json.loads((Path(__file__).parent / "fixtures" / "anomaly_synthetic_cases.json").read_text("utf-8"))
    assert stored["cases"] == json.loads(json.dumps(to_json(build_cases())))
