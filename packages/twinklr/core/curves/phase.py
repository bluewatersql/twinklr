"""Phase shift implementation for curves.

This module implements phase shifting using the sampling approach (Option B).
All phase shifts resample the curve at a uniform grid, sampling from
shifted positions in the original curve.
"""

from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.sampling import interpolate_linear, sample_uniform_grid


def apply_phase_shift_samples(
    points: list[CurvePoint],
    offset_norm: float,
    n_samples: int,
    wrap: bool = True,
) -> list[CurvePoint]:
    """Apply phase shift by resampling (MANDATORY Option B).

    Generates N uniformly-spaced output samples, each sampling
    from the original curve at (t + offset_norm).

    Args:
        points: Original curve points with non-decreasing t values.
        offset_norm: Phase offset in normalized time [0,1].
            Positive values shift the curve "earlier" (read ahead).
            Can be > 1.0 or negative; wraps if wrap=True.
        n_samples: Number of output samples to generate.
        wrap: If True, wrap around at boundaries (cyclic).
            If False, clamp to [0, 1] (non-cyclic).

    Returns:
        List of CurvePoints at the uniform grid with shifted values.

    Raises:
        ValueError: If points is empty or n_samples < 2.

    Example:
        >>> points = [CurvePoint(t=0.0, v=0.0), CurvePoint(t=1.0, v=1.0)]
        >>> shifted = apply_phase_shift_samples(points, 0.25, 4, wrap=True)
        >>> shifted[0].v  # At t=0, samples from t=0.25
        0.25
    """
    if not points:
        raise ValueError("points cannot be empty")
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)

    shifted_points: list[CurvePoint] = []
    for t in t_grid:
        t_shifted = t + offset_norm

        if wrap:
            # Wrap to [0, 1) using modulo
            t_shifted = t_shifted % 1.0
        else:
            # Clamp to [0, 1]
            t_shifted = max(0.0, min(1.0, t_shifted))

        v = interpolate_linear(points, t_shifted)
        shifted_points.append(CurvePoint(t=t, v=v))

    return shifted_points
