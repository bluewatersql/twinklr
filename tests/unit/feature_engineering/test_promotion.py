"""Tests for the Promotion Pipeline."""

from __future__ import annotations

from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateKind,
)
from twinklr.core.feature_engineering.promotion import (
    EXCLUDED_FAMILIES,
    PromotionPipeline,
    PromotionResult,
)
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe


def _make_template(
    *,
    template_id: str = "tpl-1",
    support_count: int = 25,
    distinct_pack_count: int = 5,
    cross_pack_stability: float = 0.8,
    effect_family: str = "single_strand",
) -> MinedTemplate:
    return MinedTemplate(
        template_id=template_id,
        template_kind=TemplateKind.CONTENT,
        template_signature=f"{effect_family}|sweep|palette|mid|rhythmic|single_target",
        support_count=support_count,
        distinct_pack_count=distinct_pack_count,
        support_ratio=0.4,
        cross_pack_stability=cross_pack_stability,
        onset_sync_mean=0.7,
        role="rhythm_driver",
        effect_family=effect_family,
        motion_class="sweep",
        color_class="palette",
        energy_class="mid",
        continuity_class="rhythmic",
        spatial_class="single_target",
    )


def test_promotion_filters_low_support() -> None:
    """Templates below min_support are rejected."""
    low = _make_template(template_id="low", support_count=3)
    high = _make_template(template_id="high", support_count=25)
    result = PromotionPipeline().run(
        candidates=[low, high],
        min_support=10,
    )
    assert isinstance(result, PromotionResult)
    assert len(result.promoted_recipes) == 1
    assert result.promoted_recipes[0].provenance.source == "mined"
    assert result.report["rejected_count"] == 1


def test_promotion_filters_low_stability() -> None:
    """Templates below min_stability are rejected."""
    unstable = _make_template(template_id="unstable", cross_pack_stability=0.2)
    stable = _make_template(template_id="stable", cross_pack_stability=0.8)
    result = PromotionPipeline().run(
        candidates=[unstable, stable],
        min_stability=0.5,
    )
    assert len(result.promoted_recipes) == 1
    assert result.report["rejected_count"] == 1


def test_promotion_all_pass() -> None:
    """All templates pass when they meet criteria."""
    t1 = _make_template(template_id="t1")
    t2 = _make_template(template_id="t2", effect_family="shimmer")
    result = PromotionPipeline().run(candidates=[t1, t2])
    assert len(result.promoted_recipes) == 2
    assert result.report["rejected_count"] == 0


def test_promotion_empty_candidates() -> None:
    """Empty candidates produce empty result."""
    result = PromotionPipeline().run(candidates=[])
    assert len(result.promoted_recipes) == 0
    assert result.report["rejected_count"] == 0


def test_promotion_cluster_dedup() -> None:
    """Templates in the same cluster are merged into one recipe."""
    t_a = _make_template(template_id="a", effect_family="sparkle")
    t_b = _make_template(template_id="b", effect_family="sparkle")
    clusters = [{"cluster_id": "c1", "member_ids": ["a", "b"], "keep_id": "a"}]
    result = PromotionPipeline().run(
        candidates=[t_a, t_b],
        clusters=clusters,
    )
    assert len(result.promoted_recipes) == 1
    recipe = result.promoted_recipes[0]
    assert recipe.provenance.source == "mined"


def test_promotion_produces_valid_recipes() -> None:
    """All promoted recipes are valid EffectRecipe instances."""
    t1 = _make_template(template_id="valid1")
    result = PromotionPipeline().run(candidates=[t1])
    for recipe in result.promoted_recipes:
        assert isinstance(recipe, EffectRecipe)
        assert recipe.provenance.source == "mined"
        assert len(recipe.layers) >= 1


# ── Family filter ──────────────────────────────────────────────────────────


def test_promotion_filters_excluded_families() -> None:
    """DMX, moving_head, servo, state, duplicate, glediator are excluded."""
    included = _make_template(template_id="ok", effect_family="sparkle")
    excluded = [
        _make_template(template_id=f"ex_{fam}", effect_family=fam)
        for fam in ("dmx", "moving_head", "servo", "state", "duplicate", "glediator")
    ]
    result = PromotionPipeline().run(candidates=[included, *excluded])
    assert len(result.promoted_recipes) == 1
    assert result.report["filtered_families"] == 6
    assert result.promoted_recipes[0].provenance.source == "mined"


def test_promotion_excluded_families_constant() -> None:
    """EXCLUDED_FAMILIES contains the expected set."""
    expected = {"dmx", "moving_head", "servo", "glediator", "state", "duplicate"}
    assert expected == EXCLUDED_FAMILIES


def test_promotion_custom_excluded_families() -> None:
    """Pipeline accepts custom exclusion set."""
    t1 = _make_template(template_id="t1", effect_family="fire")
    pipeline = PromotionPipeline(excluded_families=frozenset({"fire"}))
    result = pipeline.run(candidates=[t1])
    assert len(result.promoted_recipes) == 0
    assert result.report["filtered_families"] == 1
