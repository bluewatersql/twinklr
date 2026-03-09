"""Tests for recipe_builder evidence (catalog analysis) module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from twinklr.core.recipe_builder.evidence import (
    analyze_catalog,
    format_analysis_for_prompt,
    identify_opportunities,
)
from twinklr.core.recipe_builder.models import Opportunity

if TYPE_CHECKING:
    from twinklr.core.recipe_builder.models import CatalogAnalysis
    from twinklr.core.sequencer.templates.group.recipe import EffectRecipe


def test_analyze_empty_catalog():
    analysis = analyze_catalog([])
    assert analysis.total_recipes == 0
    assert "Empty catalog" in analysis.summary


def test_analyze_catalog_counts(sample_recipes: list[EffectRecipe]):
    analysis = analyze_catalog(sample_recipes)
    assert analysis.total_recipes == len(sample_recipes)


def test_analyze_catalog_effect_distribution(sample_recipes: list[EffectRecipe]):
    analysis = analyze_catalog(sample_recipes)
    effect_names = {e.name for e in analysis.effect_type_distribution}
    assert "Twinkle" in effect_names
    assert "Fire" in effect_names


def test_analyze_catalog_energy_distribution(sample_recipes: list[EffectRecipe]):
    analysis = analyze_catalog(sample_recipes)
    energy_names = {e.name for e in analysis.energy_distribution}
    assert "LOW" in energy_names
    assert "HIGH" in energy_names


def test_analyze_catalog_underutilized_effects(sample_recipes: list[EffectRecipe]):
    analysis = analyze_catalog(sample_recipes)
    assert len(analysis.underutilized_effects) > 0
    for ue in analysis.underutilized_effects:
        count = next(
            (e.count for e in analysis.effect_type_distribution if e.name == ue),
            0,
        )
        assert count <= 1


def test_analyze_catalog_underutilized_motions(sample_recipes: list[EffectRecipe]):
    analysis = analyze_catalog(sample_recipes)
    assert len(analysis.underutilized_motions) > 0


def test_analyze_catalog_layer_counts(sample_recipes: list[EffectRecipe]):
    analysis = analyze_catalog(sample_recipes)
    layer_names = {e.name for e in analysis.layer_count_distribution}
    assert "1" in layer_names


def test_identify_opportunities_non_empty(sample_analysis: CatalogAnalysis):
    opportunities = identify_opportunities(sample_analysis)
    assert len(opportunities) > 0
    for opp in opportunities:
        assert isinstance(opp, Opportunity)


def test_identify_opportunities_sorted_by_priority(sample_analysis: CatalogAnalysis):
    opportunities = identify_opportunities(sample_analysis)
    priorities = [o.priority for o in opportunities]
    assert priorities == sorted(priorities, reverse=True)


def test_identify_opportunities_respects_max(sample_analysis: CatalogAnalysis):
    opportunities = identify_opportunities(sample_analysis, max_opportunities=2)
    assert len(opportunities) <= 2


def test_identify_opportunities_includes_missing_effects(
    sample_analysis: CatalogAnalysis,
):
    opportunities = identify_opportunities(sample_analysis)
    categories = {o.category for o in opportunities}
    assert "missing_effect_type" in categories


def test_identify_opportunities_includes_missing_energy_combos(
    sample_analysis: CatalogAnalysis,
):
    opportunities = identify_opportunities(sample_analysis)
    categories = {o.category for o in opportunities}
    assert "missing_energy_variant" in categories


def test_identify_opportunities_includes_underutilized_motions(
    sample_analysis: CatalogAnalysis,
):
    opportunities = identify_opportunities(sample_analysis)
    categories = {o.category for o in opportunities}
    assert "underutilized_motion" in categories


def test_format_analysis_for_prompt(sample_analysis: CatalogAnalysis):
    text = format_analysis_for_prompt(sample_analysis)
    assert "Catalog:" in text
    assert "Twinkle" in text
    assert "Underutilized" in text


def test_opportunities_have_unique_ids(sample_analysis: CatalogAnalysis):
    opportunities = identify_opportunities(sample_analysis)
    ids = [o.opportunity_id for o in opportunities]
    assert len(ids) == len(set(ids))
