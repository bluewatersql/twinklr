"""Motion curve generators."""

import math

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import sample_uniform_grid


def generate_anticipate(n_samples: int) -> list[CurvePoint]:
    """Generate an anticipate curve (pull back then accelerate forward)."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    pullback_phase = 0.3
    pullback_min = 0.1
    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []
    for t in t_grid:
        if t <= pullback_phase:
            v = pullback_min * math.sin((t / pullback_phase) * math.pi / 2)
        else:
            v = pullback_min + (1.0 - pullback_min) * (
                (t - pullback_phase) / (1 - pullback_phase)
            ) ** 2
        points.append(CurvePoint(t=t, v=v))
    return points


def generate_overshoot(n_samples: int) -> list[CurvePoint]:
    """Generate an overshoot curve that settles at 1.0."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []
    for t in t_grid:
        base = t * t * (3 - 2 * t)
        if 0.6 <= t <= 0.9:
            t_local = (t - 0.6) / 0.3
            bounce = 0.05 * (1.0 - base) * math.sin(t_local * math.pi * 3) * math.exp(
                -t_local * 3
            )
            v = base + bounce
        else:
            v = base
        points.append(CurvePoint(t=t, v=v))
    return points
