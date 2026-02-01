"""Tests for curve sampling infrastructure."""

from __future__ import annotations

import pytest

from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.sampling import interpolate_linear, sample_uniform_grid


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


class TestInterpolateLinear:
    """Tests for interpolate_linear function."""

    def test_empty_points_raises(self) -> None:
        """Empty points list raises ValueError."""
        with pytest.raises(ValueError, match="points cannot be empty"):
            interpolate_linear([], 0.5)

    def test_t_below_range_raises(self, simple_linear_points: list[CurvePoint]) -> None:
        """t below 0 raises ValueError."""
        with pytest.raises(ValueError, match="t must be in"):
            interpolate_linear(simple_linear_points, -0.1)

    def test_t_above_range_raises(self, simple_linear_points: list[CurvePoint]) -> None:
        """t above 1 raises ValueError."""
        with pytest.raises(ValueError, match="t must be in"):
            interpolate_linear(simple_linear_points, 1.1)

    def test_same_t_values_returns_first(self) -> None:
        """Points with same t values returns first point's value."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.3),
            CurvePoint(t=0.5, v=0.7),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = interpolate_linear(points, 0.5)
        # When t values are equal, returns first point's value
        assert result == pytest.approx(0.3)
