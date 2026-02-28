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


# ── Adaptive stability ────────────────────────────────────────────────────


class TestAdaptiveStability:
    """Tests for adaptive stability threshold computation."""

    def test_lower_threshold_for_small_diversity(self) -> None:
        """Smaller corpus diversity produces a lower effective threshold."""
        from twinklr.core.feature_engineering.promotion import _adaptive_stability

        low_diversity = _adaptive_stability(median_distinct_pack_count=2)
        high_diversity = _adaptive_stability(median_distinct_pack_count=10)
        assert low_diversity < high_diversity

    def test_higher_threshold_for_large_diversity(self) -> None:
        """Larger corpus diversity produces a higher effective threshold."""
        from twinklr.core.feature_engineering.promotion import _adaptive_stability

        val_5 = _adaptive_stability(median_distinct_pack_count=5)
        val_15 = _adaptive_stability(median_distinct_pack_count=15)
        assert val_15 > val_5

    def test_clamps_at_lower_bound(self) -> None:
        """Result never goes below the hard lower bound (0.3)."""
        from twinklr.core.feature_engineering.promotion import _adaptive_stability

        result = _adaptive_stability(median_distinct_pack_count=0)
        assert result >= 0.3

    def test_clamps_at_upper_bound(self) -> None:
        """Result never exceeds the hard upper bound (0.9)."""
        from twinklr.core.feature_engineering.promotion import _adaptive_stability

        result = _adaptive_stability(median_distinct_pack_count=1000)
        assert result <= 0.9

    def test_deterministic(self) -> None:
        """Same input always produces the same output."""
        from twinklr.core.feature_engineering.promotion import _adaptive_stability

        a = _adaptive_stability(median_distinct_pack_count=7)
        b = _adaptive_stability(median_distinct_pack_count=7)
        assert a == b

    def test_custom_bounds(self) -> None:
        """Custom lower/upper bounds are respected."""
        from twinklr.core.feature_engineering.promotion import _adaptive_stability

        result_low = _adaptive_stability(
            median_distinct_pack_count=0, lower_bound=0.1, upper_bound=0.5
        )
        assert result_low >= 0.1
        result_high = _adaptive_stability(
            median_distinct_pack_count=1000, lower_bound=0.1, upper_bound=0.5
        )
        assert result_high <= 0.5


# ── Content template promotion ────────────────────────────────────────────


class TestContentTemplatePromotion:
    """Content templates are promoted alongside orchestration templates."""

    def test_content_templates_promoted(self) -> None:
        """Content-kind templates pass through promotion pipeline."""
        content = _make_template(
            template_id="content-1",
            effect_family="bars",
            support_count=20,
            cross_pack_stability=0.7,
        )
        result = PromotionPipeline().run(candidates=[content])
        assert len(result.promoted_recipes) == 1

    def test_mixed_kinds_both_promoted(self) -> None:
        """Both content and orchestration templates are promoted."""
        content = _make_template(
            template_id="content-1",
            effect_family="bars",
        )
        orch = MinedTemplate(
            template_id="orch-1",
            template_kind=TemplateKind.ORCHESTRATION,
            template_signature="sparkle|pulse|palette|high|rhythmic|single_target|accent_hit",
            support_count=25,
            distinct_pack_count=5,
            support_ratio=0.4,
            cross_pack_stability=0.8,
            role="accent_hit",
            effect_family="sparkle",
            motion_class="pulse",
            color_class="palette",
            energy_class="high",
            continuity_class="rhythmic",
            spatial_class="single_target",
        )
        result = PromotionPipeline().run(candidates=[content, orch])
        assert len(result.promoted_recipes) == 2


# ── Stack-aware prioritization ────────────────────────────────────────────


class TestStackAwarePrioritization:
    """Stack-derived candidates with layer_count > 1 are prioritized."""

    @staticmethod
    def _make_stack_template(
        *,
        template_id: str = "stack-1",
        support_count: int = 20,
        cross_pack_stability: float = 0.65,
    ) -> MinedTemplate:
        return MinedTemplate(
            template_id=template_id,
            template_kind=TemplateKind.CONTENT,
            template_signature="color_wash+bars+sparkle|sweep|palette|high|sustained|multi_target",
            support_count=support_count,
            distinct_pack_count=5,
            support_ratio=0.35,
            cross_pack_stability=cross_pack_stability,
            effect_family="color_wash",
            motion_class="sweep",
            color_class="palette",
            energy_class="high",
            continuity_class="sustained",
            spatial_class="multi_target",
            layer_count=3,
            stack_composition=("color_wash", "bars", "sparkle"),
            layer_blend_modes=("NORMAL", "ADD", "SCREEN"),
            layer_mixes=(1.0, 0.7, 0.45),
        )

    def test_stack_template_promoted_with_adaptive_threshold(self) -> None:
        """Stack-derived template with layer_count > 1 passes adaptive gate."""
        stack = self._make_stack_template(cross_pack_stability=0.45)
        # With adaptive stability for low-diversity corpus the threshold
        # should be below 0.45, allowing this template through.
        result = PromotionPipeline().run(
            candidates=[stack],
            min_support=5,
            min_stability=0.45,
            use_stack_synthesis=True,
        )
        assert len(result.promoted_recipes) == 1

    def test_stack_template_uses_stack_synthesis(self) -> None:
        """Stack templates use stack synthesis path when enabled."""
        stack = self._make_stack_template()
        result = PromotionPipeline().run(
            candidates=[stack],
            use_stack_synthesis=True,
        )
        assert len(result.promoted_recipes) == 1
        recipe = result.promoted_recipes[0]
        # Stack synthesis should produce layers matching the stack composition
        assert len(recipe.layers) == 3

    def test_stack_report_includes_stack_promoted_count(self) -> None:
        """Report includes stack_promoted_count field."""
        stack = self._make_stack_template()
        single = _make_template(template_id="single-1")
        result = PromotionPipeline().run(
            candidates=[stack, single],
            use_stack_synthesis=True,
        )
        assert "stack_promoted_count" in result.report
        assert result.report["stack_promoted_count"] == 1


# ── Adaptive stability integration in promotion run ───────────────────────


class TestAdaptiveStabilityIntegration:
    """Adaptive stability improves pass-through vs static baseline."""

    def test_adaptive_mode_promotes_more_candidates(self) -> None:
        """With adaptive stability, more candidates pass the quality gate
        for a low-diversity corpus compared to a static threshold."""
        # Very-low-diversity candidates: stability=0.45, distinct_pack_count=1
        # _adaptive_stability(median=1) ≈ 0.437, so 0.45 passes adaptive gate.
        # Static min_stability=0.5 rejects all (0.45 < 0.5).
        candidates = [
            _make_template(
                template_id=f"t-{i}",
                support_count=10,
                distinct_pack_count=1,
                cross_pack_stability=0.45,
            )
            for i in range(5)
        ]
        # Static run with min_stability=0.5 rejects all
        static_result = PromotionPipeline().run(
            candidates=candidates,
            min_stability=0.5,
            adaptive_stability=False,
        )
        # Adaptive run lowers threshold for very sparse corpus
        adaptive_result = PromotionPipeline().run(
            candidates=candidates,
            min_stability=0.5,
            adaptive_stability=True,
        )
        assert len(adaptive_result.promoted_recipes) > len(static_result.promoted_recipes)
