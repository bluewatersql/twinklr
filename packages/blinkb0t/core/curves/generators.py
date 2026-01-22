"""Standard curve generators.

This module provides functions for generating common curve shapes
as uniformly-sampled points. All generators produce points in [0, 1].
"""

import math

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import sample_uniform_grid
from blinkb0t.core.curves.semantics import center_curve, ensure_loop_ready


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


def generate_ease_in_sine(n_samples: int) -> list[CurvePoint]:
    """Generate a sine ease-in curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=1 - math.cos((t * math.pi) / 2)) for t in t_grid]


def generate_ease_out_sine(n_samples: int) -> list[CurvePoint]:
    """Generate a sine ease-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=math.sin((t * math.pi) / 2)) for t in t_grid]


def generate_ease_in_out_sine(n_samples: int) -> list[CurvePoint]:
    """Generate a sine ease-in-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=-(math.cos(math.pi * t) - 1) / 2) for t in t_grid]


def generate_ease_in_quad(n_samples: int) -> list[CurvePoint]:
    """Generate a quadratic ease-in curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=t * t) for t in t_grid]


def generate_ease_out_quad(n_samples: int) -> list[CurvePoint]:
    """Generate a quadratic ease-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=1 - (1 - t) * (1 - t)) for t in t_grid]


def generate_ease_in_out_quad(n_samples: int) -> list[CurvePoint]:
    """Generate a quadratic ease-in-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []
    for t in t_grid:
        if t < 0.5:
            v = 2 * t * t
        else:
            v = 1 - math.pow(-2 * t + 2, 2) / 2
        points.append(CurvePoint(t=t, v=v))
    return points


def generate_ease_in_cubic(n_samples: int) -> list[CurvePoint]:
    """Generate a cubic ease-in curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=t * t * t) for t in t_grid]


def generate_ease_out_cubic(n_samples: int) -> list[CurvePoint]:
    """Generate a cubic ease-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=1 - math.pow(1 - t, 3)) for t in t_grid]


def generate_ease_in_out_cubic(n_samples: int) -> list[CurvePoint]:
    """Generate a cubic ease-in-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []
    for t in t_grid:
        if t < 0.5:
            v = 4 * t * t * t
        else:
            v = 1 - math.pow(-2 * t + 2, 3) / 2
        points.append(CurvePoint(t=t, v=v))
    return points


def generate_ease_in_expo(n_samples: int) -> list[CurvePoint]:
    """Generate an exponential ease-in curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []
    for t in t_grid:
        v = 0.0 if t == 0 else math.pow(2, 10 * t - 10)
        points.append(CurvePoint(t=t, v=v))
    return points


def generate_ease_out_expo(n_samples: int) -> list[CurvePoint]:
    """Generate an exponential ease-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []
    for t in t_grid:
        v = 1.0 if t >= 1.0 else 1 - math.pow(2, -10 * t)
        points.append(CurvePoint(t=t, v=v))
    return points


def generate_ease_in_out_expo(n_samples: int) -> list[CurvePoint]:
    """Generate an exponential ease-in-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []
    for t in t_grid:
        if t == 0:
            v = 0.0
        elif t == 1:
            v = 1.0
        elif t < 0.5:
            v = math.pow(2, 20 * t - 10) / 2
        else:
            v = (2 - math.pow(2, -20 * t + 10)) / 2
        points.append(CurvePoint(t=t, v=v))
    return points


def generate_ease_in_back(n_samples: int, overshoot: float = 1.70158) -> list[CurvePoint]:
    """Generate a back ease-in curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    c3 = overshoot + 1
    return [CurvePoint(t=t, v=c3 * t * t * t - overshoot * t * t) for t in t_grid]


def generate_ease_out_back(n_samples: int, overshoot: float = 1.70158) -> list[CurvePoint]:
    """Generate a back ease-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    c3 = overshoot + 1
    points: list[CurvePoint] = []
    for t in t_grid:
        t1 = t - 1
        v = 1 + c3 * t1 * t1 * t1 + overshoot * t1 * t1
        points.append(CurvePoint(t=t, v=v))
    return points


def generate_ease_in_out_back(
    n_samples: int, overshoot: float = 1.70158
) -> list[CurvePoint]:
    """Generate a back ease-in-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    c2 = overshoot * 1.525
    points: list[CurvePoint] = []
    for t in t_grid:
        if t < 0.5:
            v = (math.pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2
        else:
            v = (math.pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2
        points.append(CurvePoint(t=t, v=v))
    return points


def _bounce_out_value(t: float) -> float:
    n1 = 7.5625
    d1 = 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def generate_bounce_out(n_samples: int) -> list[CurvePoint]:
    """Generate a bounce-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=_bounce_out_value(t)) for t in t_grid]


def generate_bounce_in(n_samples: int) -> list[CurvePoint]:
    """Generate a bounce-in curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=1 - _bounce_out_value(1 - t)) for t in t_grid]


def _elastic_out_value(t: float) -> float:
    c4 = (2 * math.pi) / 3
    if t == 0 or t == 1:
        return t
    return math.pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def generate_elastic_out(n_samples: int) -> list[CurvePoint]:
    """Generate an elastic-out curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=_elastic_out_value(t)) for t in t_grid]


def generate_elastic_in(n_samples: int) -> list[CurvePoint]:
    """Generate an elastic-in curve."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=1 - _elastic_out_value(1 - t)) for t in t_grid]


def generate_perlin_noise(n_samples: int) -> list[CurvePoint]:
    """Generate a Perlin-like noise curve using multi-octave sine waves."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    values = []
    for t in t_grid:
        value = (
            math.sin(2 * math.pi * t) * 0.5
            + math.sin(4 * math.pi * t) * 0.25
            + math.sin(8 * math.pi * t) * 0.125
            + 0.5
        )
        values.append(value)

    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        normalized = [0.5 for _ in values]
    else:
        scale = max_val - min_val
        normalized = [(v - min_val) / scale for v in values]

    return [CurvePoint(t=t, v=v) for t, v in zip(t_grid, normalized)]


def generate_simplex_noise(n_samples: int) -> list[CurvePoint]:
    """Generate a simplex-like noise curve using offset sine blends."""
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    values = []
    for t in t_grid:
        value = (
            math.sin(2 * math.pi * t + 0.3) * 0.45
            + math.sin(6 * math.pi * t + 1.1) * 0.2
            + math.sin(10 * math.pi * t + 2.2) * 0.15
            + 0.5
        )
        values.append(value)

    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        normalized = [0.5 for _ in values]
    else:
        scale = max_val - min_val
        normalized = [(v - min_val) / scale for v in values]

    return [CurvePoint(t=t, v=v) for t, v in zip(t_grid, normalized)]


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

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []
    for t in t_grid:
        v = (
            3 * (1 - t) * (1 - t) * t * p1
            + 3 * (1 - t) * t * t * p2
            + t * t * t
        )
        points.append(CurvePoint(t=t, v=v))
    return points


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


def _movement_post_process(
    points: list[CurvePoint],
    *,
    loop_mode: str = "append",
) -> list[CurvePoint]:
    """Center and enforce loop readiness for movement curves."""
    centered = center_curve(points)
    return ensure_loop_ready(centered, mode=loop_mode)


def generate_movement_linear(
    n_samples: int,
    ascending: bool = True,
    *,
    loop_mode: str = "append",
) -> list[CurvePoint]:
    """Generate a loop-ready, offset-centered linear curve for movement."""
    return _movement_post_process(
        generate_linear(n_samples=n_samples, ascending=ascending),
        loop_mode=loop_mode,
    )


def generate_movement_hold(
    n_samples: int,
    value: float = 1.0,
    *,
    loop_mode: str = "append",
) -> list[CurvePoint]:
    """Generate a loop-ready, offset-centered hold curve for movement."""
    return _movement_post_process(
        generate_hold(n_samples=n_samples, value=value),
        loop_mode=loop_mode,
    )


def generate_movement_sine(
    n_samples: int,
    cycles: float = 1.0,
    phase: float = 0.0,
    *,
    loop_mode: str = "append",
) -> list[CurvePoint]:
    """Generate a loop-ready, offset-centered sine curve for movement."""
    return _movement_post_process(
        generate_sine(n_samples=n_samples, cycles=cycles, phase=phase),
        loop_mode=loop_mode,
    )


def generate_movement_triangle(
    n_samples: int,
    cycles: float = 1.0,
    *,
    loop_mode: str = "append",
) -> list[CurvePoint]:
    """Generate a loop-ready, offset-centered triangle curve for movement."""
    return _movement_post_process(
        generate_triangle(n_samples=n_samples, cycles=cycles),
        loop_mode=loop_mode,
    )


def generate_movement_pulse(
    n_samples: int,
    cycles: float = 1.0,
    duty_cycle: float = 0.5,
    high: float = 1.0,
    low: float = 0.0,
    *,
    loop_mode: str = "append",
) -> list[CurvePoint]:
    """Generate a loop-ready, offset-centered pulse curve for movement."""
    return _movement_post_process(
        generate_pulse(
            n_samples=n_samples,
            cycles=cycles,
            duty_cycle=duty_cycle,
            high=high,
            low=low,
        ),
        loop_mode=loop_mode,
    )
