"""Easing curve generation functions.

Standard easing functions for smooth animations.
All functions take normalized time array [0, 1] and return normalized values [0, 1].

Based on Robert Penner's easing functions and professional easing-functions library.
"""

import numpy as np
from easing_functions import (
    BackEaseIn,
    BackEaseInOut,
    BackEaseOut,
    ExponentialEaseIn,
    ExponentialEaseInOut,
    ExponentialEaseOut,
)
from numpy.typing import NDArray


# Sine Easing
def ease_in_sine(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-in sine: starts slow, accelerates.

    Formula: 1 - cos(πt/2)

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    result = 1 - np.cos((t * np.pi) / 2)
    return np.asarray(result, dtype=np.float64)


def ease_out_sine(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-out sine: starts fast, decelerates.

    Formula: sin(πt/2)

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    result = np.sin((t * np.pi) / 2)
    return np.asarray(result, dtype=np.float64)


def ease_in_out_sine(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-in-out sine: slow-fast-slow.

    Formula: -(cos(πt) - 1) / 2

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    result = -(np.cos(np.pi * t) - 1) / 2
    return np.asarray(result, dtype=np.float64)


# Quadratic Easing
def ease_in_quad(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-in quadratic: starts slow, accelerates.

    Formula: t²

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    return t * t


def ease_out_quad(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-out quadratic: starts fast, decelerates.

    Formula: 1 - (1-t)²

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    result = 1 - (1 - t) * (1 - t)
    return np.asarray(result, dtype=np.float64)


def ease_in_out_quad(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-in-out quadratic: slow-fast-slow.

    Formula: t<0.5 ? 2t² : 1 - (-2t+2)²/2

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    return np.where(t < 0.5, 2 * t * t, 1 - np.power(-2 * t + 2, 2) / 2)


# Cubic Easing
def ease_in_cubic(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-in cubic: starts slow, accelerates sharply.

    Formula: t³

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    return t * t * t


def ease_out_cubic(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-out cubic: starts fast, decelerates sharply.

    Formula: 1 - (1-t)³

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    result = 1 - np.power(1 - t, 3)
    return np.asarray(result, dtype=np.float64)


def ease_in_out_cubic(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-in-out cubic: slow-fast-slow with sharp transitions.

    Formula: t<0.5 ? 4t³ : 1 - (-2t+2)³/2

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    return np.where(t < 0.5, 4 * t * t * t, 1 - np.power(-2 * t + 2, 3) / 2)


# ============================================================================
# Exponential Easing (Professional Library - Very Dramatic)
# ============================================================================


def ease_in_expo(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-in exponential: very slow start, explosive end.

    Professional library implementation for extreme dramatic effects.
    Formula: 2^(10(x-1))

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]

    Use Cases:
        - Extreme energy drops
        - Building to explosive moments
        - Maximum drama before climax
    """
    ease = ExponentialEaseIn()
    # Vectorize the easing function for numpy arrays
    result = np.array([ease(float(ti)) for ti in t])
    # Ensure DMX-safe bounds
    return np.clip(result, 0.0, 1.0)


def ease_out_expo(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-out exponential: explosive start, very slow end.

    Professional library implementation for dramatic releases.
    Formula: 1 - 2^(-10x)

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]

    Use Cases:
        - Explosive impact moments
        - Rapid energy release then settle
        - Dramatic starts
    """
    ease = ExponentialEaseOut()
    result = np.array([ease(float(ti)) for ti in t])
    return np.clip(result, 0.0, 1.0)


def ease_in_out_expo(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-in-out exponential: very dramatic S-curve.

    Professional library implementation combining both effects.
    Most dramatic of all easing curves.

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]

    Use Cases:
        - Maximum drama for climax sections
        - Extreme contrast in movement
        - Theatrical effects
    """
    ease = ExponentialEaseInOut()
    result = np.array([ease(float(ti)) for ti in t])
    return np.clip(result, 0.0, 1.0)


# ============================================================================
# Back Easing (Professional Library - Anticipation/Overshoot)
# ============================================================================


def ease_in_back(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-in back: pulls back before moving (anticipation).

    Professional library implementation for anticipation effects.
    Creates a "wind-up" motion before the main movement.

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1] (clipped for DMX safety)

    Use Cases:
        - Anticipation before big moments
        - Wind-up effects
        - Cartoon-style movement

    Note:
        May pull slightly negative in library, but clipped to [0, 1] for DMX safety.
    """
    ease = BackEaseIn()
    result = np.array([ease(float(ti)) for ti in t])
    # Back easing may go slightly negative (anticipation)
    # Clip to DMX-safe range
    return np.clip(result, 0.0, 1.0)


def ease_out_back(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-out back: overshoots target then settles.

    Professional library implementation for overshoot effects.
    Movement goes past the target then returns.

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1] (clipped for DMX safety)

    Use Cases:
        - Overshoot on landings
        - Bouncy, playful character
        - Settling into position

    Note:
        May overshoot beyond 1.0 in library, but clipped to [0, 1] for DMX safety.
    """
    ease = BackEaseOut()
    result = np.array([ease(float(ti)) for ti in t])
    # Back easing may overshoot beyond 1.0
    # Clip to DMX-safe range
    return np.clip(result, 0.0, 1.0)


def ease_in_out_back(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ease-in-out back: both anticipation and overshoot.

    Professional library implementation combining both effects.
    Pulls back at start, overshoots at end.

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1] (clipped for DMX safety)

    Use Cases:
        - Full anticipation and overshoot cycle
        - Playful, bouncy transitions
        - Cartoon-style full movement

    Note:
        May go outside [0, 1] in library, but clipped for DMX safety.
    """
    ease = BackEaseInOut()
    result = np.array([ease(float(ti)) for ti in t])
    # May go outside [0, 1] bounds
    # Clip to DMX-safe range
    return np.clip(result, 0.0, 1.0)
