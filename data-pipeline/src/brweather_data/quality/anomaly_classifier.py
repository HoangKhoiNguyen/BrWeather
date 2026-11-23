"""Classify a PM2.5 anomaly as possible measurement error, real change, or needs review (T5.2-1, US5.2).

Categories (column anomalies.category):
  data          "Có thể do lỗi đo"
  environment   "Biến động thật"
  needs_review  "Cần kiểm tra"

Rules, applied in order (the first that matches decides):
  1. data          the event's hours (±1 h) contain values flagged out_of_range, or a run of identical values
                   of at least FLATLINE_HOURS (stuck sensor)                     -> reason flagged_values / flatline
  2. needs_review  no neighbour within NEIGHBOUR_RADIUS_KM has data during the event -> reason no_neighbour
                   (US5.2: "có trạm lân cận thì đối chiếu, không có thì cần kiểm tra")
  3. environment   at least one neighbour moves the same way at the same time       -> reason neighbour_confirms
  4. data          neighbours stay flat AND the event is a one-hour spike that falls straight back
                   (isolated_spike) or starts right after a signal gap of >= SIGNAL_GAP_HOURS (after_signal_gap)
  5. needs_review  neighbours stay flat and the change lasts several hours        -> reason neighbours_disagree
                   (could be a very local real source; the app never guesses a cause)

All inputs are plain hourly series so the rules are testable without a database
(see quality/synthetic_cases.py, T5.2-2).
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median

from brweather_data.ml.anomaly import Event
from brweather_data.quality.reliability import FLATLINE_HOURS

CATEGORY_LABELS = {
    "data": "Có thể do lỗi đo",
    "environment": "Biến động thật",
    "needs_review": "Cần kiểm tra",
}
SIGNAL_GAP_HOURS = 3
SPIKE_RETURN_SHARE = 1 / 3        # next hour back within 1/3 of the jump -> the spike "fell straight back"
NEIGHBOUR_CONFIRM_SHARE = 0.5     # neighbour's relative change >= half of the station's, same direction
NEIGHBOUR_MIN_ABS = 7.5           # ... and at least this many µg/m³
BASELINE_HOURS = 72

HOUR = timedelta(hours=1)


@dataclass
class StationSeries:
    """Hourly series of one station keyed by hour start (UTC).

    raw:   raw value per hour (None when missing), flagged values included
    flags: quality_flag per hour for hours that have a record
    """
    raw: dict[datetime, float | None]
    flags: dict[datetime, str] = field(default_factory=dict)


@dataclass
class Classification:
    category: str
    reason: str
    details: dict

    @property
    def label(self) -> str:
        return CATEGORY_LABELS[self.category]


def _longest_identical_run(values: list[float | None]) -> int:
    best = run = 0
    prev = None
    for v in values:
        if v is not None and v == prev:
            run += 1
        else:
            run = 1 if v is not None else 0
        prev = v
        best = max(best, run)
    return best


def _usable(series: StationSeries, hour: datetime) -> float | None:
    v = series.raw.get(hour)
    return None if v is None or series.flags.get(hour) in ("out_of_range", "flatline") else v


def _neighbour_response(event: Event, series: StationSeries) -> dict | None:
    """How a neighbour moved during the event, relative to its own 72 h median before the event."""
    past = [_usable(series, event.start - HOUR * k) for k in range(1, BASELINE_HOURS + 1)]
    past = [v for v in past if v is not None]
    during = [_usable(series, h) for h in event.hours]
    during = [v for v in during if v is not None]
    if len(past) < 12 or not during:
        return None
    base = median(past)
    # value farthest from the baseline in the event's direction
    value = max(during) if event.direction == "up" else min(during)
    return {"baseline": base, "value": value, "change": value - base,
            "relative": (value - base) / base if base > 0 else None}


def classify(event: Event, station: StationSeries, neighbours: dict[int, StationSeries]) -> Classification:
    details: dict = {
        "peak_value": event.peak_value,
        "baseline_value": round(event.baseline, 1),
        "change": round(event.peak_value - event.baseline, 1),
        "duration_hours": event.duration_hours,
        "direction": event.direction,
    }

    # 1. data-quality evidence in the station itself
    context = [event.start + HOUR * k for k in range(-1, event.duration_hours + 1)]
    bad_flags = sorted({station.flags[h] for h in context if station.flags.get(h) in ("out_of_range", "flatline")})
    if "out_of_range" in bad_flags:
        return Classification("data", "flagged_values", {**details, "flags": bad_flags})
    run_window = [station.raw.get(event.start + HOUR * k)
                  for k in range(-FLATLINE_HOURS, event.duration_hours + FLATLINE_HOURS)]
    identical = _longest_identical_run(run_window)
    if identical >= FLATLINE_HOURS or "flatline" in bad_flags:
        return Classification("data", "flatline", {**details, "identical_hours": identical})

    # 2. neighbours
    responses = {}
    for nid, series in neighbours.items():
        r = _neighbour_response(event, series)
        if r is not None:
            responses[nid] = r
    details["neighbour_count"] = len(responses)
    if not responses:
        return Classification("needs_review", "no_neighbour", details)

    # 3. a neighbour confirms
    st_rel = (event.peak_value - event.baseline) / event.baseline if event.baseline > 0 else None
    confirming = []
    for nid, r in responses.items():
        same_sign = (r["change"] > 0) == (event.direction == "up")
        big_enough = abs(r["change"]) >= NEIGHBOUR_MIN_ABS
        rel_ok = (st_rel is None or r["relative"] is None
                  or abs(r["relative"]) >= NEIGHBOUR_CONFIRM_SHARE * abs(st_rel))
        if same_sign and big_enough and rel_ok:
            confirming.append(nid)
    details["neighbours"] = {str(nid): {k: round(v, 2) if isinstance(v, float) else v for k, v in r.items()}
                             for nid, r in responses.items()}
    if confirming:
        return Classification("environment", "neighbour_confirms",
                              {**details, "confirming_neighbours": [str(n) for n in confirming]})

    # 4. neighbours flat: isolated spike or jump after a signal gap -> possible measurement error
    gap = 0
    while station.raw.get(event.start - HOUR * (gap + 1)) is None and gap < 24:
        gap += 1
    details["gap_before_hours"] = gap
    if gap >= SIGNAL_GAP_HOURS:
        return Classification("data", "after_signal_gap", details)
    if event.duration_hours == 1:
        nxt = station.raw.get(event.end + HOUR)
        jump = event.peak_value - event.baseline
        if nxt is not None and abs(nxt - event.baseline) <= abs(jump) * SPIKE_RETURN_SHARE:
            return Classification("data", "isolated_spike", {**details, "next_value": nxt})

    # 5. sustained change that neighbours do not show
    return Classification("needs_review", "neighbours_disagree", details)


def describe(event: Event, classification: Classification) -> str:
    """One Vietnamese sentence for anomalies.description. Numbers only from the event; no cause is claimed."""
    verb = "tăng bất thường lên" if event.direction == "up" else "giảm bất thường xuống"
    hours = event.duration_hours
    span = "trong 1 giờ" if hours == 1 else f"kéo dài {hours} giờ"
    return (f"PM2.5 {verb} {fmt_number(event.peak_value)} µg/m³ ({span}), so với trung vị 72 giờ trước là "
            f"{fmt_number(event.baseline)} µg/m³. Phân loại: {classification.label.lower()}.")


def fmt_number(v: float) -> str:
    """Vietnamese number: 48.25 -> '48,3', 42.0 -> '42'."""
    r = round(v, 1)
    return str(int(r)) if r == int(r) else f"{r:.1f}".replace(".", ",")
