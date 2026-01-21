"""Tests for NativeCurveFormatter adapter."""

from blinkb0t.core.domains.sequencing.infrastructure.curves.adapters.xlights_formatter import (
    NativeCurveFormatter,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec


def test_format_for_xlights_basic():
    """Test basic xLights string generation with RAMP curve."""
    spec = ValueCurveSpec(type=NativeCurveType.RAMP, p2=150.0)

    result = NativeCurveFormatter.format_for_xlights(spec, 11)

    assert (
        result == "Active=TRUE|Id=ID_VALUECURVE_DMX11|Type=Ramp|Min=0|Max=255|P2=150.00|RV=FALSE|"
    )


def test_format_for_xlights_different_channel():
    """Test xLights string with different channel number."""
    spec = ValueCurveSpec(type=NativeCurveType.SINE, p2=100.0, p4=128.0)

    result = NativeCurveFormatter.format_for_xlights(spec, 42)

    assert "Id=ID_VALUECURVE_DMX42|" in result
    assert "P2=100.00|" in result
    assert "P4=128.00|" in result


def test_format_for_xlights_reverse():
    """Test xLights string with reverse flag."""
    spec = ValueCurveSpec(type=NativeCurveType.RAMP, p2=150.0, reverse=True)

    result = NativeCurveFormatter.format_for_xlights(spec, 11)

    assert "RV=TRUE|" in result


def test_format_for_xlights_zero_params_omitted():
    """Test that zero parameters are omitted from output."""
    spec = ValueCurveSpec(type=NativeCurveType.FLAT, p1=100.0)

    result = NativeCurveFormatter.format_for_xlights(spec, 11)

    assert "P1=100.00|" in result
    # P2, P3, P4 should not appear since they're 0.0
    assert "P2=" not in result
    assert "P3=" not in result
    assert "P4=" not in result
