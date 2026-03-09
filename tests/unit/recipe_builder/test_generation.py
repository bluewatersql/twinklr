"""Tests for recipe_builder generation module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from twinklr.core.recipe_builder.generation import (
    generate_candidates,
    generate_deterministic,
)
from twinklr.core.recipe_builder.models import (
    Opportunity,
    RecipeCandidate,
)

if TYPE_CHECKING:
    from twinklr.core.recipe_builder.models import CatalogAnalysis
    from twinklr.core.sequencer.templates.group.recipe import EffectRecipe


def test_generate_deterministic_returns_list(sample_opportunity: Opportunity):
    candidates = generate_deterministic([sample_opportunity])
    assert isinstance(candidates, list)


def test_generate_deterministic_produces_candidates(sample_opportunity: Opportunity):
    candidates = generate_deterministic([sample_opportunity])
    assert len(candidates) == 1
    assert isinstance(candidates[0], RecipeCandidate)


def test_generate_deterministic_mode_label(sample_opportunity: Opportunity):
    candidates = generate_deterministic([sample_opportunity])
    for c in candidates:
        assert c.generation_mode == "deterministic"


def test_generate_deterministic_recipe_has_layers(sample_opportunity: Opportunity):
    candidates = generate_deterministic([sample_opportunity])
    for c in candidates:
        assert len(c.recipe.layers) > 0


def test_generate_deterministic_uses_target_effect(sample_opportunity: Opportunity):
    candidates = generate_deterministic([sample_opportunity])
    recipe = candidates[0].recipe
    assert any(
        layer.effect_type == sample_opportunity.target_effect_type
        for layer in recipe.layers
    )


def test_generate_deterministic_unique_ids(sample_opportunity: Opportunity):
    opps = [
        Opportunity(
            opportunity_id=f"opp_{i}",
            category="missing_effect_type",
            description=f"Test opportunity {i}",
            priority=0.8,
            target_effect_type="Fire",
        )
        for i in range(3)
    ]
    candidates = generate_deterministic(opps)
    ids = [c.candidate_id for c in candidates]
    assert len(ids) == len(set(ids))


def test_generate_deterministic_recipe_ids_unique(sample_opportunity: Opportunity):
    opps = [
        Opportunity(
            opportunity_id=f"opp_{i}",
            category="missing_effect_type",
            description=f"Test {i}",
            priority=0.5,
            target_effect_type="Fire",
        )
        for i in range(3)
    ]
    candidates = generate_deterministic(opps)
    recipe_ids = [c.recipe.recipe_id for c in candidates]
    assert len(recipe_ids) == len(set(recipe_ids))


def test_generate_candidates_dry_run(
    sample_opportunity: Opportunity,
    sample_analysis: CatalogAnalysis,
    sample_recipes: list[EffectRecipe],
):
    candidates = generate_candidates(
        opportunities=[sample_opportunity],
        analysis=sample_analysis,
        catalog_recipes=sample_recipes,
        llm_client=None,
        dry_run=True,
    )
    assert len(candidates) == 1
    assert candidates[0].generation_mode == "deterministic"


def test_generate_candidates_no_client_fallback(
    sample_opportunity: Opportunity,
    sample_analysis: CatalogAnalysis,
    sample_recipes: list[EffectRecipe],
):
    candidates = generate_candidates(
        opportunities=[sample_opportunity],
        analysis=sample_analysis,
        catalog_recipes=sample_recipes,
        llm_client=None,
        dry_run=False,
    )
    assert len(candidates) == 1
    assert candidates[0].generation_mode == "deterministic"


def test_generate_candidates_empty_opportunities(
    sample_analysis: CatalogAnalysis,
    sample_recipes: list[EffectRecipe],
):
    candidates = generate_candidates(
        opportunities=[],
        analysis=sample_analysis,
        catalog_recipes=sample_recipes,
        dry_run=True,
    )
    assert candidates == []


def test_generate_deterministic_energy_target():
    opp = Opportunity(
        opportunity_id="opp_low_fire",
        category="missing_energy_variant",
        description="Create a LOW energy Fire recipe",
        priority=0.7,
        target_effect_type="Fire",
        target_energy="LOW",
    )
    candidates = generate_deterministic([opp])
    assert candidates[0].recipe.style_markers.energy_affinity.value == "LOW"


def test_generate_deterministic_template_type():
    opp = Opportunity(
        opportunity_id="opp_accent",
        category="missing_template_type",
        description="Create an ACCENT recipe",
        priority=0.6,
        target_template_type="ACCENT",
    )
    candidates = generate_deterministic([opp])
    assert candidates[0].recipe.template_type.value == "ACCENT"


def test_generate_deterministic_motion_target():
    opp = Opportunity(
        opportunity_id="opp_roll",
        category="underutilized_motion",
        description="Create a recipe featuring ROLL motion",
        priority=0.65,
        target_motions=["ROLL"],
    )
    candidates = generate_deterministic([opp])
    recipe = candidates[0].recipe
    motions = [m.value for layer in recipe.layers for m in layer.motion]
    assert "ROLL" in motions
