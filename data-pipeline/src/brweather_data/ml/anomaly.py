"""Statistical anomaly detection (F04, US5.1). Only looks at the past, so it can run live.

Flags an hour when it is far from the median of the previous `window` hours, measured in median
absolute deviations (robust z-score). Consecutive flagged hours in the same direction form one event.

Parameters for the live job (T5.1-2, see docs/anomaly-parameters.md):
  WINDOW = 72 h, MIN_HISTORY = 36 valid hours in that window,
  LIVE_THRESHOLD = 4.3 (|z|; ≈ 0.99 quantile on the Dragon train split, reports/pm25_anomaly_detection_evaluation.md)
  MIN_ABS_DEVIATION = 15 µg/m³ (in clean air the MAD is tiny and 5 → 12 µg/m³ would otherwise be "anomalous")
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median

WINDOW = 72
THRESHOLD = 4.0            # original research default, kept for flag_spikes()
MIN_HISTORY = WINDOW // 2
LIVE_THRESHOLD = 4.3
MIN_ABS_DEVIATION = 15.0   # µg/m³
MAX_GAP_HOURS = 1          # flagged hours separated by at most this many unflagged hours stay one event
DETECTOR = "robust_z_v1"


def past_stats(values: list[float | None], i: int, window: int = WINDOW,
               min_history: int = MIN_HISTORY) -> tuple[float, float] | None:
    """(median, MAD) of the valid values in the `window` hours before index i, or None if too few."""
    past = [x for x in values[max(0, i - window):i] if x is not None]
    if len(past) < min_history:
        return None
    m = median(past)
    mad = median(abs(x - m) for x in past) or 1.0
    return m, mad


def robust_z_scores(values: list[float | None], window: int = WINDOW) -> list[float | None]:
    scores: list[float | None] = []
    for i, v in enumerate(values):
        stats = past_stats(values, i, window, window // 2)
        if v is None or stats is None:
            scores.append(None)
            continue
        m, mad = stats
        scores.append((v - m) / (1.4826 * mad))
    return scores


def flag_spikes(values: list[float | None], threshold: float = THRESHOLD) -> list[int]:
    """Indexes of hours whose robust z-score exceeds the threshold (either direction)."""
    return [i for i, z in enumerate(robust_z_scores(values)) if z is not None and abs(z) > threshold]


@dataclass
class HourFlag:
    index: int
    z: float
    value: float
    baseline: float


@dataclass
class Event:
    """One anomaly: consecutive flagged hours in the same direction. Times are hour starts (UTC)."""
    start: datetime
    end: datetime                    # last flagged hour (inclusive)
    direction: str                   # 'up' | 'down'
    peak_time: datetime
    peak_value: float
    baseline: float                  # median of the 72 h before the peak hour
    score: float                     # robust z at the peak
    hours: list[datetime] = field(default_factory=list)

    @property
    def duration_hours(self) -> int:
        return int((self.end - self.start).total_seconds() // 3600) + 1


def flag_hours(values: list[float | None], first_index: int = 0, threshold: float = LIVE_THRESHOLD,
               min_abs: float = MIN_ABS_DEVIATION) -> list[HourFlag]:
    """Flag hours from `first_index` on whose robust z is beyond the threshold AND whose absolute
    deviation from the past median is at least `min_abs` µg/m³. Each hour only uses earlier hours."""
    out = []
    for i in range(first_index, len(values)):
        v = values[i]
        stats = past_stats(values, i)
        if v is None or stats is None:
            continue
        m, mad = stats
        z = (v - m) / (1.4826 * mad)
        if abs(z) > threshold and abs(v - m) >= min_abs:
            out.append(HourFlag(i, z, v, m))
    return out


def detect_events(times: list[datetime], values: list[float | None], first_index: int = 0,
                  threshold: float = LIVE_THRESHOLD, min_abs: float = MIN_ABS_DEVIATION) -> list[Event]:
    """Group flagged hours into events. `times` are consecutive hour starts matching `values`."""
    events: list[Event] = []
    current: list[HourFlag] = []

    def close() -> None:
        if not current:
            return
        peak = max(current, key=lambda f: abs(f.z))
        events.append(Event(
            start=times[current[0].index], end=times[current[-1].index],
            direction="up" if peak.z > 0 else "down",
            peak_time=times[peak.index], peak_value=peak.value, baseline=peak.baseline,
            score=round(peak.z, 2), hours=[times[f.index] for f in current],
        ))

    for flag in flag_hours(values, first_index, threshold, min_abs):
        same_dir = current and (flag.z > 0) == (current[-1].z > 0)
        if current and same_dir and flag.index - current[-1].index <= MAX_GAP_HOURS + 1:
            current.append(flag)
        else:
            close()
            current = [flag]
    close()
    return events


def hour_range(start: datetime, hours: int) -> list[datetime]:
    return [start + timedelta(hours=h) for h in range(hours)]
