from __future__ import annotations

from twinklr.core.feature_engineering.ann_retrieval import AnnTemplateRetrievalIndexer
from twinklr.core.feature_engineering.models.retrieval import (
    TemplateRecommendation,
    TemplateRetrievalIndex,
)
from twinklr.core.feature_engineering.models.templates import TemplateKind


def _recommendation(template_id: str, effect_family: str, score: float) -> TemplateRecommendation:
    return TemplateRecommendation(
        template_id=template_id,
        template_kind=TemplateKind.CONTENT,
        retrieval_score=score,
        rank=1,
        support_count=20,
        support_ratio=0.2,
        cross_pack_stability=0.7,
        onset_sync_mean=0.5,
        transition_in_count=2,
        transition_out_count=3,
        transition_flow_count=5,
        transition_flow_norm=0.5,
        taxonomy_label_count=1,
        taxonomy_labels=("rhythm_driver",),
        role=None,
        effect_family=effect_family,
        motion_class="sweep",
        color_class="palette",
        energy_class="mid",
        continuity_class="rhythmic",
        spatial_class="group",
    )


def test_ann_indexer_builds_index_and_eval() -> None:
    retrieval_index = TemplateRetrievalIndex(
        schema_version="v1.0.0",
        ranker_version="baseline",
        total_templates=3,
        recommendations=(
            _recommendation("t1", "on", 0.8),
            _recommendation("t2", "on", 0.79),
            _recommendation("t3", "bars", 0.65),
        ),
    )

    indexer = AnnTemplateRetrievalIndexer()
    ann_index = indexer.build_index(retrieval_index)
    report = indexer.evaluate(index=ann_index, retrieval_index=retrieval_index)

    assert ann_index.total_entries == 3
    assert ann_index.vector_dim == 12
    assert report.total_queries == 3
    assert 0.0 <= report.same_effect_family_recall_at_5 <= 1.0
