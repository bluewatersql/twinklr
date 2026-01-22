"""Parametric curve generators."""

import math

import bezier
import numpy as np

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import sample_uniform_grid


def generate_bezier(
    n_samples: int,
    p1: float = 0.1,
    p2: float = 0.9,
) -> list[CurvePoint]:
    """Generate a cubic Bezier curve with fixed endpoints."""
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

    return [CurvePoint(t=t, v=float(v)) for t, v in zip(t_grid, values)]


def generate_lissajous(
    n_samples: int,
    b: int = 2,
    delta: float = math.pi / 2,
) -> list[CurvePoint]:
    """Generate a Lissajous curve using the y-component."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    if b <= 0:
        raise ValueError("b must be > 0")

    t_grid = sample_uniform_grid(n_samples)
    return [
        CurvePoint(t=t, v=(math.sin(b * 2 * math.pi * t + delta) + 1) / 2)
        for t in t_grid
    ]
