"""Shared fixtures for recipe_builder tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from twinklr.core.recipe_builder.models import (
    CatalogAnalysis,
    DistributionEntry,
    Opportunity,
)
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    VisualDepth,
)


@pytest.fixture
def sample_recipe() -> EffectRecipe:
    """Minimal valid EffectRecipe for testing."""
    layer = RecipeLayer(
        layer_index=0,
        layer_name="main",
        layer_depth=VisualDepth.BACKGROUND,
        effect_type="Twinkle",
        blend_mode=BlendMode.NORMAL,
        mix=1.0,
        density=0.5,
    )
    return EffectRecipe(
        recipe_id="test_twinkle_v1",
        name="Test Twinkle",
        description="A simple test twinkle recipe for unit testing",
        recipe_version="1.0.0",
        effect_family="twinkle",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["twinkle", "test"],
        timing=TimingHints(bars_min=4, bars_max=16),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(layer,),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.3, energy_affinity=EnergyTarget.LOW),
    )


@pytest.fixture
def sample_recipes(sample_recipe: EffectRecipe) -> list[EffectRecipe]:
    """Multiple diverse recipes for catalog analysis testing."""
    fire_layer = RecipeLayer(
        layer_index=0,
        layer_name="fire_bg",
        layer_depth=VisualDepth.MIDGROUND,
        effect_type="Fire",
        blend_mode=BlendMode.ADD,
        mix=1.0,
        motion=[MotionVerb.SHIMMER],
        density=0.7,
    )
    fire_recipe = EffectRecipe(
        recipe_id="test_fire_v1",
        name="Test Fire",
        description="A fire recipe for testing catalog analysis",
        recipe_version="1.0.0",
        effect_family="fire",
        template_type=GroupTemplateType.RHYTHM,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["fire", "test"],
        timing=TimingHints(bars_min=2, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=(fire_layer,),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.6, energy_affinity=EnergyTarget.HIGH),
    )

    spiral_layer = RecipeLayer(
        layer_index=0,
        layer_name="spiral_main",
        layer_depth=VisualDepth.MIDGROUND,
        effect_type="Spirals",
        blend_mode=BlendMode.ADD,
        mix=1.0,
        motion=[MotionVerb.SWEEP],
        density=0.5,
    )
    spiral_recipe = EffectRecipe(
        recipe_id="test_spirals_v1",
        name="Test Spirals",
        description="A spirals recipe for testing catalog analysis",
        recipe_version="1.0.0",
        effect_family="spirals",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.GEOMETRIC,
        tags=["spirals", "test"],
        timing=TimingHints(bars_min=1, bars_max=4),
        palette_spec=PaletteSpec(mode=ColorMode.TRIAD, palette_roles=["primary", "accent"]),
        layers=(spiral_layer,),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.7, energy_affinity=EnergyTarget.HIGH),
    )

    return [sample_recipe, fire_recipe, spiral_recipe]


@pytest.fixture
def sample_analysis() -> CatalogAnalysis:
    """Minimal catalog analysis for testing."""
    return CatalogAnalysis(
        generated_at=datetime.now(UTC),
        total_recipes=3,
        effect_type_distribution=[
            DistributionEntry(name="Twinkle", count=1, percentage=33.3),
            DistributionEntry(name="Fire", count=1, percentage=33.3),
            DistributionEntry(name="Spirals", count=1, percentage=33.3),
        ],
        energy_distribution=[
            DistributionEntry(name="LOW", count=1, percentage=33.3),
            DistributionEntry(name="HIGH", count=2, percentage=66.7),
        ],
        template_type_distribution=[
            DistributionEntry(name="BASE", count=1, percentage=33.3),
            DistributionEntry(name="RHYTHM", count=1, percentage=33.3),
            DistributionEntry(name="ACCENT", count=1, percentage=33.3),
        ],
        underutilized_effects=["Ripple", "Snowflakes", "Pinwheel"],
        underutilized_motions=["ROLL", "FLIP", "WIPE"],
        missing_energy_combos=["Twinkle × HIGH", "Fire × LOW"],
        summary="3 recipes in catalog.",
    )


@pytest.fixture
def sample_opportunity() -> Opportunity:
    """A single creative opportunity for testing."""
    return Opportunity(
        opportunity_id="opp_test_001",
        category="missing_effect_type",
        description="Effect type 'Ripple' has 0 recipes. Create a recipe showcasing Ripple.",
        priority=0.9,
        target_effect_type="Ripple",
        context="This effect is completely absent in the catalog.",
    )
