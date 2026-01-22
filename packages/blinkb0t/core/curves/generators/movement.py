"""Movement curve wrappers for offset-centered, loop-ready output."""

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.semantics import center_curve, ensure_loop_ready

from .basic import (
    generate_hold,
    generate_linear,
    generate_pulse,
    generate_sine,
    generate_triangle,
)


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
