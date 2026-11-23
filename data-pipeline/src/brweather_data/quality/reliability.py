"""Data quality checks and the High/Medium/Low reliability score (F08, US4.1).

Four checks (T4.1-1, T4.1-2):
  out_of_range         latest value < 0 or > PM25_MAX_PLAUSIBLE µg/m³
  flatline             the last FLATLINE_HOURS consecutive hourly values are identical (stuck sensor)
  stale                the latest reading is older than STALE_AFTER
  neighbour_deviation  the latest value is far from the local median (this station + stations within
                       NEIGHBOUR_RADIUS_KM with a recent reading); only applied when such stations exist.
                       Including the station itself keeps one outlier neighbour from condemning the others.

Level: no failed check -> high; only one of (stale, neighbour_deviation) -> medium; anything else -> low.
No reading for NO_DATA_AFTER -> low.

Thresholds are starting values; tune them after one week of real data (see T3.1-2 for the same caveat).
Reason codes are turned into plain Vietnamese sentences by the product (T4.1-4); `details` carries the
numbers behind each code so explanations never invent figures (US6.1).
"""
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

PM25_MAX_PLAUSIBLE = 1000.0  # µg/m³
FLATLINE_HOURS = 6
STALE_AFTER = timedelta(hours=3)
NO_DATA_AFTER = timedelta(hours=24)
NEIGHBOUR_RADIUS_KM = 10.0
NEIGHBOUR_MAX_TIME_GAP = timedelta(hours=2)  # neighbour reading must be this close in time
NEIGHBOUR_RATIO = 0.5       # deviation from the neighbour median, as a share of that median ...
NEIGHBOUR_MIN_ABS = 15.0    # ... and at least this many µg/m³ (avoids flagging 8 vs 5 in clean air)

REASONS = ("out_of_range", "flatline", "stale", "neighbour_deviation")


def _require_aware(t: datetime, name: str) -> None:
    if t.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware; refusing to guess the timezone")


def range_flag(value: float | None) -> str:
    if value is None:
        return "ok"  # missing is stored as NULL, not flagged
    if math.isnan(value) or value < 0 or value > PM25_MAX_PLAUSIBLE:
        return "out_of_range"
    return "ok"


def flatline_length(values: Sequence[float | None]) -> int:
    """How many consecutive hours at the end of the series have exactly the same value (0 if last is missing).

    `values` is an hourly series with None for missing hours, so a gap breaks the run.
    """
    if not values or values[-1] is None:
        return 0
    last, n = values[-1], 0
    for v in reversed(values):
        if v is None or v != last:
            break
        n += 1
    return n


def is_flatline(values: Sequence[float | None], hours: int = FLATLINE_HOURS) -> bool:
    """True when the last `hours` readings are identical (a stuck sensor)."""
    return flatline_length(values) >= hours


def is_stale(last_measured: datetime | None, now: datetime, stale_after: timedelta = STALE_AFTER) -> bool:
    if last_measured is None:
        return True
    _require_aware(last_measured, "last_measured")
    _require_aware(now, "now")
    return now - last_measured > stale_after


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Reading:
    """Latest usable reading of one station."""
    station_id: int
    lat: float
    lon: float
    value: float | None
    measured_at: datetime | None


def neighbour_values(
    target: Reading,
    others: Sequence[Reading],
    radius_km: float = NEIGHBOUR_RADIUS_KM,
    max_time_gap: timedelta = NEIGHBOUR_MAX_TIME_GAP,
) -> list[float]:
    """Values of other stations within radius_km whose reading is close in time to the target's (T4.1-2)."""
    if target.measured_at is None:
        return []
    out = []
    for o in others:
        if o.station_id == target.station_id or o.value is None or o.measured_at is None:
            continue
        if haversine_km(target.lat, target.lon, o.lat, o.lon) > radius_km:
            continue
        if abs(o.measured_at - target.measured_at) > max_time_gap:
            continue
        out.append(o.value)
    return out


def median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def local_median(value: float, neighbour_values: Sequence[float]) -> float:
    return median([value, *neighbour_values])


def deviates_from_neighbours(value: float | None, neighbour_values: Sequence[float]) -> bool | None:
    """None when there is no neighbour to compare with (the check is not applied)."""
    if value is None or not neighbour_values:
        return None
    m = local_median(value, neighbour_values)
    if m <= 0:
        return None
    diff = abs(value - m)
    return diff / m > NEIGHBOUR_RATIO and diff > NEIGHBOUR_MIN_ABS


def score(
    values: Sequence[float | None],
    last_measured: datetime | None,
    now: datetime,
    neighbour_values: Sequence[float],
) -> tuple[str, list[str]]:
    """Return (level, reasons). `values` is the hourly series (oldest first, None for missing hours)."""
    level, reasons, _ = assess(values, last_measured, now, neighbour_values)
    return level, reasons


def assess(
    values: Sequence[float | None],
    last_measured: datetime | None,
    now: datetime,
    neighbour_values: Sequence[float],
    latest_value: float | None = None,
) -> tuple[str, list[str], dict]:
    """Like score(), plus the numbers behind the result for reliability_scores.details.

    latest_value: the latest raw value (defaults to the last non-missing value of `values`).
    """
    if latest_value is None:
        latest_value = next((v for v in reversed(values) if v is not None), None)

    reasons: list[str] = []
    if range_flag(latest_value) != "ok":
        reasons.append("out_of_range")
    flat = flatline_length(values)
    if flat >= FLATLINE_HOURS:
        reasons.append("flatline")
    stale = is_stale(last_measured, now)
    if stale:
        reasons.append("stale")
    deviates = deviates_from_neighbours(latest_value, neighbour_values)
    if deviates:
        reasons.append("neighbour_deviation")

    hours_since = None if last_measured is None else round((now - last_measured).total_seconds() / 3600, 1)
    details = {
        "latest_value": latest_value,
        "last_measured": last_measured.isoformat() if last_measured else None,
        "hours_since_last": hours_since,
        "flatline_hours": flat,
        "neighbour_count": len(neighbour_values),
        "local_median": local_median(latest_value, neighbour_values)
        if neighbour_values and latest_value is not None else None,
        "neighbour_check_applied": deviates is not None,
    }

    no_data = last_measured is None or now - last_measured > NO_DATA_AFTER
    if not reasons:
        level = "high"
    elif not no_data and len(reasons) == 1 and reasons[0] in ("stale", "neighbour_deviation"):
        level = "medium"
    else:
        level = "low"
    return level, reasons, details
