"""Tests for Phase 01 promotion threshold changes.

Validates:
- Default config thresholds (0.05 stability, adaptive=True, max_per_family=10)
- Adaptive stability lower bound fix (0.03 instead of 0.3)
- Per-family cap logic
- Promotion at relaxed 0.05 stability
"""

from __future__ import annotations

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateKind,
)
from twinklr.core.feature_engineering.promotion import (
    PromotionPipeline,
    _adaptive_stability,
)


def _make_template(
    *,
    template_id: str = "tpl-1",
    support_count: int = 25,
    distinct_pack_count: int = 5,
    cross_pack_stability: float = 0.8,
    effect_family: str = "single_strand",
) -> MinedTemplate:
    """Create a MinedTemplate for testing."""
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


# ── Default config thresholds ─────────────────────────────────────────────


class TestDefaultThresholds:
    """Verify config defaults match Phase 01 spec."""

    def test_min_stability_default(self) -> None:
        """recipe_promotion_min_stability defaults to 0.03."""
        opts = FeatureEngineeringPipelineOptions()
        assert opts.recipe_promotion_min_stability == 0.03

    def test_adaptive_stability_default(self) -> None:
        """recipe_promotion_adaptive_stability defaults to True."""
        opts = FeatureEngineeringPipelineOptions()
        assert opts.recipe_promotion_adaptive_stability is True

    def test_max_per_family_default(self) -> None:
        """recipe_promotion_max_per_family defaults to 10."""
        opts = FeatureEngineeringPipelineOptions()
        assert opts.recipe_promotion_max_per_family == 10


# ── Adaptive stability lower bound ────────────────────────────────────────


class TestAdaptiveStabilityLowerBound:
    """Verify _adaptive_stability lower bound is 0.03 (not 0.3)."""

    def test_adaptive_at_median_1_below_03(self) -> None:
        """_adaptive_stability(1.0) returns a value < 0.3."""
        val = _adaptive_stability(1.0)
        assert val < 0.3, f"Expected < 0.3, got {val}"

    def test_adaptive_at_zero_near_lower_bound(self) -> None:
        """_adaptive_stability(0.0) returns the lower bound (~0.03)."""
        val = _adaptive_stability(0.0)
        assert val <= 0.05, f"Expected <= 0.05, got {val}"
        assert val >= 0.02, f"Expected >= 0.02, got {val}"

    def test_adaptive_still_scales_upward(self) -> None:
        """Higher diversity still produces higher thresholds."""
        low = _adaptive_stability(2.0)
        high = _adaptive_stability(15.0)
        assert high > low


# ── Per-family cap ─────────────────────────────────────────────────────────


class TestPerFamilyCap:
    """Verify per-family cap limits recipes from dominant families."""

    def test_cap_limits_single_family(self) -> None:
        """15 templates of same family are capped to max_per_family=10."""
        candidates = [
            _make_template(
                template_id=f"t-{i}",
                support_count=20,
                effect_family="sparkle",
            )
            for i in range(15)
        ]
        result = PromotionPipeline().run(
            candidates=candidates,
            min_support=5,
            min_stability=0.1,
            max_per_family=10,
        )
        assert len(result.promoted_recipes) == 10

    def test_cap_preserves_highest_support(self) -> None:
        """Per-family cap keeps templates with highest support_count."""
        candidates = [
            _make_template(
                template_id=f"t-{i}",
                support_count=100 + i,  # t-0=100, t-14=114
                effect_family="sparkle",
            )
            for i in range(15)
        ]
        result = PromotionPipeline().run(
            candidates=candidates,
            min_support=5,
            min_stability=0.1,
            max_per_family=10,
        )
        assert len(result.promoted_recipes) == 10
        # The 5 lowest-support templates (100-104) should be dropped
        # Recipe IDs encode the template_id
        recipe_ids = {r.recipe_id for r in result.promoted_recipes}
        for i in range(5, 15):
            assert any(f"t-{i}" in rid for rid in recipe_ids), (
                f"Template t-{i} (support={100 + i}) should have been kept"
            )

    def test_cap_zero_means_no_cap(self) -> None:
        """max_per_family=0 disables the cap."""
        candidates = [
            _make_template(
                template_id=f"t-{i}",
                support_count=20,
                effect_family="sparkle",
            )
            for i in range(15)
        ]
        result = PromotionPipeline().run(
            candidates=candidates,
            min_support=5,
            min_stability=0.1,
            max_per_family=0,
        )
        assert len(result.promoted_recipes) == 15

    def test_cap_does_not_affect_small_families(self) -> None:
        """Families with fewer than max_per_family are not affected."""
        candidates = [
            _make_template(template_id=f"a-{i}", effect_family="sparkle") for i in range(3)
        ] + [_make_template(template_id=f"b-{i}", effect_family="shimmer") for i in range(3)]
        result = PromotionPipeline().run(
            candidates=candidates,
            min_support=5,
            min_stability=0.1,
            max_per_family=10,
        )
        assert len(result.promoted_recipes) == 6


# ── Promotion at 0.05 stability ───────────────────────────────────────────


class TestRelaxedStability:
    """Templates that pass at 0.05 but would fail at 0.3."""

    def test_stability_006_passes_at_005(self) -> None:
        """Template with stability=0.06 passes at min_stability=0.05."""
        t = _make_template(
            template_id="relaxed-1",
            support_count=10,
            cross_pack_stability=0.06,
        )
        result = PromotionPipeline().run(
            candidates=[t],
            min_support=5,
            min_stability=0.05,
        )
        assert len(result.promoted_recipes) == 1

    def test_stability_006_would_fail_at_03(self) -> None:
        """Same template fails at the old 0.3 threshold."""
        t = _make_template(
            template_id="relaxed-1",
            support_count=10,
            cross_pack_stability=0.06,
        )
        result = PromotionPipeline().run(
            candidates=[t],
            min_support=5,
            min_stability=0.3,
        )
        assert len(result.promoted_recipes) == 0
