"""Simple forecasting using linear regression and moving averages.

Provides lightweight trend analysis utilities that operate on plain lists of
numeric values -- no database interaction required.
"""

from __future__ import annotations

import structlog
import numpy as np

log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Linear-regression forecast
# ---------------------------------------------------------------------------


async def forecast_trend(
    values: list[float],
    periods_ahead: int = 7,
) -> list[float]:
    """Forecast future values using simple linear regression (degree-1 polyfit).

    Args:
        values: Historical observations ordered from oldest to newest.
        periods_ahead: Number of future periods to predict.

    Returns:
        A list of ``periods_ahead`` predicted values.  If there are fewer
        than two data points the function returns the last observed value
        repeated ``periods_ahead`` times (flat extrapolation).
    """

    if len(values) < 2:
        fallback = values[-1] if values else 0.0
        log.warning("forecast_insufficient_data", n_values=len(values))
        return [fallback] * periods_ahead

    x = np.arange(len(values), dtype=np.float64)
    y = np.array(values, dtype=np.float64)

    # Degree-1 polynomial fit: y = slope * x + intercept
    coefficients: np.ndarray = np.polyfit(x, y, deg=1)
    poly = np.poly1d(coefficients)

    future_x = np.arange(len(values), len(values) + periods_ahead, dtype=np.float64)
    predictions: list[float] = [round(float(v), 4) for v in poly(future_x)]

    log.debug(
        "forecast_computed",
        n_input=len(values),
        periods_ahead=periods_ahead,
        slope=round(float(coefficients[0]), 6),
        intercept=round(float(coefficients[1]), 4),
    )

    return predictions


# ---------------------------------------------------------------------------
# Moving average
# ---------------------------------------------------------------------------


async def compute_moving_average(
    values: list[float],
    window: int = 7,
) -> list[float]:
    """Compute a simple moving average with the given window size.

    The first ``window - 1`` values use a growing window (i.e. the average of
    all available prior values) so the output length always equals the input
    length.

    Args:
        values: Ordered numeric observations.
        window: Window size for the moving average.

    Returns:
        A list of smoothed values with the same length as *values*.  An empty
        input returns an empty list.
    """

    if not values:
        return []

    if window < 1:
        log.warning("moving_average_invalid_window", window=window)
        window = 1

    arr = np.array(values, dtype=np.float64)
    n = len(arr)

    # Clamp window to data length
    effective_window = min(window, n)

    # Use cumulative sum for O(n) moving average
    cumsum = np.cumsum(arr)
    result = np.empty(n, dtype=np.float64)

    # Growing window for the initial elements
    for i in range(effective_window - 1):
        result[i] = cumsum[i] / (i + 1)

    # Full window from index (effective_window - 1) onward
    if effective_window > 1:
        result[effective_window - 1] = cumsum[effective_window - 1] / effective_window
        for i in range(effective_window, n):
            result[i] = (cumsum[i] - cumsum[i - effective_window]) / effective_window
    else:
        # window == 1: result is the values themselves
        result = arr.copy()

    smoothed: list[float] = [round(float(v), 4) for v in result]

    log.debug(
        "moving_average_computed",
        n_input=n,
        window=effective_window,
    )

    return smoothed


# ---------------------------------------------------------------------------
# Trend direction detection
# ---------------------------------------------------------------------------


async def detect_trend_direction(values: list[float]) -> str:
    """Determine whether a trend is ``"rising"``, ``"falling"``, or ``"stable"``.

    Uses the slope of a linear fit over the last 30% of the data (at least 2
    points).  A slope whose absolute value is less than 1% of the mean
    absolute value is considered stable.

    Args:
        values: Ordered numeric observations.

    Returns:
        One of ``"rising"``, ``"falling"``, or ``"stable"``.
    """

    if len(values) < 2:
        log.debug("trend_direction_insufficient_data", n_values=len(values))
        return "stable"

    # Use the last ~30% of values (minimum 2 points)
    tail_length = max(2, int(len(values) * 0.3))
    tail = values[-tail_length:]

    x = np.arange(len(tail), dtype=np.float64)
    y = np.array(tail, dtype=np.float64)

    coefficients: np.ndarray = np.polyfit(x, y, deg=1)
    slope = float(coefficients[0])

    # Compute mean absolute value for relative comparison
    mean_abs = float(np.mean(np.abs(y))) if np.any(y != 0) else 1.0
    relative_slope = abs(slope) / mean_abs if mean_abs > 0 else 0.0

    # Threshold: 1% of mean absolute value
    threshold = 0.01

    if relative_slope < threshold:
        direction = "stable"
    elif slope > 0:
        direction = "rising"
    else:
        direction = "falling"

    log.debug(
        "trend_direction_detected",
        direction=direction,
        slope=round(slope, 6),
        relative_slope=round(relative_slope, 6),
        tail_length=tail_length,
    )

    return direction
