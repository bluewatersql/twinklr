"""Tests for curve sampling infrastructure."""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import interpolate_linear, sample_uniform_grid


class TestSampleUniformGrid:
    """Tests for sample_uniform_grid function."""

    def test_returns_correct_count(self) -> None:
        """Returns requested number of samples."""
        result = sample_uniform_grid(4)
        assert len(result) == 4

    def test_returns_evenly_spaced_values(self) -> None:
        """Returns evenly spaced values in [0, 1)."""
        result = sample_uniform_grid(4)
        assert result == [0.0, 0.25, 0.5, 0.75]

    def test_starts_at_zero(self) -> None:
        """First sample is always 0.0."""
        result = sample_uniform_grid(10)
        assert result[0] == 0.0

    def test_does_not_include_one(self) -> None:
        """Samples are in [0, 1), not [0, 1]."""
        result = sample_uniform_grid(10)
        assert result[-1] < 1.0

    def test_minimum_two_samples(self) -> None:
        """Two samples returns [0.0, 0.5]."""
        result = sample_uniform_grid(2)
        assert result == [0.0, 0.5]

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

    def test_interpolate_midpoint(self, ramp_up_points: list[CurvePoint]) -> None:
        """Interpolating at midpoint returns midpoint value."""
        result = interpolate_linear(ramp_up_points, 0.5)
        assert result == pytest.approx(0.5)

    def test_interpolate_at_start(self, ramp_up_points: list[CurvePoint]) -> None:
        """Interpolating at t=0 returns first point value."""
        result = interpolate_linear(ramp_up_points, 0.0)
        assert result == pytest.approx(0.0)

    def test_interpolate_at_end(self, ramp_up_points: list[CurvePoint]) -> None:
        """Interpolating at t=1 returns last point value."""
        result = interpolate_linear(ramp_up_points, 1.0)
        assert result == pytest.approx(1.0)

    def test_interpolate_quarter(self, ramp_up_points: list[CurvePoint]) -> None:
        """Interpolating at t=0.25 returns 0.25 for linear ramp."""
        result = interpolate_linear(ramp_up_points, 0.25)
        assert result == pytest.approx(0.25)

    def test_interpolate_descending_ramp(self, ramp_down_points: list[CurvePoint]) -> None:
        """Interpolating descending ramp works correctly."""
        result = interpolate_linear(ramp_down_points, 0.5)
        assert result == pytest.approx(0.5)

    def test_interpolate_before_first_point(self, simple_linear_points: list[CurvePoint]) -> None:
        """Interpolating before first point returns first value."""
        result = interpolate_linear(simple_linear_points, 0.0)
        assert result == simple_linear_points[0].v

    def test_interpolate_after_last_point(self, simple_linear_points: list[CurvePoint]) -> None:
        """Interpolating after last point returns last value."""
        result = interpolate_linear(simple_linear_points, 1.0)
        assert result == simple_linear_points[-1].v

    def test_interpolate_between_segments(self, simple_linear_points: list[CurvePoint]) -> None:
        """Interpolating between segments works correctly."""
        result = interpolate_linear(simple_linear_points, 0.75)
        assert result == pytest.approx(0.75)

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

    def test_interpolate_constant_curve(self, simple_hold_points: list[CurvePoint]) -> None:
        """Interpolating constant curve returns constant value."""
        for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
            result = interpolate_linear(simple_hold_points, t)
            assert result == pytest.approx(0.5)

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
