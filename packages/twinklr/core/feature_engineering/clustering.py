"""Deterministic template clustering + review queue (V2.1 baseline)."""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from twinklr.core.feature_engineering.models.clustering import (
    ClusterMember,
    ClusterReviewQueueRow,
    TemplateClusterCandidate,
    TemplateClusterCatalog,
)
from twinklr.core.feature_engineering.models.retrieval import TemplateRetrievalIndex
from twinklr.core.feature_engineering.models.templates import MinedTemplate, TemplateCatalog


@dataclass(frozen=True)
class TemplateClustererOptions:
    schema_version: str = "v2.1.0"
    clusterer_version: str = "template_clusterer_v1"
    similarity_threshold: float = 0.92
    min_cluster_size: int = 2


class TemplateClusterer:
    """Build deterministic template clusters from template descriptors."""

    def __init__(self, options: TemplateClustererOptions | None = None) -> None:
        self._options = options or TemplateClustererOptions()

    def build_clusters(
        self,
        *,
        content_catalog: TemplateCatalog,
        orchestration_catalog: TemplateCatalog,
        retrieval_index: TemplateRetrievalIndex | None,
    ) -> TemplateClusterCatalog:
        templates = tuple(content_catalog.templates) + tuple(orchestration_catalog.templates)
        retrieval_by_id = {
            row.template_id: row
            for row in (retrieval_index.recommendations if retrieval_index else ())
        }

        template_by_id = {row.template_id: row for row in templates}
        vectors = {row.template_id: self._vectorize(row, retrieval_by_id) for row in templates}
        grouped = self._build_complete_link_groups(
            template_by_id=template_by_id,
            vectors=vectors,
        )

        candidates: list[TemplateClusterCandidate] = []
        queue_rows: list[ClusterReviewQueueRow] = []
        for members in grouped:
            if len(members) < self._options.min_cluster_size:
                continue
            ordered = sorted(members, key=lambda row: row.template_id)
            template_ids = tuple(row.template_id for row in ordered)
            cluster_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{self._options.clusterer_version}:{','.join(template_ids)}",
                )
            )

            similarities: list[float] = []
            for i, left in enumerate(template_ids):
                for right in template_ids[i + 1 :]:
                    similarities.append(self._cosine(vectors[left], vectors[right]))
            mean_similarity = sum(similarities) / len(similarities) if similarities else 1.0

            effect_counts: dict[str, int] = {}
            for row in ordered:
                effect_counts[row.effect_family] = effect_counts.get(row.effect_family, 0) + 1
            dominant_effect = sorted(effect_counts.items(), key=lambda item: (-item[1], item[0]))[
                0
            ][0]

            candidate = TemplateClusterCandidate(
                cluster_id=cluster_id,
                cluster_size=len(ordered),
                mean_similarity=round(mean_similarity, 6),
                dominant_effect_family=dominant_effect,
                member_template_ids=template_ids,
                members=tuple(
                    ClusterMember(
                        template_id=row.template_id,
                        template_kind=row.template_kind,
                        effect_family=row.effect_family,
                        role=row.role,
                    )
                    for row in ordered
                ),
            )
            candidates.append(candidate)
            queue_rows.append(self._review_row(candidate))

        candidates.sort(key=lambda row: row.cluster_id)
        queue_rows.sort(key=lambda row: (row.priority, row.cluster_id))
        return TemplateClusterCatalog(
            schema_version=self._options.schema_version,
            clusterer_version=self._options.clusterer_version,
            min_cluster_size=self._options.min_cluster_size,
            similarity_threshold=self._options.similarity_threshold,
            total_templates=len(templates),
            total_clusters=len(candidates),
            clusters=tuple(candidates),
            review_queue=tuple(queue_rows),
        )

    def _build_complete_link_groups(
        self,
        *,
        template_by_id: dict[str, MinedTemplate],
        vectors: dict[str, tuple[float, ...]],
    ) -> list[list[MinedTemplate]]:
        unassigned = sorted(template_by_id.keys())
        groups: list[list[MinedTemplate]] = []

        while unassigned:
            seed_id = unassigned.pop(0)
            group_ids = [seed_id]
            idx = 0
            while idx < len(unassigned):
                candidate_id = unassigned[idx]
                if self._passes_complete_link(
                    candidate_id=candidate_id,
                    group_ids=group_ids,
                    vectors=vectors,
                ):
                    group_ids.append(candidate_id)
                    unassigned.pop(idx)
                    continue
                idx += 1
            groups.append([template_by_id[item] for item in sorted(group_ids)])
        return groups

    def _passes_complete_link(
        self,
        *,
        candidate_id: str,
        group_ids: list[str],
        vectors: dict[str, tuple[float, ...]],
    ) -> bool:
        candidate_vector = vectors[candidate_id]
        for existing_id in group_ids:
            similarity = self._cosine(candidate_vector, vectors[existing_id])
            if similarity < self._options.similarity_threshold:
                return False
        return True

    @staticmethod
    def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm <= 0.0 or right_norm <= 0.0:
            return 0.0
        value = numerator / (left_norm * right_norm)
        return max(0.0, min(1.0, value))

    @staticmethod
    def _stable_bucket(value: str | None, modulus: int) -> float:
        raw = value or ""
        acc = 0
        for index, char in enumerate(raw):
            acc += (index + 1) * ord(char)
        return (acc % modulus) / float(modulus)

    def _vectorize(
        self,
        template: MinedTemplate,
        retrieval_by_id: Mapping[str, object],
    ) -> tuple[float, ...]:
        retrieval = retrieval_by_id.get(template.template_id)
        retrieval_score = float(getattr(retrieval, "retrieval_score", 0.0))
        flow_norm = float(getattr(retrieval, "transition_flow_norm", 0.0))
        taxonomy_count = float(len(template.taxonomy_labels))
        onset = float(template.onset_sync_mean or 0.0)

        return (
            template.support_ratio,
            template.cross_pack_stability,
            onset,
            retrieval_score,
            flow_norm,
            min(1.0, taxonomy_count / 6.0),
            self._stable_bucket(template.effect_family, 97),
            self._stable_bucket(template.motion_class, 97),
            self._stable_bucket(template.energy_class, 97),
            self._stable_bucket(template.role, 97),
        )

    @staticmethod
    def _review_row(candidate: TemplateClusterCandidate) -> ClusterReviewQueueRow:
        reason_keys: list[str] = []
        if candidate.cluster_size >= 5:
            reason_keys.append("large_cluster")
        if candidate.mean_similarity < 0.95:
            reason_keys.append("borderline_similarity")
        if not reason_keys:
            reason_keys.append("standard_review")

        if "large_cluster" in reason_keys:
            priority = 1
            suggestion = "review_for_split_or_promote"
        elif "borderline_similarity" in reason_keys:
            priority = 2
            suggestion = "review_for_merge_threshold"
        else:
            priority = 3
            suggestion = "review_for_template_family"

        return ClusterReviewQueueRow(
            cluster_id=candidate.cluster_id,
            priority=priority,
            reason_keys=tuple(sorted(reason_keys)),
            suggestion=suggestion,
        )
