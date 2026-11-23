"""Checks on Open-Meteo payloads before/after they are stored.

T1.2-1: the next 24 hours of a snapshot are complete, continuous, in order and in UTC.
T1.3-1: the daily block has 7 days with high/low, rain total, rain probability, weather code, sunrise/sunset.

Each check returns a CheckResult with machine-readable issue codes; the pipeline logs them as warnings
(a gap in the source's forecast is not a pipeline failure, but it must be visible).
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from brweather_data.connectors.open_meteo import DAILY_WEATHER, HOURLY_WEATHER


@dataclass
class CheckResult:
    ok: bool
    found: int                      # hours (or days) present in the window
    expected: int
    issues: list[str] = field(default_factory=list)


def _as_utc(naive_iso: str) -> datetime:
    """Open-Meteo returns naive ISO times when timezone=UTC."""
    t = datetime.fromisoformat(naive_iso)
    if t.tzinfo is not None:
        return t.astimezone(timezone.utc)
    return t.replace(tzinfo=timezone.utc)


def _floor_hour(t: datetime) -> datetime:
    if t.tzinfo is None:
        raise ValueError("start must be timezone-aware; refusing to guess the timezone")
    return t.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _timezone_issues(payload: dict) -> list[str]:
    tz = payload.get("timezone")
    offset = payload.get("utc_offset_seconds")
    if (tz is not None and tz not in ("UTC", "GMT")) or (offset not in (None, 0)):
        return [f"timezone_not_utc:{tz}:{offset}"]
    return []


def check_hourly_window(payload: dict, start: datetime, hours: int = 24) -> CheckResult:
    """Is there one row per hour for [start, start + hours), with every field the app needs?

    Issue codes:
      timezone_not_utc:<tz>:<offset>   the response is not in UTC
      missing_field:<name>             a requested hourly variable is absent from the response
      not_sorted / duplicate_time      the time axis is not strictly increasing
      missing_hour:<iso>               an hour of the window has no row
      all_null:<name>                  a variable is NULL for every hour of the window
    Individual NULL values are allowed (the API returns null, never 0).
    """
    first = _floor_hour(start)
    expected = [first + timedelta(hours=i) for i in range(hours)]
    issues = _timezone_issues(payload)

    block = payload.get("hourly") or {}
    issues += [f"missing_field:{name}" for name in HOURLY_WEATHER if name not in block]

    times = [_as_utc(t) for t in block.get("time") or []]
    if any(b < a for a, b in zip(times, times[1:])):
        issues.append("not_sorted")
    if len(set(times)) != len(times):
        issues.append("duplicate_time")

    index = {t: i for i, t in enumerate(times)}
    present = [t for t in expected if t in index]
    issues += [f"missing_hour:{t.isoformat()}" for t in expected if t not in index]

    for name in HOURLY_WEATHER:
        values = block.get(name)
        if values is None or not present:
            continue
        window = [values[index[t]] if index[t] < len(values) else None for t in present]
        if all(v is None for v in window):
            issues.append(f"all_null:{name}")

    return CheckResult(ok=not issues, found=len(present), expected=hours, issues=issues)


def check_daily(payload: dict, first_day: date | None = None, days: int = 7) -> CheckResult:
    """Are there `days` consecutive days (from first_day, default: the first day returned) with all fields?

    Issue codes: timezone_not_utc, missing_field:<name>, missing_day:<iso>, all_null:<name>,
    null_value:<name>:<day>, max_below_min:<day>.
    """
    issues = _timezone_issues(payload)
    block = payload.get("daily") or {}
    issues += [f"missing_field:{name}" for name in DAILY_WEATHER if name not in block]

    day_list = [date.fromisoformat(d) for d in block.get("time") or []]
    if first_day is None:
        first_day = day_list[0] if day_list else date.today()
    expected = [first_day + timedelta(days=i) for i in range(days)]
    index = {d: i for i, d in enumerate(day_list)}
    present = [d for d in expected if d in index]
    issues += [f"missing_day:{d.isoformat()}" for d in expected if d not in index]

    for name in DAILY_WEATHER:
        values = block.get(name)
        if values is None or not present:
            continue
        window = {d: (values[index[d]] if index[d] < len(values) else None) for d in present}
        if all(v is None for v in window.values()):
            issues.append(f"all_null:{name}")
        else:
            issues += [f"null_value:{name}:{d.isoformat()}" for d, v in window.items() if v is None]

    highs, lows = block.get("temperature_2m_max") or [], block.get("temperature_2m_min") or []
    for d in present:
        i = index[d]
        if i < len(highs) and i < len(lows) and highs[i] is not None and lows[i] is not None and highs[i] < lows[i]:
            issues.append(f"max_below_min:{d.isoformat()}")

    return CheckResult(ok=not issues, found=len(present), expected=days, issues=issues)
