"""Tests for recipe_builder Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError
import pytest

from twinklr.core.recipe_builder.models import (
    SCHEMA_VERSION,
    CatalogAnalysis,
    DistributionEntry,
    MetadataEnrichmentCandidate,
    Opportunity,
    RecipeCandidate,
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
    VisualDepth,
)


def _make_recipe(recipe_id: str = "r1") -> EffectRecipe:
    layer = RecipeLayer(
        layer_index=0,
        layer_name="bg",
        layer_depth=VisualDepth.BACKGROUND,
        effect_type="On",
        blend_mode=BlendMode.NORMAL,
        mix=1.0,
        density=0.5,
    )
    return EffectRecipe(
        recipe_id=recipe_id,
        name="R1",
        description="A recipe",
        recipe_version="1.0.0",
        effect_family="test",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["test"],
        timing=TimingHints(bars_min=4, bars_max=16),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=(layer,),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.5, energy_affinity=EnergyTarget.MED),
    )


def test_schema_version_constant():
    assert SCHEMA_VERSION == "2.0.0"


def test_distribution_entry_defaults():
    entry = DistributionEntry(name="test")
    assert entry.count == 0
    assert entry.percentage == 0.0


def test_distribution_entry_percentage_bounds():
    with pytest.raises(ValidationError):
        DistributionEntry(name="x", count=1, percentage=101.0)


def test_catalog_analysis_frozen():
    analysis = CatalogAnalysis(
        generated_at=datetime.now(UTC),
        total_recipes=0,
    )
    with pytest.raises((TypeError, ValidationError)):
        analysis.total_recipes = 5  # type: ignore[misc]


def test_catalog_analysis_defaults():
    analysis = CatalogAnalysis(generated_at=datetime.now(UTC))
    assert analysis.total_recipes == 0
    assert analysis.underutilized_effects == []
    assert analysis.missing_energy_combos == []


def test_opportunity_mode_literal():
    with pytest.raises(ValidationError):
        Opportunity(
            opportunity_id="opp1",
            category="invalid_category",  # type: ignore[arg-type]
            description="test",
            priority=0.5,
        )


def test_opportunity_priority_bounds():
    with pytest.raises(ValidationError):
        Opportunity(
            opportunity_id="opp1",
            category="missing_effect_type",
            description="test",
            priority=1.5,
        )


def test_recipe_candidate_schema_version():
    recipe = _make_recipe()
    candidate = RecipeCandidate(
        candidate_id="cid1",
        source_opportunity_id="opp1",
        recipe=recipe,
    )
    assert candidate.schema_version == SCHEMA_VERSION


def test_recipe_candidate_frozen():
    recipe = _make_recipe()
    candidate = RecipeCandidate(
        candidate_id="cid1",
        source_opportunity_id="opp1",
        recipe=recipe,
    )
    with pytest.raises((TypeError, ValidationError)):
        candidate.candidate_id = "changed"  # type: ignore[misc]


def test_metadata_enrichment_candidate_frozen():
    candidate = MetadataEnrichmentCandidate(
        candidate_id="enr_abc123",
        target_recipe_id="r1",
        proposed_metadata_patch={"tags": ["a", "b"]},
    )
    with pytest.raises((TypeError, ValidationError)):
        candidate.target_recipe_id = "r2"  # type: ignore[misc]
