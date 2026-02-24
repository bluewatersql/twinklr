"""Tests for builtin GroupPlanTemplate to EffectRecipe converter."""

from __future__ import annotations

from twinklr.core.sequencer.templates.group.converter import convert_builtin_to_recipe
from twinklr.core.sequencer.templates.group.models.template import (
    GroupPlanTemplate,
    LayerRecipe,
    ProjectionSpec,
    TimingHints,
)
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    ProjectionIntent,
    VisualDepth,
)


def _make_single_layer_builtin() -> GroupPlanTemplate:
    """Create a minimal single-layer builtin template."""
    return GroupPlanTemplate(
        template_id="gtpl_base_glow_warm",
        name="Warm Glow",
        description="A warm ambient glow",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["warm", "ambient"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=4, bars_max=64),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["glow"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.5,
                contrast=0.3,
                color_mode=ColorMode.MONOCHROME,
            ),
        ],
        template_version="1.0.0",
    )


def _make_multi_layer_builtin() -> GroupPlanTemplate:
    """Create a multi-layer builtin template."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_sparkle_burst",
        name="Sparkle Burst",
        description="Multi-layer sparkle accent",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["sparkle", "burst"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        timing=TimingHints(bars_min=1, bars_max=4),
        layer_recipe=[
            LayerRecipe(
                layer=VisualDepth.BACKGROUND,
                motifs=["wash"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FADE],
                density=0.3,
                contrast=0.2,
                color_mode=ColorMode.MONOCHROME,
            ),
            LayerRecipe(
                layer=VisualDepth.FOREGROUND,
                motifs=["sparkle"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.SPARKLE, MotionVerb.PULSE],
                density=0.8,
                contrast=0.7,
                color_mode=ColorMode.DICHROME,
            ),
        ],
        template_version="2.0.0",
    )


def test_convert_single_layer_builtin_to_recipe() -> None:
    builtin = _make_single_layer_builtin()
    recipe = convert_builtin_to_recipe(builtin)
    assert isinstance(recipe, EffectRecipe)
    assert recipe.recipe_id == builtin.template_id
    assert recipe.template_type == builtin.template_type
    assert len(recipe.layers) == len(builtin.layer_recipe)
    assert recipe.provenance.source == "builtin"


def test_convert_preserves_metadata() -> None:
    builtin = _make_single_layer_builtin()
    recipe = convert_builtin_to_recipe(builtin)
    assert recipe.name == builtin.name
    assert recipe.description == builtin.description
    assert recipe.visual_intent == builtin.visual_intent
    assert recipe.tags == builtin.tags
    assert recipe.recipe_version == builtin.template_version
    assert recipe.timing == builtin.timing


def test_convert_maps_layer_fields() -> None:
    builtin = _make_single_layer_builtin()
    recipe = convert_builtin_to_recipe(builtin)
    layer = recipe.layers[0]
    src = builtin.layer_recipe[0]
    assert layer.layer_index == 0
    assert layer.layer_depth == src.layer
    assert layer.motion == src.motion
    assert layer.density == src.density
    assert layer.blend_mode == BlendMode.NORMAL  # first layer defaults to NORMAL


def test_convert_multi_layer_builtin() -> None:
    builtin = _make_multi_layer_builtin()
    recipe = convert_builtin_to_recipe(builtin)
    assert len(recipe.layers) == 2
    assert recipe.layers[0].layer_index == 0
    assert recipe.layers[1].layer_index == 1
    assert recipe.layers[1].layer_depth == VisualDepth.FOREGROUND


def test_convert_multi_layer_blend_modes() -> None:
    builtin = _make_multi_layer_builtin()
    recipe = convert_builtin_to_recipe(builtin)
    # First layer: NORMAL, subsequent layers: ADD
    assert recipe.layers[0].blend_mode == BlendMode.NORMAL
    assert recipe.layers[1].blend_mode == BlendMode.ADD
