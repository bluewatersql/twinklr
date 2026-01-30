"""Curve sampling infrastructure.

This module provides functions for sampling curves at uniform intervals
and for linear interpolation between curve points.
"""

from twinklr.core.curves.models import CurvePoint


def sample_uniform_grid(n: int) -> list[float]:
    """Generate N evenly-spaced samples in [0, 1).

    Returns N samples: [0.0, 1/N, 2/N, ..., (N-1)/N]

    Args:
        n: Number of samples to generate. Must be >= 2.

    Returns:
        List of N evenly-spaced float values in [0, 1).

    Raises:
        ValueError: If n < 2.

    Example:
        >>> sample_uniform_grid(4)
        [0.0, 0.25, 0.5, 0.75]
    """
    if n < 2:
        raise ValueError("n must be >= 2")
    return [i / n for i in range(n)]


def interpolate_linear(points: list[CurvePoint], t: float) -> float:
    """Linearly interpolate value at time t.

    Given a list of curve points with non-decreasing t values,
    find the value at the specified time using linear interpolation.

    If t is before the first point, returns the first point's value.
    If t is after the last point, returns the last point's value.

    Args:
        points: List of CurvePoints with non-decreasing t values.
        t: Time value in [0, 1] at which to interpolate.

    Returns:
        Interpolated value at time t.

    Raises:
        ValueError: If points is empty or t is outside [0, 1].

    Example:
        >>> points = [CurvePoint(t=0.0, v=0.0), CurvePoint(t=1.0, v=1.0)]
        >>> interpolate_linear(points, 0.5)
        0.5
    """
    if not points:
        raise ValueError("points cannot be empty")
    if not (0.0 <= t <= 1.0):
        raise ValueError(f"t must be in [0, 1], got {t}")

    # Edge cases: clamp to boundaries
    if t <= points[0].t:
        return points[0].v
    if t >= points[-1].t:
        return points[-1].v

    # Find bracket containing t
    for i in range(len(points) - 1):
        if points[i].t <= t <= points[i + 1].t:
            t0, v0 = points[i].t, points[i].v
            t1, v1 = points[i + 1].t, points[i + 1].v
            if t1 > t0:
                alpha = (t - t0) / (t1 - t0)
                return v0 + alpha * (v1 - v0)
            else:
                # Degenerate case: same t values
                return v0

    # Should not reach here if points are monotonic
    return points[-1].v
