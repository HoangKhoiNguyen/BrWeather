"""Data quality checks and the High/Medium/Low reliability score (F08).

Thresholds are starting values; tune them after measuring the real update frequency in week 1.
"""
from datetime import datetime, timedelta

PM25_MAX_PLAUSIBLE = 1000.0  # µg/m³
FLATLINE_HOURS = 6
STALE_AFTER = timedelta(hours=3)
NEIGHBOUR_RATIO = 0.5  # deviation from the neighbour median, as a share of that median


def range_flag(value: float | None) -> str:
    if value is None:
        return "ok"  # missing is stored as NULL, not flagged
    if value < 0 or value > PM25_MAX_PLAUSIBLE:
        return "out_of_range"
    return "ok"


def is_flatline(values: list[float | None], hours: int = FLATLINE_HOURS) -> bool:
    """True when the last `hours` readings are identical (a stuck sensor)."""
    recent = [v for v in values[-hours:] if v is not None]
    return len(recent) == hours and len(set(recent)) == 1


def is_stale(last_measured: datetime | None, now: datetime, stale_after: timedelta = STALE_AFTER) -> bool:
    return last_measured is None or now - last_measured > stale_after


def deviates_from_neighbours(value: float | None, neighbour_values: list[float]) -> bool | None:
    """None when there is no neighbour to compare with (the UI then says 'needs review')."""
    if value is None or not neighbour_values:
        return None
    ordered = sorted(neighbour_values)
    median = ordered[len(ordered) // 2]
    if median <= 0:
        return None
    return abs(value - median) / median > NEIGHBOUR_RATIO


def score(
    values: list[float | None],
    last_measured: datetime | None,
    now: datetime,
    neighbour_values: list[float],
) -> tuple[str, list[str]]:
    """Return (level, reasons). Each failed check lowers the level by one step."""
    reasons: list[str] = []
    latest = values[-1] if values else None
    if range_flag(latest) != "ok":
        reasons.append("out_of_range")
    if is_flatline(values):
        reasons.append("flatline")
    if is_stale(last_measured, now):
        reasons.append("stale")
    if deviates_from_neighbours(latest, neighbour_values):
        reasons.append("neighbour_deviation")

    if not reasons:
        return "high", reasons
    if len(reasons) == 1 and reasons[0] in ("stale", "neighbour_deviation"):
        return "medium", reasons
    return "low", reasons
