"""ANN-style retrieval index and hybrid reranking baseline (V2.3)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from twinklr.core.feature_engineering.models.ann_retrieval import (
    AnnIndexEntry,
    AnnRetrievalCheck,
    AnnRetrievalEvalReport,
    AnnRetrievalIndex,
    AnnRetrievalSliceMetric,
)
from twinklr.core.feature_engineering.models.retrieval import (
    TemplateRecommendation,
    TemplateRetrievalIndex,
)


@dataclass(frozen=True)
class AnnRetrievalOptions:
    schema_version: str = "v2.3.0"
    index_version: str = "ann_retrieval_v1"
    vector_dim: int = 12
    min_same_effect_family_recall_at_5: float = 0.80
    max_avg_query_latency_ms: float = 10.0


class AnnTemplateRetrievalIndexer:
    """Build vector index from template retrieval recommendations."""

    def __init__(self, options: AnnRetrievalOptions | None = None) -> None:
        self._options = options or AnnRetrievalOptions()

    def build_index(self, retrieval_index: TemplateRetrievalIndex) -> AnnRetrievalIndex:
        entries = tuple(
            AnnIndexEntry(
                template_id=row.template_id,
                template_kind=row.template_kind,
                effect_family=row.effect_family,
                role=row.role,
                vector=self._vectorize(row),
            )
            for row in retrieval_index.recommendations
        )
        return AnnRetrievalIndex(
            schema_version=self._options.schema_version,
            index_version=self._options.index_version,
            vector_dim=self._options.vector_dim,
            total_entries=len(entries),
            entries=entries,
        )

    def evaluate(
        self,
        *,
        index: AnnRetrievalIndex,
        retrieval_index: TemplateRetrievalIndex,
        top_k: int = 5,
    ) -> AnnRetrievalEvalReport:
        entry_by_id = {row.template_id: row for row in index.entries}
        rec_by_id = {row.template_id: row for row in retrieval_index.recommendations}
        if not entry_by_id:
            return AnnRetrievalEvalReport(
                schema_version=index.schema_version,
                index_version=index.index_version,
                total_queries=0,
                avg_top1_similarity=0.0,
                same_effect_family_recall_at_5=0.0,
                avg_query_latency_ms=0.0,
                min_same_effect_family_recall_at_5=self._options.min_same_effect_family_recall_at_5,
                max_avg_query_latency_ms=self._options.max_avg_query_latency_ms,
            )

        top1_sims: list[float] = []
        recalls: list[float] = []
        latencies: list[float] = []
        effect_slice_pairs: dict[str, list[float]] = {}
        role_slice_pairs: dict[str, list[float]] = {}

        for template_id, query in sorted(entry_by_id.items()):
            start = time.perf_counter()
            ranked = self.search(
                index=index,
                query_vector=query.vector,
                top_k=top_k + 1,
                exclude_template_id=template_id,
            )
            latencies.append((time.perf_counter() - start) * 1000.0)

            if ranked:
                top1_sims.append(ranked[0][1])
            else:
                top1_sims.append(0.0)

            query_effect = getattr(rec_by_id.get(template_id), "effect_family", "")
            if not query_effect:
                recalls.append(0.0)
                continue

            universe = [
                row.template_id
                for row in retrieval_index.recommendations
                if row.template_id != template_id and row.effect_family == query_effect
            ]
            if not universe:
                recalls.append(1.0)
                continue

            hits = {
                candidate_id
                for candidate_id, _score in ranked[:top_k]
                if getattr(rec_by_id.get(candidate_id), "effect_family", "") == query_effect
            }
            recall_hit = 1.0 if hits else 0.0
            recalls.append(recall_hit)
            effect_slice_pairs.setdefault(query_effect, []).append(recall_hit)

            query_role = getattr(rec_by_id.get(template_id), "role", None) or "none"
            role_universe = [
                row.template_id
                for row in retrieval_index.recommendations
                if row.template_id != template_id and (row.role or "none") == query_role
            ]
            if not role_universe:
                role_slice_pairs.setdefault(query_role, []).append(1.0)
            else:
                role_hits = {
                    candidate_id
                    for candidate_id, _score in ranked[:top_k]
                    if (getattr(rec_by_id.get(candidate_id), "role", None) or "none") == query_role
                }
                role_slice_pairs.setdefault(query_role, []).append(1.0 if role_hits else 0.0)

        avg_top1_similarity = round(sum(top1_sims) / len(top1_sims), 6)
        same_family_recall = round(sum(recalls) / len(recalls), 6)
        avg_latency = round(sum(latencies) / len(latencies), 6)
        effect_family_slices = tuple(
            AnnRetrievalSliceMetric(
                slice_key=key,
                query_count=len(values),
                same_group_recall_at_5=round(sum(values) / len(values), 6),
            )
            for key, values in sorted(effect_slice_pairs.items(), key=lambda item: item[0])
        )
        role_slices = tuple(
            AnnRetrievalSliceMetric(
                slice_key=key,
                query_count=len(values),
                same_group_recall_at_5=round(sum(values) / len(values), 6),
            )
            for key, values in sorted(role_slice_pairs.items(), key=lambda item: item[0])
        )
        checks = (
            AnnRetrievalCheck(
                check_id="same_effect_family_recall_at_5",
                passed=same_family_recall >= self._options.min_same_effect_family_recall_at_5,
                value=same_family_recall,
                threshold=self._options.min_same_effect_family_recall_at_5,
            ),
            AnnRetrievalCheck(
                check_id="avg_query_latency_ms",
                passed=avg_latency <= self._options.max_avg_query_latency_ms,
                value=avg_latency,
                threshold=self._options.max_avg_query_latency_ms,
            ),
        )
        gates_passed = all(check.passed for check in checks)

        return AnnRetrievalEvalReport(
            schema_version=index.schema_version,
            index_version=index.index_version,
            total_queries=len(entry_by_id),
            avg_top1_similarity=avg_top1_similarity,
            same_effect_family_recall_at_5=same_family_recall,
            avg_query_latency_ms=avg_latency,
            effect_family_slices=effect_family_slices,
            role_slices=role_slices,
            min_same_effect_family_recall_at_5=self._options.min_same_effect_family_recall_at_5,
            max_avg_query_latency_ms=self._options.max_avg_query_latency_ms,
            gates_passed=gates_passed,
            checks=checks,
        )

    def search(
        self,
        *,
        index: AnnRetrievalIndex,
        query_vector: tuple[float, ...],
        top_k: int,
        exclude_template_id: str | None = None,
    ) -> list[tuple[str, float]]:
        scored: list[tuple[str, float]] = []
        for row in index.entries:
            if exclude_template_id is not None and row.template_id == exclude_template_id:
                continue
            scored.append((row.template_id, self._cosine(query_vector, row.vector)))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_k]

    def _vectorize(self, row: TemplateRecommendation) -> tuple[float, ...]:
        return (
            row.retrieval_score,
            row.support_ratio,
            row.cross_pack_stability,
            float(row.onset_sync_mean or 0.0),
            row.transition_flow_norm,
            min(1.0, row.taxonomy_label_count / 6.0),
            self._stable_bucket(row.effect_family, 101),
            self._stable_bucket(row.motion_class, 101),
            self._stable_bucket(row.energy_class, 101),
            self._stable_bucket(row.continuity_class, 101),
            self._stable_bucket(row.spatial_class, 101),
            self._stable_bucket(row.role, 101),
        )

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
