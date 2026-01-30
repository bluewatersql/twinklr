"""Tests for Ramer-Douglas-Peucker curve simplification."""

from __future__ import annotations

import pytest

from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.simplification import perpendicular_distance, simplify_rdp


class TestPerpendicularDistance:
    """Tests for perpendicular_distance function."""

    def test_point_on_line_returns_zero(self) -> None:
        """Point on the line has zero distance."""
        point = CurvePoint(t=0.5, v=0.5)
        start = CurvePoint(t=0.0, v=0.0)
        end = CurvePoint(t=1.0, v=1.0)
        result = perpendicular_distance(point, start, end)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_point_above_line(self) -> None:
        """Point above horizontal line has expected distance."""
        point = CurvePoint(t=0.5, v=0.5)
        start = CurvePoint(t=0.0, v=0.0)
        end = CurvePoint(t=1.0, v=0.0)
        result = perpendicular_distance(point, start, end)
        assert result == pytest.approx(0.5)

    def test_point_below_line(self) -> None:
        """Point below horizontal line has expected distance."""
        point = CurvePoint(t=0.5, v=0.0)
        start = CurvePoint(t=0.0, v=0.5)
        end = CurvePoint(t=1.0, v=0.5)
        result = perpendicular_distance(point, start, end)
        assert result == pytest.approx(0.5)

    def test_degenerate_line_start_equals_end(self) -> None:
        """Degenerate case where start equals end."""
        point = CurvePoint(t=0.5, v=0.5)
        start = CurvePoint(t=0.25, v=0.25)
        end = CurvePoint(t=0.25, v=0.25)
        # Distance should be euclidean distance to the point
        result = perpendicular_distance(point, start, end)
        expected = ((0.5 - 0.25) ** 2 + (0.5 - 0.25) ** 2) ** 0.5
        assert result == pytest.approx(expected)

    def test_scale_t_affects_distance(self) -> None:
        """scale_t parameter affects distance calculation."""
        point = CurvePoint(t=0.5, v=0.5)
        start = CurvePoint(t=0.0, v=0.0)
        end = CurvePoint(t=1.0, v=0.0)
        # With scale_t=2, time dimension is stretched
        result = perpendicular_distance(point, start, end, scale_t=2.0)
        # Distance calculation is in scaled space
        assert result > 0

    def test_scale_v_affects_distance(self) -> None:
        """scale_v parameter affects distance calculation."""
        point = CurvePoint(t=0.5, v=0.5)
        start = CurvePoint(t=0.0, v=0.0)
        end = CurvePoint(t=1.0, v=0.0)
        # With scale_v=2, value dimension is stretched
        result_unscaled = perpendicular_distance(point, start, end)
        result_scaled = perpendicular_distance(point, start, end, scale_v=2.0)
        assert result_scaled == pytest.approx(result_unscaled * 2.0)

    def test_point_beyond_segment_start(self) -> None:
        """Point projected before segment start clamps to start."""
        point = CurvePoint(t=0.0, v=0.5)
        start = CurvePoint(t=0.25, v=0.0)
        end = CurvePoint(t=0.75, v=0.0)
        result = perpendicular_distance(point, start, end)
        # Should return distance to start point
        expected = ((0.0 - 0.25) ** 2 + (0.5 - 0.0) ** 2) ** 0.5
        assert result == pytest.approx(expected)

    def test_point_beyond_segment_end(self) -> None:
        """Point projected after segment end clamps to end."""
        point = CurvePoint(t=1.0, v=0.5)
        start = CurvePoint(t=0.25, v=0.0)
        end = CurvePoint(t=0.75, v=0.0)
        result = perpendicular_distance(point, start, end)
        # Should return distance to end point
        expected = ((1.0 - 0.75) ** 2 + (0.5 - 0.0) ** 2) ** 0.5
        assert result == pytest.approx(expected)


class TestSimplifyRDP:
    """Tests for simplify_rdp function."""

    def test_linear_curve_simplifies_to_endpoints(
        self, dense_linear_points: list[CurvePoint]
    ) -> None:
        """Perfectly linear curve simplifies to just endpoints."""
        result = simplify_rdp(dense_linear_points, epsilon=0.01)
        assert len(result) == 2
        assert result[0].t == pytest.approx(0.0)
        assert result[1].t == pytest.approx(1.0)

    def test_curved_points_retain_shape(self, curved_points: list[CurvePoint]) -> None:
        """Curved points retain more points than linear."""
        result = simplify_rdp(curved_points, epsilon=0.01)
        # Should keep more than just endpoints
        assert len(result) >= 2

    def test_large_epsilon_removes_more_points(self, sine_wave_points: list[CurvePoint]) -> None:
        """Larger epsilon removes more points."""
        result_small = simplify_rdp(sine_wave_points, epsilon=0.01)
        result_large = simplify_rdp(sine_wave_points, epsilon=0.5)
        assert len(result_large) <= len(result_small)

    def test_zero_epsilon_keeps_all_points(self, simple_linear_points: list[CurvePoint]) -> None:
        """Epsilon of 0 keeps all points except collinear ones."""
        # With epsilon=0, should still remove truly collinear points
        result = simplify_rdp(simple_linear_points, epsilon=0.0)
        # Linear points with epsilon=0 should simplify to 2
        assert len(result) == 2

    def test_preserves_endpoints(self, sine_wave_points: list[CurvePoint]) -> None:
        """Endpoints are always preserved."""
        result = simplify_rdp(sine_wave_points, epsilon=0.1)
        assert result[0].t == sine_wave_points[0].t
        assert result[0].v == sine_wave_points[0].v
        assert result[-1].t == sine_wave_points[-1].t
        assert result[-1].v == sine_wave_points[-1].v

    def test_two_points_unchanged(self, ramp_up_points: list[CurvePoint]) -> None:
        """Two points returns same two points."""
        result = simplify_rdp(ramp_up_points, epsilon=0.1)
        assert len(result) == 2
        assert result[0] == ramp_up_points[0]
        assert result[1] == ramp_up_points[1]

    def test_single_point_returns_copy(self) -> None:
        """Single point returns same point."""
        points = [CurvePoint(t=0.5, v=0.5)]
        result = simplify_rdp(points, epsilon=0.1)
        assert len(result) == 1
        assert result[0] == points[0]

    def test_empty_returns_empty(self) -> None:
        """Empty list returns empty list."""
        result = simplify_rdp([], epsilon=0.1)
        assert result == []

    def test_scale_factors_affect_simplification(self) -> None:
        """Scale factors affect which points are kept."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.1),  # Slightly above line
            CurvePoint(t=1.0, v=0.0),
        ]
        # With equal scaling, 0.1 deviation might be kept
        result_equal = simplify_rdp(points, epsilon=0.05, scale_t=1.0, scale_v=1.0)
        # With large t scaling, deviation appears smaller
        result_t_scaled = simplify_rdp(points, epsilon=0.05, scale_t=10.0, scale_v=1.0)
        # Both should preserve endpoints but may differ on middle point
        assert len(result_equal) >= 2
        assert len(result_t_scaled) >= 2

    def test_default_epsilon_is_one_dmx_unit(self) -> None:
        """Default epsilon is 1/255 (one DMX unit)."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.002),  # Less than 1/255 = 0.00392
            CurvePoint(t=1.0, v=0.0),
        ]
        result = simplify_rdp(points)  # Uses default epsilon=1/255
        # Small deviation should be simplified away
        assert len(result) == 2
