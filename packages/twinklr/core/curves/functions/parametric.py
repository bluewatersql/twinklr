"""Parametric curve generators."""

import math

import bezier
import numpy as np

from twinklr.core.curves.defaults import DEFAULT_CURVE_INTENSITY_PARAMS
from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.sampling import sample_uniform_grid


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

    nodes = np.asfortranarray(
        [
            [0.0, 0.25, 0.75, 1.0],
            [0.0, p1, p2, 1.0],
        ]
    )
    curve = bezier.Curve(nodes, degree=3)

    t_grid = sample_uniform_grid(n_samples)
    evaluated = curve.evaluate_multi(np.array(t_grid))
    values = evaluated[1, :]

    return [CurvePoint(t=t, v=float(v)) for t, v in zip(t_grid, values, strict=False)]


def generate_lissajous(
    n_samples: int,
    b: int = 2,
    delta: float = math.pi / 2,
    amplitude: float = DEFAULT_CURVE_INTENSITY_PARAMS["amplitude"],
    frequency: float = DEFAULT_CURVE_INTENSITY_PARAMS["frequency"],
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
