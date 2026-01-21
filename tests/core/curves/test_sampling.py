"""Tests for Curve Sampling Infrastructure.

Tests sample_uniform_grid and interpolate_linear functions.
All 10 test cases per implementation plan Task 1.1.
"""

import time

import pytest

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import interpolate_linear, sample_uniform_grid


class TestSampleUniformGrid:
    """Tests for sample_uniform_grid function."""

    def test_sample_uniform_grid_n2_returns_0_and_half(self) -> None:
        """Test sample_uniform_grid(2) returns [0.0, 0.5]."""
        result = sample_uniform_grid(2)
        assert result == [0.0, 0.5]

    def test_sample_uniform_grid_n4_returns_quarters(self) -> None:
        """Test sample_uniform_grid(4) returns [0.0, 0.25, 0.5, 0.75]."""
        result = sample_uniform_grid(4)
        assert result == [0.0, 0.25, 0.5, 0.75]

    def test_sample_uniform_grid_n1_raises_value_error(self) -> None:
        """Test sample_uniform_grid(1) raises ValueError."""
        with pytest.raises(ValueError, match="n must be >= 2"):
            sample_uniform_grid(1)

    def test_sample_uniform_grid_n0_raises_value_error(self) -> None:
        """Test sample_uniform_grid(0) raises ValueError."""
        with pytest.raises(ValueError, match="n must be >= 2"):
            sample_uniform_grid(0)

    def test_sample_uniform_grid_negative_raises_value_error(self) -> None:
        """Test sample_uniform_grid(-1) raises ValueError."""
        with pytest.raises(ValueError, match="n must be >= 2"):
            sample_uniform_grid(-1)


class TestInterpolateLinear:
    """Tests for interpolate_linear function."""

    def test_interpolate_at_exact_points(self) -> None:
        """Test interpolate_linear at exact point values."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=1.0, v=1.0),
        ]
        assert interpolate_linear(points, 0.0) == 0.0
        assert interpolate_linear(points, 0.5) == 0.5
        assert interpolate_linear(points, 1.0) == 1.0

    def test_interpolate_midpoint_between_two_points(self) -> None:
        """Test interpolate_linear at midpoint between two points."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        # Midpoint at t=0.5 should give v=0.5
        assert interpolate_linear(points, 0.5) == 0.5
        # Quarter point at t=0.25 should give v=0.25
        assert interpolate_linear(points, 0.25) == 0.25
        # Three-quarter point at t=0.75 should give v=0.75
        assert interpolate_linear(points, 0.75) == 0.75

    def test_interpolate_before_first_point_clamps(self) -> None:
        """Test interpolate_linear before first point returns first value."""
        points = [
            CurvePoint(t=0.2, v=0.3),
            CurvePoint(t=0.8, v=0.9),
        ]
        # t=0.0 is before first point (t=0.2), should clamp to v=0.3
        assert interpolate_linear(points, 0.0) == 0.3
        assert interpolate_linear(points, 0.1) == 0.3

    def test_interpolate_after_last_point_clamps(self) -> None:
        """Test interpolate_linear after last point returns last value."""
        points = [
            CurvePoint(t=0.2, v=0.3),
            CurvePoint(t=0.8, v=0.9),
        ]
        # t=1.0 is after last point (t=0.8), should clamp to v=0.9
        assert interpolate_linear(points, 1.0) == 0.9
        assert interpolate_linear(points, 0.95) == 0.9

    def test_interpolate_t_less_than_zero_raises_value_error(self) -> None:
        """Test interpolate_linear with t < 0 raises ValueError."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        with pytest.raises(ValueError, match="t must be in"):
            interpolate_linear(points, -0.1)

    def test_interpolate_t_greater_than_one_raises_value_error(self) -> None:
        """Test interpolate_linear with t > 1 raises ValueError."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        with pytest.raises(ValueError, match="t must be in"):
            interpolate_linear(points, 1.1)

    def test_interpolate_empty_points_raises_value_error(self) -> None:
        """Test interpolate_linear with empty points raises ValueError."""
        with pytest.raises(ValueError, match="points cannot be empty"):
            interpolate_linear([], 0.5)


class TestInterpolateLinearPerformance:
    """Performance benchmarks for interpolate_linear."""

    def test_interpolate_1000_calls_under_10ms(self) -> None:
        """Benchmark: 1000 interpolations < 10ms."""
        points = [CurvePoint(t=i / 63, v=(i / 63) ** 2) for i in range(64)]

        start = time.perf_counter()
        for _ in range(1000):
            interpolate_linear(points, 0.5)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 10.0, f"1000 interpolations took {elapsed_ms:.2f}ms (should be < 10ms)"
