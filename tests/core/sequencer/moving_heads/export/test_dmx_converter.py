"""Tests for Curve to DMX Converter.

Tests for converting normalized curves to absolute DMX values,
handling both offset-centered and absolute curve modes.
"""


from blinkb0t.core.curves.models import CurvePoint, PointsCurve
from blinkb0t.core.sequencer.moving_heads.export.dmx_converter import (
    DMXCurve,
    DMXPoint,
    convert_absolute,
    convert_offset_centered,
    convert_segment_to_dmx,
)
from blinkb0t.core.sequencer.moving_heads.models.channel import ChannelName
from blinkb0t.core.sequencer.moving_heads.models.ir import ChannelSegment

# =============================================================================
# Tests for Offset-Centered Conversion
# =============================================================================


class TestOffsetCentered:
    """Tests for offset-centered curve conversion."""

    def test_center_value_returns_base(self) -> None:
        """Test that v=0.5 returns base_dmx."""
        result = convert_offset_centered(
            value=0.5,
            base_dmx=128,
            amplitude_dmx=64,
        )
        assert result == 128

    def test_max_value_returns_base_plus_half_amplitude(self) -> None:
        """Test that v=1.0 returns base + amplitude/2."""
        result = convert_offset_centered(
            value=1.0,
            base_dmx=128,
            amplitude_dmx=64,
        )
        # 128 + (1.0 - 0.5) * 64 = 128 + 32 = 160
        assert result == 160

    def test_min_value_returns_base_minus_half_amplitude(self) -> None:
        """Test that v=0.0 returns base - amplitude/2."""
        result = convert_offset_centered(
            value=0.0,
            base_dmx=128,
            amplitude_dmx=64,
        )
        # 128 + (0.0 - 0.5) * 64 = 128 - 32 = 96
        assert result == 96

    def test_clamping_upper(self) -> None:
        """Test that values are clamped to clamp_max."""
        result = convert_offset_centered(
            value=1.0,
            base_dmx=250,
            amplitude_dmx=100,
            clamp_max=255,
        )
        # 250 + 50 = 300 -> clamped to 255
        assert result == 255

    def test_clamping_lower(self) -> None:
        """Test that values are clamped to clamp_min."""
        result = convert_offset_centered(
            value=0.0,
            base_dmx=20,
            amplitude_dmx=100,
            clamp_min=0,
        )
        # 20 - 50 = -30 -> clamped to 0
        assert result == 0

    def test_custom_clamp_range(self) -> None:
        """Test custom clamp range."""
        result = convert_offset_centered(
            value=1.0,
            base_dmx=200,
            amplitude_dmx=100,
            clamp_min=50,
            clamp_max=200,
        )
        # 200 + 50 = 250 -> clamped to 200
        assert result == 200


# =============================================================================
# Tests for Absolute Conversion
# =============================================================================


class TestAbsolute:
    """Tests for absolute curve conversion."""

    def test_min_value_returns_clamp_min(self) -> None:
        """Test that v=0.0 returns clamp_min."""
        result = convert_absolute(
            value=0.0,
            clamp_min=0,
            clamp_max=255,
        )
        assert result == 0

    def test_max_value_returns_clamp_max(self) -> None:
        """Test that v=1.0 returns clamp_max."""
        result = convert_absolute(
            value=1.0,
            clamp_min=0,
            clamp_max=255,
        )
        assert result == 255

    def test_mid_value_returns_midpoint(self) -> None:
        """Test that v=0.5 returns midpoint."""
        result = convert_absolute(
            value=0.5,
            clamp_min=0,
            clamp_max=255,
        )
        # lerp(0, 255, 0.5) = 127.5 -> 127
        assert result == 127

    def test_custom_range(self) -> None:
        """Test custom clamp range."""
        result = convert_absolute(
            value=0.5,
            clamp_min=100,
            clamp_max=200,
        )
        # lerp(100, 200, 0.5) = 150
        assert result == 150

    def test_clamping_above_one(self) -> None:
        """Test that v > 1.0 is clamped."""
        result = convert_absolute(
            value=1.5,
            clamp_min=0,
            clamp_max=255,
        )
        assert result == 255

    def test_clamping_below_zero(self) -> None:
        """Test that v < 0.0 is clamped."""
        result = convert_absolute(
            value=-0.5,
            clamp_min=0,
            clamp_max=255,
        )
        assert result == 0


# =============================================================================
# Tests for DMXCurve
# =============================================================================


class TestDMXCurve:
    """Tests for DMXCurve model."""

    def test_create_dmx_curve(self) -> None:
        """Test creating DMX curve."""
        points = [
            DMXPoint(t=0.0, v=0),
            DMXPoint(t=0.5, v=128),
            DMXPoint(t=1.0, v=255),
        ]
        curve = DMXCurve(points=points)
        assert len(curve.points) == 3

    def test_to_xlights_string(self) -> None:
        """Test conversion to xLights format string."""
        points = [
            DMXPoint(t=0.0, v=0),
            DMXPoint(t=0.5, v=128),
            DMXPoint(t=1.0, v=255),
        ]
        curve = DMXCurve(points=points)
        result = curve.to_xlights_string(channel=11)

        assert "Type=Custom" in result
        assert "Active=TRUE" in result
        assert "DMX11" in result
        # Values should be normalized to 0-1 on 255 scale
        assert "Values=" in result


# =============================================================================
# Tests for Segment Conversion
# =============================================================================


class TestSegmentConversion:
    """Tests for converting IR segments to DMX curves."""

    def test_convert_static_segment(self) -> None:
        """Test converting static segment."""
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.DIMMER,
            t0_ms=0,
            t1_ms=1000,
            static_dmx=200,
        )
        result = convert_segment_to_dmx(segment)

        # Static segment should produce flat curve at static_dmx
        assert len(result.points) == 2
        assert all(p.v == 200 for p in result.points)

    def test_convert_absolute_curve_segment(self) -> None:
        """Test converting absolute curve segment (dimmer)."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.5, v=0.5),
            CurvePoint(t=1.0, v=1.0),
        ]
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.DIMMER,
            t0_ms=0,
            t1_ms=1000,
            curve=PointsCurve(points=points),
            offset_centered=False,
            clamp_min=0,
            clamp_max=255,
        )
        result = convert_segment_to_dmx(segment)

        # Values should be lerped to DMX range
        assert result.points[0].v == 0
        assert result.points[1].v == 127  # lerp(0, 255, 0.5)
        assert result.points[2].v == 255

    def test_convert_offset_centered_segment(self) -> None:
        """Test converting offset-centered segment (pan/tilt)."""
        points = [
            CurvePoint(t=0.0, v=0.5),  # center
            CurvePoint(t=0.5, v=1.0),  # max
            CurvePoint(t=1.0, v=0.0),  # min
        ]
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.PAN,
            t0_ms=0,
            t1_ms=1000,
            curve=PointsCurve(points=points),
            offset_centered=True,
            base_dmx=128,
            amplitude_dmx=64,
        )
        result = convert_segment_to_dmx(segment)

        # v=0.5 -> 128
        assert result.points[0].v == 128
        # v=1.0 -> 128 + 32 = 160
        assert result.points[1].v == 160
        # v=0.0 -> 128 - 32 = 96
        assert result.points[2].v == 96

    def test_time_values_preserved(self) -> None:
        """Test that time values are preserved in conversion."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=0.25, v=0.5),
            CurvePoint(t=0.75, v=0.5),
            CurvePoint(t=1.0, v=1.0),
        ]
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.DIMMER,
            t0_ms=0,
            t1_ms=1000,
            curve=PointsCurve(points=points),
        )
        result = convert_segment_to_dmx(segment)

        assert result.points[0].t == 0.0
        assert result.points[1].t == 0.25
        assert result.points[2].t == 0.75
        assert result.points[3].t == 1.0

    def test_clamping_applied(self) -> None:
        """Test that clamping is applied during conversion."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.DIMMER,
            t0_ms=0,
            t1_ms=1000,
            curve=PointsCurve(points=points),
            clamp_min=50,
            clamp_max=200,
        )
        result = convert_segment_to_dmx(segment)

        # v=0.0 -> lerp(50, 200, 0) = 50
        assert result.points[0].v == 50
        # v=1.0 -> lerp(50, 200, 1) = 200
        assert result.points[1].v == 200


# =============================================================================
# Tests for Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in DMX conversion."""

    def test_two_point_curve(self) -> None:
        """Test conversion of minimal two-point curve."""
        points = [
            CurvePoint(t=0.0, v=0.5),
            CurvePoint(t=1.0, v=0.5),
        ]
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.DIMMER,
            t0_ms=0,
            t1_ms=1000,
            curve=PointsCurve(points=points),
        )
        result = convert_segment_to_dmx(segment)
        assert len(result.points) == 2

    def test_max_dmx_range(self) -> None:
        """Test conversion with full DMX range."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.DIMMER,
            t0_ms=0,
            t1_ms=1000,
            curve=PointsCurve(points=points),
            clamp_min=0,
            clamp_max=255,
        )
        result = convert_segment_to_dmx(segment)

        assert result.points[0].v == 0
        assert result.points[1].v == 255

    def test_zero_amplitude(self) -> None:
        """Test offset-centered with zero amplitude."""
        points = [
            CurvePoint(t=0.0, v=0.0),
            CurvePoint(t=1.0, v=1.0),
        ]
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.PAN,
            t0_ms=0,
            t1_ms=1000,
            curve=PointsCurve(points=points),
            offset_centered=True,
            base_dmx=128,
            amplitude_dmx=0,
        )
        result = convert_segment_to_dmx(segment)

        # All values should be base_dmx when amplitude is 0
        assert all(p.v == 128 for p in result.points)
