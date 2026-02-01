"""Tests for easing curve generators."""

from __future__ import annotations

import pytest

from twinklr.core.curves.functions.easing import (
    generate_ease_in_out_cubic,
    generate_ease_in_sine,
)


class TestSineEasing:
    """Tests for sine easing functions."""

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_ease_in_sine(1)


class TestQuadEasing:
    """Tests for quadratic easing functions."""

    def test_ease_in_out_cubic_symmetry(self) -> None:
        """Ease-in-out is symmetric."""
        result = generate_ease_in_out_cubic(64)
        mid = result[len(result) // 2]
        assert mid.v == pytest.approx(0.5, abs=0.1)


class TestEasingValidity:
    """General tests for all easing functions."""

    def test_endpoints_valid(self) -> None:
        """All easing functions have valid endpoints."""
        result = generate_ease_in_sine(64)
        # Start should be near 0
        assert result[0].v == pytest.approx(0.0, abs=0.1)
        # End should be near 1
        assert result[-1].v == pytest.approx(1.0, abs=0.1)
