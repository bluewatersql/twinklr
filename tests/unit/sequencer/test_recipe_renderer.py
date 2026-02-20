"""Tests for RecipeRenderer — renders EffectRecipe layers into concrete effect specs."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.recipe_renderer import (
    RecipeRenderer,
    RecipeRenderResult,
    RenderedLayer,
    RenderEnvironment,
)
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    PaletteSpec,
    ParamValue,
    RecipeLayer,
    RecipeProvenance,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    VisualDepth,
)


def _make_layer(
    *,
    layer_index: int = 0,
    effect_type: str = "ColorWash",
    blend_mode: BlendMode = BlendMode.NORMAL,
    mix: float = 1.0,
    params: dict[str, ParamValue] | None = None,
    density: float = 0.5,
    color_source: str = ColorSource.PALETTE_PRIMARY,
    timing_offset_beats: float | None = None,
) -> RecipeLayer:
    return RecipeLayer(
        layer_index=layer_index,
        layer_name=f"Layer {layer_index}",
        layer_depth=VisualDepth.BACKGROUND,
        effect_type=effect_type,
        blend_mode=blend_mode,
        mix=mix,
        params=params or {},
        motion=[MotionVerb.FADE],
        density=density,
        color_source=color_source,
        timing_offset_beats=timing_offset_beats,
    )


def _make_recipe(layers: tuple[RecipeLayer, ...] | None = None) -> EffectRecipe:
    if layers is None:
        layers = (_make_layer(),)
    return EffectRecipe(
        recipe_id="test-recipe",
        name="Test Recipe",
        description="A test recipe",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=[],
        timing=TimingHints(bars_min=2, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=layers,
        provenance=RecipeProvenance(source="builtin"),
    )


def _default_env() -> RenderEnvironment:
    return RenderEnvironment(
        energy=0.7,
        density=0.6,
        palette_colors={"primary": "#FF0000", "accent": "#00FF00"},
    )


# ============================================================================
# Single-layer rendering
# ============================================================================


def test_single_layer_renders() -> None:
    """Single-layer recipe produces 1 RenderedLayer with correct values."""
    result = RecipeRenderer().render(_make_recipe(), _default_env())
    assert isinstance(result, RecipeRenderResult)
    assert result.recipe_id == "test-recipe"
    assert len(result.layers) == 1
    layer = result.layers[0]
    assert isinstance(layer, RenderedLayer)
    assert layer.effect_type == "ColorWash"
    assert layer.blend_mode == BlendMode.NORMAL
    assert layer.mix == 1.0


# ============================================================================
# Multi-layer rendering
# ============================================================================


def test_multi_layer_renders() -> None:
    """Multi-layer recipe produces correct layer stack."""
    layers = (
        _make_layer(layer_index=0, blend_mode=BlendMode.NORMAL),
        _make_layer(layer_index=1, effect_type="Sparkles", blend_mode=BlendMode.ADD, mix=0.7),
        _make_layer(layer_index=2, effect_type="Chase", blend_mode=BlendMode.SCREEN, mix=0.5),
    )
    result = RecipeRenderer().render(_make_recipe(layers), _default_env())
    assert len(result.layers) == 3
    assert result.layers[0].blend_mode == BlendMode.NORMAL
    assert result.layers[1].effect_type == "Sparkles"
    assert result.layers[1].blend_mode == BlendMode.ADD
    assert result.layers[1].mix == 0.7
    assert result.layers[2].blend_mode == BlendMode.SCREEN


# ============================================================================
# Dynamic parameter evaluation
# ============================================================================


def test_dynamic_param_evaluation() -> None:
    """ParamValue with expr='energy * 0.8' evaluates correctly."""
    layer = _make_layer(params={"speed": ParamValue(expr="energy * 0.8")})
    env = RenderEnvironment(energy=0.7, density=0.5, palette_colors={})
    result = RecipeRenderer().render(_make_recipe((layer,)), env)
    assert result.layers[0].resolved_params["speed"] == pytest.approx(0.56)


def test_dynamic_param_clamping() -> None:
    """ParamValue with min/max bounds clamps correctly."""
    layer = _make_layer(
        params={"brightness": ParamValue(expr="energy * 0.1", min_val=0.3, max_val=1.0)}
    )
    env = RenderEnvironment(energy=0.5, density=0.5, palette_colors={})
    result = RecipeRenderer().render(_make_recipe((layer,)), env)
    # 0.5 * 0.1 = 0.05, clamped to min 0.3
    assert result.layers[0].resolved_params["brightness"] == pytest.approx(0.3)


def test_static_param_passthrough() -> None:
    """ParamValue with static value passes through."""
    layer = _make_layer(
        params={
            "direction": ParamValue(value="left"),
            "count": ParamValue(value=5),
        }
    )
    result = RecipeRenderer().render(_make_recipe((layer,)), _default_env())
    assert result.layers[0].resolved_params["direction"] == "left"
    assert result.layers[0].resolved_params["count"] == 5


# ============================================================================
# Color source resolution
# ============================================================================


def test_color_source_palette_primary() -> None:
    """PALETTE_PRIMARY resolves to palette hex."""
    layer = _make_layer(color_source=ColorSource.PALETTE_PRIMARY)
    result = RecipeRenderer().render(_make_recipe((layer,)), _default_env())
    assert result.layers[0].resolved_color == "#FF0000"


def test_color_source_palette_accent() -> None:
    """PALETTE_ACCENT resolves to accent hex."""
    layer = _make_layer(color_source=ColorSource.PALETTE_ACCENT)
    result = RecipeRenderer().render(_make_recipe((layer,)), _default_env())
    assert result.layers[0].resolved_color == "#00FF00"


def test_color_source_white_only() -> None:
    """WHITE_ONLY always returns #FFFFFF."""
    layer = _make_layer(color_source=ColorSource.WHITE_ONLY)
    result = RecipeRenderer().render(_make_recipe((layer,)), _default_env())
    assert result.layers[0].resolved_color == "#FFFFFF"


def test_default_environment_fallback() -> None:
    """Empty environment falls back to #FFFFFF for palette colors."""
    layer = _make_layer(color_source=ColorSource.PALETTE_PRIMARY)
    result = RecipeRenderer().render(_make_recipe((layer,)), RenderEnvironment())
    assert result.layers[0].resolved_color == "#FFFFFF"
