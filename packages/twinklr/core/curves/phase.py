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

    A curve that does not close on its start value has no continuous cyclic
    extension by modulo: reading past t=1 jumps straight back to v(0), which on a
    moving head is a full-span snap mid-segment. Such curves are therefore extended
    by reflection (the curve plays back the way it came) rather than by modulo, which
    is continuous at the wrap and physically what a head has to do anyway. Curves
    that do close are wrapped by modulo exactly as before.

    Args:
        points: Original curve points with non-decreasing t values.
        offset_norm: Phase offset in normalized time [0,1].
            Positive values shift the curve "earlier" (read ahead).
            Can be > 1.0 or negative; wraps if wrap=True.
        n_samples: Number of output samples to generate.
        wrap: If True, extend the curve cyclically past its bounds.
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
    reflect = wrap and not _closes_on_itself(points)

    shifted_points: list[CurvePoint] = []
    for t in t_grid:
        t_shifted = t + offset_norm

        if not wrap:
            t_shifted = max(0.0, min(1.0, t_shifted))
        elif reflect:
            t_shifted = _reflect_into_unit_interval(t_shifted)
        else:
            t_shifted %= 1.0

        v = interpolate_linear(points, t_shifted)
        shifted_points.append(CurvePoint(t=t, v=v))

    return shifted_points


def _closes_on_itself(points: list[CurvePoint], tolerance: float = 1e-6) -> bool:
    """Whether the curve ends where it began, so modulo wrapping is continuous."""
    return abs(points[-1].v - points[0].v) <= tolerance


def _reflect_into_unit_interval(t: float) -> float:
    """Fold `t` into [0, 1] by reflection, so the extension has no discontinuity.

    t in [0,1] is unchanged, [1,2] plays backwards, [2,3] forwards again.
    """
    folded = t % 2.0
    return 2.0 - folded if folded > 1.0 else folded
