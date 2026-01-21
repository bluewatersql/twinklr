"""Motion-based curve generation functions.

Physics-inspired easing functions with bounce and elastic effects.
All functions take normalized time array [0, 1] and return normalized values [0, 1].
"""

import numpy as np
from numpy.typing import NDArray


def bounce_out(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Bounce-out: bounces and settles at 1.0.

    Simulates a ball bouncing to rest. Based on Robert Penner's bounce easing.

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    n1 = 7.5625
    d1 = 2.75

    def bounce_single(x: float) -> float:
        if x < 1 / d1:
            return n1 * x * x
        elif x < 2 / d1:
            x -= 1.5 / d1
            return n1 * x * x + 0.75
        elif x < 2.5 / d1:
            x -= 2.25 / d1
            return n1 * x * x + 0.9375
        else:
            x -= 2.625 / d1
            return n1 * x * x + 0.984375

    return np.array([bounce_single(x) for x in t])


def bounce_in(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Bounce-in: reverse of bounce-out.

    Bounces before settling at 0, then accelerates to 1.

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    return 1 - bounce_out(1 - t)


def elastic_out(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Elastic-out: elastic oscillation at end.

    Overshoots target with decreasing amplitude, like a spring.
    Formula: 2^(-10t) * sin((10t - 0.75) * 2π/3) + 1

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1] (with slight overshoot)
    """
    c4 = (2 * np.pi) / 3
    return np.where(
        (t == 0) | (t == 1),
        t,
        np.power(2, -10 * t) * np.sin((t * 10 - 0.75) * c4) + 1,
    )


def elastic_in(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Elastic-in: reverse of elastic-out.

    Starts with elastic oscillation before accelerating to target.

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1] (with slight undershoot)
    """
    return 1 - elastic_out(1 - t)


def anticipate(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Anticipate: pulls back before moving forward.

    Constrained to [0, 1] for valid DMX output.
    Dips to 10% in first 30%, then accelerates to 100%.

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    pullback_phase = 0.3  # First 30% is the pullback
    pullback_min = 0.1  # Pull back to 10% (not negative)

    return np.where(
        t <= pullback_phase,
        # Pullback phase: ease from 0 to pullback_min
        pullback_min * np.sin((t / pullback_phase) * np.pi / 2),
        # Acceleration phase: quadratic ease from pullback_min to 1.0
        pullback_min + (1.0 - pullback_min) * ((t - pullback_phase) / (1 - pullback_phase)) ** 2,
    )


def overshoot(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Overshoot: overshoots target then settles.

    Constrained to [0, 1] for valid DMX output.
    Rapid ease to ~98%, small bounce to 100%, settle at 100%.

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    # Use smoothstep as base (guaranteed [0, 1])
    base = t * t * (3 - 2 * t)

    # Add controlled overshoot effect in the range [0.6, 0.9]
    overshoot_window = np.logical_and(t >= 0.6, t <= 0.9)
    t_local = (t - 0.6) / 0.3  # Normalize to [0, 1] within window

    # Damped oscillation: starts strong, fades out
    # Scale by (1 - base) to ensure we never exceed 1.0
    bounce_factor = 0.05 * (1.0 - base) * np.sin(t_local * np.pi * 3) * np.exp(-t_local * 3)

    # Apply bounce only in window
    result = base + np.where(overshoot_window, bounce_factor, 0.0)
    return np.asarray(result, dtype=np.float64)
