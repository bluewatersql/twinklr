from __future__ import annotations

from twinklr.core.feature_engineering.models import (
    MinedTemplate,
    TemplateCatalog,
    TemplateKind,
    TransitionEdge,
    TransitionGraph,
    TransitionType,
)
from twinklr.core.feature_engineering.retrieval import TemplateRetrievalRanker


def _catalog(
    kind: TemplateKind,
    templates: tuple[MinedTemplate, ...],
) -> TemplateCatalog:
    return TemplateCatalog(
        schema_version="v1.5.0",
        miner_version="template_miner_v1",
        template_kind=kind,
        total_phrase_count=10,
        assigned_phrase_count=10,
        assignment_coverage=1.0,
        min_instance_count=1,
        min_distinct_pack_count=1,
        templates=templates,
        assignments=(),
    )


def _template(
    template_id: str,
    kind: TemplateKind,
    *,
    support_ratio: float,
    cross_pack_stability: float,
    onset_sync_mean: float | None,
) -> MinedTemplate:
    return MinedTemplate(
        template_id=template_id,
        template_kind=kind,
        template_signature=f"sig-{template_id}",
        support_count=5,
        distinct_pack_count=2,
        support_ratio=support_ratio,
        cross_pack_stability=cross_pack_stability,
        onset_sync_mean=onset_sync_mean,
        taxonomy_labels=("sustainer",),
        effect_family="on",
        motion_class="static",
        color_class="mono",
        energy_class="mid",
        continuity_class="sustained",
        spatial_class="single_target",
        provenance=(),
    )


def test_template_retrieval_ranker_builds_ranked_index() -> None:
    content = _catalog(
        TemplateKind.CONTENT,
        (
            _template(
                "t-content-1",
                TemplateKind.CONTENT,
                support_ratio=0.40,
                cross_pack_stability=1.0,
                onset_sync_mean=0.8,
            ),
        ),
    )
    orchestration = _catalog(
        TemplateKind.ORCHESTRATION,
        (
            _template(
                "t-orch-1",
                TemplateKind.ORCHESTRATION,
                support_ratio=0.30,
                cross_pack_stability=0.8,
                onset_sync_mean=0.6,
            ),
        ),
    )
    transitions = TransitionGraph(
        schema_version="v1.6.0",
        graph_version="transition_graph_v1",
        total_transitions=2,
        total_nodes=2,
        total_edges=2,
        edges=(
            TransitionEdge(
                source_template_id="t-content-1",
                target_template_id="t-orch-1",
                edge_count=5,
                confidence=1.0,
                mean_gap_ms=50.0,
                transition_type_distribution={TransitionType.CROSSFADE: 5},
            ),
            TransitionEdge(
                source_template_id="t-orch-1",
                target_template_id="t-content-1",
                edge_count=2,
                confidence=0.4,
                mean_gap_ms=150.0,
                transition_type_distribution={TransitionType.TIMED_GAP: 2},
            ),
        ),
        transitions=(),
        anomalies=(),
    )

    index = TemplateRetrievalRanker().build_index(
        content_catalog=content,
        orchestration_catalog=orchestration,
        transition_graph=transitions,
    )

    assert index.total_templates == 2
    assert len(index.recommendations) == 2
    assert index.recommendations[0].rank == 1
    assert index.recommendations[0].retrieval_score >= index.recommendations[1].retrieval_score

