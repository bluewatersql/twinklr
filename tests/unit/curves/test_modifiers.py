"""Tests for curve modifiers."""

from __future__ import annotations

import pytest

from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.modifiers import (
    bounce_curve,
    mirror_curve,
    reverse_curve,
)

# Skip trivial enum tests


class TestReverseCurve:
    """Tests for reverse_curve function."""

    def test_reverses_time_values(self, ramp_up_points: list[CurvePoint]) -> None:
        """Reverses t values (1 - t) while preserving values."""
        result = reverse_curve(ramp_up_points)
        # Original ramp goes from (t=0,v=0) to (t=1,v=1)
        # After reverse: time flips but values stay, so (t=0,v=1) to (t=1,v=0)
        assert result[0].t == pytest.approx(0.0)
        assert result[0].v == pytest.approx(1.0)
        assert result[1].t == pytest.approx(1.0)
        assert result[1].v == pytest.approx(0.0)

    def test_mirrors_values_vertically(self, ramp_up_points: list[CurvePoint]) -> None:
        """Mirrors v values (1 - v) while preserving time."""
        result = mirror_curve(ramp_up_points)
        # Original ramp goes from (t=0,v=0) to (t=1,v=1)
        # After mirror: values flip but time stays, so (t=0,v=1) to (t=1,v=0)
        assert result[0].t == pytest.approx(0.0)
        assert result[0].v == pytest.approx(1.0)
        assert result[1].t == pytest.approx(1.0)
        assert result[1].v == pytest.approx(0.0)

    def test_bounce_transformation(self) -> None:
        """Bounce applies 1 - abs(v - 0.5) * 2 transformation."""
        points = [
            CurvePoint(t=0.0, v=0.0),  # 1 - abs(0-0.5)*2 = 1 - 1 = 0
            CurvePoint(t=0.5, v=0.5),  # 1 - abs(0.5-0.5)*2 = 1 - 0 = 1
            CurvePoint(t=1.0, v=1.0),  # 1 - abs(1-0.5)*2 = 1 - 1 = 0
        ]
        result = bounce_curve(points)
        assert result[0].v == pytest.approx(0.0)
        assert result[1].v == pytest.approx(1.0)
        assert result[2].v == pytest.approx(0.0)
