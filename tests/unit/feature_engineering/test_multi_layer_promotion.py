"""Tests for dual-threshold promotion behavior.

Validates that multi-layer templates (layer_count >= 2) use separate,
lower thresholds while single-layer templates use standard thresholds.
"""

from __future__ import annotations

from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateKind,
)
from twinklr.core.feature_engineering.promotion import PromotionPipeline


def _make_template(
    template_id: str = "tmpl-001",
    effect_family: str = "bars",
    support_count: int = 5,
    cross_pack_stability: float = 0.1,
    layer_count: int = 1,
    distinct_pack_count: int = 3,
) -> MinedTemplate:
    """Create a MinedTemplate with configurable thresholds and layer count."""
    return MinedTemplate(
        template_id=template_id,
        template_kind=TemplateKind.CONTENT,
        template_signature=f"{effect_family}|sweep|high",
        support_count=support_count,
        distinct_pack_count=distinct_pack_count,
        support_ratio=0.01,
        cross_pack_stability=cross_pack_stability,
        effect_family=effect_family,
        motion_class="sweep",
        color_class="palette",
        energy_class="high",
        continuity_class="rhythmic",
        spatial_class="multi_target",
        layer_count=layer_count,
        stack_composition=tuple([effect_family] * layer_count) if layer_count > 1 else (),
    )


class TestMultiLayerPromotion:
    """Verify dual-threshold promotion behavior."""

    def test_multi_layer_lower_thresholds(self) -> None:
        """Multi-layer template promoted with lower thresholds."""
        tmpl = _make_template(
            support_count=3,
            cross_pack_stability=0.03,
            layer_count=2,
        )
        result = PromotionPipeline().run(
            [tmpl],
            min_support=5,
            min_stability=0.05,
            multi_layer_min_support=2,
            multi_layer_min_stability=0.02,
        )
        assert len(result.promoted_recipes) == 1

    def test_single_layer_uses_standard_thresholds(self) -> None:
        """Single-layer template NOT promoted with same low values."""
        tmpl = _make_template(
            support_count=3,
            cross_pack_stability=0.03,
            layer_count=1,
        )
        result = PromotionPipeline().run(
            [tmpl],
            min_support=5,
            min_stability=0.05,
            multi_layer_min_support=2,
            multi_layer_min_stability=0.02,
        )
        assert len(result.promoted_recipes) == 0

    def test_both_paths_in_single_run(self) -> None:
        """Mixed single and multi-layer templates use appropriate thresholds."""
        single = _make_template(
            template_id="single-001",
            support_count=10,
            cross_pack_stability=0.1,
            layer_count=1,
        )
        multi_pass = _make_template(
            template_id="multi-001",
            effect_family="color_wash",
            support_count=3,
            cross_pack_stability=0.03,
            layer_count=3,
        )
        multi_fail = _make_template(
            template_id="multi-002",
            effect_family="sparkle",
            support_count=1,
            cross_pack_stability=0.01,
            layer_count=2,
        )
        result = PromotionPipeline().run(
            [single, multi_pass, multi_fail],
            min_support=5,
            min_stability=0.05,
            multi_layer_min_support=2,
            multi_layer_min_stability=0.02,
        )
        # single passes standard gates, multi_pass passes multi gates, multi_fail fails
        assert len(result.promoted_recipes) == 2

    def test_multi_layer_per_family_cap_applied(self) -> None:
        """Per-family cap applies to multi-layer templates too."""
        templates = [
            _make_template(
                template_id=f"multi-{i:03d}",
                support_count=5,
                cross_pack_stability=0.05,
                layer_count=2,
            )
            for i in range(15)
        ]
        result = PromotionPipeline().run(
            templates,
            min_support=2,
            min_stability=0.02,
            multi_layer_min_support=2,
            multi_layer_min_stability=0.02,
            max_per_family=10,
        )
        assert len(result.promoted_recipes) <= 10
