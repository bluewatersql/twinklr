"""Curve semantics helpers.

Provides helpers for offset-centered movement curves and loop readiness.
"""

from __future__ import annotations

from enum import StrEnum

from twinklr.core.curves.models import CurvePoint


class CurveKind(StrEnum):
    """Semantic kind for normalized curves."""

    MOVEMENT_OFFSET = "movement_offset"
    DIMMER_ABSOLUTE = "dimmer_absolute"


def center_curve(points: list[CurvePoint]) -> list[CurvePoint]:
    """Recenter curve values on 0.5 without changing how far they travel.

    Translates the curve so its midpoint ``(min + max) / 2`` sits at 0.5.
    Constant curves map to 0.5.

    This is a pure translation, deliberately *not* a rescale to full range
    (P4-M6). Rescaling made physical excursion a function of frequency: a
    window containing less than a full oscillation has a narrower observed
    min/max, and stretching that partial arc back to [0, 1] turned a *slower*
    movement into a *wider* one — inverting the SLOW/SMOOTH intent, since low
    intensities are paired with low frequencies. Translating preserves the
    generator's own amplitude envelope, so frequency sets the rate and
    amplitude sets the excursion envelope; realized excursion also depends on how much of the cycle the frequency completes within the segment.
    """
    if not points:
        raise ValueError("points cannot be empty")

    values = [p.v for p in points]
    shift = 0.5 - (min(values) + max(values)) / 2.0

    # Generators emit within [0, 1], so a midpoint-centered span cannot leave
    # [0, 1]; the clamp only absorbs float error at the boundaries.
    return [CurvePoint(t=p.t, v=min(1.0, max(0.0, p.v + shift))) for p in points]


def _continuation_value(points: list[CurvePoint], t: float) -> float:
    """Linearly extrapolate the curve's own motion out to `t`."""
    if len(points) < 2:
        return points[-1].v

    previous, last = points[-2], points[-1]
    span = last.t - previous.t
    if span <= 0.0:
        return last.v

    value = last.v + (last.v - previous.v) * (t - last.t) / span
    return min(1.0, max(0.0, value))


def ensure_loop_ready(
    points: list[CurvePoint],
    *,
    mode: str = "append",
    tolerance: float = 1e-6,
) -> list[CurvePoint]:
    """Ensure curve endpoints are well defined at t=1.0.

    Args:
        points: Input curve points with non-decreasing t values.
        mode: "append" adds an endpoint at t=1.0 carrying the *start* value.
            "adjust_last" rewrites the last point's value to match the first.
            "extend" adds an endpoint at t=1.0 that *continues* the motion
            instead of jumping back to the start value.
        tolerance: Allowed difference between start/end values.

    Returns:
        New list of CurvePoints with a defined endpoint.

    Note:
        Curves are sampled on ``[0, 1)`` (``sample_uniform_grid``), so the last
        sample sits at ``(n-1)/n`` and something has to define t=1.0. "append"
        answers with the start value, which is only correct when the window
        closes on a whole number of oscillations; for every other curve it
        synthesises a full-excursion snap back to the start inside the final
        ``1/n`` of the segment (P4-M5). "extend" keeps a point at t=1.0 — so
        phase-shifted chase curves still have a defined value across the whole
        domain — but gives it the value the motion was heading for.
    """
    if not points:
        raise ValueError("points cannot be empty")

    if mode not in {"append", "adjust_last", "extend"}:
        raise ValueError("mode must be 'append', 'adjust_last' or 'extend'")

    start = points[0]
    end = points[-1]

    if mode == "extend":
        if end.t >= 1.0 - tolerance:
            return list(points)
        return [*points, CurvePoint(t=1.0, v=_continuation_value(points, 1.0))]

    if abs(start.v - end.v) <= tolerance:
        return list(points)

    if mode == "adjust_last":
        return [*points[:-1], CurvePoint(t=end.t, v=start.v)]

    # mode == "append"
    if end.t >= 1.0 - tolerance:
        return [*points[:-1], CurvePoint(t=end.t, v=start.v)]

    return [*points, CurvePoint(t=1.0, v=start.v)]
