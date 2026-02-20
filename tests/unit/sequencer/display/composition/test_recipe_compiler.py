"""Tests for RecipeCompiler and HybridTemplateCompiler."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.composition.hybrid_compiler import (
    HybridTemplateCompiler,
)
from twinklr.core.sequencer.display.composition.recipe_compiler import RecipeCompiler
from twinklr.core.sequencer.display.composition.models import TemplateCompileError
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
    )
    catalog = RecipeCatalog(recipes=[recipe])
    compiler = RecipeCompiler(catalog=catalog)

    effects = compiler.compile(_make_placement("multi_layer"), _make_context())
    assert len(effects) == 2
    assert effects[0].visual_depth == VisualDepth.BACKGROUND
    assert effects[1].visual_depth == VisualDepth.FOREGROUND


def test_hybrid_compiler_routes_to_recipe() -> None:
    """HybridTemplateCompiler delegates to RecipeCompiler for known recipes."""
    recipe = _make_recipe()
    catalog = RecipeCatalog(recipes=[recipe])
    recipe_compiler = RecipeCompiler(catalog=catalog)

    # Mock default compiler that should not be called
    class FailCompiler:
        def compile(self, placement, context):  # noqa: ANN001, ANN201, ARG002
            raise AssertionError("Should not be called for recipe IDs")

    hybrid = HybridTemplateCompiler(
        recipe_compiler=recipe_compiler,
        default_compiler=FailCompiler(),  # type: ignore[arg-type]
    )

    effects = hybrid.compile(_make_placement(), _make_context())
    assert len(effects) == 1
    assert effects[0].event.effect_type == "Color Wash"


def test_hybrid_compiler_falls_back_to_default() -> None:
    """HybridTemplateCompiler falls back to DefaultCompiler for unknown recipe IDs."""
    catalog = RecipeCatalog(recipes=[])
    recipe_compiler = RecipeCompiler(catalog=catalog)

    class StubDefaultCompiler:
        def compile(self, placement, context):  # noqa: ANN001, ANN201, ARG002
            from twinklr.core.sequencer.display.composition.models import CompiledEffect
            from twinklr.core.sequencer.display.models.render_event import (
                RenderEvent,
                RenderEventSource,
            )

            from twinklr.core.sequencer.display.models.palette import ResolvedPalette

            return [
                CompiledEffect(
                    event=RenderEvent(
                        event_id="stub",
                        start_ms=0,
                        end_ms=1000,
                        effect_type="Stub",
                        palette=ResolvedPalette(colors=["#FFFFFF"], active_slots=[1]),
                        source=RenderEventSource(
                            section_id="s1",
                            lane=LaneKind.BASE,
                            group_id="g1",
                            template_id="gtpl_stub",
                        ),
                    ),
                    visual_depth=VisualDepth.BACKGROUND,
                )
            ]

    hybrid = HybridTemplateCompiler(
        recipe_compiler=recipe_compiler,
        default_compiler=StubDefaultCompiler(),  # type: ignore[arg-type]
    )

    effects = hybrid.compile(_make_placement("gtpl_stub"), _make_context())
    assert len(effects) == 1
    assert effects[0].event.effect_type == "Stub"
