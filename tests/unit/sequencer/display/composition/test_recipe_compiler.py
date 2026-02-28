"""Tests for RecipeCompiler."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.composition.models import TemplateCompileError
from twinklr.core.sequencer.display.composition.recipe_compiler import RecipeCompiler
from twinklr.core.sequencer.display.composition.template_compiler import (
    TemplateCompileContext,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.templates.group.models import GroupPlacement
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EffectDuration,
    GroupTemplateType,
    GroupVisualIntent,
    IntensityLevel,
    LaneKind,
    MotionVerb,
    TargetType,
    VisualDepth,
)
from twinklr.core.sequencer.vocabulary import EnergyTarget as _EnergyTarget
from twinklr.core.sequencer.vocabulary.planning import PlanningTimeRef


def _make_recipe(recipe_id: str = "recipe_wash") -> EffectRecipe:
    return EffectRecipe(
        recipe_id=recipe_id,
        name="Color Wash",
        description="Test recipe",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        timing=TimingHints(bars_min=2, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="Color Wash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[MotionVerb.FADE],
                density=0.5,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="mined"),
        style_markers=StyleMarkers(complexity=0.33, energy_affinity=_EnergyTarget.LOW),
    )


def _make_placement(template_id: str = "recipe_wash") -> GroupPlacement:
    return GroupPlacement(
        placement_id="p1",
        template_id=template_id,
        target=PlanTarget(type=TargetType.GROUP, id="outline_left"),
        start=PlanningTimeRef(bar=1, beat=1),
        duration=EffectDuration.PHRASE,
        intensity=IntensityLevel.MED,
    )


def _make_context() -> TemplateCompileContext:
    return TemplateCompileContext(
        section_id="verse_1",
        lane=LaneKind.BASE,
        palette=ResolvedPalette(colors=["#FF0000", "#00FF00"], active_slots=[1, 2]),
        start_ms=0,
        end_ms=4000,
        intensity=0.7,
        placement_index=0,
    )


def test_recipe_compiler_produces_compiled_effects() -> None:
    """RecipeCompiler produces one CompiledEffect per recipe layer."""
    recipe = _make_recipe()
    catalog = RecipeCatalog(recipes=[recipe])
    compiler = RecipeCompiler(catalog=catalog)

    effects = compiler.compile(_make_placement(), _make_context())

    assert len(effects) == 1
    effect = effects[0]
    assert effect.event.effect_type == "Color Wash"
    assert effect.event.start_ms == 0
    assert effect.event.end_ms == 4000
    assert effect.visual_depth == VisualDepth.BACKGROUND
    assert effect.event.source.template_id == "recipe_wash"


def test_recipe_compiler_uses_palette_colors() -> None:
    """RecipeCompiler passes palette colors from context to renderer."""
    recipe = _make_recipe()
    catalog = RecipeCatalog(recipes=[recipe])
    compiler = RecipeCompiler(catalog=catalog)

    effects = compiler.compile(_make_placement(), _make_context())
    assert len(effects) == 1


def test_recipe_compiler_unknown_recipe_raises() -> None:
    """RecipeCompiler raises TemplateCompileError for unknown ID."""
    catalog = RecipeCatalog(recipes=[])
    compiler = RecipeCompiler(catalog=catalog)

    with pytest.raises(TemplateCompileError, match="not found"):
        compiler.compile(_make_placement("nonexistent"), _make_context())


def test_recipe_compiler_can_compile() -> None:
    """can_compile returns True for known recipes, False otherwise."""
    recipe = _make_recipe()
    catalog = RecipeCatalog(recipes=[recipe])
    compiler = RecipeCompiler(catalog=catalog)

    assert compiler.can_compile("recipe_wash") is True
    assert compiler.can_compile("nonexistent") is False


def test_recipe_compiler_multi_layer() -> None:
    """RecipeCompiler handles multi-layer recipes."""
    recipe = EffectRecipe(
        recipe_id="multi_layer",
        name="Multi Layer",
        description="Two layers",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        timing=TimingHints(bars_min=1, bars_max=4),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="Color Wash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                density=0.5,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
            RecipeLayer(
                layer_index=1,
                layer_name="Sparkle",
                layer_depth=VisualDepth.FOREGROUND,
                effect_type="Sparkles",
                blend_mode=BlendMode.ADD,
                mix=0.6,
                density=0.3,
                color_source=ColorSource.WHITE_ONLY,
            ),
        ),
        provenance=RecipeProvenance(source="mined"),
        style_markers=StyleMarkers(complexity=0.67, energy_affinity=_EnergyTarget.MED),
    )
    catalog = RecipeCatalog(recipes=[recipe])
    compiler = RecipeCompiler(catalog=catalog)

    effects = compiler.compile(_make_placement("multi_layer"), _make_context())
    assert len(effects) == 2
    assert effects[0].visual_depth == VisualDepth.BACKGROUND
    assert effects[1].visual_depth == VisualDepth.FOREGROUND


def test_recipe_compiler_uses_layer_effect_type() -> None:
    """Compiler uses the layer's own effect_type when it is a real xLights effect."""
    recipe = EffectRecipe(
        recipe_id="gtpl_base_motif_abstract_ambient",
        name="Enriched Recipe",
        description="Layer has enriched effect_type",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        timing=TimingHints(bars_min=2, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="Twinkle",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[MotionVerb.FADE],
                density=0.5,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.33, energy_affinity=_EnergyTarget.LOW),
    )
    catalog = RecipeCatalog(recipes=[recipe])
    compiler = RecipeCompiler(catalog=catalog)

    effects = compiler.compile(
        _make_placement("gtpl_base_motif_abstract_ambient"),
        _make_context(),
    )

    assert len(effects) == 1
    # Should use layer's own effect_type "Twinkle", NOT the template-level
    # resolved type "Color Wash" from effect_map
    assert effects[0].event.effect_type == "Twinkle"


def test_recipe_compiler_falls_back_for_placeholder_effect_type() -> None:
    """Compiler falls back to resolve_effect_type when layer has a placeholder."""
    recipe = EffectRecipe(
        recipe_id="gtpl_base_motif_abstract_ambient",
        name="Unenriched Recipe",
        description="Layer still has placeholder effect_type",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        timing=TimingHints(bars_min=2, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="ABSTRACT",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={},
                motion=[MotionVerb.FADE],
                density=0.5,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.33, energy_affinity=_EnergyTarget.LOW),
    )
    catalog = RecipeCatalog(recipes=[recipe])
    compiler = RecipeCompiler(catalog=catalog)

    effects = compiler.compile(
        _make_placement("gtpl_base_motif_abstract_ambient"),
        _make_context(),
    )

    assert len(effects) == 1
    # Should fall back to resolve_effect_type which maps this to "Color Wash"
    assert effects[0].event.effect_type == "Color Wash"
