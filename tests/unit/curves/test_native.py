"""Tests for native curve specification and tuning."""

from __future__ import annotations

from twinklr.core.curves.native import (
    NativeCurveType,
    xLightsNativeCurve,
)

# Skip trivial enum tests


class TestXLightsNativeCurve:
    """Tests for xLightsNativeCurve model."""

    def test_valid_curve_creation(self) -> None:
        """Valid curve is created with defaults."""
        curve = xLightsNativeCurve(type=NativeCurveType.SINE)
        assert curve.type == NativeCurveType.SINE
        assert curve.p1 == 0.0
        assert curve.p2 == 0.0
        assert curve.p3 == 0.0
        assert curve.p4 == 0.0
        assert curve.reverse is False
        assert curve.min_val == 0
        assert curve.max_val == 255

    def test_curve_with_parameters(self) -> None:
        """Curve is created with custom parameters."""
        curve = xLightsNativeCurve(
            type=NativeCurveType.SINE,
            p1=10.0,
            p2=100.0,
            p3=50.0,
            p4=128.0,
            reverse=True,
            min_val=10,
            max_val=200,
        )
        assert curve.p1 == 10.0
        assert curve.p2 == 100.0
        assert curve.p3 == 50.0
        assert curve.p4 == 128.0
        assert curve.reverse is True
        assert curve.min_val == 10
        assert curve.max_val == 200

    def test_to_xlights_string_basic(self) -> None:
        """to_xlights_string produces correct format."""
        curve = xLightsNativeCurve(type=NativeCurveType.SINE)
        result = curve.to_xlights_string(channel=1)
        assert "Active=TRUE" in result
        assert "Id=ID_VALUECURVE_DMX1" in result
        assert "Type=Sine" in result
        assert "Min=0" in result
        assert "Max=255" in result
        assert "RV=FALSE" in result

    def test_to_xlights_string_with_parameters(self) -> None:
        """to_xlights_string includes non-zero parameters."""
        curve = xLightsNativeCurve(
            type=NativeCurveType.SINE,
            p1=10.0,
            p2=100.0,
            reverse=True,
        )
        result = curve.to_xlights_string(channel=2)
        assert "P1=10.00" in result
        assert "P2=100.00" in result
        assert "RV=TRUE" in result
        assert "Id=ID_VALUECURVE_DMX2" in result
