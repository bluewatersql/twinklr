"""Tests for LayerSpec and TargetSelector models."""

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.planning import LayerSpec, TargetSelector
from twinklr.core.sequencer.vocabulary import BlendMode, LayerRole, TimingDriver


def test_target_selector_single_role():
    """TargetSelector with single role."""
    selector = TargetSelector(roles=["OUTLINE"])
    assert len(selector.roles) == 1
    assert selector.coordination == "unified"


def test_target_selector_multiple_roles():
    """TargetSelector supports multiple roles for coordinated impact."""
    selector = TargetSelector(roles=["OUTLINE", "MEGA_TREE", "HERO"], coordination="unified")
    assert len(selector.roles) == 3


def test_target_selector_invalid_role():
    """Invalid role in TargetSelector rejected."""
    with pytest.raises(ValidationError, match="Invalid role"):
        TargetSelector(roles=["INVALID_ROLE"])


def test_target_selector_empty_roles():
    """Empty roles list rejected."""
    with pytest.raises(ValidationError):
        TargetSelector(roles=[])


def test_layer_spec_valid():
    """Valid LayerSpec passes."""
    spec = LayerSpec(
        layer_index=0,
        layer_role=LayerRole.BASE,
        target_selector=TargetSelector(roles=["OUTLINE", "ARCHES"]),
        blend_mode=BlendMode.NORMAL,
        timing_driver=TimingDriver.BARS,
        usage_notes="Foundation layer, slow evolving wash",
    )
    assert spec.layer_index == 0
    assert spec.layer_role == LayerRole.BASE
    assert len(spec.target_selector.roles) == 2
    assert spec.intensity_bias == 1.0  # Default value


def test_layer_index_out_of_range_high():
    """Layer index > 4 rejected."""
    with pytest.raises(ValidationError):
        LayerSpec(
            layer_index=5,
            layer_role=LayerRole.BASE,
            target_selector=TargetSelector(roles=["OUTLINE"]),
            blend_mode=BlendMode.NORMAL,
            timing_driver=TimingDriver.BARS,
            usage_notes="Test notes",
        )


def test_layer_index_out_of_range_negative():
    """Negative layer index rejected."""
    with pytest.raises(ValidationError):
        LayerSpec(
            layer_index=-1,
            layer_role=LayerRole.BASE,
            target_selector=TargetSelector(roles=["OUTLINE"]),
            blend_mode=BlendMode.NORMAL,
            timing_driver=TimingDriver.BARS,
            usage_notes="Test notes",
        )


def test_intensity_bias_default():
    """Intensity bias defaults to 1.0."""
    spec = LayerSpec(
        layer_index=1,
        layer_role=LayerRole.RHYTHM,
        target_selector=TargetSelector(roles=["MEGA_TREE"]),
        blend_mode=BlendMode.ADD,
        timing_driver=TimingDriver.BEATS,
        usage_notes="Beat-driven pulses",
    )
    assert spec.intensity_bias == 1.0


def test_intensity_bias_custom():
    """Custom intensity bias accepted."""
    spec = LayerSpec(
        layer_index=2,
        layer_role=LayerRole.ACCENT,
        target_selector=TargetSelector(roles=["HERO"]),
        blend_mode=BlendMode.ADD,
        timing_driver=TimingDriver.PEAKS,
        intensity_bias=1.3,
        usage_notes="High-impact accent moments",
    )
    assert spec.intensity_bias == 1.3


def test_intensity_bias_out_of_range_high():
    """Intensity bias > 1.5 rejected."""
    with pytest.raises(ValidationError):
        LayerSpec(
            layer_index=2,
            layer_role=LayerRole.ACCENT,
            target_selector=TargetSelector(roles=["HERO"]),
            blend_mode=BlendMode.ADD,
            timing_driver=TimingDriver.PEAKS,
            intensity_bias=1.6,
            usage_notes="Test notes",
        )


def test_intensity_bias_out_of_range_negative():
    """Negative intensity bias rejected."""
    with pytest.raises(ValidationError):
        LayerSpec(
            layer_index=2,
            layer_role=LayerRole.ACCENT,
            target_selector=TargetSelector(roles=["HERO"]),
            blend_mode=BlendMode.ADD,
            timing_driver=TimingDriver.PEAKS,
            intensity_bias=-0.1,
            usage_notes="Test notes",
        )


def test_usage_notes_too_short():
    """Usage notes < 10 characters rejected."""
    with pytest.raises(ValidationError):
        LayerSpec(
            layer_index=0,
            layer_role=LayerRole.BASE,
            target_selector=TargetSelector(roles=["OUTLINE"]),
            blend_mode=BlendMode.NORMAL,
            timing_driver=TimingDriver.BARS,
            usage_notes="Short",
        )


def test_layer_spec_serialization():
    """LayerSpec serializes to/from JSON."""
    spec = LayerSpec(
        layer_index=1,
        layer_role=LayerRole.RHYTHM,
        target_selector=TargetSelector(roles=["MEGA_TREE", "OUTLINE"], coordination="unified"),
        blend_mode=BlendMode.ADD,
        timing_driver=TimingDriver.DOWNBEATS,
        intensity_bias=1.2,
        usage_notes="Synchronized downbeat pulses across main elements",
    )

    # Export to JSON
    json_str = spec.model_dump_json(indent=2)
    assert "RHYTHM" in json_str
    assert "DOWNBEATS" in json_str

    # Import from JSON
    spec2 = LayerSpec.model_validate_json(json_str)
    assert spec == spec2
