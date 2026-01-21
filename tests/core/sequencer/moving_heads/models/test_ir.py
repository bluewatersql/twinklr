"""Tests for IR Segment Model.

Tests ChannelSegment with all validators.
All 12 test cases per implementation plan Task 0.4.
"""

import json

from pydantic import ValidationError
import pytest

from blinkb0t.core.curves.models import CurvePoint, NativeCurve, PointsCurve
from blinkb0t.core.sequencer.moving_heads.models.channel import BlendMode, ChannelName
from blinkb0t.core.sequencer.moving_heads.models.ir import ChannelSegment


class TestChannelSegmentValidCreation:
    """Tests for valid ChannelSegment creation."""

    def test_static_dmx_segment_creation(self) -> None:
        """Test static DMX segment creation (valid)."""
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.PAN,
            t0_ms=0,
            t1_ms=2000,
            static_dmx=128,
        )
        assert segment.fixture_id == "fix1"
        assert segment.channel == ChannelName.PAN
        assert segment.t0_ms == 0
        assert segment.t1_ms == 2000
        assert segment.static_dmx == 128
        assert segment.curve is None

    def test_curve_segment_creation(self) -> None:
        """Test curve segment creation (valid)."""
        curve = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.0),
                CurvePoint(t=1.0, v=1.0),
            ]
        )
        segment = ChannelSegment(
            fixture_id="fix2",
            channel=ChannelName.DIMMER,
            t0_ms=1000,
            t1_ms=3000,
            curve=curve,
        )
        assert segment.fixture_id == "fix2"
        assert segment.curve is not None
        assert segment.static_dmx is None

    def test_offset_centered_curve_with_base_amplitude(self) -> None:
        """Test offset-centered curve with base/amplitude (valid)."""
        curve = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.5),
                CurvePoint(t=0.5, v=1.0),
                CurvePoint(t=1.0, v=0.5),
            ]
        )
        segment = ChannelSegment(
            fixture_id="fix3",
            channel=ChannelName.PAN,
            t0_ms=0,
            t1_ms=4000,
            curve=curve,
            offset_centered=True,
            base_dmx=128,
            amplitude_dmx=64,
        )
        assert segment.offset_centered is True
        assert segment.base_dmx == 128
        assert segment.amplitude_dmx == 64


class TestChannelSegmentValidation:
    """Tests for ChannelSegment validation."""

    def test_rejects_both_static_dmx_and_curve(self) -> None:
        """Test rejects both static_dmx and curve set."""
        curve = NativeCurve(curve_id="LINEAR")
        with pytest.raises(ValidationError) as exc_info:
            ChannelSegment(
                fixture_id="fix1",
                channel=ChannelName.PAN,
                t0_ms=0,
                t1_ms=1000,
                static_dmx=128,
                curve=curve,
            )
        assert "both" in str(exc_info.value).lower()

    def test_rejects_neither_static_dmx_nor_curve(self) -> None:
        """Test rejects neither static_dmx nor curve set."""
        with pytest.raises(ValidationError) as exc_info:
            ChannelSegment(
                fixture_id="fix1",
                channel=ChannelName.PAN,
                t0_ms=0,
                t1_ms=1000,
            )
        assert "either" in str(exc_info.value).lower()

    def test_t1_less_than_t0_raises_error(self) -> None:
        """Test t1_ms < t0_ms raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ChannelSegment(
                fixture_id="fix1",
                channel=ChannelName.PAN,
                t0_ms=2000,
                t1_ms=1000,
                static_dmx=128,
            )
        assert "t1_ms" in str(exc_info.value).lower() or "t0_ms" in str(exc_info.value).lower()

    def test_clamp_max_less_than_clamp_min_raises_error(self) -> None:
        """Test clamp_max < clamp_min raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ChannelSegment(
                fixture_id="fix1",
                channel=ChannelName.PAN,
                t0_ms=0,
                t1_ms=1000,
                static_dmx=128,
                clamp_min=200,
                clamp_max=100,
            )
        assert "clamp" in str(exc_info.value).lower()

    def test_offset_centered_without_base_dmx_raises_error(self) -> None:
        """Test offset_centered without base_dmx raises ValueError."""
        curve = NativeCurve(curve_id="SINE")
        with pytest.raises(ValidationError) as exc_info:
            ChannelSegment(
                fixture_id="fix1",
                channel=ChannelName.PAN,
                t0_ms=0,
                t1_ms=1000,
                curve=curve,
                offset_centered=True,
                amplitude_dmx=64,
                # Missing base_dmx
            )
        assert (
            "base_dmx" in str(exc_info.value).lower()
            or "offset_centered" in str(exc_info.value).lower()
        )

    def test_offset_centered_without_amplitude_dmx_raises_error(self) -> None:
        """Test offset_centered without amplitude_dmx raises ValueError."""
        curve = NativeCurve(curve_id="SINE")
        with pytest.raises(ValidationError) as exc_info:
            ChannelSegment(
                fixture_id="fix1",
                channel=ChannelName.PAN,
                t0_ms=0,
                t1_ms=1000,
                curve=curve,
                offset_centered=True,
                base_dmx=128,
                # Missing amplitude_dmx
            )
        assert (
            "amplitude_dmx" in str(exc_info.value).lower()
            or "offset_centered" in str(exc_info.value).lower()
        )

    def test_invalid_fixture_id_empty_string_raises_error(self) -> None:
        """Test invalid fixture_id (empty string) raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ChannelSegment(
                fixture_id="",
                channel=ChannelName.PAN,
                t0_ms=0,
                t1_ms=1000,
                static_dmx=128,
            )
        assert "fixture_id" in str(exc_info.value).lower() or "min" in str(exc_info.value).lower()


class TestFieldConstraints:
    """Tests for field constraints (ge=0, le=255, min_length=1)."""

    def test_all_field_constraints(self) -> None:
        """Test all field constraints (ge=0, le=255, min_length=1)."""
        # Test t0_ms >= 0
        with pytest.raises(ValidationError):
            ChannelSegment(
                fixture_id="fix1",
                channel=ChannelName.PAN,
                t0_ms=-1,
                t1_ms=1000,
                static_dmx=128,
            )

        # Test static_dmx <= 255
        with pytest.raises(ValidationError):
            ChannelSegment(
                fixture_id="fix1",
                channel=ChannelName.PAN,
                t0_ms=0,
                t1_ms=1000,
                static_dmx=256,
            )

        # Test static_dmx >= 0
        with pytest.raises(ValidationError):
            ChannelSegment(
                fixture_id="fix1",
                channel=ChannelName.PAN,
                t0_ms=0,
                t1_ms=1000,
                static_dmx=-1,
            )

        # Valid segment with all constraints satisfied
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.PAN,
            t0_ms=0,
            t1_ms=1000,
            static_dmx=255,
            clamp_min=0,
            clamp_max=255,
        )
        assert segment.static_dmx == 255


class TestJsonSerialization:
    """Tests for JSON serialization roundtrip."""

    def test_json_serialization_roundtrip(self) -> None:
        """Test JSON serialization roundtrip."""
        curve = PointsCurve(
            points=[
                CurvePoint(t=0.0, v=0.0),
                CurvePoint(t=0.5, v=1.0),
                CurvePoint(t=1.0, v=0.0),
            ]
        )
        original = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.PAN,
            t0_ms=0,
            t1_ms=2000,
            curve=curve,
            blend_mode=BlendMode.OVERRIDE,
            clamp_min=10,
            clamp_max=245,
        )
        json_str = original.model_dump_json()
        restored = ChannelSegment.model_validate_json(json_str)

        assert restored.fixture_id == original.fixture_id
        assert restored.channel == original.channel
        assert restored.t0_ms == original.t0_ms
        assert restored.t1_ms == original.t1_ms
        assert restored.blend_mode == original.blend_mode
        assert restored.clamp_min == original.clamp_min
        assert restored.clamp_max == original.clamp_max

        # Verify curve preserved
        assert restored.curve is not None
        assert isinstance(restored.curve, PointsCurve)
        assert len(restored.curve.points) == 3

    def test_static_segment_json_roundtrip(self) -> None:
        """Test static segment JSON serialization."""
        original = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.DIMMER,
            t0_ms=500,
            t1_ms=1500,
            static_dmx=200,
        )
        json_str = original.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["fixture_id"] == "fix1"
        assert parsed["channel"] == "DIMMER"
        assert parsed["static_dmx"] == 200
        assert parsed["curve"] is None


class TestDefaultValues:
    """Tests for default field values."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.PAN,
            t0_ms=0,
            t1_ms=1000,
            static_dmx=128,
        )

        # Check defaults
        assert segment.blend_mode == BlendMode.OVERRIDE
        assert segment.clamp_min == 0
        assert segment.clamp_max == 255
        assert segment.offset_centered is False
        assert segment.base_dmx is None
        assert segment.amplitude_dmx is None


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_duration_segment_allowed(self) -> None:
        """Test t0_ms == t1_ms is allowed (zero duration)."""
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.PAN,
            t0_ms=1000,
            t1_ms=1000,
            static_dmx=128,
        )
        assert segment.t0_ms == segment.t1_ms

    def test_offset_centered_false_does_not_require_base_amplitude(self) -> None:
        """Test offset_centered=False doesn't require base_dmx/amplitude_dmx."""
        curve = NativeCurve(curve_id="SINE")
        segment = ChannelSegment(
            fixture_id="fix1",
            channel=ChannelName.DIMMER,
            t0_ms=0,
            t1_ms=1000,
            curve=curve,
            offset_centered=False,
            # No base_dmx or amplitude_dmx needed
        )
        assert segment.offset_centered is False
