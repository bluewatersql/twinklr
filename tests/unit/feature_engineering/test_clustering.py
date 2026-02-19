from __future__ import annotations

from twinklr.core.feature_engineering.clustering import TemplateClusterer
from twinklr.core.feature_engineering.models.retrieval import (
    TemplateRecommendation,
    TemplateRetrievalIndex,
)
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateCatalog,
    TemplateKind,
)


def _template(template_id: str, support: float) -> MinedTemplate:
    return MinedTemplate(
        template_id=template_id,
        template_kind=TemplateKind.CONTENT,
        template_signature=f"sig-{template_id}",
        support_count=int(support * 100),
        distinct_pack_count=2,
        support_ratio=support,
        cross_pack_stability=0.9,
        onset_sync_mean=0.8,
        role=None,
        taxonomy_labels=("rhythm_driver",),
        effect_family="on",
        motion_class="sweep",
        color_class="palette",
        energy_class="mid",
        continuity_class="rhythmic",
        spatial_class="group",
        provenance=(),
    )


def _recommendation(template_id: str, score: float) -> TemplateRecommendation:
    return TemplateRecommendation(
        template_id=template_id,
        template_kind=TemplateKind.CONTENT,
        retrieval_score=score,
        rank=1,
        support_count=50,
        support_ratio=0.5,
        cross_pack_stability=0.9,
        onset_sync_mean=0.8,
        transition_in_count=5,
        transition_out_count=5,
        transition_flow_count=10,
        transition_flow_norm=0.8,
        taxonomy_label_count=1,
        taxonomy_labels=("rhythm_driver",),
        role=None,
        effect_family="on",
        motion_class="sweep",
        color_class="palette",
        energy_class="mid",
        continuity_class="rhythmic",
        spatial_class="group",
    )


def test_template_clusterer_groups_similar_templates() -> None:
    content_catalog = TemplateCatalog(
        schema_version="v1.5.0",
        miner_version="test",
        template_kind=TemplateKind.CONTENT,
        total_phrase_count=100,
        assigned_phrase_count=100,
        assignment_coverage=1.0,
        min_instance_count=1,
        min_distinct_pack_count=1,
        templates=(
            _template("t1", 0.50),
            _template("t2", 0.51),
        ),
        assignments=(),
    )
    orchestration_catalog = TemplateCatalog(
        schema_version="v1.5.0",
        miner_version="test",
        template_kind=TemplateKind.ORCHESTRATION,
        total_phrase_count=0,
        assigned_phrase_count=0,
        assignment_coverage=0.0,
        min_instance_count=1,
        min_distinct_pack_count=1,
        templates=(),
        assignments=(),
    )
    retrieval_index = TemplateRetrievalIndex(
        schema_version="v1.0.0",
        ranker_version="test",
        total_templates=2,
        recommendations=(
            _recommendation("t1", 0.8),
            _recommendation("t2", 0.79),
        ),
    )

    catalog = TemplateClusterer().build_clusters(
        content_catalog=content_catalog,
        orchestration_catalog=orchestration_catalog,
        retrieval_index=retrieval_index,
    )

    assert catalog.total_clusters >= 1
    assert catalog.clusters[0].cluster_size == 2
    assert len(catalog.review_queue) == catalog.total_clusters
