"""Curve composition operations.

This module provides functions for composing curves through
multiplication (envelopes) and other operations.
"""

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import interpolate_linear, sample_uniform_grid


def multiply_curves(
    a: list[CurvePoint],
    b: list[CurvePoint],
    n_samples: int | None = None,
) -> list[CurvePoint]:
    """Pointwise multiplication of two curves: (a * b).

    Both curves are resampled to a uniform grid and their values
    are multiplied pointwise. The result is clamped to [0, 1].

    Args:
        a: First curve (list of CurvePoints).
        b: Second curve (list of CurvePoints).
        n_samples: Number of output samples. If None, uses max(len(a), len(b)).

    Returns:
        List of CurvePoints representing (a * b) at uniform grid.

    Raises:
        ValueError: If either curve is empty.

    Example:
        >>> a = [CurvePoint(t=0.0, v=0.5), CurvePoint(t=1.0, v=0.5)]
        >>> b = [CurvePoint(t=0.0, v=1.0), CurvePoint(t=1.0, v=0.0)]
        >>> result = multiply_curves(a, b, n_samples=4)
        >>> result[0].v  # 0.5 * 1.0 = 0.5
        0.5
    """
    if not a or not b:
        raise ValueError("Both curves must be non-empty")

    if n_samples is None:
        n_samples = max(len(a), len(b))

    t_grid = sample_uniform_grid(n_samples)

    result: list[CurvePoint] = []
    for t in t_grid:
        va = interpolate_linear(a, t)
        vb = interpolate_linear(b, t)
        # Multiply and clamp to [0, 1]
        v = max(0.0, min(1.0, va * vb))
        result.append(CurvePoint(t=t, v=v))

    return result


def apply_envelope(
    curve: list[CurvePoint],
    envelope: list[CurvePoint],
    n_samples: int | None = None,
) -> list[CurvePoint]:
    """Apply envelope to curve (alias for multiply_curves).

    Multiplies the curve values by the envelope values pointwise.
    Common use cases:
    - Fade in: envelope from 0→1
    - Fade out: envelope from 1→0
    - Amplitude modulation

    Args:
        curve: The curve to apply the envelope to.
        envelope: The envelope curve (typically 0→1 or 1→0).
        n_samples: Number of output samples. If None, uses max(len(curve), len(envelope)).

    Returns:
        List of CurvePoints representing curve * envelope at uniform grid.

    Raises:
        ValueError: If either curve is empty.

    Example:
        >>> curve = [CurvePoint(t=0.0, v=0.8), CurvePoint(t=1.0, v=0.8)]
        >>> fade_in = [CurvePoint(t=0.0, v=0.0), CurvePoint(t=1.0, v=1.0)]
        >>> result = apply_envelope(curve, fade_in, n_samples=4)
        >>> result[0].v  # 0.8 * 0.0 = 0.0
        0.0
    """
    return multiply_curves(curve, envelope, n_samples)
