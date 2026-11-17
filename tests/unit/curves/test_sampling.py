"""Tests for curve sampling infrastructure."""

from __future__ import annotations

import pytest

from twinklr.core.curves.sampling import sample_uniform_grid


class TestSampleUniformGrid:
    """Tests for sample_uniform_grid function."""

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n must be >= 2"):
            sample_uniform_grid(1)

    def test_n_zero_raises(self) -> None:
        """n = 0 raises ValueError."""
        with pytest.raises(ValueError, match="n must be >= 2"):
            sample_uniform_grid(0)

    def test_n_negative_raises(self) -> None:
        """Negative n raises ValueError."""
        with pytest.raises(ValueError, match="n must be >= 2"):
            sample_uniform_grid(-5)
