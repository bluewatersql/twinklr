"""Tests for curve models."""

from __future__ import annotations

from twinklr.core.curves.models import CurvePoint, PointsCurve


class TestCurvePoint:
    """Tests for CurvePoint model."""

    def test_equal_t_values_allowed(self) -> None:
        """Equal consecutive t values are allowed (non-decreasing)."""
        curve = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.0),
                CurvePoint(t=0.5, v=0.3),
                CurvePoint(t=0.5, v=0.7),  # Same t is allowed
                CurvePoint(t=1.0, v=1.0),
            ]
        )
        assert len(curve.points) == 4

    def test_kind_discriminator_is_points(self) -> None:
        """Kind field is always 'POINTS'."""
        curve = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.0),
                CurvePoint(t=1.0, v=1.0),
            ]
        )
        assert curve.kind == "POINTS"


class TestNativeCurve:
    """Tests for NativeCurve model."""
