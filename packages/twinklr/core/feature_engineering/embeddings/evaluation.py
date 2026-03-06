"""Retrieval quality evaluator for embedding-based similarity search."""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from twinklr.core.feature_engineering.embeddings.models import (
    RetrievalQualityReport,
    SequenceEmbedding,
    SimilarityLink,
)


class RetrievalQualityEvaluator:
    """Compare embedding-based retrieval against ground truth.

    Measures precision@k, recall@k, NDCG@k, and query latency.

    Args:
        k: Number of results to evaluate.
        min_precision: Minimum precision@k for quality gate.
        max_latency_ms: Maximum average query latency for quality gate.
    """

    def __init__(
        self,
        k: int = 5,
        min_precision: float = 0.5,
        max_latency_ms: float = 10.0,
    ) -> None:
        self._k = k
        self._min_precision = min_precision
        self._max_latency_ms = max_latency_ms

    def evaluate(
        self,
        ground_truth: dict[str, set[str]],
        query_fn: Callable[[SequenceEmbedding], tuple[SimilarityLink, ...]],
        queries: tuple[SequenceEmbedding, ...],
    ) -> RetrievalQualityReport:
        """Run comparative evaluation.

        Args:
            ground_truth: Maps "{pkg_id}/{seq_id}" to set of relevant "{pkg_id}/{seq_id}" keys.
            query_fn: Function that takes a SequenceEmbedding and returns SimilarityLink results.
            queries: Test query embeddings.

        Returns:
            RetrievalQualityReport with metrics and quality gate pass/fail.
        """
        precisions: list[float] = []
        recalls: list[float] = []
        ndcgs: list[float] = []
        latencies: list[float] = []

        for query in queries:
            key = f"{query.package_id}/{query.sequence_file_id}"
            relevant = ground_truth.get(key, set())

            start = time.perf_counter()
            results = query_fn(query)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

            retrieved = [
                f"{r.target_package_id}/{r.target_sequence_id}" for r in results[: self._k]
            ]

            # Precision@k
            hits = sum(1 for r in retrieved if r in relevant)
            precisions.append(hits / self._k if self._k > 0 else 0.0)

            # Recall@k
            if relevant:
                recalls.append(hits / len(relevant))
            else:
                recalls.append(1.0 if hits == 0 else 0.0)

            # NDCG@k
            dcg = sum(
                (1.0 if r in relevant else 0.0) / math.log2(i + 2) for i, r in enumerate(retrieved)
            )
            ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), self._k)))
            ndcgs.append(dcg / ideal if ideal > 0 else 0.0)

        n = len(queries) or 1
        mean_p = sum(precisions) / n
        mean_r = sum(recalls) / n
        mean_ndcg = sum(ndcgs) / n
        mean_lat = sum(latencies) / n

        return RetrievalQualityReport(
            precision_at_5=round(mean_p, 6),
            recall_at_5=round(mean_r, 6),
            ndcg_at_5=round(mean_ndcg, 6),
            mean_query_latency_ms=round(mean_lat, 4),
            total_queries=len(queries),
            passes_quality_gate=(
                mean_p >= self._min_precision and mean_lat <= self._max_latency_ms
            ),
        )
