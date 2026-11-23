"""Labelled synthetic PM2.5 cases for testing anomaly detection and classification (T5.2-2).

SYNTHETIC DATA: every value here is generated, not measured. Use only in tests and QA.

Each case has one station series (and optionally neighbour series) of 120 hours, a human-readable label
and the expected result:
  expected_event     True if the detector must find exactly one event in the last 24 hours
  expected_category  'data' | 'environment' | 'needs_review'  (see quality/anomaly_classifier.py)
  expected_reason    the classifier rule expected to decide

Export for QA / other languages:
    python -m brweather_data.quality.synthetic_cases tests/fixtures/anomaly_synthetic_cases.json
"""
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

START = datetime(2026, 11, 1, tzinfo=timezone.utc)
HOURS = 120
EVENT_AT = 100            # index of the first abnormal hour (after > 72 h of history)
STATION_ID, NEIGHBOUR_ID, NEIGHBOUR2_ID = 900001, 900002, 900003


def _normal(h: int, level: float = 35.0, amplitude: float = 6.0, seed: int = 0) -> float:
    """Daily cycle plus a small deterministic wobble (never two identical values in a row)."""
    wobble = (((h + seed) * 7) % 5 - 2) * 0.8
    return round(level + amplitude * math.sin(2 * math.pi * h / 24) + wobble + 0.01 * (h % 3), 1)


def _series(level: float = 35.0, seed: int = 0) -> list[float | None]:
    return [_normal(h, level, seed=seed) for h in range(HOURS)]


@dataclass
class Case:
    case_id: str
    label: str
    description: str
    station: list[float | None]
    neighbours: dict[int, list[float | None]] = field(default_factory=dict)
    flags: dict[int, str] = field(default_factory=dict)   # index -> quality_flag for the station
    expected_event: bool = True
    expected_category: str | None = None
    expected_reason: str | None = None

    @property
    def times(self) -> list[datetime]:
        return [START + timedelta(hours=h) for h in range(HOURS)]


def build_cases() -> list[Case]:
    cases = []

    s = _series()
    for h in range(EVENT_AT, EVENT_AT + 8):
        s[h] = 90.0
    cases.append(Case("stuck_high", "Đứng yên (cảm biến kẹt)",
                      "Số đo nhảy lên 90 µg/m³ rồi giữ nguyên 8 giờ; trạm lân cận bình thường.",
                      s, {NEIGHBOUR_ID: _series(seed=1)},
                      expected_category="data", expected_reason="flatline"))

    s = _series()
    s[EVENT_AT] = 180.0
    cases.append(Case("single_spike", "Nhảy vọt 1 giờ",
                      "Một giờ 180 µg/m³ rồi về ngay mức thường; trạm lân cận không đổi.",
                      s, {NEIGHBOUR_ID: _series(seed=1)},
                      expected_category="data", expected_reason="isolated_spike"))

    s = _series()
    for h in range(EVENT_AT - 5, EVENT_AT):
        s[h] = None
    s[EVENT_AT], s[EVENT_AT + 1] = 120.0, 110.0
    cases.append(Case("after_signal_loss", "Mất tín hiệu rồi nhảy vọt",
                      "Mất 5 giờ dữ liệu, có tín hiệu lại thì báo 120 và 110 µg/m³; lân cận không đổi.",
                      s, {NEIGHBOUR_ID: _series(seed=1)},
                      expected_category="data", expected_reason="after_signal_gap"))

    s, n = _series(), _series(seed=1)
    for k, h in enumerate(range(EVENT_AT, EVENT_AT + 6)):
        s[h] = 95.0 + 3 * k
        n[h] = 85.0 + 3 * k
    cases.append(Case("regional_rise", "Tăng thật trên diện rộng",
                      "Trạm và trạm lân cận cùng tăng lên khoảng 90–110 µg/m³ trong 6 giờ.",
                      s, {NEIGHBOUR_ID: n, NEIGHBOUR2_ID: _series(seed=2)},
                      expected_category="environment", expected_reason="neighbour_confirms"))

    s, n = _series(level=85, seed=0), _series(level=80, seed=1)
    for k, h in enumerate(range(EVENT_AT, EVENT_AT + 4)):
        s[h] = 25.0 + k
        n[h] = 28.0 + k
    cases.append(Case("regional_drop", "Giảm thật trên diện rộng",
                      "Trạm và trạm lân cận cùng giảm từ khoảng 85 xuống 25–30 µg/m³ (ví dụ sau mưa).",
                      s, {NEIGHBOUR_ID: n},
                      expected_category="environment", expected_reason="neighbour_confirms"))

    s = _series()
    for k, h in enumerate(range(EVENT_AT, EVENT_AT + 5)):
        s[h] = 100.0 + 4 * k
    cases.append(Case("rise_no_neighbour", "Tăng, không có trạm lân cận",
                      "Trạm tăng lên 100–116 µg/m³ trong 5 giờ, không có trạm nào trong bán kính 10 km.",
                      s, {}, expected_category="needs_review", expected_reason="no_neighbour"))

    s = _series()
    s[EVENT_AT] = 180.0
    cases.append(Case("spike_no_neighbour", "Nhảy vọt, không có trạm lân cận",
                      "Một giờ 180 µg/m³, không có trạm lân cận để đối chiếu.",
                      s, {}, expected_category="needs_review", expected_reason="no_neighbour"))

    s = _series()
    for k, h in enumerate(range(EVENT_AT, EVENT_AT + 5)):
        s[h] = 100.0 + 4 * k
    cases.append(Case("local_sustained", "Tăng kéo dài chỉ ở một trạm",
                      "Trạm tăng 5 giờ liên tục nhưng trạm lân cận không đổi: có thể là nguồn rất gần trạm.",
                      s, {NEIGHBOUR_ID: _series(seed=1)},
                      expected_category="needs_review", expected_reason="neighbours_disagree"))

    s = _series()
    s[EVENT_AT] = 1500.0
    cases.append(Case("out_of_range", "Giá trị ngoài khoảng hợp lý",
                      "Một giờ 1500 µg/m³, đã bị gắn cờ out_of_range khi nạp; bộ phát hiện bỏ qua giờ này.",
                      s, {NEIGHBOUR_ID: _series(seed=1)}, flags={EVENT_AT: "out_of_range"},
                      expected_event=False))

    cases.append(Case("normal", "Bình thường (đối chứng)",
                      "Chu kỳ ngày đêm bình thường, không có bất thường.",
                      _series(), {NEIGHBOUR_ID: _series(seed=1)}, expected_event=False))
    return cases


def to_json(cases: list[Case]) -> list[dict]:
    times = [t.isoformat() for t in cases[0].times]
    return [{
        "case_id": c.case_id,
        "label": c.label,
        "description": c.description,
        "synthetic": True,
        "times_utc": times,
        "station": {"id": STATION_ID, "values": c.station,
                    "flags": {times[i]: f for i, f in c.flags.items()}},
        "neighbours": [{"id": nid, "values": vals} for nid, vals in c.neighbours.items()],
        "expected": {"event": c.expected_event, "category": c.expected_category, "reason": c.expected_reason},
    } for c in cases]


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "anomaly_synthetic_cases.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"note": "SYNTHETIC test data for T5.2-2, not measurements", "cases": to_json(build_cases())},
                  f, ensure_ascii=False, indent=1)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
