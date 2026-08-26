"""Parametric curve generators."""

import math
from typing import Any

from twinklr.core.curves.defaults import DEFAULT_CURVE_INTENSITY_PARAMS
from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.sampling import sample_uniform_grid


def _evaluate_bezier_ordinate(control_points: tuple[float, ...], t: float) -> float:
    """Evaluate one Bezier ordinate with the numerically stable de Casteljau algorithm."""
    if not control_points:
        raise ValueError("control_points cannot be empty")
    if not 0.0 <= t <= 1.0:
        raise ValueError("t must be in [0, 1]")
    if t == 0.0:
        return float(control_points[0])
    if t == 1.0:
        return float(control_points[-1])

    values = [float(value) for value in control_points]
    for width in range(len(values) - 1, 0, -1):
        for index in range(width):
            values[index] = (1.0 - t) * values[index] + t * values[index + 1]
    return values[0]


def generate_bezier(
    n_samples: int,
    p1: float = 0.1,
    p2: float = 0.9,
    **kwargs,  # Accept but ignore intensity params
) -> list[CurvePoint]:
    """Generate a cubic Bezier curve with fixed endpoints.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        p1: Control point 1 y-coordinate.
        p2: Control point 2 y-coordinate.
        **kwargs: Ignored parameters (for compatibility).

    Returns:
        List of CurvePoints forming a Bezier curve.
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    p1 = max(0.0, min(1.0, p1))
    p2 = max(0.0, min(1.0, p2))

    t_grid = sample_uniform_grid(n_samples)
    control_ordinates = (0.0, p1, p2, 1.0)
    values = [_evaluate_bezier_ordinate(control_ordinates, t) for t in t_grid]

    return [CurvePoint(t=t, v=float(v)) for t, v in zip(t_grid, values, strict=False)]


def generate_lissajous(
    n_samples: int,
    b: int = 2,
    delta: float = math.pi / 2,
    amplitude: float = DEFAULT_CURVE_INTENSITY_PARAMS["amplitude"],
    frequency: float = DEFAULT_CURVE_INTENSITY_PARAMS["frequency"],
    **kwargs: Any,
) -> list[CurvePoint]:
    """Generate a Lissajous curve with intensity support using the y-component.

    Lissajous curves create figure-8 and infinity symbol patterns through
    harmonic motion. Amplitude scales the curve height, frequency affects
    the timing.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        b: Frequency ratio for the y-component (must be > 0).
        delta: Phase offset in radians (default: π/2).
        amplitude: Amplitude scaling factor [0, 1] (default: 1.0 = full amplitude).
        frequency: Frequency multiplier applied to time (default: 1.0 = no change).
        **kwargs: Ignored parameters (for compatibility with movement handler).

    Returns:
        List of CurvePoints forming a Lissajous curve in normalized [0, 1] space.

    Raises:
        ValueError: If n_samples < 2 or b <= 0.
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    if b <= 0:
        raise ValueError("b must be > 0")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        # Apply frequency multiplier to time
        effective_t = t * frequency
        # Generate y-component with amplitude scaling
        v = (amplitude * math.sin(b * 2 * math.pi * effective_t + delta) + 1) / 2
        points.append(CurvePoint(t=t, v=v))

    return points
