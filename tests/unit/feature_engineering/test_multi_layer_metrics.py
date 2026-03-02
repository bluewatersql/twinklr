"""Tests for multi-layer fields in PromotionReport.

Validates that the promotion report tracks multi-layer candidate counts,
promoted counts, average layers, and family distribution.
"""

from __future__ import annotations

from twinklr.core.feature_engineering.models.promotion import PromotionReport
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateKind,
)
from twinklr.core.feature_engineering.promotion import PromotionPipeline


def _make_template(
    template_id: str = "tmpl-001",
    effect_family: str = "bars",
    support_count: int = 10,
    cross_pack_stability: float = 0.1,
    layer_count: int = 1,
    distinct_pack_count: int = 3,
) -> MinedTemplate:
    """Create a MinedTemplate for testing report metrics."""
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


class TestMultiLayerMetrics:
    """Verify multi-layer fields in promotion report."""

    def test_promotion_report_has_multi_layer_fields(self) -> None:
        """Report tracks multi-layer promoted count and avg layers."""
        templates = [
            _make_template(template_id="s-001", layer_count=1),
            _make_template(
                template_id="m-001",
                effect_family="color_wash",
                layer_count=2,
            ),
            _make_template(
                template_id="m-002",
                effect_family="sparkle",
                layer_count=3,
            ),
        ]
        result = PromotionPipeline().run(
            templates,
            min_support=2,
            min_stability=0.01,
            multi_layer_min_support=2,
            multi_layer_min_stability=0.01,
        )
        report = result.report
        assert report["multi_layer_candidates"] == 2
        assert report["multi_layer_promoted"] == 2
        assert report["avg_layers_multi_layer"] == 2.5
        assert report["max_layers_promoted"] == 3

    def test_multi_layer_family_distribution(self) -> None:
        """Report captures per-family counts for multi-layer recipes."""
        templates = [
            _make_template(
                template_id="m-001",
                effect_family="color_wash",
                layer_count=2,
            ),
            _make_template(
                template_id="m-002",
                effect_family="color_wash",
                layer_count=3,
            ),
            _make_template(
                template_id="m-003",
                effect_family="bars",
                layer_count=2,
            ),
        ]
        result = PromotionPipeline().run(
            templates,
            min_support=2,
            min_stability=0.01,
            multi_layer_min_support=2,
            multi_layer_min_stability=0.01,
        )
        dist = result.report["multi_layer_family_distribution"]
        assert dist["color_wash"] == 2
        assert dist["bars"] == 1

    def test_report_model_accepts_multi_layer_fields(self) -> None:
        """PromotionReport model accepts and validates multi-layer fields."""
        report = PromotionReport(
            total_candidates=100,
            filtered_families=5,
            eligible_count=95,
            passed_quality_gate=50,
            rejected_count=45,
            after_cluster_dedup=50,
            promoted_count=30,
            effective_min_stability=0.05,
            effective_min_support=5,
            adaptive_stability_used=True,
            family_distribution={"bars": 10},
            lane_distribution={"CONTENT": 30},
            avg_layers_per_recipe=2.5,
            multi_layer_candidates=20,
            multi_layer_promoted=15,
            avg_layers_multi_layer=2.8,
            max_layers_promoted=4,
            multi_layer_family_distribution={"bars": 5, "color_wash": 10},
        )
        assert report.multi_layer_promoted == 15
        assert report.max_layers_promoted == 4
        assert report.multi_layer_family_distribution == {"bars": 5, "color_wash": 10}
