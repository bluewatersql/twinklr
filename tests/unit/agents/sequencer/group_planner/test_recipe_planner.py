"""Tests for recipe-aware planner context and shaping.

Verifies that SectionPlanningContext accepts an optional RecipeCatalog
and that shape_planner_context surfaces recipe metadata for the LLM.
"""

from __future__ import annotations

from typing import Any

import pytest

from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
from twinklr.core.agents.sequencer.group_planner.context_shaping import (
    shape_planner_context,
)
from twinklr.core.agents.sequencer.group_planner.timing import TimingContext
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog, TemplateInfo
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    ModelAffinity,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
)
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
    MotionVerb,
    VisualDepth,
)


def _make_recipe(
    *,
    recipe_id: str = "test_recipe",
    template_type: GroupTemplateType = GroupTemplateType.RHYTHM,
    effect_type: str = "ColorWash",
    model_affinities: list[ModelAffinity] | None = None,
    num_layers: int = 1,
) -> EffectRecipe:
    """Helper to create test EffectRecipe."""
    layers = tuple(
        RecipeLayer(
            layer_index=i,
            layer_name=f"Layer {i}",
            layer_depth=VisualDepth.BACKGROUND if i == 0 else VisualDepth.MIDGROUND,
            effect_type=effect_type if i == 0 else "Sparkles",
            blend_mode=BlendMode.NORMAL if i == 0 else BlendMode.ADD,
            mix=1.0 if i == 0 else 0.5,
            params={},
            motion=[MotionVerb.FADE],
            density=0.5,
            color_source=ColorSource.PALETTE_PRIMARY,
        )
        for i in range(num_layers)
    )
    return EffectRecipe(
        recipe_id=recipe_id,
        name=f"Test {recipe_id}",
        description="Test recipe",
        recipe_version="1.0.0",
        template_type=template_type,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=[],
        timing=TimingHints(bars_min=2, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=layers,
        provenance=RecipeProvenance(source="mined"),
        model_affinities=model_affinities or [],
    )


def _make_section_context(
    *,
    recipe_catalog: RecipeCatalog | None = None,
) -> SectionPlanningContext:
    """Helper to create SectionPlanningContext with optional recipe catalog."""
    groups = [
        ChoreoGroup(id="MEGA_TREE", role="HERO"),
        ChoreoGroup(id="ARCHES", role="ARCHES"),
    ]
    choreo_graph = ChoreographyGraph(graph_id="test_display", groups=groups)
    template_catalog = TemplateCatalog(
        schema_version="template-catalog.v1",
        entries=[
            TemplateInfo(
                template_id="gtpl_base_glow",
                version="1.0",
                name="Glow",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                tags=(),
            ),
        ],
    )
    timing_context = TimingContext(
        song_duration_ms=120000,
        beats_per_bar=4,
    )
    return SectionPlanningContext(
        section_id="verse_1",
        section_name="Verse",
        start_ms=0,
        end_ms=8000,
        energy_target="LOW",
        motion_density="SPARSE",
        choreography_style="ABSTRACT",
        primary_focus_targets=["HERO"],
        secondary_targets=["ARCHES"],
        choreo_graph=choreo_graph,
        template_catalog=template_catalog,
        timing_context=timing_context,
        recipe_catalog=recipe_catalog,
    )


# ============================================================================
# SectionPlanningContext accepts recipe_catalog
# ============================================================================


def test_section_context_accepts_recipe_catalog() -> None:
    """SectionPlanningContext can be created with a RecipeCatalog."""
    catalog = RecipeCatalog(recipes=[_make_recipe(recipe_id="r1")])
    ctx = _make_section_context(recipe_catalog=catalog)
    assert ctx.recipe_catalog is not None
    assert ctx.recipe_catalog.has_recipe("r1")


def test_section_context_recipe_catalog_defaults_none() -> None:
    """RecipeCatalog defaults to None when not provided."""
    ctx = _make_section_context()
    assert ctx.recipe_catalog is None


def test_recipes_for_lane() -> None:
    """recipes_for_lane returns recipes filtered by lane."""
    base = _make_recipe(recipe_id="base1", template_type=GroupTemplateType.BASE)
    rhythm = _make_recipe(recipe_id="rhythm1", template_type=GroupTemplateType.RHYTHM)
    catalog = RecipeCatalog(recipes=[base, rhythm])
    ctx = _make_section_context(recipe_catalog=catalog)
    base_recipes = ctx.recipes_for_lane(LaneKind.BASE)
    assert len(base_recipes) == 1
    assert base_recipes[0].recipe_id == "base1"


def test_recipes_for_lane_no_catalog() -> None:
    """recipes_for_lane returns empty list when no catalog."""
    ctx = _make_section_context()
    assert ctx.recipes_for_lane(LaneKind.BASE) == []


# ============================================================================
# shape_planner_context includes recipe metadata
# ============================================================================


def test_shape_planner_context_includes_recipe_catalog() -> None:
    """shape_planner_context includes recipe_catalog when present."""
    r1 = _make_recipe(
        recipe_id="synth_sparkle_sweep_1",
        template_type=GroupTemplateType.RHYTHM,
        effect_type="Sparkles",
        num_layers=2,
        model_affinities=[ModelAffinity(model_type="megatree", score=0.9)],
    )
    catalog = RecipeCatalog(recipes=[r1])
    ctx = _make_section_context(recipe_catalog=catalog)
    shaped = shape_planner_context(ctx)

    assert "recipe_catalog" in shaped
    rc = shaped["recipe_catalog"]
    assert len(rc["entries"]) == 1
    entry = rc["entries"][0]
    assert entry["recipe_id"] == "synth_sparkle_sweep_1"
    assert entry["layer_count"] == 2
    assert "Sparkles" in entry["effect_types"]
    assert len(entry["model_affinities"]) == 1
    assert entry["model_affinities"][0]["model_type"] == "megatree"


def test_shape_planner_context_recipe_catalog_none() -> None:
    """shape_planner_context sets recipe_catalog to None when absent."""
    ctx = _make_section_context()
    shaped = shape_planner_context(ctx)
    assert shaped["recipe_catalog"] is None


def test_shape_planner_context_recipe_effect_types_unique() -> None:
    """Recipe effect_types in shaped context are deduplicated."""
    r1 = _make_recipe(
        recipe_id="multi_layer",
        num_layers=3,
        effect_type="ColorWash",  # layer 0=ColorWash, 1,2=Sparkles
    )
    catalog = RecipeCatalog(recipes=[r1])
    ctx = _make_section_context(recipe_catalog=catalog)
    shaped = shape_planner_context(ctx)
    entry = shaped["recipe_catalog"]["entries"][0]
    # ColorWash + Sparkles (deduplicated)
    assert len(entry["effect_types"]) == 2
    assert "ColorWash" in entry["effect_types"]
    assert "Sparkles" in entry["effect_types"]
