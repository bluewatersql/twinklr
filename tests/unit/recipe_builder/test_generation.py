"""Tests for recipe_builder generation module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from twinklr.core.agents.providers.base import (
    LLMProvider,
    LLMResponse,
    ResponseMetadata,
)
from twinklr.core.config.models import AgentConfig
from twinklr.core.recipe_builder.generation import (
    _select_diverse_examples,
    generate_candidates,
    generate_deterministic,
    generate_with_llm,
)
from twinklr.core.recipe_builder.models import (
    Opportunity,
    RecipeCandidate,
)

if TYPE_CHECKING:
    from twinklr.core.recipe_builder.models import CatalogAnalysis
    from twinklr.core.sequencer.templates.group.recipe import EffectRecipe


class _FakeProvider(LLMProvider):
    """Fake LLMProvider that returns a pre-built LLMResponse."""

    def __init__(self, content: dict[str, Any]) -> None:
        self._content = content
        self.calls: list[dict[str, Any]] = []

    def generate_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                **kwargs,
            }
        )
        return LLMResponse(content=self._content, metadata=ResponseMetadata())


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
        layer.effect_type == sample_opportunity.target_effect_type for layer in recipe.layers
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
        provider=None,
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
        provider=None,
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


# ---------------------------------------------------------------------------
# generate_with_llm — provider framework
# ---------------------------------------------------------------------------


def test_generate_with_llm_uses_provider_framework(
    sample_opportunity: Opportunity,
    sample_analysis: CatalogAnalysis,
    sample_recipes: list[EffectRecipe],
    sample_recipe: EffectRecipe,
) -> None:
    """generate_with_llm() calls provider.generate_json() with config's model/
    temperature and reads response.content directly (no manual json.loads)."""
    raw = sample_recipe.model_dump(mode="json")
    raw["recipe_id"] = "rb_generated_test_v1"
    provider = _FakeProvider(content=raw)
    config = AgentConfig(
        model="configured-recipe-model",
        temperature=0.42,
        reasoning_effort="high",
        max_tokens=1234,
        timeout_seconds=17,
    )

    candidates = generate_with_llm(
        opportunities=[sample_opportunity],
        analysis=sample_analysis,
        catalog_recipes=sample_recipes,
        provider=provider,
        config=config,
    )

    assert len(candidates) == 1
    assert candidates[0].generation_mode == "llm"
    assert len(provider.calls) == 1
    assert provider.calls[0]["model"] == "configured-recipe-model"
    assert provider.calls[0]["temperature"] == pytest.approx(0.42)
    assert provider.calls[0]["reasoning_effort"] == "high"
    assert provider.calls[0]["max_tokens"] == 1234
    assert provider.calls[0]["timeout_seconds"] == 17


def test_generate_candidates_dispatches_to_provider(
    sample_opportunity: Opportunity,
    sample_analysis: CatalogAnalysis,
    sample_recipes: list[EffectRecipe],
    sample_recipe: EffectRecipe,
) -> None:
    """generate_candidates() with a provider and dry_run=False uses the LLM path."""
    raw = sample_recipe.model_dump(mode="json")
    raw["recipe_id"] = "rb_generated_test_v2"
    provider = _FakeProvider(content=raw)

    candidates = generate_candidates(
        opportunities=[sample_opportunity],
        analysis=sample_analysis,
        catalog_recipes=sample_recipes,
        provider=provider,
        dry_run=False,
    )

    assert len(candidates) == 1
    assert candidates[0].generation_mode == "llm"
    assert len(provider.calls) == 1


def test_generate_candidates_uses_central_sol_tier_request_defaults(
    sample_opportunity: Opportunity,
    sample_analysis: CatalogAnalysis,
    sample_recipes: list[EffectRecipe],
    sample_recipe: EffectRecipe,
) -> None:
    """The live default is the spec's sol-tier config with every request knob explicit."""
    raw = sample_recipe.model_dump(mode="json")
    raw["recipe_id"] = "rb_generated_sol_default_v1"
    provider = _FakeProvider(content=raw)

    candidates = generate_candidates(
        opportunities=[sample_opportunity],
        analysis=sample_analysis,
        catalog_recipes=sample_recipes,
        provider=provider,
        dry_run=False,
    )

    assert len(candidates) == 1
    assert len(provider.calls) == 1
    request = {key: value for key, value in provider.calls[0].items() if key != "messages"}
    assert request == {
        "model": "gpt-5.6-sol",
        "temperature": 0.9,
        "reasoning_effort": "high",
        "max_tokens": 50000,
        "timeout_seconds": 60,
    }


# ---------------------------------------------------------------------------
# _select_diverse_examples — seeded shuffle determinism
# ---------------------------------------------------------------------------


def test_select_diverse_examples_is_deterministic(
    sample_opportunity: Opportunity,
    sample_recipes: list[EffectRecipe],
) -> None:
    """Two calls with the same opportunity + catalog produce identical
    selected-example ordering; a different opportunity may (not must)
    produce a different ordering."""
    first = _select_diverse_examples(sample_recipes, sample_opportunity)
    second = _select_diverse_examples(sample_recipes, sample_opportunity)

    assert [r.recipe_id for r in first] == [r.recipe_id for r in second]

    other_opportunity = Opportunity(
        opportunity_id="opp_other_002",
        category="missing_effect_type",
        description="A different opportunity for shuffle-seed comparison.",
        priority=0.5,
        target_effect_type="Fire",
    )
    other = _select_diverse_examples(sample_recipes, other_opportunity)
    # Reproducibility (not divergence) is the primary claim — re-running with
    # the same opportunity is still deterministic even when compared here.
    other_repeat = _select_diverse_examples(sample_recipes, other_opportunity)
    assert [r.recipe_id for r in other] == [r.recipe_id for r in other_repeat]
