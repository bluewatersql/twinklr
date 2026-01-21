"""Tests for xLights custom curve adapter.

V2 Behavior:
- CurvePoints contain DMX values (0-255 or 0-65535)
- xLights adapter normalizes DMX to [0-1] for output
- xLights uses Min/Max fields to scale back when rendering
"""

from __future__ import annotations

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import (
    CustomCurveSpec,
    XLightsAdapter,
)
from blinkb0t.core.domains.sequencing.models.curves import CurvePoint, ValueCurveSpec


class TestCustomCurveSpec:
    """Tests for CustomCurveSpec class."""

    def test_init_valid(self) -> None:
        """Test successful initialization with valid points."""
        points = [CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=255.0)]
        spec = CustomCurveSpec(points, min_val=0, max_val=255)

        assert spec.points == points
        assert spec.min_val == 0
        assert spec.max_val == 255

    def test_init_empty_points_error(self) -> None:
        """Test that empty points list raises error."""
        with pytest.raises(ValueError, match="at least one point"):
            CustomCurveSpec([], min_val=0, max_val=255)

    def test_init_invalid_range_error(self) -> None:
        """Test that min >= max raises error."""
        points = [CurvePoint(time=0.0, value=0.0)]

        with pytest.raises(ValueError, match="must be less than"):
            CustomCurveSpec(points, min_val=255, max_val=0)

        with pytest.raises(ValueError, match="must be less than"):
            CustomCurveSpec(points, min_val=100, max_val=100)

    def test_to_xlights_string_basic(self) -> None:
        """Test basic xLights string generation."""
        # In V2, points contain DMX values that get normalized to [0-1] for xLights
        points = [
            CurvePoint(time=0.0, value=0.0),  # DMX 0 → normalized 0.00
            CurvePoint(time=0.5, value=127.5),  # DMX 127.5 → normalized 0.50
            CurvePoint(time=1.0, value=255.0),  # DMX 255 → normalized 1.00
        ]
        spec = CustomCurveSpec(points, min_val=0, max_val=255)

        result = spec.to_xlights_string(11)

        # Verify format structure
        assert result.startswith("Active=TRUE|")
        assert "Id=ID_VALUECURVE_DMX11|" in result
        assert "Type=Custom|" in result
        assert "Min=0.00|Max=255.00|" in result
        assert "Values=" in result
        assert result.endswith("|")

        # V2 format: time:normalized_value pairs separated by semicolons
        # DMX values are normalized to [0-1] scale: value/255
        # Time uses 4 decimal places for precision, value uses 2
        assert "Values=0.0000:0.00;0.5000:0.50;1.0000:1.00|" in result

    def test_to_xlights_string_different_channel(self) -> None:
        """Test xLights string with different channel number."""
        points = [CurvePoint(time=0.0, value=0.0)]
        spec = CustomCurveSpec(points)

        result = spec.to_xlights_string(42)

        assert "Id=ID_VALUECURVE_DMX42|" in result

    def test_to_xlights_string_custom_dmx_range(self) -> None:
        """Test xLights string with custom DMX range."""
        # Points contain DMX values
        points = [
            CurvePoint(time=0.0, value=50.0),  # DMX 50 → 50/255 = 0.20
            CurvePoint(time=0.5, value=125.0),  # DMX 125 → 125/255 = 0.49
            CurvePoint(time=1.0, value=200.0),  # DMX 200 → 200/255 = 0.78
        ]
        spec = CustomCurveSpec(points, min_val=50, max_val=200)

        result = spec.to_xlights_string(11)

        # Min/Max in output are always 0-255 (xLights standard)
        assert "Min=0.00|Max=255.00|" in result
        # Values are normalized and truncated (not rounded): 50/255≈0.196→0.19, 125/255≈0.490→0.49, 200/255≈0.784→0.78
        # Time uses 4 decimal places for precision
        assert "Values=0.0000:0.19;0.5000:0.49;1.0000:0.78|" in result

    def test_to_xlights_string_many_points(self) -> None:
        """Test xLights string with many points."""
        import math

        # 100 points - sine wave in DMX space [0, 255]
        points = [
            CurvePoint(
                time=i / 99,
                value=(math.sin(i / 99 * 2 * math.pi) + 1) / 2 * 255,  # DMX value
            )
            for i in range(100)
        ]
        spec = CustomCurveSpec(points, min_val=0, max_val=255)

        result = spec.to_xlights_string(11)

        # Verify structure
        assert "Type=Custom|" in result
        assert "Values=" in result
        assert result.endswith("|")

        # Count semicolon-separated time:value pairs (should be 100)
        values_part = result.split("Values=")[1].rstrip("|")
        pairs = values_part.split(";")
        assert len(pairs) == 100

        # Each pair should be "time:value" format
        for pair in pairs:
            assert ":" in pair
            time_str, value_str = pair.split(":")
            time_val = float(time_str)
            value_val = float(value_str)
            assert 0.0 <= time_val <= 1.0
            assert 0.0 <= value_val <= 1.0


class TestXLightsAdapter:
    """Tests for XLightsAdapter class."""

    def test_native_to_xlights(self) -> None:
        """Test native curve conversion."""
        spec = ValueCurveSpec(type=NativeCurveType.SINE, p1=128.0, p2=60.0, min_val=0, max_val=255)

        result = XLightsAdapter.native_to_xlights(spec, 11)

        # Verify it calls the spec's to_xlights_string method
        assert "Active=TRUE" in result
        assert "Id=ID_VALUECURVE_DMX11" in result
        assert "Type=Sine" in result  # Title case for xLights output
        assert "P1=128.00" in result
        assert "P2=60.00" in result

    def test_custom_to_xlights_basic(self) -> None:
        """Test custom curve conversion."""
        # Points contain DMX values
        points = [
            CurvePoint(time=0.0, value=0.0),  # DMX 0 → 0/255 = 0.00
            CurvePoint(time=1.0, value=255.0),  # DMX 255 → 255/255 = 1.00
        ]

        result = XLightsAdapter.custom_to_xlights(points, 11, dmx_min=0, dmx_max=255)

        assert "Active=TRUE" in result
        assert "Id=ID_VALUECURVE_DMX11" in result
        assert "Type=Custom" in result
        assert "Values=0.0000:0.00;1.0000:1.00|" in result

    def test_custom_to_xlights_with_range(self) -> None:
        """Test custom curve conversion with custom DMX range."""
        # Points contain DMX values in range [75, 200]
        points = [
            CurvePoint(time=0.0, value=75.0),  # DMX 75 → 75/255 = 0.29
            CurvePoint(time=0.5, value=137.5),  # DMX 137.5 → 137.5/255 = 0.54
            CurvePoint(time=1.0, value=200.0),  # DMX 200 → 200/255 = 0.78
        ]

        result = XLightsAdapter.custom_to_xlights(points, 11, dmx_min=75, dmx_max=200)

        assert "Active=TRUE" in result
        assert "Type=Custom" in result
        # Values are normalized and truncated (not rounded): 75/255≈0.294→0.29, 137.5/255≈0.539→0.53, 200/255≈0.784→0.78
        assert "Values=0.0000:0.29;0.5000:0.53;1.0000:0.78|" in result

    def test_format_curve_string_native(self) -> None:
        """Test format_curve_string with native curve."""
        spec = ValueCurveSpec(type=NativeCurveType.RAMP, p1=10.0, p2=255.0)

        result = XLightsAdapter.format_curve_string("native", spec, 11)

        assert "Type=Ramp" in result
        assert "P1=10.00" in result
        assert "P2=255.00" in result

    def test_format_curve_string_custom(self) -> None:
        """Test format_curve_string with custom curve."""
        points = [
            CurvePoint(time=0.0, value=0.0),
            CurvePoint(time=1.0, value=255.0),
        ]

        result = XLightsAdapter.format_curve_string("custom", points, 11, dmx_min=0, dmx_max=255)

        assert "Type=Custom" in result
        assert "Values=" in result

    def test_format_curve_string_invalid_type(self) -> None:
        """Test format_curve_string with invalid curve type."""
        points = [CurvePoint(time=0.0, value=0.0)]

        with pytest.raises(ValueError, match="Unknown curve type"):
            XLightsAdapter.format_curve_string("invalid", points, 11)

    def test_format_curve_string_type_mismatch(self) -> None:
        """Test format_curve_string with mismatched type and spec."""
        spec = ValueCurveSpec(type=NativeCurveType.SINE)

        # Passing ValueCurveSpec to custom curve
        with pytest.raises(ValueError, match="Custom curve requires list"):
            XLightsAdapter.format_curve_string("custom", spec, 11)  # type: ignore

        # Passing list to native curve
        points = [CurvePoint(time=0.0, value=0.0)]
        with pytest.raises(ValueError, match="Native curve requires ValueCurveSpec"):
            XLightsAdapter.format_curve_string("native", points, 11)  # type: ignore


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""

    def test_bounce_curve_integration(self) -> None:
        """Test bounce curve end-to-end."""
        # Simulated bounce curve in DMX space [50, 190]
        points = [
            CurvePoint(time=0.0, value=50.0),
            CurvePoint(time=0.2, value=190.0),  # Peak
            CurvePoint(time=0.4, value=80.0),  # Bounce
            CurvePoint(time=0.6, value=150.0),  # Second peak
            CurvePoint(time=0.8, value=100.0),  # Settle
            CurvePoint(time=1.0, value=120.0),  # Final
        ]

        spec = CustomCurveSpec(points, min_val=50, max_val=190)
        result = spec.to_xlights_string(13)

        assert "Type=Custom" in result
        assert "Values=" in result
        # Verify it's semicolon-separated time:value pairs
        values_str = result.split("Values=")[1].rstrip("|")
        pairs = values_str.split(";")
        assert len(pairs) == 6

    def test_lissajous_curve_integration(self) -> None:
        """Test Lissajous curve end-to-end."""
        import math

        # Complex Lissajous pattern in DMX space
        points = [
            CurvePoint(
                time=i / 49,
                value=127.5 + 100 * math.sin(3 * 2 * math.pi * i / 49),  # DMX value
            )
            for i in range(50)
        ]

        spec = CustomCurveSpec(points, min_val=0, max_val=255)
        result = spec.to_xlights_string(11)

        assert "Type=Custom" in result
        # Verify all values are normalized [0-1]
        values_str = result.split("Values=")[1].rstrip("|")
        pairs = values_str.split(";")
        for pair in pairs:
            _, value_str = pair.split(":")
            value = float(value_str)
            assert 0.0 <= value <= 1.0

    def test_16bit_dmx_range(self) -> None:
        """Test 16-bit DMX range (0-65535)."""
        # Points in 16-bit DMX space
        points = [
            CurvePoint(time=0.0, value=0.0),
            CurvePoint(time=0.5, value=32767.5),  # Mid-point
            CurvePoint(time=1.0, value=65535.0),  # Max
        ]

        spec = CustomCurveSpec(points, min_val=0, max_val=65535)
        result = spec.to_xlights_string(11)

        # xLights always uses 255 scale for normalization
        # 0/255=0.00, 32767.5/255=128.50, 65535/255=257.00 (but we normalize correctly)
        assert "Type=Custom" in result
        assert "Values=" in result

    def test_partial_dmx_range(self) -> None:
        """Test partial DMX range (fixture-specific limits)."""
        # Restricted range [86, 170] for tilt
        points = [
            CurvePoint(time=0.0, value=86.0),
            CurvePoint(time=0.5, value=128.0),
            CurvePoint(time=1.0, value=170.0),
        ]

        spec = CustomCurveSpec(points, min_val=86, max_val=170)
        result = spec.to_xlights_string(13)

        # Normalized and truncated (not rounded): 86/255≈0.337→0.33, 128/255≈0.501→0.50, 170/255≈0.666→0.66
        assert "Values=0.0000:0.33;0.5000:0.50;1.0000:0.66|" in result
