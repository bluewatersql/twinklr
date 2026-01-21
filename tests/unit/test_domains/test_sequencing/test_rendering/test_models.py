"""Tests for rendering pipeline data models.

Tests all core models used in the rendering pipeline:
- ChannelSpecs
- SequencedEffect
- RenderedChannels
- RenderedEffect
- BoundaryInfo
- ChannelOverlay
"""

from pydantic import ValidationError
import pytest

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
from blinkb0t.core.domains.sequencing.models.curves import CurvePoint, ValueCurveSpec
from blinkb0t.core.domains.sequencing.rendering.models import (
    BoundaryInfo,
    ChannelOverlay,
    ChannelSpecs,
    RenderedChannels,
    RenderedEffect,
    SequencedEffect,
)

# ============================================================================
# BoundaryInfo Tests
# ============================================================================


def test_boundary_info_minimal():
    """Test BoundaryInfo can be created with defaults."""
    info = BoundaryInfo()
    assert info.is_section_start is False
    assert info.is_section_end is False
    assert info.section_id is None
    assert info.entry_transition is None
    assert info.exit_transition is None
    assert info.is_gap_fill is False
    assert info.gap_type is None


def test_boundary_info_section_start():
    """Test BoundaryInfo for section start."""
    info = BoundaryInfo(
        is_section_start=True,
        section_id="intro",
    )
    assert info.is_section_start is True
    assert info.is_section_end is False
    assert info.section_id == "intro"


def test_boundary_info_section_end():
    """Test BoundaryInfo for section end."""
    info = BoundaryInfo(
        is_section_end=True,
        section_id="chorus",
    )
    assert info.is_section_start is False
    assert info.is_section_end is True
    assert info.section_id == "chorus"


def test_boundary_info_gap_fill():
    """Test BoundaryInfo for gap fill."""
    info = BoundaryInfo(
        is_gap_fill=True,
        gap_type="inter_section",
    )
    assert info.is_gap_fill is True
    assert info.gap_type == "inter_section"


# ============================================================================
# ChannelSpecs Tests
# ============================================================================


def test_channel_specs_with_curve_specs():
    """Test ChannelSpecs with ValueCurveSpec objects."""
    pan_spec = ValueCurveSpec(type=NativeCurveType.RAMP, p2=180.0)
    tilt_spec = ValueCurveSpec(type=NativeCurveType.SINE, p2=100.0)
    dimmer_spec = ValueCurveSpec(type=NativeCurveType.RAMP, p2=255.0)

    specs = ChannelSpecs(
        pan=pan_spec,
        tilt=tilt_spec,
        dimmer=dimmer_spec,
    )

    assert specs.pan == pan_spec
    assert specs.tilt == tilt_spec
    assert specs.dimmer == dimmer_spec
    assert specs.shutter is None
    assert specs.color is None
    assert specs.gobo is None


def test_channel_specs_with_static_values():
    """Test ChannelSpecs with static integer values."""
    specs = ChannelSpecs(
        pan=128,
        tilt=64,
        dimmer=255,
    )

    assert specs.pan == 128
    assert specs.tilt == 64
    assert specs.dimmer == 255


def test_channel_specs_mixed_specs_and_values():
    """Test ChannelSpecs with mix of specs and static values."""
    pan_spec = ValueCurveSpec(type=NativeCurveType.SINE, p2=180.0)

    specs = ChannelSpecs(
        pan=pan_spec,
        tilt=90,
        dimmer=255,
    )

    assert isinstance(specs.pan, ValueCurveSpec)
    assert specs.tilt == 90
    assert specs.dimmer == 255


def test_channel_specs_with_appearance_channels():
    """Test ChannelSpecs with optional appearance channels."""
    specs = ChannelSpecs(
        pan=128,
        tilt=64,
        dimmer=255,
        shutter=200,
        color=(255, 0, 0),  # Red RGB
        gobo=3,
    )

    assert specs.shutter == 200
    assert specs.color == (255, 0, 0)
    assert specs.gobo == 3


def test_channel_specs_serialization():
    """Test ChannelSpecs can be serialized/deserialized."""
    original = ChannelSpecs(
        pan=128,
        tilt=64,
        dimmer=255,
        shutter=200,
    )

    # Serialize
    data = original.model_dump()
    assert data["pan"] == 128
    assert data["shutter"] == 200

    # Deserialize
    restored = ChannelSpecs.model_validate(data)
    assert restored.pan == original.pan
    assert restored.shutter == original.shutter


# ============================================================================
# SequencedEffect Tests
# ============================================================================


def test_sequenced_effect_minimal():
    """Test SequencedEffect with minimal required fields."""
    channels = ChannelSpecs(pan=128, tilt=64, dimmer=255)

    effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=channels,
    )

    assert effect.fixture_id == "MH1"
    assert effect.start_ms == 0
    assert effect.end_ms == 1000
    assert effect.channels == channels
    assert effect.boundary_info is None
    assert effect.metadata == {}


def test_sequenced_effect_with_boundary_info():
    """Test SequencedEffect with boundary information."""
    channels = ChannelSpecs(pan=128, tilt=64, dimmer=255)
    boundary = BoundaryInfo(is_section_start=True, section_id="intro")

    effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=channels,
        boundary_info=boundary,
    )

    assert effect.boundary_info is not None
    assert effect.boundary_info.is_section_start is True
    assert effect.boundary_info.section_id == "intro"


def test_sequenced_effect_with_metadata():
    """Test SequencedEffect with metadata."""
    channels = ChannelSpecs(pan=128, tilt=64, dimmer=255)

    effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=channels,
        metadata={
            "source": "segment_renderer",
            "template_step": "step_1",
            "movement": "circle",
        },
    )

    assert effect.metadata["source"] == "segment_renderer"
    assert effect.metadata["movement"] == "circle"


def test_sequenced_effect_negative_timing_allowed():
    """Test SequencedEffect allows any integer timing values."""
    # Note: Validation of logical timing constraints happens elsewhere
    channels = ChannelSpecs(pan=128, tilt=64, dimmer=255)

    effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=-100,  # Unusual but allowed
        end_ms=1000,
        channels=channels,
    )

    assert effect.start_ms == -100


def test_sequenced_effect_label():
    """Test SequencedEffect with optional label."""
    channels = ChannelSpecs(pan=128, tilt=64, dimmer=255)

    effect = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=channels,
        label="Circle Movement",
    )

    assert effect.label == "Circle Movement"


# ============================================================================
# RenderedChannels Tests
# ============================================================================


def test_rendered_channels_minimal():
    """Test RenderedChannels with required fields only."""
    pan_points = [CurvePoint(time=0.0, value=128.0), CurvePoint(time=1.0, value=180.0)]
    tilt_points = [CurvePoint(time=0.0, value=64.0), CurvePoint(time=1.0, value=90.0)]
    dimmer_points = [CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=255.0)]

    channels = RenderedChannels(
        pan=pan_points,
        tilt=tilt_points,
        dimmer=dimmer_points,
    )

    assert channels.pan == pan_points
    assert channels.tilt == tilt_points
    assert channels.dimmer == dimmer_points
    assert channels.shutter is None
    assert channels.color is None
    assert channels.gobo is None


def test_rendered_channels_with_appearance():
    """Test RenderedChannels with optional appearance channels."""
    pan_points = [CurvePoint(time=0.0, value=128.0)]
    tilt_points = [CurvePoint(time=0.0, value=64.0)]
    dimmer_points = [CurvePoint(time=0.0, value=255.0)]
    shutter_points = [CurvePoint(time=0.0, value=200.0)]
    color_points = [CurvePoint(time=0.0, value=255.0)]
    gobo_points = [CurvePoint(time=0.0, value=3.0)]

    channels = RenderedChannels(
        pan=pan_points,
        tilt=tilt_points,
        dimmer=dimmer_points,
        shutter=shutter_points,
        color=color_points,
        gobo=gobo_points,
    )

    assert channels.shutter == shutter_points
    assert channels.color == color_points
    assert channels.gobo == gobo_points


def test_rendered_channels_empty_point_lists_allowed():
    """Test RenderedChannels allows empty point lists."""
    # Empty lists might occur in edge cases
    channels = RenderedChannels(
        pan=[],
        tilt=[],
        dimmer=[],
    )

    assert channels.pan == []
    assert channels.tilt == []
    assert channels.dimmer == []


def test_rendered_channels_validation_missing_pan():
    """Test RenderedChannels validation fails when pan is missing."""
    with pytest.raises(ValidationError) as exc_info:
        RenderedChannels(
            tilt=[CurvePoint(time=0.0, value=64.0)],
            dimmer=[CurvePoint(time=0.0, value=255.0)],
        )

    assert "pan" in str(exc_info.value)
    assert "Field required" in str(exc_info.value)


def test_rendered_channels_validation_missing_tilt():
    """Test RenderedChannels validation fails when tilt is missing."""
    with pytest.raises(ValidationError) as exc_info:
        RenderedChannels(
            pan=[CurvePoint(time=0.0, value=128.0)],
            dimmer=[CurvePoint(time=0.0, value=255.0)],
        )

    assert "tilt" in str(exc_info.value)


def test_rendered_channels_validation_missing_dimmer():
    """Test RenderedChannels validation fails when dimmer is missing."""
    with pytest.raises(ValidationError) as exc_info:
        RenderedChannels(
            pan=[CurvePoint(time=0.0, value=128.0)],
            tilt=[CurvePoint(time=0.0, value=64.0)],
        )

    assert "dimmer" in str(exc_info.value)


def test_rendered_channels_with_many_points():
    """Test RenderedChannels with multi-point curves (realistic scenario)."""
    # Create realistic multi-point curves (10 points each)
    pan_points = [CurvePoint(time=i * 0.1, value=128.0 + i * 5) for i in range(10)]
    tilt_points = [CurvePoint(time=i * 0.1, value=64.0 + i * 2) for i in range(10)]
    dimmer_points = [CurvePoint(time=i * 0.1, value=200.0 + i) for i in range(10)]

    channels = RenderedChannels(
        pan=pan_points,
        tilt=tilt_points,
        dimmer=dimmer_points,
    )

    assert len(channels.pan) == 10
    assert len(channels.tilt) == 10
    assert len(channels.dimmer) == 10
    assert channels.pan[0].time == 0.0
    assert channels.pan[-1].time == 0.9
    assert channels.pan[0].value == 128.0
    assert channels.pan[-1].value == 173.0  # 128 + 9*5


def test_rendered_channels_type_validation():
    """Test RenderedChannels validates types on instantiation."""
    # Test that wrong types are rejected during creation
    with pytest.raises(ValidationError):
        RenderedChannels(
            pan="invalid_string",  # Should be list[CurvePoint]
            tilt=[CurvePoint(time=0.0, value=64.0)],
            dimmer=[CurvePoint(time=0.0, value=255.0)],
        )


# ============================================================================
# RenderedEffect Tests
# ============================================================================


def test_rendered_effect_minimal():
    """Test RenderedEffect with minimal required fields."""
    rendered_channels = RenderedChannels(
        pan=[CurvePoint(time=0.0, value=128.0)],
        tilt=[CurvePoint(time=0.0, value=64.0)],
        dimmer=[CurvePoint(time=0.0, value=255.0)],
    )

    effect = RenderedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        rendered_channels=rendered_channels,
    )

    assert effect.fixture_id == "MH1"
    assert effect.start_ms == 0
    assert effect.end_ms == 1000
    assert effect.rendered_channels == rendered_channels
    assert effect.metadata == {}


def test_rendered_effect_with_metadata():
    """Test RenderedEffect preserves metadata from SequencedEffect."""
    rendered_channels = RenderedChannels(
        pan=[CurvePoint(time=0.0, value=128.0)],
        tilt=[CurvePoint(time=0.0, value=64.0)],
        dimmer=[CurvePoint(time=0.0, value=255.0)],
    )

    effect = RenderedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        rendered_channels=rendered_channels,
        metadata={
            "source": "curve_pipeline",
            "original_movement": "circle",
        },
    )

    assert effect.metadata["source"] == "curve_pipeline"
    assert effect.metadata["original_movement"] == "circle"


def test_rendered_effect_label():
    """Test RenderedEffect with optional label."""
    rendered_channels = RenderedChannels(
        pan=[CurvePoint(time=0.0, value=128.0)],
        tilt=[CurvePoint(time=0.0, value=64.0)],
        dimmer=[CurvePoint(time=0.0, value=255.0)],
    )

    effect = RenderedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        rendered_channels=rendered_channels,
        label="Rendered Circle",
    )

    assert effect.label == "Rendered Circle"


def test_rendered_effect_validation_missing_fixture_id():
    """Test RenderedEffect validation fails when fixture_id is missing."""
    rendered_channels = RenderedChannels(
        pan=[CurvePoint(time=0.0, value=128.0)],
        tilt=[CurvePoint(time=0.0, value=64.0)],
        dimmer=[CurvePoint(time=0.0, value=255.0)],
    )

    with pytest.raises(ValidationError) as exc_info:
        RenderedEffect(
            start_ms=0,
            end_ms=1000,
            rendered_channels=rendered_channels,
        )

    assert "fixture_id" in str(exc_info.value)


def test_rendered_effect_validation_missing_timing():
    """Test RenderedEffect validation fails when timing is missing."""
    rendered_channels = RenderedChannels(
        pan=[CurvePoint(time=0.0, value=128.0)],
        tilt=[CurvePoint(time=0.0, value=64.0)],
        dimmer=[CurvePoint(time=0.0, value=255.0)],
    )

    with pytest.raises(ValidationError) as exc_info:
        RenderedEffect(
            fixture_id="MH1",
            rendered_channels=rendered_channels,
        )

    assert "start_ms" in str(exc_info.value) or "end_ms" in str(exc_info.value)


def test_rendered_effect_validation_missing_channels():
    """Test RenderedEffect validation fails when rendered_channels is missing."""
    with pytest.raises(ValidationError) as exc_info:
        RenderedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
        )

    assert "rendered_channels" in str(exc_info.value)


def test_rendered_effect_with_all_optional_channels():
    """Test RenderedEffect with all optional appearance channels populated."""
    rendered_channels = RenderedChannels(
        pan=[CurvePoint(time=0.0, value=128.0), CurvePoint(time=1.0, value=180.0)],
        tilt=[CurvePoint(time=0.0, value=64.0), CurvePoint(time=1.0, value=90.0)],
        dimmer=[CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=255.0)],
        shutter=[CurvePoint(time=0.0, value=200.0), CurvePoint(time=1.0, value=250.0)],
        color=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=128.0)],
        gobo=[CurvePoint(time=0.0, value=1.0), CurvePoint(time=1.0, value=5.0)],
    )

    effect = RenderedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=2000,
        rendered_channels=rendered_channels,
        label="Full Effect",
        metadata={"template": "circle", "section": "chorus"},
    )

    assert effect.rendered_channels.shutter is not None
    assert len(effect.rendered_channels.shutter) == 2
    assert effect.rendered_channels.color is not None
    assert len(effect.rendered_channels.color) == 2
    assert effect.rendered_channels.gobo is not None
    assert len(effect.rendered_channels.gobo) == 2
    assert effect.label == "Full Effect"
    assert effect.metadata["template"] == "circle"
    assert effect.metadata["section"] == "chorus"


def test_rendered_effect_timing_consistency():
    """Test RenderedEffect with realistic timing values."""
    rendered_channels = RenderedChannels(
        pan=[CurvePoint(time=0.0, value=128.0)],
        tilt=[CurvePoint(time=0.0, value=64.0)],
        dimmer=[CurvePoint(time=0.0, value=255.0)],
    )

    # Typical 4-beat segment at 120 BPM (2000ms)
    effect = RenderedEffect(
        fixture_id="MH2",
        start_ms=4000,
        end_ms=6000,
        rendered_channels=rendered_channels,
    )

    duration_ms = effect.end_ms - effect.start_ms
    assert duration_ms == 2000
    assert effect.start_ms == 4000
    assert effect.end_ms == 6000


# ============================================================================
# ChannelOverlay Tests
# ============================================================================


def test_channel_overlay_with_static_values():
    """Test ChannelOverlay with static integer values."""
    overlay = ChannelOverlay(
        shutter=255,
        color=(255, 0, 0),  # Red
        gobo=3,
    )

    assert overlay.shutter == 255
    assert overlay.color == (255, 0, 0)
    assert overlay.gobo == 3


def test_channel_overlay_with_curve_specs():
    """Test ChannelOverlay with ValueCurveSpec for dynamic channels.

    NOTE: Phase 4 feature - skipped for Phase 3.
    Phase 3 uses static values only. Dynamic curves will be added in Phase 4.
    """
    pytest.skip("Phase 4 feature - dynamic curves not implemented in Phase 3")


def test_channel_overlay_with_rgb_color():
    """Test ChannelOverlay with RGB tuple for color."""
    overlay = ChannelOverlay(
        shutter=255,
        color=(128, 64, 200),  # Purple
        gobo=1,
    )

    assert overlay.color == (128, 64, 200)
    assert isinstance(overlay.color, tuple)
    assert len(overlay.color) == 3


def test_channel_overlay_none_values_not_allowed():
    """Test ChannelOverlay requires all fields (no None allowed)."""
    # According to Phase 2 design, all fields are required
    with pytest.raises(ValidationError):
        ChannelOverlay(
            shutter=255,
            color=None,  # Not allowed
            gobo=0,
        )


def test_channel_overlay_serialization():
    """Test ChannelOverlay can be serialized/deserialized."""
    original = ChannelOverlay(
        shutter=200,
        color=(255, 255, 0),  # Yellow
        gobo=2,
    )

    # Serialize
    data = original.model_dump()
    assert data["shutter"] == 200
    assert data["color"] == (255, 255, 0)

    # Deserialize
    restored = ChannelOverlay.model_validate(data)
    assert restored.shutter == original.shutter
    assert restored.color == original.color
    assert restored.gobo == original.gobo


# ============================================================================
# Integration / Relationship Tests
# ============================================================================


def test_sequenced_to_rendered_workflow():
    """Test typical workflow from SequencedEffect to RenderedEffect."""
    # 1. Create SequencedEffect with specs
    pan_spec = ValueCurveSpec(type=NativeCurveType.SINE, p2=180.0)
    channels = ChannelSpecs(pan=pan_spec, tilt=64, dimmer=255)

    sequenced = SequencedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        channels=channels,
        metadata={"source": "test"},
    )

    # 2. Simulate rendering (CurvePipeline would do this)
    rendered_channels = RenderedChannels(
        pan=[CurvePoint(time=0.0, value=128.0), CurvePoint(time=1.0, value=180.0)],
        tilt=[CurvePoint(time=0.0, value=64.0), CurvePoint(time=1.0, value=64.0)],
        dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
    )

    # 3. Create RenderedEffect
    rendered = RenderedEffect(
        fixture_id=sequenced.fixture_id,
        start_ms=sequenced.start_ms,
        end_ms=sequenced.end_ms,
        rendered_channels=rendered_channels,
        metadata=sequenced.metadata,
    )

    # Verify
    assert rendered.fixture_id == sequenced.fixture_id
    assert rendered.start_ms == sequenced.start_ms
    assert rendered.metadata == sequenced.metadata


def test_channel_specs_type_safety():
    """Test ChannelSpecs provides type-safe access."""
    specs = ChannelSpecs(pan=128, tilt=64, dimmer=255)

    # Type-safe attribute access (not dict access)
    assert specs.pan == 128  # IDE autocomplete works!
    assert specs.tilt == 64
    assert specs.dimmer == 255

    # Pydantic validation catches errors
    with pytest.raises(ValidationError):
        ChannelSpecs(pan="invalid", tilt=64, dimmer=255)  # type: ignore
