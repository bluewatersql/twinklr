"""Noise curve generators backed by the noise library."""

from noise import pnoise1

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import sample_uniform_grid


def _normalize_noise(value: float) -> float:
    return max(0.0, min(1.0, (value + 1.0) / 2.0))


def generate_perlin_noise(
    n_samples: int,
    *,
    scale: float = 4.0,
    octaves: int = 4,
    repeat: int = 1024,
    base: int = 0,
    **kwargs,  # Accept but ignore intensity params
) -> list[CurvePoint]:
    """Generate a Perlin noise curve sampled on the uniform grid.

    Args:
        n_samples: Number of samples to generate (must be >= 2).
        scale: Noise scale factor.
        octaves: Number of octaves for noise.
        repeat: Repeat parameter for noise.
        base: Base seed for noise.
        **kwargs: Ignored parameters (for compatibility).

    Returns:
        List of CurvePoints with Perlin noise values.
    """
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")

    t_grid = sample_uniform_grid(n_samples)
    return [
        CurvePoint(
            t=t,
            v=_normalize_noise(
                pnoise1(
                    t * scale,
                    octaves=octaves,
                    repeat=repeat,
                    base=base,
                )
            ),
        )
        for t in t_grid
    ]
