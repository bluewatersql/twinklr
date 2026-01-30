"""Basic curve generators."""

import math

from twinklr.core.curves.defaults import DEFAULT_CURVE_INTENSITY_PARAMS
from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.sampling import sample_uniform_grid


def generate_linear(
    n_samples: int,
    ascending: bool = True,
    **kwargs,  # Accept but ignore intensity params
) -> list[CurvePoint]:
    """Generate a linear ramp curve.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        ascending: If True, ramp from 0→1. If False, ramp from 1→0.
        **kwargs: Ignored parameters (for compatibility).

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
        v = i / (n_samples - 1) if n_samples > 1 else 0.0
        if not ascending:
            v = 1.0 - v
        points.append(CurvePoint(t=t, v=v))

    return points


def generate_hold(
    n_samples: int,
    value: float = 1.0,
    **kwargs,  # Accept but ignore intensity params
) -> list[CurvePoint]:
    """Generate a constant (hold) curve.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        value: Constant value (clamped to [0, 1]).
        **kwargs: Ignored parameters (for compatibility).

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

    clamped_value = max(0.0, min(1.0, value))

    t_grid = sample_uniform_grid(n_samples)
    return [CurvePoint(t=t, v=clamped_value) for t in t_grid]


def generate_sine(
    n_samples: int,
    cycles: float = 1.0,
    phase: float = 0.0,
    amplitude: float = DEFAULT_CURVE_INTENSITY_PARAMS["amplitude"],
    frequency: float = DEFAULT_CURVE_INTENSITY_PARAMS["frequency"],
) -> list[CurvePoint]:
    """Generate a sine wave curve with intensity support.

    All timing is normalized to [0, 1] time domain. Amplitude scales the wave
    height around 0.5 center. Frequency multiplies the cycle count.

    The sine wave is normalized to [0, 1] where:
    - 0.5 is the midpoint
    - 1.0 is the peak
    - 0.0 is the trough

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Base number of complete cycles in the output.
        phase: Phase offset in radians (default 0 = start at midpoint rising).
        amplitude: Amplitude scaling factor [0, 1] (default: 1.0 = full amplitude).
        frequency: Frequency multiplier applied to cycles (default: 1.0 = no change).

    Returns:
        List of CurvePoints forming a sine wave in normalized [0, 1] space.

    Raises:
        ValueError: If n_samples < 2 or cycles <= 0.

    Example:
        >>> result = generate_sine(10, cycles=1.0, amplitude=0.5, frequency=2.0)
        >>> len(result)
        10
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    if cycles <= 0:
        raise ValueError("cycles must be > 0")

    # Apply frequency multiplier to cycles
    effective_cycles = cycles * frequency

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        angle = 2 * math.pi * effective_cycles * t + phase
        # Apply amplitude scaling: v = 0.5 + 0.5 * amplitude * sin(angle)
        v = 0.5 + 0.5 * amplitude * math.sin(angle)
        points.append(CurvePoint(t=t, v=v))

    return points


def generate_triangle(
    n_samples: int,
    cycles: float = 1.0,
    amplitude: float = DEFAULT_CURVE_INTENSITY_PARAMS["amplitude"],
    frequency: float = DEFAULT_CURVE_INTENSITY_PARAMS["frequency"],
    phase: float = 0.0,
) -> list[CurvePoint]:
    """Generate a triangle wave curve with intensity support.

    The triangle wave goes: 0 → 1 → 0 for one cycle.
    Amplitude scales the wave height around 0.5 center.
    Frequency multiplies the cycle count.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Base number of complete cycles in the output.
        amplitude: Amplitude scaling factor [0, 1] (default: 1.0 = full amplitude).
        frequency: Frequency multiplier applied to cycles (default: 1.0 = no change).
        phase: Phase offset in radians (currently unused, reserved for future use).

    Returns:
        List of CurvePoints forming a triangle wave in normalized [0, 1] space.

    Raises:
        ValueError: If n_samples < 2 or cycles <= 0.

    Note:
        Phase parameter is accepted for API compatibility with other wave generators
        but is not currently applied. TODO: Implement phase support for triangle waves.
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    if cycles <= 0:
        raise ValueError("cycles must be > 0")

    # Apply frequency multiplier to cycles
    effective_cycles = cycles * frequency

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        cycle_pos = (t * effective_cycles) % 1.0

        if cycle_pos < 0.5:
            v = cycle_pos * 2.0
        else:
            v = 2.0 - cycle_pos * 2.0

        # Scale by amplitude (centered at 0.5)
        v = 0.5 + (v - 0.5) * amplitude

        points.append(CurvePoint(t=t, v=v))

    return points


def generate_pulse(
    n_samples: int,
    cycles: float = 1.0,
    duty_cycle: float = 0.5,
    high: float = 1.0,
    low: float = 0.0,
    frequency: float = DEFAULT_CURVE_INTENSITY_PARAMS["frequency"],
    **kwargs,  # Accept but ignore extra params (e.g., phase, amplitude)
) -> list[CurvePoint]:
    """Generate a pulse (square) wave curve with frequency support.

    Frequency multiplies the cycle count. Amplitude control is handled
    via the high/low parameters. Extra parameters are ignored.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Base number of complete cycles in the output.
        duty_cycle: Fraction of cycle that is high (0.0 to 1.0).
        high: Value during high portion (clamped to [0, 1]).
        low: Value during low portion (clamped to [0, 1]).
        frequency: Frequency multiplier applied to cycles (default: 1.0 = no change).
        **kwargs: Ignored parameters (for compatibility).

    Returns:
        List of CurvePoints forming a pulse wave.

    Raises:
        ValueError: If n_samples < 2 or cycles <= 0.
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    if cycles <= 0:
        raise ValueError("cycles must be > 0")

    high = max(0.0, min(1.0, high))
    low = max(0.0, min(1.0, low))
    duty_cycle = max(0.0, min(1.0, duty_cycle))

    # Apply frequency multiplier to cycles
    effective_cycles = cycles * frequency

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        cycle_pos = (t * effective_cycles) % 1.0

        v = high if cycle_pos < duty_cycle else low
        points.append(CurvePoint(t=t, v=v))

    return points


def generate_cosine(
    n_samples: int,
    cycles: float = 1.0,
    phase: float = 0.0,
    amplitude: float = DEFAULT_CURVE_INTENSITY_PARAMS["amplitude"],
    frequency: float = DEFAULT_CURVE_INTENSITY_PARAMS["frequency"],
) -> list[CurvePoint]:
    """Generate a cosine wave curve with intensity support (complementary to sine).

    All timing is normalized to [0, 1] time domain. Amplitude scales the wave
    height around 0.5 center. Frequency multiplies the cycle count.

    The cosine wave is normalized to [0, 1] where:
    - 1.0 is the peak (at phase = 0)
    - 0.0 is the trough (half-cycle later)

    Formula:
        v(t) = 0.5 + 0.5 * amplitude * cos(2π * cycles * frequency * t + phase)

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Base number of complete cycles in the output.
        phase: Phase offset in radians (default 0 = start at peak).
        amplitude: Amplitude scaling factor [0, 1] (default: 1.0 = full amplitude).
        frequency: Frequency multiplier applied to cycles (default: 1.0 = no change).

    Returns:
        List of CurvePoints forming a cosine wave in normalized [0, 1] space.

    Raises:
        ValueError: If n_samples < 2 or cycles <= 0.
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    if cycles <= 0:
        raise ValueError("cycles must be > 0")

    # Apply frequency multiplier to cycles
    effective_cycles = cycles * frequency

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        angle = 2 * math.pi * effective_cycles * t + phase
        # Apply amplitude scaling
        v = 0.5 + 0.5 * amplitude * math.cos(angle)
        points.append(CurvePoint(t=t, v=v))

    return points


def generate_s_curve(
    n_samples: int,
    steepness: float = 12.0,
    **kwargs,  # Accept but ignore intensity params
) -> list[CurvePoint]:
    """Generate an S-curve (sigmoid) easing curve.

    Smooth transition from 0 to 1 with slow start/end and fast middle.

    Formula:
        v(t) = 1 / (1 + e^(-k(t - 0.5)))

    Where k is the steepness parameter.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        steepness: Controls how steep the transition is (must be > 0).
        **kwargs: Ignored parameters (for compatibility).

    Returns:
        List of CurvePoints forming an S-curve.

    Raises:
        ValueError: If n_samples < 2 or steepness <= 0.
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    if steepness <= 0:
        raise ValueError("steepness must be > 0")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        x = (t - 0.5) * steepness
        v = 1.0 / (1.0 + math.exp(-x))
        points.append(CurvePoint(t=t, v=v))

    return points


def generate_square(
    n_samples: int,
    cycles: float = 1.0,
    duty_cycle: float = 0.5,
    high: float = 1.0,
    low: float = 0.0,
    **kwargs,  # Accept but ignore extra intensity params
) -> list[CurvePoint]:
    """Generate a square wave curve (binary on/off).

    This is a convenience wrapper around :func:`generate_pulse` with a default
    duty_cycle of 0.5.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        cycles: Number of complete cycles in the output.
        duty_cycle: Fraction of cycle that is high (0.0 to 1.0).
        high: Value during high portion (clamped to [0, 1]).
        low: Value during low portion (clamped to [0, 1]).
        **kwargs: Ignored parameters (for compatibility).

    Returns:
        List of CurvePoints forming a square wave.

    Raises:
        ValueError: If n_samples < 2 or cycles <= 0.
    """
    return generate_pulse(
        n_samples=n_samples,
        cycles=cycles,
        duty_cycle=duty_cycle,
        high=high,
        low=low,
        **kwargs,  # Pass through
    )


def generate_smooth_step(
    n_samples: int,
    **kwargs,  # Accept but ignore intensity params
) -> list[CurvePoint]:
    """Generate smooth-step function (Hermite interpolation).

    Smooth transition from 0 to 1, smoother than linear.

    Formula:
        v(t) = 3t² - 2t³

    Args:
        n_samples: Number of samples to generate (must be >= 2).

    Returns:
        List of CurvePoints forming a smooth-step curve.

    Raises:
        ValueError: If n_samples < 2.
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        v = t * t * (3.0 - 2.0 * t)
        points.append(CurvePoint(t=t, v=v))

    return points


def generate_smoother_step(
    n_samples: int,
    **kwargs,  # Accept but ignore intensity params
) -> list[CurvePoint]:
    """Generate smoother-step function (Ken Perlin's improved smoothstep).

    Even smoother transition than smooth_step.

    Formula:
        v(t) = 6t⁵ - 15t⁴ + 10t³

    Args:
        n_samples: Number of samples to generate (must be >= 2).

    Returns:
        List of CurvePoints forming a smoother-step curve.

    Raises:
        ValueError: If n_samples < 2.
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    points: list[CurvePoint] = []

    for t in t_grid:
        v = t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
        points.append(CurvePoint(t=t, v=v))

    return points
