"""Tests for curve semantics helpers."""

from __future__ import annotations

import pytest

from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.semantics import center_curve, ensure_loop_ready

# Skip trivial enum tests


class TestCenterCurve:
    """Tests for center_curve function."""

    def test_center_normalizes_range(self) -> None:
        """Centers values so midpoint maps to 0.5."""
        points = [
            CurvePoint(t=0.0, v=0.2),
            CurvePoint(t=0.5, v=0.6),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = center_curve(points)
        # min=0.2, max=1.0, range=0.8
        # Normalized: (0.2-0.2)/0.8=0, (0.6-0.2)/0.8=0.5, (1.0-0.2)/0.8=1.0
        assert result[0].v == pytest.approx(0.0)
        assert result[1].v == pytest.approx(0.5)
        assert result[2].v == pytest.approx(1.0)

    def test_center_constant_curve_maps_to_half(self) -> None:
        """Constant curve values all map to 0.5."""
        points = [
            CurvePoint(t=0.0, v=0.3),
            CurvePoint(t=0.5, v=0.3),
            CurvePoint(t=1.0, v=0.3),
        ]
        result = center_curve(points)
        for p in result:
            assert p.v == pytest.approx(0.5)

    def test_center_empty_raises(self) -> None:
        """Empty list raises ValueError."""
        with pytest.raises(ValueError, match="points cannot be empty"):
            center_curve([])

    def test_empty_raises(self) -> None:
        """Empty list raises ValueError."""
        with pytest.raises(ValueError, match="points cannot be empty"):
            ensure_loop_ready([])

    def test_invalid_mode_raises(self, non_loop_ready_points: list[CurvePoint]) -> None:
        """Invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="mode must be"):
            ensure_loop_ready(non_loop_ready_points, mode="invalid")

    def test_tolerance_parameter(self) -> None:
        """Tolerance parameter controls alignment check."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=0.0001),
        ]
        result_strict = ensure_loop_ready(points, tolerance=1e-6)
        result_relaxed = ensure_loop_ready(points, tolerance=1e-3)
        # Strict tolerance adjusts value, relaxed tolerance keeps original
        assert result_strict[-1].v == pytest.approx(0.0)
        assert result_relaxed[-1].v == pytest.approx(0.0001)

    def test_append_when_last_t_near_one(self) -> None:
        """When last t is near 1.0, replaces last point instead of adding."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=0.9999, v=1.0),  # Very close to 1.0
        ]
        result = ensure_loop_ready(points, mode="append", tolerance=1e-3)
        # Should replace last point, not add new one
        assert len(result) == 3
        assert result[-1].v == pytest.approx(0.0)
