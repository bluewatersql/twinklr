"""Tests for DMX conversion helpers."""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.dmx_conversion import scale_curve_to_dmx_range
from blinkb0t.core.curves.models import CurvePoint


class TestScaleCurveToDmxRange:
    """Tests for scale_curve_to_dmx_range function."""

    def test_full_range_conversion(self) -> None:
        """Full range [0, 255] conversion."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = scale_curve_to_dmx_range(points, clamp_min=0.0, clamp_max=255.0)
        assert result[0].v == pytest.approx(0.0)
        assert result[1].v == pytest.approx(1.0)

    def test_partial_range_conversion(self) -> None:
        """Partial range conversion scales values."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = scale_curve_to_dmx_range(points, clamp_min=50.0, clamp_max=200.0)
        # v=0 -> 50, v=1 -> 200
        assert result[0].v == pytest.approx(50.0 / 255.0)
        assert result[1].v == pytest.approx(200.0 / 255.0)

    def test_midpoint_conversion(self) -> None:
        """Midpoint value is scaled correctly."""
        points = [
            CurvePoint(t=0.5, v=0.5),
        ]
        result = scale_curve_to_dmx_range(points, clamp_min=0.0, clamp_max=200.0)
        # v=0.5 -> 0 + 0.5 * 200 = 100
        assert result[0].v == pytest.approx(100.0 / 255.0)

    def test_clamp_min_enforced(self) -> None:
        """Result is clamped to clamp_min."""
        points = [
            CurvePoint(t=0.0, v=0.0),
        ]
        result = scale_curve_to_dmx_range(points, clamp_min=50.0, clamp_max=200.0)
        # v=0 -> min + 0*range = 50
        assert result[0].v == pytest.approx(50.0 / 255.0)

    def test_clamp_max_enforced(self) -> None:
        """Result is clamped to clamp_max."""
        points = [
            CurvePoint(t=0.0, v=1.0),
        ]
        result = scale_curve_to_dmx_range(points, clamp_min=50.0, clamp_max=200.0)
        # v=1 -> min + 1*range = 200
        assert result[0].v == pytest.approx(200.0 / 255.0)

    def test_preserves_time_values(self) -> None:
        """Time values are preserved."""
        points = [
            CurvePoint(t=0.0, v=0.5),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=1.0, v=0.5),
        ]
        result = scale_curve_to_dmx_range(points, clamp_min=0.0, clamp_max=255.0)
        assert result[0].t == 0.0
        assert result[1].t == 0.5
        assert result[2].t == 1.0

    def test_output_normalized_to_01(self) -> None:
        """Output values are normalized to [0, 1]."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=1.0, v=1.0),
        ]
        result = scale_curve_to_dmx_range(points, clamp_min=0.0, clamp_max=255.0)
        for p in result:
            assert 0.0 <= p.v <= 1.0

    def test_empty_list_returns_empty(self) -> None:
        """Empty input returns empty output."""
        result = scale_curve_to_dmx_range([], clamp_min=0.0, clamp_max=255.0)
        assert result == []

    def test_constant_curve(self) -> None:
        """Constant curve produces constant output."""
        points = [
            CurvePoint(t=0.0, v=0.5),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=1.0, v=0.5),
        ]
        result = scale_curve_to_dmx_range(points, clamp_min=0.0, clamp_max=200.0)
        expected = 100.0 / 255.0  # 0 + 0.5 * 200 = 100
        for p in result:
            assert p.v == pytest.approx(expected)
