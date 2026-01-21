"""Custom implementations of xLights native curves.

These functions generate point arrays that match xLights native curve behavior,
enabling blending operations while maintaining visual equivalence.

All functions:
- Take normalized time array [0, 1]
- Take xLights parameters (p1, p2, p3, p4) matching native curve API
- Return normalized values [0, 1]
- Match xLights native curve output for blending support

Example:
    >>> import numpy as np
    >>> t = np.linspace(0, 1, 100)
    >>> # Create sine wave matching xLights native SINE curve
    >>> curve = sine_x(t, p2=100.0, p4=50.0)
    >>> # Result can be blended with other curves
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def flat_x(
    t: NDArray[np.float64],
    p1: float = 50.0,
    p2: float = 50.0,
    p3: float = 50.0,
    p4: float = 50.0,
) -> NDArray[np.float64]:
    """Custom implementation of FLAT native curve.

    Returns constant value across entire time range.
    Equivalent to xLights "Flat" curve type.

    Args:
        t: Normalized time array [0, 1]
        p1: Constant value (0-100) -> normalized to [0, 1]
        p2-p4: Unused (maintained for API consistency)

    Returns:
        Constant array of shape t.shape with value p1/100

    Example:
        >>> t = np.linspace(0, 1, 100)
        >>> flat_x(t, p1=50)  # Returns array of 0.5 values
        array([0.5, 0.5, 0.5, ..., 0.5])
    """
    value = np.clip(p1 / 100.0, 0.0, 1.0)  # Normalize 0-100 to 0-1
    return np.full_like(t, value)


def ramp_x(
    t: NDArray[np.float64],
    p1: float = 0.0,
    p2: float = 100.0,
    p3: float = 50.0,
    p4: float = 50.0,
) -> NDArray[np.float64]:
    """Custom implementation of RAMP native curve.

    Linear interpolation from start to end value.
    Equivalent to xLights "Ramp" curve type.

    Args:
        t: Normalized time array [0, 1]
        p1: Start value (0-100) -> normalized to [0, 1]
        p2: End value (0-100) -> normalized to [0, 1]
        p3-p4: Unused

    Returns:
        Linear ramp from p1/100 to p2/100

    Example:
        >>> t = np.array([0.0, 0.5, 1.0])
        >>> ramp_x(t, p1=0, p2=100)  # 0% to 100%
        array([0.0, 0.5, 1.0])
    """
    start = np.clip(p1 / 100.0, 0.0, 1.0)
    end = np.clip(p2 / 100.0, 0.0, 1.0)
    return start + (end - start) * t  # type: ignore[no-any-return]


def sine_x(
    t: NDArray[np.float64],
    p1: float = 50.0,
    p2: float = 100.0,
    p3: float = 50.0,
    p4: float = 50.0,
) -> NDArray[np.float64]:
    """Custom implementation of SINE native curve.

    Sine wave with configurable amplitude and center.
    Equivalent to xLights "Sine" curve type.

    Args:
        t: Normalized time array [0, 1]
        p1: Unused (reserved for future use)
        p2: Amplitude (0-200), 100=full range
        p3: Unused (reserved for future use)
        p4: Center offset (0-100)

    Returns:
        Sine wave oscillating around center

    Formula:
        center + amplitude * sin(2πt)

    Example:
        >>> t = np.linspace(0, 1, 100)
        >>> sine_x(t, p2=100, p4=50)  # Full sine centered at 50%
    """
    amplitude = (p2 / 100.0) * 0.5  # Normalize amplitude
    center = np.clip(p4 / 100.0, 0.0, 1.0)

    # Sine wave: sin(2πt) oscillates [-1, 1]
    wave = np.sin(2 * np.pi * t)

    # Scale by amplitude and offset by center
    result = center + amplitude * wave

    # Clamp to [0, 1] to match xLights behavior
    return np.clip(result, 0.0, 1.0)  # type: ignore[no-any-return]


def abs_sine_x(
    t: NDArray[np.float64],
    p1: float = 50.0,
    p2: float = 100.0,
    p3: float = 50.0,
    p4: float = 50.0,
) -> NDArray[np.float64]:
    """Custom implementation of ABS_SINE native curve.

    Absolute value of sine wave (always positive oscillation).
    Equivalent to xLights "Abs Sine" curve type.

    Args:
        t: Normalized time array [0, 1]
        p1: Unused
        p2: Amplitude (0-200)
        p3: Unused
        p4: Center offset (0-100)

    Returns:
        Absolute sine wave

    Formula:
        center + amplitude * |sin(2πt)|

    Example:
        >>> t = np.linspace(0, 1, 100)
        >>> abs_sine_x(t, p2=100, p4=50)  # Always positive oscillation
    """
    amplitude = (p2 / 100.0) * 0.5
    center = np.clip(p4 / 100.0, 0.0, 1.0)

    # Absolute sine: |sin(2πt)| oscillates [0, 1]
    wave = np.abs(np.sin(2 * np.pi * t))

    result = center + amplitude * wave
    return np.clip(result, 0.0, 1.0)  # type: ignore[no-any-return]


def parabolic_x(
    t: NDArray[np.float64],
    p1: float = 50.0,
    p2: float = 100.0,
    p3: float = 50.0,
    p4: float = 50.0,
) -> NDArray[np.float64]:
    """Custom implementation of PARABOLIC native curve.

    Parabolic (quadratic) curve creating U-shape.
    Equivalent to xLights "Parabolic" curve type.

    Args:
        t: Normalized time array [0, 1]
        p1: Unused
        p2: Amplitude/curve strength (0-200)
        p3: Unused
        p4: Center offset (0-100)

    Returns:
        Parabolic curve

    Formula:
        center + amplitude * (2t - 1)²

    Example:
        >>> t = np.linspace(0, 1, 100)
        >>> parabolic_x(t, p2=100, p4=50)  # U-shaped curve
    """
    amplitude = (p2 / 100.0) * 0.5
    center = np.clip(p4 / 100.0, 0.0, 1.0)

    # Parabola: (2t - 1)² produces U-shape from 1 → 0 → 1
    parabola = (2 * t - 1) ** 2

    # Center the parabola around the specified center
    result = center + amplitude * (parabola - 0.5)
    return np.clip(result, 0.0, 1.0)  # type: ignore[no-any-return]


def logarithmic_x(
    t: NDArray[np.float64],
    p1: float = 0.0,
    p2: float = 100.0,
    p3: float = 50.0,
    p4: float = 50.0,
) -> NDArray[np.float64]:
    """Custom implementation of LOGARITHMIC native curve.

    Logarithmic growth curve (fast start, slow end).
    Equivalent to xLights "Logarithmic" curve type.

    Args:
        t: Normalized time array [0, 1]
        p1: Start value (0-100)
        p2: End value (0-100)
        p3-p4: Unused (reserved for curve strength)

    Returns:
        Logarithmic curve

    Formula:
        start + (end - start) * log(1 + t) / log(2)

    Example:
        >>> t = np.linspace(0, 1, 100)
        >>> logarithmic_x(t, p1=0, p2=100)  # Fast start, slow end
    """
    start = np.clip(p1 / 100.0, 0.0, 1.0)
    end = np.clip(p2 / 100.0, 0.0, 1.0)

    # Avoid log(0): use log(1 + t) / log(2) for range [0, 1]
    # This gives fast growth at start, slowing toward end
    curve = np.log1p(t) / np.log(2.0)

    result = start + (end - start) * curve
    return np.clip(result, 0.0, 1.0)  # type: ignore[no-any-return]


def exponential_x(
    t: NDArray[np.float64],
    p1: float = 0.0,
    p2: float = 100.0,
    p3: float = 50.0,
    p4: float = 50.0,
) -> NDArray[np.float64]:
    """Custom implementation of EXPONENTIAL native curve.

    Exponential growth curve (slow start, fast end).
    Equivalent to xLights "Exponential" curve type.

    Args:
        t: Normalized time array [0, 1]
        p1: Start value (0-100)
        p2: End value (0-100)
        p3-p4: Unused (reserved for curve strength)

    Returns:
        Exponential curve

    Formula:
        start + (end - start) * (e^t - 1) / (e - 1)

    Example:
        >>> t = np.linspace(0, 1, 100)
        >>> exponential_x(t, p1=0, p2=100)  # Slow start, fast end
    """
    start = np.clip(p1 / 100.0, 0.0, 1.0)
    end = np.clip(p2 / 100.0, 0.0, 1.0)

    # Exponential: (e^t - 1) / (e - 1) maps [0, 1] → [0, 1]
    # Slow start, rapid acceleration toward end
    curve = (np.exp(t) - 1) / (np.e - 1)

    result = start + (end - start) * curve
    return np.clip(result, 0.0, 1.0)  # type: ignore[no-any-return]


def saw_tooth_x(
    t: NDArray[np.float64],
    p1: float = 0.0,
    p2: float = 100.0,
    p3: float = 50.0,
    p4: float = 50.0,
) -> NDArray[np.float64]:
    """Custom implementation of SAW_TOOTH native curve.

    Sawtooth wave (linear ramp that resets).
    Equivalent to xLights "Saw Tooth" curve type.

    Args:
        t: Normalized time array [0, 1]
        p1: Min value (0-100)
        p2: Max value (0-100)
        p3: Frequency/cycles (affects repetition rate, ~10-100)
        p4: Unused

    Returns:
        Sawtooth wave

    Formula:
        Linear rise from min to max, then sharp drop and repeat

    Example:
        >>> t = np.linspace(0, 1, 100)
        >>> saw_tooth_x(t, p1=0, p2=100, p3=50)  # ~5 cycles
    """
    min_val = np.clip(p1 / 100.0, 0.0, 1.0)
    max_val = np.clip(p2 / 100.0, 0.0, 1.0)

    # Sawtooth: t % 1 gives linear ramp [0, 1]
    # For multiple cycles, use (t * cycles) % 1
    # p3=50 → ~5 cycles (divide by 10 for reasonable cycle count)
    cycles = max(1, int(p3 / 10))
    sawtooth = (t * cycles) % 1.0

    result = min_val + (max_val - min_val) * sawtooth
    return np.clip(result, 0.0, 1.0)  # type: ignore[no-any-return]
