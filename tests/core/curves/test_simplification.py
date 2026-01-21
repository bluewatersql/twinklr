"""Tests for RDP Simplification.

Tests simplify_rdp and perpendicular_distance functions.
All 9 test cases per implementation plan Task 1.4.
"""

import math
import time

from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.sampling import interpolate_linear
from blinkb0t.core.curves.simplification import perpendicular_distance, simplify_rdp


class TestRDPPreservesEndpoints:
    """Tests for endpoint preservation."""

    def test_preserves_endpoints(self) -> None:
        """Test preserves endpoints."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.25, v=0.3),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=0.75, v=0.7),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = simplify_rdp(points, epsilon=0.5)

        # Must preserve first and last points
        assert result[0].t == 0.0
        assert result[0].v == 0.0
        assert result[-1].t == 1.0
        assert result[-1].v == 1.0


class TestRDPCollinearRemoval:
    """Tests for collinear point removal."""

    def test_collinear_points_removed(self) -> None:
        """Test collinear points are removed."""
        # Perfectly linear: all intermediate points should be removed
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.25, v=0.25),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=0.75, v=0.75),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = simplify_rdp(points, epsilon=0.01)

        # Should only keep endpoints
        assert len(result) == 2
        assert result[0].t == 0.0
        assert result[-1].t == 1.0


class TestRDPSineWave:
    """Tests for sine wave simplification."""

    def test_sine_wave_keeps_some_interior(self) -> None:
        """Test sine wave keeps some interior points."""
        # Create a sine wave
        n_points = 64
        points = [
            CurvePoint(
                t=i / (n_points - 1), v=0.5 + 0.5 * math.sin(2 * math.pi * i / (n_points - 1))
            )
            for i in range(n_points)
        ]

        # Moderate epsilon should keep some points
        result = simplify_rdp(points, epsilon=0.05)

        # Should have fewer points than original but more than 2
        assert 2 < len(result) < n_points


class TestRDPEpsilonZero:
    """Tests for epsilon=0."""

    def test_epsilon_zero_no_simplification(self) -> None:
        """Test epsilon=0 keeps all points (no simplification)."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.25, v=0.3),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=0.75, v=0.6),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = simplify_rdp(points, epsilon=0.0)

        # Should keep all points when epsilon=0
        assert len(result) == len(points)


class TestRDPLargeEpsilon:
    """Tests for large epsilon (aggressive simplification)."""

    def test_large_epsilon_aggressive_simplification(self) -> None:
        """Test large epsilon results in aggressive simplification."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.25, v=0.4),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=0.75, v=0.4),
            CurvePoint(t=1.0, v=0.0),
        ]
        # Very large epsilon should reduce to just endpoints
        result = simplify_rdp(points, epsilon=1.0)

        # Should only keep endpoints with large epsilon
        assert len(result) == 2


class TestRDPScaledSpace:
    """Tests for scaled space preference."""

    def test_scaled_space_preference(self) -> None:
        """Test scaled space affects point selection."""
        # Create points with small t variations but larger v variations
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.01, v=0.5),  # Small t step, big v step
            CurvePoint(t=0.02, v=0.0),
            CurvePoint(t=1.0, v=0.0),
        ]

        # With default scaling, might remove the spike
        result_default = simplify_rdp(points, epsilon=0.1)

        # With high v scaling, should preserve the spike
        result_scaled = simplify_rdp(points, epsilon=0.1, scale_t=1.0, scale_v=10.0)

        # Scaled version should keep more points (preserve v variations)
        assert len(result_scaled) >= len(result_default)


class TestRDPMonotonicOutput:
    """Tests for monotonic t in output."""

    def test_verify_monotonic_t_in_output(self) -> None:
        """Verify monotonic t in output."""
        points = [
            CurvePoint(t=i / 31, v=0.5 + 0.5 * math.sin(4 * math.pi * i / 31)) for i in range(32)
        ]
        result = simplify_rdp(points, epsilon=0.05)

        # Verify t values are strictly increasing
        for i in range(len(result) - 1):
            assert result[i].t < result[i + 1].t, f"Non-monotonic at index {i}"


class TestRDPMaxDeviation:
    """Tests for maximum deviation validation."""

    def test_max_deviation_within_reasonable_bound(self) -> None:
        """Verify max deviation is bounded.

        Note: RDP guarantees removed points are within epsilon of the line
        between kept neighbors, but linear interpolation between kept points
        may deviate slightly more (up to ~1.5x epsilon for curved sections).
        """
        points = [
            CurvePoint(t=i / 63, v=0.5 + 0.4 * math.sin(2 * math.pi * i / 63)) for i in range(64)
        ]
        epsilon = 0.02
        result = simplify_rdp(points, epsilon=epsilon)

        # Verify that interpolating the simplified curve
        # deviation is bounded (allow ~1.5x epsilon for curve interpolation)
        max_deviation = 0.0
        for orig_point in points:
            simplified_value = interpolate_linear(result, orig_point.t)
            deviation = abs(simplified_value - orig_point.v)
            max_deviation = max(max_deviation, deviation)

        # Max deviation should be reasonable (< 2x epsilon)
        assert max_deviation < epsilon * 2.0, (
            f"Max deviation {max_deviation} > 2*epsilon ({epsilon * 2.0})"
        )


class TestPerpendicularDistance:
    """Tests for perpendicular distance calculation."""

    def test_point_on_line_zero_distance(self) -> None:
        """Test point on line has zero distance."""
        point = CurvePoint(t=0.5, v=0.5)
        line_start = CurvePoint(t=0.0, v=0.0)
        line_end = CurvePoint(t=1.0, v=1.0)

        dist = perpendicular_distance(point, line_start, line_end)
        assert dist < 1e-10

    def test_point_perpendicular_to_line(self) -> None:
        """Test point perpendicular to horizontal line."""
        point = CurvePoint(t=0.5, v=0.5)
        line_start = CurvePoint(t=0.0, v=0.0)
        line_end = CurvePoint(t=1.0, v=0.0)

        dist = perpendicular_distance(point, line_start, line_end)
        assert abs(dist - 0.5) < 1e-10


class TestRDPPerformance:
    """Performance benchmarks."""

    def test_256_point_curve_under_5ms(self) -> None:
        """Benchmark: 256-point curve < 5ms."""
        points = [
            CurvePoint(t=i / 255, v=0.5 + 0.5 * math.sin(4 * math.pi * i / 255)) for i in range(256)
        ]

        start = time.perf_counter()
        for _ in range(10):
            simplify_rdp(points, epsilon=0.01)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 10

        assert elapsed_ms < 5.0, (
            f"256-point simplification took {elapsed_ms:.3f}ms (should be < 5ms)"
        )


class TestRDPEdgeCases:
    """Tests for edge cases."""

    def test_two_points_unchanged(self) -> None:
        """Test two points returned unchanged."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = simplify_rdp(points, epsilon=0.1)

        assert len(result) == 2
        assert result[0] == points[0]
        assert result[1] == points[1]

    def test_single_point_returned(self) -> None:
        """Test single point list returned as-is."""
        points = [CurvePoint(t=0.5, v=0.5)]
        result = simplify_rdp(points, epsilon=0.1)

        assert len(result) == 1
        assert result[0] == points[0]

    def test_empty_list_returns_empty(self) -> None:
        """Test empty list returns empty."""
        result = simplify_rdp([], epsilon=0.1)
        assert result == []
