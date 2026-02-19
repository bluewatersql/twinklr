from __future__ import annotations

from twinklr.core.feature_engineering.models.retrieval import (
    TemplateRecommendation,
    TemplateRetrievalIndex,
)
from twinklr.core.feature_engineering.models.templates import TemplateKind
from twinklr.core.feature_engineering.retrieval import (
    TemplateQuery,
    TemplateRetrievalQueryEngine,
)


def _rec(
    template_id: str,
    *,
    kind: TemplateKind,
    score: float,
    flow: float,
    role: str | None,
    effect_family: str,
) -> TemplateRecommendation:
    return TemplateRecommendation(
        template_id=template_id,
        template_kind=kind,
        retrieval_score=score,
        rank=1,
        support_count=10,
        support_ratio=0.5,
        cross_pack_stability=0.8,
        onset_sync_mean=0.7,
        transition_in_count=4,
        transition_out_count=4,
        transition_flow_count=8,
        transition_flow_norm=flow,
        taxonomy_label_count=2,
        taxonomy_labels=("rhythm_driver",),
        role=role,
        effect_family=effect_family,
        motion_class="sweep",
        color_class="palette",
        energy_class="mid",
        continuity_class="rhythmic",
        spatial_class="multi_target",
    )


def test_template_query_filters_by_kind_and_role() -> None:
    index = TemplateRetrievalIndex(
        schema_version="v1.0.0",
        ranker_version="template_retrieval_ranker_v1",
        total_templates=2,
        recommendations=(
            _rec(
                "t1",
                kind=TemplateKind.CONTENT,
                score=0.8,
                flow=0.5,
                role=None,
                effect_family="on",
            ),
            _rec(
                "t2",
                kind=TemplateKind.ORCHESTRATION,
                score=0.75,
                flow=0.7,
                role="lead",
                effect_family="bars",
            ),
        ),
    )
    rows = TemplateRetrievalQueryEngine().query(
        index=index,
        query=TemplateQuery(
            template_kind=TemplateKind.ORCHESTRATION,
            role="lead",
            top_n=5,
        ),
    )
    assert len(rows) == 1
    assert rows[0].template_id == "t2"


def test_template_query_sorts_by_query_relevance() -> None:
    index = TemplateRetrievalIndex(
        schema_version="v1.0.0",
        ranker_version="template_retrieval_ranker_v1",
        total_templates=2,
        recommendations=(
            _rec(
                "t1",
                kind=TemplateKind.CONTENT,
                score=0.70,
                flow=0.2,
                role=None,
                effect_family="on",
            ),
            _rec(
                "t2",
                kind=TemplateKind.CONTENT,
                score=0.68,
                flow=0.9,
                role=None,
                effect_family="on",
            ),
        ),
    )
    rows = TemplateRetrievalQueryEngine().query(
        index=index,
        query=TemplateQuery(effect_family="on", top_n=5),
    )
    assert len(rows) == 2
    assert rows[0].template_id == "t2"

