"""Baselines for PM2.5 forecasting (F03). Any candidate model must beat the best of these.

`history` is an hourly series ordered oldest → newest, with None for missing hours.
"""


def persistence(history: list[float | None], horizon: int) -> list[float | None]:
    """Repeat the last known value for every hour ahead."""
    last = next((v for v in reversed(history) if v is not None), None)
    return [last] * horizon


def seasonal_naive(history: list[float | None], horizon: int, season: int = 24) -> list[float | None]:
    """Use the value at the same hour on the previous day."""
    if len(history) < season:
        return [None] * horizon
    return [history[len(history) - season + (h % season)] for h in range(horizon)]


def mae(actual: list[float | None], predicted: list[float | None]) -> float | None:
    """Mean absolute error over hours where both values exist."""
    pairs = [(a, p) for a, p in zip(actual, predicted) if a is not None and p is not None]
    if not pairs:
        return None
    return sum(abs(a - p) for a, p in pairs) / len(pairs)
