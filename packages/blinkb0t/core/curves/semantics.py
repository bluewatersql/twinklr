"""Curve semantics helpers.

Provides helpers for offset-centered movement curves and loop readiness.
"""

from __future__ import annotations

from enum import Enum

from blinkb0t.core.curves.models import CurvePoint


class CurveKind(str, Enum):
    """Semantic kind for normalized curves."""

    MOVEMENT_OFFSET = "movement_offset"
    DIMMER_ABSOLUTE = "dimmer_absolute"


def center_curve(points: list[CurvePoint]) -> list[CurvePoint]:
    """Center curve values around 0.5 while preserving shape.

    Normalizes values to [0, 1] based on current min/max, which
    guarantees the midpoint maps to 0.5. Constant curves map to 0.5.
    """
    if not points:
        raise ValueError("points cannot be empty")

    values = [p.v for p in points]
    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return [CurvePoint(t=p.t, v=0.5) for p in points]

    value_range = max_val - min_val
    return [CurvePoint(t=p.t, v=(p.v - min_val) / value_range) for p in points]


def ensure_loop_ready(
    points: list[CurvePoint],
    *,
    mode: str = "append",
    tolerance: float = 1e-6,
) -> list[CurvePoint]:
    """Ensure curve endpoints align for looping.

    Args:
        points: Input curve points with non-decreasing t values.
        mode: "append" adds an endpoint at t=1.0 when needed.
            "adjust_last" modifies the last point's value to match the first.
        tolerance: Allowed difference between start/end values.

    Returns:
        New list of CurvePoints with loop-ready endpoints.
    """
    if not points:
        raise ValueError("points cannot be empty")

    start = points[0]
    end = points[-1]
    aligned = abs(start.v - end.v) <= tolerance

    if aligned:
        return list(points)

    if mode not in {"append", "adjust_last"}:
        raise ValueError("mode must be 'append' or 'adjust_last'")

    if mode == "adjust_last":
        return [*points[:-1], CurvePoint(t=end.t, v=start.v)]

    # mode == "append"
    if end.t >= 1.0 - tolerance:
        return [*points[:-1], CurvePoint(t=end.t, v=start.v)]

    return [*points, CurvePoint(t=1.0, v=start.v)]
