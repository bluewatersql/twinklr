"""Tests for easing curve generators."""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.functions.easing import (
    generate_ease_in_cubic,
    generate_ease_in_out_cubic,
    generate_ease_in_out_quad,
    generate_ease_in_out_sine,
    generate_ease_in_quad,
    generate_ease_in_sine,
    generate_ease_out_cubic,
    generate_ease_out_quad,
    generate_ease_out_sine,
)


class TestSineEasing:
    """Tests for sine easing functions."""

    def test_ease_in_sine_count(self) -> None:
        """Returns correct number of points."""
        result = generate_ease_in_sine(10)
        assert len(result) == 10

    def test_ease_in_sine_starts_slow(self) -> None:
        """Ease-in starts slowly."""
        result = generate_ease_in_sine(10)
        # Early values should be below linear
        assert result[1].v < 0.2

    def test_ease_out_sine_ends_slow(self) -> None:
        """Ease-out ends slowly."""
        result = generate_ease_out_sine(10)
        # Late values should be above linear
        assert result[-2].v > 0.8

    def test_ease_in_out_sine_symmetry(self) -> None:
        """Ease-in-out is symmetric."""
        result = generate_ease_in_out_sine(64)
        # Value at midpoint should be near 0.5
        mid = result[len(result) // 2]
        assert mid.v == pytest.approx(0.5, abs=0.1)

    def test_n_samples_less_than_two_raises(self) -> None:
        """n_samples < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_samples must be >= 2"):
            generate_ease_in_sine(1)


class TestQuadEasing:
    """Tests for quadratic easing functions."""

    def test_ease_in_quad_count(self) -> None:
        """Returns correct number of points."""
        result = generate_ease_in_quad(10)
        assert len(result) == 10

    def test_ease_in_quad_curve_shape(self) -> None:
        """Ease-in quad accelerates."""
        result = generate_ease_in_quad(10)
        values = [p.v for p in result]
        # Should be concave up (accelerating)
        assert values[2] < 0.1  # Slow start

    def test_ease_out_quad_curve_shape(self) -> None:
        """Ease-out quad decelerates."""
        result = generate_ease_out_quad(10)
        values = [p.v for p in result]
        # Should be concave down (decelerating)
        assert values[2] > 0.2  # Fast start

    def test_ease_in_out_quad_symmetry(self) -> None:
        """Ease-in-out is symmetric."""
        result = generate_ease_in_out_quad(64)
        mid = result[len(result) // 2]
        assert mid.v == pytest.approx(0.5, abs=0.1)


class TestCubicEasing:
    """Tests for cubic easing functions."""

    def test_ease_in_cubic_count(self) -> None:
        """Returns correct number of points."""
        result = generate_ease_in_cubic(10)
        assert len(result) == 10

    def test_ease_in_cubic_slower_than_quad(self) -> None:
        """Ease-in cubic starts slower than quad."""
        cubic = generate_ease_in_cubic(10)
        quad = generate_ease_in_quad(10)
        # Cubic should be even slower at start
        assert cubic[1].v < quad[1].v

    def test_ease_out_cubic_curve_shape(self) -> None:
        """Ease-out cubic decelerates."""
        result = generate_ease_out_cubic(10)
        values = [p.v for p in result]
        assert values[2] > 0.3  # Fast start

    def test_ease_in_out_cubic_symmetry(self) -> None:
        """Ease-in-out is symmetric."""
        result = generate_ease_in_out_cubic(64)
        mid = result[len(result) // 2]
        assert mid.v == pytest.approx(0.5, abs=0.1)


class TestEasingValidity:
    """General tests for all easing functions."""

    @pytest.mark.parametrize(
        "gen_func",
        [
            generate_ease_in_sine,
            generate_ease_out_sine,
            generate_ease_in_out_sine,
            generate_ease_in_quad,
            generate_ease_out_quad,
            generate_ease_in_out_quad,
            generate_ease_in_cubic,
            generate_ease_out_cubic,
            generate_ease_in_out_cubic,
        ],
    )
    def test_endpoints_valid(self, gen_func) -> None:
        """All easing functions have valid endpoints."""
        result = gen_func(64)
        # Start should be near 0
        assert result[0].v == pytest.approx(0.0, abs=0.1)
        # End should be near 1
        assert result[-1].v == pytest.approx(1.0, abs=0.1)

    @pytest.mark.parametrize(
        "gen_func",
        [
            generate_ease_in_sine,
            generate_ease_out_sine,
            generate_ease_in_out_sine,
            generate_ease_in_quad,
            generate_ease_out_quad,
            generate_ease_in_out_quad,
            generate_ease_in_cubic,
            generate_ease_out_cubic,
            generate_ease_in_out_cubic,
        ],
    )
    def test_time_values_valid(self, gen_func) -> None:
        """All easing functions have valid time values."""
        result = gen_func(10)
        for p in result:
            assert 0.0 <= p.t <= 1.0
