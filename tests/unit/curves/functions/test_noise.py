"""Tests for noise curve generators."""

from __future__ import annotations

import pytest

from twinklr.core.curves.functions.noise import (
    generate_perlin_noise,
)


class TestNormalizeNoise:
    """Tests for _normalize_noise helper function."""

    def test_n_less_than_two_raises(self) -> None:
        """n < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_perlin_noise(1)
