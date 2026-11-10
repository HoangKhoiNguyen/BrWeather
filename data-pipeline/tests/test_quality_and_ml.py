from datetime import datetime, timedelta, timezone

from brweather_data.ml.anomaly import flag_spikes
from brweather_data.ml.baseline import mae, persistence, seasonal_naive
from brweather_data.quality.reliability import is_flatline, range_flag, score

NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)


def test_range_flag():
    assert range_flag(35.0) == "ok"
    assert range_flag(-1.0) == "out_of_range"
    assert range_flag(None) == "ok"


def test_flatline_detects_stuck_sensor():
    assert is_flatline([10, 20, 30, 30, 30, 30, 30, 30])
    assert not is_flatline([30, 30, 30, 31, 30, 30])


def test_score_levels():
    healthy = [20, 22, 25, 24, 23, 26]
    assert score(healthy, NOW - timedelta(hours=1), NOW, [24, 25])[0] == "high"
    assert score(healthy, NOW - timedelta(hours=5), NOW, [24, 25]) == ("medium", ["stale"])
    stuck = [30] * 8
    assert score(stuck, NOW - timedelta(hours=5), NOW, [])[0] == "low"


def test_baselines():
    history = list(range(48))  # 0..47
    assert persistence(history + [None], 3) == [47, 47, 47]
    assert seasonal_naive(history, 2) == [24, 25]
    assert mae([1, 2, None], [2, 2, 5]) == 0.5


def test_flag_spikes_finds_jump():
    values = [20.0 + (i % 3) for i in range(100)]
    values[90] = 150.0
    assert flag_spikes(values) == [90]
