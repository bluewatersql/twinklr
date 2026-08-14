"""Tests for LayeringPlan model."""

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.planning import (
    LayeringPlan,
    LayerSpec,
    TargetSelector,
)
from twinklr.core.sequencer.vocabulary import BlendMode, LayerRole, TimingDriver


def _create_layer(
    index: int,
    role: LayerRole,
    roles: list[str],
    blend: BlendMode,
    timing: TimingDriver,
) -> LayerSpec:
    """Helper to create a LayerSpec."""
    return LayerSpec(
        layer_index=index,
        layer_role=role,
        target_selector=TargetSelector(roles=roles),
        blend_mode=blend,
        timing_driver=timing,
        usage_notes="Test layer usage notes for validation",
    )


def test_layering_plan_valid_minimal():
    """Valid LayeringPlan with minimal layers (BASE only)."""
    base = _create_layer(0, LayerRole.BASE, ["OUTLINE"], BlendMode.NORMAL, TimingDriver.BARS)

    plan = LayeringPlan(layers=[base])

    assert len(plan.layers) == 1
    assert plan.layers[0].layer_role == LayerRole.BASE


def test_layering_plan_valid_complete():
    """Valid LayeringPlan with multiple layers."""
    base = _create_layer(0, LayerRole.BASE, ["OUTLINE"], BlendMode.NORMAL, TimingDriver.BARS)
    rhythm = _create_layer(1, LayerRole.RHYTHM, ["MEGA_TREE"], BlendMode.ADD, TimingDriver.BEATS)
    accent = _create_layer(2, LayerRole.ACCENT, ["HERO"], BlendMode.ADD, TimingDriver.PEAKS)

    plan = LayeringPlan(
        layers=[base, rhythm, accent],
    )

    assert len(plan.layers) == 3


def test_layering_plan_missing_base_layer():
    """LayeringPlan without BASE layer rejected."""
    rhythm = _create_layer(1, LayerRole.RHYTHM, ["MEGA_TREE"], BlendMode.ADD, TimingDriver.BEATS)
    accent = _create_layer(2, LayerRole.ACCENT, ["HERO"], BlendMode.ADD, TimingDriver.PEAKS)

    with pytest.raises(ValidationError, match="Must have exactly one BASE layer"):
        LayeringPlan(layers=[rhythm, accent])


def test_layering_plan_multiple_base_layers():
    """LayeringPlan with multiple BASE layers rejected."""
    base1 = _create_layer(0, LayerRole.BASE, ["OUTLINE"], BlendMode.NORMAL, TimingDriver.BARS)
    base2 = _create_layer(1, LayerRole.BASE, ["ARCHES"], BlendMode.NORMAL, TimingDriver.BARS)

    with pytest.raises(ValidationError, match="Must have exactly one BASE layer"):
        LayeringPlan(layers=[base1, base2])


def test_layering_plan_duplicate_indices():
    """Duplicate layer indices rejected."""
    base = _create_layer(0, LayerRole.BASE, ["OUTLINE"], BlendMode.NORMAL, TimingDriver.BARS)
    rhythm = _create_layer(0, LayerRole.RHYTHM, ["MEGA_TREE"], BlendMode.ADD, TimingDriver.BEATS)

    with pytest.raises(ValidationError, match="Duplicate layer index"):
        LayeringPlan(layers=[base, rhythm])


def test_layering_plan_empty_layers():
    """Empty layers list rejected."""
    with pytest.raises(ValidationError, match="at least 1 item"):
        LayeringPlan(layers=[])


def test_layering_plan_too_many_layers():
    """More than 5 layers rejected."""
    # Create 6 layers with duplicate indices to bypass per-layer validation
    layers = [
        _create_layer(0, LayerRole.BASE, ["OUTLINE"], BlendMode.NORMAL, TimingDriver.BARS),
        _create_layer(1, LayerRole.RHYTHM, ["MEGA_TREE"], BlendMode.ADD, TimingDriver.BEATS),
        _create_layer(2, LayerRole.ACCENT, ["HERO"], BlendMode.ADD, TimingDriver.PEAKS),
        _create_layer(3, LayerRole.FILL, ["CUSTOM"], BlendMode.ADD, TimingDriver.DOWNBEATS),
        _create_layer(4, LayerRole.TEXTURE, ["FLOODS"], BlendMode.ADD, TimingDriver.PHRASES),
        _create_layer(
            0, LayerRole.RHYTHM, ["TREES"], BlendMode.ADD, TimingDriver.BEATS
        ),  # 6th layer (duplicate index)
    ]

    with pytest.raises(ValidationError, match="at most 5 items"):
        LayeringPlan(layers=layers)


def test_layering_plan_base_must_use_normal_blend():
    """BASE layer must use NORMAL blend mode."""
    base_with_add = _create_layer(0, LayerRole.BASE, ["OUTLINE"], BlendMode.ADD, TimingDriver.BARS)

    with pytest.raises(ValidationError, match="BASE layer must use NORMAL blend"):
        LayeringPlan(layers=[base_with_add])


def test_layering_plan_strategy_notes_is_deleted():
    """Legacy prose strategy notes are rejected by the closed schema."""
    base = _create_layer(0, LayerRole.BASE, ["OUTLINE"], BlendMode.NORMAL, TimingDriver.BARS)

    with pytest.raises(ValidationError, match="strategy_notes"):
        LayeringPlan(layers=[base], strategy_notes="legacy strategy")


def test_layering_plan_serialization():
    """LayeringPlan serializes to/from JSON."""
    base = _create_layer(
        0, LayerRole.BASE, ["OUTLINE", "ARCHES"], BlendMode.NORMAL, TimingDriver.BARS
    )
    rhythm = _create_layer(1, LayerRole.RHYTHM, ["MEGA_TREE"], BlendMode.ADD, TimingDriver.BEATS)

    plan = LayeringPlan(
        layers=[base, rhythm],
    )

    # Export to JSON
    json_str = plan.model_dump_json(indent=2)
    assert "BASE" in json_str
    assert "RHYTHM" in json_str

    # Import from JSON
    plan2 = LayeringPlan.model_validate_json(json_str)
    assert len(plan2.layers) == 2
    assert plan2.layers[0].layer_role == LayerRole.BASE


def test_layering_plan_layer_ordering():
    """Layers can be defined in any order (validation doesn't enforce ordering)."""
    # Define out of index order
    rhythm = _create_layer(1, LayerRole.RHYTHM, ["MEGA_TREE"], BlendMode.ADD, TimingDriver.BEATS)
    base = _create_layer(0, LayerRole.BASE, ["OUTLINE"], BlendMode.NORMAL, TimingDriver.BARS)
    accent = _create_layer(2, LayerRole.ACCENT, ["HERO"], BlendMode.ADD, TimingDriver.PEAKS)

    plan = LayeringPlan(
        layers=[rhythm, base, accent],  # Out of order
    )

    assert len(plan.layers) == 3
    # Verify all layers present
    indices = {layer.layer_index for layer in plan.layers}
    assert indices == {0, 1, 2}
