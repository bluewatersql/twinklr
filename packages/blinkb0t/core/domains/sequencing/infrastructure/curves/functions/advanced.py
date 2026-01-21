"""Advanced curve generation functions.

Complex mathematical curves including noise, Lissajous, and Bezier.
All functions take normalized time array [0, 1] and return normalized values [0, 1].
"""

from __future__ import annotations

import numpy as np
from noise import pnoise1, snoise2
from numpy.typing import NDArray


def perlin_noise(
    t: NDArray[np.float64],
    octaves: int = 3,
    persistence: float = 0.5,
    lacunarity: float = 2.0,
    scale: float = 1.0,
) -> NDArray[np.float64]:
    """True Perlin noise: smooth procedural noise using noise library.

    Creates organic, natural-looking random variation with configurable detail.
    Superior to sine approximation - provides true pseudo-random smoothness.

    Args:
        t: Normalized time array [0, 1]
        octaves: Number of noise layers (detail level)
            - 1: Very smooth, low detail
            - 3: Balanced (default)
            - 5+: High detail, complex texture
        persistence: Amplitude multiplier per octave (0.0-1.0)
            - Lower: Smoother, less detail influence
            - 0.5: Balanced (default)
            - Higher: More detail, rougher
        lacunarity: Frequency multiplier per octave
            - 2.0: Standard (default)
            - Higher: Faster detail frequency increase
        scale: Overall frequency scale
            - <1: Zoomed in (slower variation)
            - 1.0: Standard (default)
            - >1: Zoomed out (faster variation)

    Returns:
        Normalized values [0, 1]

    Use Cases:
        - Organic motion (breathing, floating)
        - Natural intensity variation
        - Living effects (fire flicker, water shimmer)
        - Unpredictable but smooth changes

    Example:
        >>> t = np.linspace(0, 1, 200)
        >>> # Smooth organic motion
        >>> smooth = perlin_noise(t, octaves=1, scale=1.0)
        >>> # Detailed organic texture
        >>> detailed = perlin_noise(t, octaves=5, scale=2.0)
    """
    # Generate Perlin noise using noise library
    values = np.array(
        [
            pnoise1(
                float(x) * scale,
                octaves=octaves,
                persistence=persistence,
                lacunarity=lacunarity,
            )
            for x in t
        ]
    )

    # Normalize to [0, 1]
    v_min = values.min()
    v_max = values.max()

    if v_max - v_min > 1e-10:  # Avoid division by zero
        result = (values - v_min) / (v_max - v_min)
        return np.asarray(result, dtype=np.float64)
    else:
        result = np.ones_like(values) * 0.5  # Constant if no variation
        return np.asarray(result, dtype=np.float64)


def simplex_noise(t: NDArray[np.float64], scale: float = 1.0) -> NDArray[np.float64]:
    """Simplex noise: faster alternative to Perlin noise.

    Ken Perlin's improved noise algorithm - faster computation, similar quality.
    Good for performance-critical applications.

    Uses 2D simplex noise (snoise2) with fixed y=0 to simulate 1D.

    Args:
        t: Normalized time array [0, 1]
        scale: Overall frequency scale
            - <1: Zoomed in (slower variation)
            - 1.0: Standard (default)
            - >1: Zoomed out (faster variation)

    Returns:
        Normalized values [0, 1]

    Use Cases:
        - Real-time organic motion
        - Performance-critical effects
        - Large arrays needing smooth randomness

    Performance:
        ~30% faster than Perlin noise with similar quality

    Example:
        >>> t = np.linspace(0, 1, 1000)  # Large array
        >>> noise = simplex_noise(t, scale=1.0)  # Fast computation
    """
    # Generate Simplex noise using 2D simplex with fixed y=0
    # snoise2 returns values in range [-1, 1]
    values = np.array([snoise2(float(x) * scale, 0.0) for x in t])

    # Normalize to [0, 1]
    v_min = values.min()
    v_max = values.max()

    if v_max - v_min > 1e-10:  # Avoid division by zero
        result = (values - v_min) / (v_max - v_min)
        return np.asarray(result, dtype=np.float64)
    else:
        result = np.ones_like(values) * 0.5  # Constant if no variation
        return np.asarray(result, dtype=np.float64)


def lissajous(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Lissajous curve: complex oscillating pattern.

    Uses frequency ratio a=3, b=2 for interesting pattern.
    Returns y-component only (normalized to [0, 1]).

    Formula: (sin(2 * 2πt + π/2) + 1) / 2

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    b = 2  # Frequency parameter for y-component
    delta = np.pi / 2
    # Y-component of Lissajous
    result = (np.sin(b * 2 * np.pi * t + delta) + 1) / 2
    return np.asarray(result, dtype=np.float64)


def bezier(t: NDArray[np.float64]) -> NDArray[np.float64]:
    """Cubic Bezier curve with default control points.

    Control points: P0=(0,0), P1=(0.25,0.1), P2=(0.75,0.9), P3=(1,1)
    Creates a smooth S-curve-like transition.

    Formula: (1-t)³P0 + 3(1-t)²tP1 + 3(1-t)t²P2 + t³P3

    Args:
        t: Normalized time array [0, 1]

    Returns:
        Normalized values [0, 1]
    """
    # Cubic Bezier formula
    p0_y, p1_y, p2_y, p3_y = 0.0, 0.1, 0.9, 1.0

    result = (
        np.power(1 - t, 3) * p0_y
        + 3 * np.power(1 - t, 2) * t * p1_y
        + 3 * (1 - t) * np.power(t, 2) * p2_y
        + np.power(t, 3) * p3_y
    )
    return np.asarray(result, dtype=np.float64)
