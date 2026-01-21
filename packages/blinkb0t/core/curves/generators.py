"""Standard curve generators.

This module provides functions for generating common curve shapes
as uniformly-sampled points. All generators produce points in [0, 1].
"""

import math

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import sample_uniform_grid


def generate_linear(
    n_samples: int,
    ascending: bool = True,
) -> list[CurvePoint]:
    """Generate a linear ramp curve.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        ascending: If True, ramp from 0→1. If False, ramp from 1→0.

    Returns:
        List of CurvePoints forming a linear ramp.

    Raises:
        ValueError: If n_samples < 2.

    Example:
        >>> result = generate_linear(4)
        >>> [p.v for p in result]  # Approximately
        [0.0, 0.333, 0.666, 1.0]
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for i, t in enumerate(t_grid):
        # Linear interpolation: v goes from 0 to 1 over n_samples
        v = i / (n_samples - 1) if n_samples > 1 else 0.0
        if not ascending:
            v = 1.0 - v
        points.append(CurvePoint(t=t, v=v))

    return points


def generate_hold(
    n_samples: int,
    value: float = 1.0,
) -> list[CurvePoint]:
    """Generate a constant (hold) curve.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        value: Constant value (clamped to [0, 1]).

    Returns:
        List of CurvePoints all with the same value.

    Raises:
        ValueError: If n_samples < 2.

    Example:
        >>> result = generate_hold(4, value=0.5)
        >>> [p.v for p in result]
        [0.5, 0.5, 0.5, 0.5]
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    # Clamp value to [0, 1]
    clamped_value = max(0.0, min(1.0, value))

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=clamped_value) for t in t_grid]


def generate_sine(
    n_samples: int,
    cycles: float = 1.0,
    phase: float = 0.0,
) -> list[CurvePoint]:
    """Generate a sine wave curve.

    The sine wave is normalized to [0, 1] where:
    - 0.5 is the midpoint
    - 1.0 is the peak
    - 0.0 is the trough

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Number of complete cycles in the output.
        phase: Phase offset in radians (default 0 = start at midpoint rising).

    Returns:
        List of CurvePoints forming a sine wave.

    Raises:
        ValueError: If n_samples < 2 or cycles <= 0.

    Example:
        >>> result = generate_sine(8, cycles=1.0)
        >>> result[0].v  # Starts at midpoint
        0.5
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    if cycles <= 0:
        raise ValueError("cycles must be > 0")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        # Sine normalized to [0, 1]
        angle = 2 * math.pi * cycles * t + phase
        v = 0.5 + 0.5 * math.sin(angle)
        points.append(CurvePoint(t=t, v=v))

    return points


def generate_triangle(
    n_samples: int,
    cycles: float = 1.0,
) -> list[CurvePoint]:
    """Generate a triangle wave curve.

    The triangle wave goes: 0 → 1 → 0 for one cycle.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Number of complete cycles in the output.

    Returns:
        List of CurvePoints forming a triangle wave.

    Raises:
        ValueError: If n_samples < 2 or cycles <= 0.

    Example:
        >>> result = generate_triangle(8, cycles=1.0)
        >>> result[0].v  # Starts at 0
        0.0
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    if cycles <= 0:
        raise ValueError("cycles must be > 0")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        # Position within cycle [0, 1)
        cycle_pos = (t * cycles) % 1.0

        # Triangle: rise for first half, fall for second half
        if cycle_pos < 0.5:
            v = cycle_pos * 2.0  # 0 → 1
        else:
            v = 2.0 - cycle_pos * 2.0  # 1 → 0

        points.append(CurvePoint(t=t, v=v))

    return points


def generate_pulse(
    n_samples: int,
    cycles: float = 1.0,
    duty_cycle: float = 0.5,
    high: float = 1.0,
    low: float = 0.0,
) -> list[CurvePoint]:
    """Generate a pulse (square) wave curve.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Number of complete cycles in the output.
        duty_cycle: Fraction of cycle that is high (0.0 to 1.0).
        high: Value during high portion (clamped to [0, 1]).
        low: Value during low portion (clamped to [0, 1]).

    Returns:
        List of CurvePoints forming a pulse wave.

    Raises:
        ValueError: If n_samples < 2 or cycles <= 0.

    Example:
        >>> result = generate_pulse(8, cycles=1.0, duty_cycle=0.5)
        >>> result[0].v  # First half is high
        1.0
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    if cycles <= 0:
        raise ValueError("cycles must be > 0")

    # Clamp values
    high = max(0.0, min(1.0, high))
    low = max(0.0, min(1.0, low))
    duty_cycle = max(0.0, min(1.0, duty_cycle))

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        # Position within cycle [0, 1)
        cycle_pos = (t * cycles) % 1.0

        # High if within duty cycle, low otherwise
        v = high if cycle_pos < duty_cycle else low
        points.append(CurvePoint(t=t, v=v))

    return points
