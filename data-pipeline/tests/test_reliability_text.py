"""T4.1-4: one plain sentence per reason, numbers only from details."""
import re
from datetime import datetime, timedelta, timezone

import pytest

from brweather_data.quality.reliability import assess
from brweather_data.quality.reliability_text import LEVEL_LABELS, TEMPLATES, messages

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)


def _texts(values, hours_ago, neighbours, latest=None):
    last = None if hours_ago is None else NOW - timedelta(hours=hours_ago)
    level, reasons, details = assess(values, last, NOW, neighbours, latest_value=latest)
    return level, reasons, details, messages(level, reasons, details)


def test_every_reason_code_has_a_sentence():
    assert set(TEMPLATES) >= {"out_of_range", "flatline", "stale", "neighbour_deviation", "no_data"}
    assert LEVEL_LABELS == {"high": "Cao", "medium": "Trung bình", "low": "Thấp – cần kiểm tra"}


def test_high_level():
    _, _, _, m = _texts([20.0, 22.0, 25.0, 24.0], 1, [24.0, 25.0])
    assert m["level_label"] == "Cao"
    assert m["summary"] == "Số đo mới, trong khoảng hợp lý và gần với 2 trạm lân cận."
    _, _, _, m = _texts([20.0, 22.0, 25.0, 24.0], 1, [])
    assert m["summary"] == "Số đo mới, trong khoảng hợp lý và có thay đổi theo thời gian."


def test_flatline_sentence_matches_po_example():
    _, _, _, m = _texts([30.0] * 7, 1, [])
    assert m["level_label"] == "Thấp – cần kiểm tra"
    assert m["summary"] == "Số đo không đổi (30 µg/m³) trong 7 giờ liên tiếp, cảm biến có thể đang bị kẹt."


def test_stale_and_no_data():
    _, _, _, m = _texts([20.0, 22.0, 25.0, 24.0], 4.5, [])
    assert m["summary"] == "Số đo mới nhất cách đây 4,5 giờ nên có thể chưa phản ánh hiện tại."
    _, _, _, m = _texts([None] * 24, None, [])
    assert m["summary"] == "Không có số đo nào trong 24 giờ qua."
    _, _, _, m = _texts([20.0], 30, [])
    assert m["summary"] == "Không có số đo nào trong 24 giờ qua."


def test_neighbour_deviation_sentence():
    _, reasons, _, m = _texts([40.0, 41.0, 150.0], 1, [40.0, 42.0])
    assert reasons == ["neighbour_deviation"]
    assert m["summary"] == ("Số đo (150 µg/m³) khác nhiều so với 2 trạm lân cận trong bán kính 10 km "
                            "(trung vị khu vực 42 µg/m³).")


def test_out_of_range_comes_first_when_several_reasons():
    _, reasons, _, m = _texts([20.0, 1500.0], 5, [])
    assert set(reasons) == {"out_of_range", "stale"}
    assert m["summary"].startswith("Số đo 1500 µg/m³ nằm ngoài khoảng hợp lý")
    assert len(m["messages"]) == 2


@pytest.mark.parametrize("values, hours_ago, neighbours", [
    ([30.0] * 7, 1, []), ([20.0, 1500.0], 5, []), ([40.0, 41.0, 150.0], 1, [40.0, 42.0]),
    ([20.0, 22.0], 4.5, []),
])
def test_no_number_outside_details(values, hours_ago, neighbours):
    """Every number in the text appears in details or is a fixed threshold (0, 1000, 10, 24)."""
    _, _, details, m = _texts(values, hours_ago, neighbours)
    allowed = {"0", "1000", "10", "24", "2.5"}
    for k in ("latest_value", "flatline_hours", "hours_since_last", "neighbour_count", "local_median"):
        if details.get(k) is not None:
            v = float(details[k])
            allowed.add(str(int(v)) if v == int(v) else f"{round(v, 1)}")
    for text in m["messages"]:
        for n in re.findall(r"\d+(?:,\d+)?", text.replace("PM2.5", "")):
            assert n.replace(",", ".") in allowed, (n, text)


def test_low_label_has_no_alarm_words():
    for text in list(LEVEL_LABELS.values()) + list(TEMPLATES.values()):
        for word in ("nguy hiểm", "báo động", "khẩn cấp"):
            assert word not in text.lower()
