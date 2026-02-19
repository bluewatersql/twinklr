"""Deterministic template retrieval/ranking baseline (V1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from twinklr.core.feature_engineering.models.retrieval import (
    TemplateRecommendation,
    TemplateRetrievalIndex,
)
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateCatalog,
    TemplateKind,
)
from twinklr.core.feature_engineering.models.transitions import TransitionGraph


@dataclass(frozen=True)
class TemplateRetrievalRankerOptions:
    schema_version: str = "v1.0.0"
    ranker_version: str = "template_retrieval_ranker_v1"


class TemplateRetrievalRanker:
    """Build a ranked template index from mined templates and transitions."""

    def __init__(self, options: TemplateRetrievalRankerOptions | None = None) -> None:
        self._options = options or TemplateRetrievalRankerOptions()

    def build_index(
        self,
        *,
        content_catalog: TemplateCatalog,
        orchestration_catalog: TemplateCatalog,
        transition_graph: TransitionGraph | None,
    ) -> TemplateRetrievalIndex:
        templates = tuple(content_catalog.templates) + tuple(orchestration_catalog.templates)

        in_counts: dict[str, int] = {}
        out_counts: dict[str, int] = {}
        if transition_graph is not None:
            for edge in transition_graph.edges:
                out_counts[edge.source_template_id] = (
                    out_counts.get(edge.source_template_id, 0) + edge.edge_count
                )
                in_counts[edge.target_template_id] = (
                    in_counts.get(edge.target_template_id, 0) + edge.edge_count
                )

        max_flow = max((in_counts.get(row.template_id, 0) + out_counts.get(row.template_id, 0)) for row in templates) if templates else 0

        rows: list[TemplateRecommendation] = []
        for template in templates:
            transition_in_count = in_counts.get(template.template_id, 0)
            transition_out_count = out_counts.get(template.template_id, 0)
            transition_flow_count = transition_in_count + transition_out_count
            transition_flow_norm = (
                transition_flow_count / max_flow if max_flow > 0 else 0.0
            )
            score = self._score(template, transition_flow_norm)
            rows.append(
                TemplateRecommendation(
                    template_id=template.template_id,
                    template_kind=template.template_kind,
                    retrieval_score=round(score, 6),
                    rank=1,
                    support_count=template.support_count,
                    support_ratio=template.support_ratio,
                    cross_pack_stability=template.cross_pack_stability,
                    onset_sync_mean=template.onset_sync_mean,
                    transition_in_count=transition_in_count,
                    transition_out_count=transition_out_count,
                    transition_flow_count=transition_flow_count,
                    transition_flow_norm=round(transition_flow_norm, 6),
                    taxonomy_label_count=len(template.taxonomy_labels),
                    taxonomy_labels=template.taxonomy_labels,
                    role=template.role,
                    effect_family=template.effect_family,
                    motion_class=template.motion_class,
                    color_class=template.color_class,
                    energy_class=template.energy_class,
                    continuity_class=template.continuity_class,
                    spatial_class=template.spatial_class,
                )
            )

        rows.sort(
            key=lambda item: (
                -item.retrieval_score,
                -item.support_count,
                item.template_kind.value,
                item.template_id,
            )
        )
        ranked = tuple(
            row.model_copy(update={"rank": idx + 1}) for idx, row in enumerate(rows)
        )
        return TemplateRetrievalIndex(
            schema_version=self._options.schema_version,
            ranker_version=self._options.ranker_version,
            total_templates=len(ranked),
            recommendations=ranked,
        )

    @staticmethod
    def _score(template: MinedTemplate, transition_flow_norm: float) -> float:
        onset = template.onset_sync_mean if template.onset_sync_mean is not None else 0.0
        taxonomy_richness = min(1.0, len(template.taxonomy_labels) / 4.0)
        # Weighted deterministic baseline for retrieval ranking.
        return (
            (template.support_ratio * 0.45)
            + (template.cross_pack_stability * 0.25)
            + (onset * 0.15)
            + (transition_flow_norm * 0.10)
            + (taxonomy_richness * 0.05)
        )


@dataclass(frozen=True)
class TemplateQuery:
    template_kind: TemplateKind | None = None
    role: str | None = None
    effect_family: str | None = None
    motion_class: str | None = None
    energy_class: str | None = None
    min_base_score: float = 0.0
    min_transition_flow: float = 0.0
    min_taxonomy_label_count: int = 0
    top_n: int = 10


class TemplateRetrievalQueryEngine:
    """Query ranked template index with deterministic intent filters."""

    @staticmethod
    def load_index(path: Path) -> TemplateRetrievalIndex:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        return TemplateRetrievalIndex.model_validate(payload)

    def query(
        self,
        *,
        index: TemplateRetrievalIndex,
        query: TemplateQuery,
    ) -> tuple[TemplateRecommendation, ...]:
        rows = [
            row
            for row in index.recommendations
            if self._passes_filters(row=row, query=query)
        ]
        rows.sort(
            key=lambda row: (
                -self._query_score(row=row, query=query),
                -row.retrieval_score,
                row.template_kind.value,
                row.template_id,
            )
        )
        return tuple(rows[: query.top_n])

    @staticmethod
    def _passes_filters(*, row: TemplateRecommendation, query: TemplateQuery) -> bool:
        if query.template_kind is not None and row.template_kind is not query.template_kind:
            return False
        if query.role is not None and (row.role or "") != query.role:
            return False
        if query.effect_family is not None and row.effect_family != query.effect_family:
            return False
        if query.motion_class is not None and row.motion_class != query.motion_class:
            return False
        if query.energy_class is not None and row.energy_class != query.energy_class:
            return False
        if row.retrieval_score < query.min_base_score:
            return False
        if row.transition_flow_norm < query.min_transition_flow:
            return False
        if row.taxonomy_label_count < query.min_taxonomy_label_count:
            return False
        return True

    @staticmethod
    def _query_score(*, row: TemplateRecommendation, query: TemplateQuery) -> float:
        score = row.retrieval_score * 0.75
        score += row.transition_flow_norm * 0.10
        score += min(1.0, row.taxonomy_label_count / 4.0) * 0.05
        if query.role is not None and (row.role or "") == query.role:
            score += 0.05
        if query.effect_family is not None and row.effect_family == query.effect_family:
            score += 0.025
        if query.motion_class is not None and row.motion_class == query.motion_class:
            score += 0.015
        if query.energy_class is not None and row.energy_class == query.energy_class:
            score += 0.01
        return score
