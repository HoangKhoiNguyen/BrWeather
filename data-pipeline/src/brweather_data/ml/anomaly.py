"""Statistical anomaly detection (F04). Only looks at the past, so it can run live.

Flags an hour when it is far from the median of the previous `window` hours,
measured in median absolute deviations (robust z-score).
"""
from statistics import median

WINDOW = 72
THRESHOLD = 4.0


def robust_z_scores(values: list[float | None], window: int = WINDOW) -> list[float | None]:
    scores: list[float | None] = []
    for i, v in enumerate(values):
        past = [x for x in values[max(0, i - window):i] if x is not None]
        if v is None or len(past) < window // 2:
            scores.append(None)
            continue
        m = median(past)
        mad = median(abs(x - m) for x in past) or 1.0
        scores.append((v - m) / (1.4826 * mad))
    return scores


def flag_spikes(values: list[float | None], threshold: float = THRESHOLD) -> list[int]:
    """Indexes of hours whose robust z-score exceeds the threshold (either direction)."""
    return [i for i, z in enumerate(robust_z_scores(values)) if z is not None and abs(z) > threshold]
