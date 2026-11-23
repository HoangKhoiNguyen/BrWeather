"""Plain Vietnamese sentences for the reliability level and its reasons (T4.1-4, US4.1).

The job compute_reliability stores the result in reliability_scores.details:
    details.level_label   "Cao" | "Trung bình" | "Thấp – cần kiểm tra"
    details.summary       the one line shown under the label in the app
    details.messages      one sentence per failed check (most severe first)

Every number in a sentence comes from `details`, so the text never contains a figure that was not measured.
US4.1: level Low reads "cần kiểm tra" and must not use alarm wording or red.
"""
from brweather_data.quality.anomaly_classifier import fmt_number
from brweather_data.quality.reliability import NEIGHBOUR_RADIUS_KM, NO_DATA_AFTER, PM25_MAX_PLAUSIBLE

LEVEL_LABELS = {
    "high": "Cao",
    "medium": "Trung bình",
    "low": "Thấp – cần kiểm tra",
}

# Reason code -> sentence template; placeholders are filled from details.
TEMPLATES = {
    "out_of_range": "Số đo {latest_value} µg/m³ nằm ngoài khoảng hợp lý (0–{max_plausible} µg/m³), có thể do lỗi cảm biến.",
    "flatline": "Số đo không đổi ({latest_value} µg/m³) trong {flatline_hours} giờ liên tiếp, cảm biến có thể đang bị kẹt.",
    "stale": "Số đo mới nhất cách đây {hours_since_last} giờ nên có thể chưa phản ánh hiện tại.",
    "no_data": "Không có số đo nào trong {no_data_hours} giờ qua.",
    "neighbour_deviation": "Số đo ({latest_value} µg/m³) khác nhiều so với {neighbour_count} trạm lân cận "
                           "trong bán kính {radius_km} km (trung vị khu vực {local_median} µg/m³).",
}
HIGH_TEXT = "Số đo mới, trong khoảng hợp lý và có thay đổi theo thời gian."
HIGH_WITH_NEIGHBOURS = "Số đo mới, trong khoảng hợp lý và gần với {neighbour_count} trạm lân cận."
SEVERITY_ORDER = ("out_of_range", "flatline", "stale", "neighbour_deviation")


def _num(v) -> str:
    return "?" if v is None else fmt_number(float(v))


def messages(level: str, reasons: list[str], details: dict) -> dict:
    """Return {level_label, summary, messages} for one reliability result."""
    values = {
        "latest_value": _num(details.get("latest_value")),
        "max_plausible": _num(PM25_MAX_PLAUSIBLE),
        "flatline_hours": details.get("flatline_hours"),
        "hours_since_last": _num(details.get("hours_since_last")),
        "no_data_hours": int(NO_DATA_AFTER.total_seconds() // 3600),
        "neighbour_count": details.get("neighbour_count"),
        "radius_km": _num(NEIGHBOUR_RADIUS_KM),
        "local_median": _num(details.get("local_median")),
    }
    out = []
    for code in SEVERITY_ORDER:
        if code not in reasons:
            continue
        if code == "stale" and (details.get("last_measured") is None
                                or (details.get("hours_since_last") or 0) > values["no_data_hours"]):
            code = "no_data"
        out.append(TEMPLATES[code].format(**values))
    if not out:
        applied = details.get("neighbour_check_applied")
        out.append(HIGH_WITH_NEIGHBOURS.format(**values) if applied else HIGH_TEXT)
    return {"level_label": LEVEL_LABELS[level], "summary": out[0], "messages": out}
