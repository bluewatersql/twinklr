"""Curve sampling infrastructure.

This module provides functions for sampling curves at uniform intervals
and for linear interpolation between curve points.
"""


def sample_uniform_grid(n: int) -> list[float]:
    """Generate N evenly-spaced samples in [0, 1).

    Returns N samples: [0.0, 1/N, 2/N, ..., (N-1)/N]

    Args:
        n: Number of samples to generate. Must be >= 2.

    Returns:
        List of N evenly-spaced float values in [0, 1).

    Raises:
        ValueError: If n < 2.

    Example:
        >>> sample_uniform_grid(4)
        [0.0, 0.25, 0.5, 0.75]
    """
    if n < 2:
        raise ValueError("n must be >= 2")
    return [i / n for i in range(n)]
