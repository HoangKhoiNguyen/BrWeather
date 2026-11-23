"""T4.1-1 (range, flatline, stale), T4.1-2 (neighbours within a radius), T4.1-3 (job inputs)."""
from datetime import datetime, timedelta, timezone

import pytest

from brweather_data.jobs.compute_reliability import flatline_hours, station_inputs
from brweather_data.quality.reliability import (
    FLATLINE_HOURS,
    NEIGHBOUR_RADIUS_KM,
    Reading,
    assess,
    deviates_from_neighbours,
    flatline_length,
    haversine_km,
    is_flatline,
    is_stale,
    neighbour_values,
    range_flag,
    score,
)

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
HEALTHY = [20.0, 22.0, 25.0, 24.0, 23.0, 26.0]


# ---------------------------------------------------------------- T4.1-1 range
@pytest.mark.parametrize("value, flag", [
    (0.0, "ok"), (1000.0, "ok"), (35.5, "ok"), (None, "ok"),
    (-0.1, "out_of_range"), (1000.1, "out_of_range"), (float("nan"), "out_of_range"),
])
def test_range_flag_boundaries(value, flag):
    assert range_flag(value) == flag


# ---------------------------------------------------------------- T4.1-1 flatline
def test_flatline_needs_six_consecutive_identical_hours():
    assert is_flatline([10, 20] + [30] * FLATLINE_HOURS)
    assert not is_flatline([10] + [30] * (FLATLINE_HOURS - 1))
    assert flatline_length([10, 30, 30, 30]) == 3


def test_flatline_is_broken_by_a_missing_hour_or_change():
    assert not is_flatline([30, 30, 30, None, 30, 30, 30])
    assert not is_flatline([30, 30, 30, 31, 30, 30])
    assert flatline_length([30] * 8 + [None]) == 0  # latest hour missing: stale, not flatline


def test_flatline_on_empty_series():
    assert flatline_length([]) == 0 and not is_flatline([])


# ---------------------------------------------------------------- T4.1-1 stale
def test_stale_boundary_is_three_hours():
    assert not is_stale(NOW - timedelta(hours=3), NOW)
    assert is_stale(NOW - timedelta(hours=3, minutes=1), NOW)
    assert is_stale(None, NOW)


def test_stale_rejects_naive_datetimes():
    with pytest.raises(ValueError):
        is_stale(datetime(2026, 11, 20, 10), NOW)


# ---------------------------------------------------------------- T4.1-2 neighbours
def test_haversine_known_distance():
    # Hoàn Kiếm -> Cầu Giấy is about 6.7 km
    assert haversine_km(21.0285, 105.8542, 21.0362, 105.7906) == pytest.approx(6.65, abs=0.2)


def test_neighbours_only_within_radius_and_close_in_time():
    target = Reading(1, 21.00, 105.80, 50.0, NOW)
    others = [
        Reading(1, 21.00, 105.80, 99.0, NOW),                         # itself
        Reading(2, 21.03, 105.80, 40.0, NOW),                         # ~3.3 km: used
        Reading(3, 21.00, 105.85, 45.0, NOW - timedelta(hours=1)),    # ~5.2 km, 1 h apart: used
        Reading(4, 21.20, 105.80, 10.0, NOW),                         # ~22 km: too far
        Reading(5, 21.01, 105.80, 10.0, NOW - timedelta(hours=5)),    # too old
        Reading(6, 21.01, 105.80, None, None),                        # no data
    ]
    assert sorted(neighbour_values(target, others)) == [40.0, 45.0]
    assert NEIGHBOUR_RADIUS_KM == 10.0


def test_no_neighbour_means_check_not_applied():
    target = Reading(1, 21.0, 105.8, 50.0, NOW)
    assert neighbour_values(target, [Reading(4, 21.5, 105.8, 10.0, NOW)]) == []
    assert deviates_from_neighbours(50.0, []) is None
    _, reasons, details = assess(HEALTHY, NOW - timedelta(hours=1), NOW, [])
    assert "neighbour_deviation" not in reasons
    assert details["neighbour_check_applied"] is False and details["neighbour_count"] == 0


def test_neighbour_deviation_needs_both_ratio_and_absolute_gap():
    assert deviates_from_neighbours(100.0, [40.0, 45.0, 50.0]) is True     # local median 47.5: +52.5, +110%
    assert deviates_from_neighbours(50.0, [40.0, 45.0, 50.0]) is False
    assert deviates_from_neighbours(9.0, [5.0, 5.0]) is False             # +80% but only 4 µg/m³
    assert deviates_from_neighbours(10.0, [0.0, 0.0]) is None             # median 0: cannot compare


def test_one_outlier_neighbour_does_not_condemn_the_others():
    # Stations reading 40, 42 and 150 µg/m³: only the 150 one is flagged
    assert deviates_from_neighbours(40.0, [42.0, 150.0]) is False
    assert deviates_from_neighbours(42.0, [40.0, 150.0]) is False
    assert deviates_from_neighbours(150.0, [40.0, 42.0]) is True


# ---------------------------------------------------------------- levels
def test_score_levels():
    assert score(HEALTHY, NOW - timedelta(hours=1), NOW, [24, 25])[0] == "high"
    assert score(HEALTHY, NOW - timedelta(hours=5), NOW, [24, 25]) == ("medium", ["stale"])
    assert score(HEALTHY[:-1] + [80.0], NOW - timedelta(hours=1), NOW, [24, 25]) == \
        ("medium", ["neighbour_deviation"])
    assert score([30.0] * 8, NOW - timedelta(hours=1), NOW, []) == ("low", ["flatline"])
    assert score([30.0] * 8, NOW - timedelta(hours=5), NOW, [])[0] == "low"
    assert score([20.0, 1500.0], NOW - timedelta(hours=1), NOW, []) == ("low", ["out_of_range"])


def test_no_reading_for_a_day_is_low():
    assert score([None] * 24, None, NOW, []) == ("low", ["stale"])
    assert score(HEALTHY, NOW - timedelta(hours=30), NOW, [])[0] == "low"


def test_assess_details_carry_the_numbers():
    level, reasons, d = assess([30.0] * 7, NOW - timedelta(hours=4), NOW, [28.0, 32.0])
    assert level == "low" and reasons == ["flatline", "stale"]
    assert d["latest_value"] == 30.0
    assert d["hours_since_last"] == 4.0
    assert d["flatline_hours"] == 7
    assert d["neighbour_count"] == 2 and d["local_median"] == 30.0
    assert d["last_measured"] == "2026-11-20T08:00:00+00:00"


# ---------------------------------------------------------------- T4.1-3 job inputs
def _row(h, value, raw=None, flag="ok", status=None):
    raw = value if raw is None else raw
    status = status or ("ok" if value is not None else ("flagged" if raw is not None else "missing"))
    return (NOW - timedelta(hours=h), value, raw, flag if raw is not None else None, status)


def test_station_inputs_from_hourly_series():
    series = [
        _row(5, 20.0),
        _row(4, None, raw=None),                          # missing hour
        _row(3, None, raw=1500.0, flag="out_of_range"),    # flagged value
        _row(2, 30.0),
        _row(1, None, raw=30.0, flag="flatline"),          # already flagged stuck
        _row(0, None, raw=None),
    ]
    inp = station_inputs(series)
    assert inp["values"] == [20.0, None, None, 30.0, 30.0, None]
    assert inp["latest_value"] == 30.0
    assert inp["last_measured"] == NOW - timedelta(hours=1)
    assert inp["latest_usable"] == (NOW - timedelta(hours=2), 30.0)


def test_station_inputs_without_any_data():
    inp = station_inputs([_row(h, None, raw=None) for h in range(3)])
    assert inp["latest_value"] is None and inp["last_measured"] is None
    assert inp["latest_usable"] == (None, None)


def test_flatline_hours_to_flag():
    series = [_row(h, 30.0) for h in range(7, -1, -1)]  # 8 hours, oldest first
    assert flatline_hours(series, 8) == (NOW - timedelta(hours=7), NOW)
    assert flatline_hours(series, 5) is None
