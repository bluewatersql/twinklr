"""Basic curve generation functions.

Pure mathematical functions for generating basic curve shapes.
All functions take normalized time array [0, 1] and return normalized values [0, 1].
"""

import numpy as np
from numpy.typing import NDArray


def cosine(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Generate cosine wave (complementary to sine).

    Starts at 1, dips to 0 at middle, returns to 1.
    Formula: (cos(2πt) + 1) / 2

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    result = (np.cos(2 * np.pi * t) + 1) / 2
    return np.asarray(result, dtype=np.float64)


def triangle(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Generate triangle wave (linear rise and fall).

    Rises linearly from 0 to 1, then falls back to 0.
    Formula: 1 - |((2t) mod 2) - 1|

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    result = 1 - np.abs((t * 2) % 2 - 1)
    return np.asarray(result, dtype=np.float64)


def s_curve(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Generate S-curve (sigmoid function).

    Smooth transition from 0 to 1 with slow start/end and fast middle.
    Formula: 1 / (1 + e^(-12(t - 0.5)))

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    # Sigmoid function scaled to [0, 1]
    # Use range [-6, 6] for good S-shape
    x = (t - 0.5) * 12  # Scale to [-6, 6]
    result = 1 / (1 + np.exp(-x))
    return np.asarray(result, dtype=np.float64)


def square(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Generate square wave (binary on/off).

    Alternates between 0 and 1 with sharp transitions.
    Formula: (sign(sin(2πt)) + 1) / 2

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0 or 1]
    """
    result = (np.sign(np.sin(2 * np.pi * t)) + 1) / 2
    return np.asarray(result, dtype=np.float64)


def smooth_step(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Generate smooth-step function (Hermite interpolation).

    Smooth transition from 0 to 1, smoother than linear.
    Formula: 3t² - 2t³

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    return t * t * (3 - 2 * t)


def smoother_step(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Generate smoother-step function (Ken Perlin's improved smoothstep).

    Even smoother transition than smooth_step.
    Formula: 6t⁵ - 15t⁴ + 10t³

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    return t * t * t * (t * (t * 6 - 15) + 10)
