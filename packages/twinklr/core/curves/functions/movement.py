"""Movement curve wrappers for offset-centered, loop-ready output."""

from twinklr.core.curves.defaults import DEFAULT_CURVE_INTENSITY_PARAMS
from twinklr.core.curves.functions.basic import (
    generate_hold,
    generate_linear,
    generate_pulse,
    generate_sine,
    generate_triangle,
)
from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.semantics import center_curve, ensure_loop_ready


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
    **kwargs,  # Accept but ignore intensity params (cycles, frequency, amplitude)
) -> list[CurvePoint]:
    """Generate a loop-ready, offset-centered linear curve for movement.

    Args:
        n_samples: Number of samples to generate.
        ascending: If True, ramp from 0→1. If False, ramp from 1→0.
        loop_mode: Loop preparation mode.
        **kwargs: Ignored intensity parameters (for compatibility).

    Returns:
        List of CurvePoints centered at 0.5 and loop-ready.
    """
    return _movement_post_process(
        generate_linear(n_samples=n_samples, ascending=ascending),
        loop_mode=loop_mode,
    )


def generate_movement_hold(
    n_samples: int,
    value: float = 1.0,
    *,
    loop_mode: str = "append",
    **kwargs,  # Accept but ignore intensity params (cycles, frequency, amplitude)
) -> list[CurvePoint]:
    """Generate a loop-ready, offset-centered hold curve for movement.

    Args:
        n_samples: Number of samples to generate.
        value: Constant value (clamped to [0, 1]).
        loop_mode: Loop preparation mode.
        **kwargs: Ignored intensity parameters (for compatibility).

    Returns:
        List of CurvePoints centered at 0.5 and loop-ready.
    """
    return _movement_post_process(
        generate_hold(n_samples=n_samples, value=value),
        loop_mode=loop_mode,
    )


def generate_movement_sine(
    n_samples: int,
    cycles: float = 1.0,
    phase: float = 0.0,
    amplitude: float = DEFAULT_CURVE_INTENSITY_PARAMS["amplitude"],
    frequency: float = DEFAULT_CURVE_INTENSITY_PARAMS["frequency"],
    *,
    loop_mode: str = "append",
) -> list[CurvePoint]:
    """Generate a loop-ready, offset-centered sine curve for movement.

    Args:
        n_samples: Number of samples to generate.
        cycles: Base number of complete cycles.
        phase: Phase offset in radians.
        amplitude: Amplitude scaling factor [0, 1] (default: 1.0).
        frequency: Frequency multiplier (default: 1.0).
        loop_mode: Loop preparation mode.

    Returns:
        List of CurvePoints centered at 0.5 and loop-ready.
    """
    return _movement_post_process(
        generate_sine(
            n_samples=n_samples,
            cycles=cycles,
            phase=phase,
            amplitude=amplitude,
            frequency=frequency,
        ),
        loop_mode=loop_mode,
    )


def generate_movement_triangle(
    n_samples: int,
    cycles: float = 1.0,
    amplitude: float = DEFAULT_CURVE_INTENSITY_PARAMS["amplitude"],
    frequency: float = DEFAULT_CURVE_INTENSITY_PARAMS["frequency"],
    *,
    loop_mode: str = "append",
) -> list[CurvePoint]:
    """Generate a loop-ready, offset-centered triangle curve for movement.

    Args:
        n_samples: Number of samples to generate.
        cycles: Base number of complete cycles.
        amplitude: Amplitude scaling factor [0, 1] (default: 1.0).
        frequency: Frequency multiplier (default: 1.0).
        loop_mode: Loop preparation mode.

    Returns:
        List of CurvePoints centered at 0.5 and loop-ready.
    """
    return _movement_post_process(
        generate_triangle(
            n_samples=n_samples,
            cycles=cycles,
            amplitude=amplitude,
            frequency=frequency,
        ),
        loop_mode=loop_mode,
    )


def generate_movement_pulse(
    n_samples: int,
    cycles: float = 1.0,
    duty_cycle: float = 0.5,
    high: float = 1.0,
    low: float = 0.0,
    frequency: float = DEFAULT_CURVE_INTENSITY_PARAMS["frequency"],
    *,
    loop_mode: str = "append",
    **kwargs,  # Accept but ignore other params (e.g., amplitude from defaults)
) -> list[CurvePoint]:
    """Generate a loop-ready, offset-centered pulse curve for movement.

    This curve uses high/low parameters instead of amplitude. The parameter
    adapter (adapt_movement_pulse_params) translates categorical amplitude
    to high/low values.

    Args:
        n_samples: Number of samples to generate.
        cycles: Base number of complete cycles.
        duty_cycle: Fraction of cycle that is high.
        high: Value during high portion.
        low: Value during low portion.
        frequency: Frequency multiplier (default: 1.0).
        loop_mode: Loop preparation mode.

    Returns:
        List of CurvePoints centered at 0.5 and loop-ready.
    """
    return _movement_post_process(
        generate_pulse(
            n_samples=n_samples,
            cycles=cycles,
            duty_cycle=duty_cycle,
            high=high,
            low=low,
            frequency=frequency,
        ),
        loop_mode=loop_mode,
    )
