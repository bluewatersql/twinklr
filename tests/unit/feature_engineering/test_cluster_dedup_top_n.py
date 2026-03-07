"""Tests for cluster dedup keeping top-N per cluster by support_count."""

from __future__ import annotations

from twinklr.core.feature_engineering.models.templates import MinedTemplate
from twinklr.core.feature_engineering.promotion import PromotionPipeline


def _make_template(
    template_id: str,
    effect_family: str = "wave",
    support_count: int = 5,
    cross_pack_stability: float = 0.5,
    layer_count: int = 1,
) -> MinedTemplate:
    return MinedTemplate(
        template_id=template_id,
        template_kind="content",
        template_signature=f"sig_{template_id}",
        effect_family=effect_family,
        motion_class="static",
        color_class="warm",
        energy_class="low",
        continuity_class="sustained",
        spatial_class="full",
        role="BASE",
        support_count=support_count,
        distinct_pack_count=2,
        support_ratio=support_count / 100.0,
        cross_pack_stability=cross_pack_stability,
        onset_sync_mean=0.5,
        taxonomy_labels=("label_a",),
        layer_count=layer_count,
    )


class TestClusterDedupTopN:
    """Verify that cluster dedup keeps top N templates per cluster by support."""

    def test_default_keeps_one_per_cluster(self) -> None:
        """With max_per_cluster=1 (default), only highest-support survives."""
        t1 = _make_template("t1", support_count=10)
        t2 = _make_template("t2", support_count=20)
        t3 = _make_template("t3", support_count=5)

        clusters = [
            {"cluster_id": "c1", "member_ids": ["t1", "t2", "t3"], "keep_id": "t1"},
        ]

        pipeline = PromotionPipeline()
        result = pipeline._apply_cluster_dedup([t1, t2, t3], clusters, max_per_cluster=1)

        assert len(result) == 1
        assert result[0].template_id == "t2"  # highest support

    def test_top_two_per_cluster(self) -> None:
        """With max_per_cluster=2, top 2 by support survive."""
        t1 = _make_template("t1", support_count=10)
        t2 = _make_template("t2", support_count=20)
        t3 = _make_template("t3", support_count=5)
        t4 = _make_template("t4", support_count=15)

        clusters = [
            {"cluster_id": "c1", "member_ids": ["t1", "t2", "t3", "t4"], "keep_id": "t1"},
        ]

        pipeline = PromotionPipeline()
        result = pipeline._apply_cluster_dedup([t1, t2, t3, t4], clusters, max_per_cluster=2)

        ids = {t.template_id for t in result}
        assert ids == {"t2", "t4"}  # top 2 by support: 20, 15

    def test_unclustered_templates_survive(self) -> None:
        """Templates NOT in any cluster always survive dedup."""
        t1 = _make_template("t1", support_count=10)
        t2 = _make_template("t2", support_count=20)
        t_free = _make_template("t_free", support_count=3)

        clusters = [
            {"cluster_id": "c1", "member_ids": ["t1", "t2"], "keep_id": "t1"},
        ]

        pipeline = PromotionPipeline()
        result = pipeline._apply_cluster_dedup([t1, t2, t_free], clusters, max_per_cluster=1)

        ids = {t.template_id for t in result}
        assert "t_free" in ids
        assert "t2" in ids  # best in cluster
        assert len(result) == 2

    def test_multiple_clusters(self) -> None:
        """Each cluster independently keeps top N."""
        t1 = _make_template("t1", effect_family="wave", support_count=10)
        t2 = _make_template("t2", effect_family="wave", support_count=20)
        t3 = _make_template("t3", effect_family="galaxy", support_count=5)
        t4 = _make_template("t4", effect_family="galaxy", support_count=15)
        t5 = _make_template("t5", effect_family="galaxy", support_count=25)

        clusters = [
            {"cluster_id": "c1", "member_ids": ["t1", "t2"], "keep_id": "t1"},
            {"cluster_id": "c2", "member_ids": ["t3", "t4", "t5"], "keep_id": "t3"},
        ]

        pipeline = PromotionPipeline()
        result = pipeline._apply_cluster_dedup([t1, t2, t3, t4, t5], clusters, max_per_cluster=2)

        ids = {t.template_id for t in result}
        # cluster c1: t2 (20), t1 (10) — top 2
        # cluster c2: t5 (25), t4 (15) — top 2
        assert ids == {"t1", "t2", "t4", "t5"}

    def test_multi_layer_guarantee(self) -> None:
        """Multi-layer templates are guaranteed even if outside top N by support."""
        t1 = _make_template("t1", support_count=100, layer_count=1)
        t2 = _make_template("t2", support_count=90, layer_count=1)
        t3 = _make_template("t3", support_count=50, layer_count=2)
        t4 = _make_template("t4", support_count=30, layer_count=2)

        clusters = [
            {"cluster_id": "c1", "member_ids": ["t1", "t2", "t3", "t4"], "keep_id": "t1"},
        ]

        pipeline = PromotionPipeline()
        # max_per_cluster=2 picks t1(100) and t2(90) — both single-layer
        # multi_layer_min_per_cluster=1 adds t3(50) — best multi-layer
        result = pipeline._apply_cluster_dedup(
            [t1, t2, t3, t4],
            clusters,
            max_per_cluster=2,
            multi_layer_min_per_cluster=1,
        )

        ids = {t.template_id for t in result}
        assert "t1" in ids  # top by support
        assert "t2" in ids  # second by support
        assert "t3" in ids  # guaranteed multi-layer
        assert "t4" not in ids  # second multi-layer not needed
        assert len(result) == 3

    def test_report_records_pre_dedup_count(self) -> None:
        """passed_quality_gate should reflect count BEFORE cluster dedup."""
        templates = [
            _make_template(f"t{i}", support_count=10, cross_pack_stability=0.5) for i in range(10)
        ]
        clusters = [
            {"cluster_id": "c1", "member_ids": [f"t{i}" for i in range(10)], "keep_id": "t0"},
        ]

        pipeline = PromotionPipeline()
        result = pipeline.run(
            templates,
            min_support=2,
            min_stability=0.01,
            clusters=clusters,
            max_per_cluster=1,
        )

        # All 10 pass quality gate, but only 1 survives dedup
        assert result.report["passed_quality_gate"] == 10
        assert result.report["after_cluster_dedup"] == 1
