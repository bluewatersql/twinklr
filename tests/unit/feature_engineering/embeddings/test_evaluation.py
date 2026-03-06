"""Tests for RetrievalQualityEvaluator."""

from __future__ import annotations

from twinklr.core.feature_engineering.embeddings.evaluation import RetrievalQualityEvaluator
from twinklr.core.feature_engineering.embeddings.models import (
    SequenceEmbedding,
    SimilarityLink,
)


def _make_embedding(
    pkg: str, seq: str, values: tuple[float, ...] = (0.1, 0.2, 0.3)
) -> SequenceEmbedding:
    return SequenceEmbedding(
        package_id=pkg,
        sequence_file_id=seq,
        embedding=values,
        dimensionality=len(values),
        strategy="test",
    )


def _make_link(
    src_pkg: str,
    src_seq: str,
    tgt_pkg: str,
    tgt_seq: str,
    sim: float = 0.9,
    rank: int = 1,
) -> SimilarityLink:
    return SimilarityLink(
        source_package_id=src_pkg,
        source_sequence_id=src_seq,
        target_package_id=tgt_pkg,
        target_sequence_id=tgt_seq,
        similarity=sim,
        rank=rank,
    )


def test_perfect_retrieval_precision() -> None:
    """All retrieved results are relevant -> precision@5 = 1.0."""
    query = _make_embedding("pkg_a", "seq_1")
    relevant_keys = {f"pkg_b/seq_{i}" for i in range(1, 6)}
    ground_truth = {"pkg_a/seq_1": relevant_keys}

    def query_fn(q: SequenceEmbedding) -> tuple[SimilarityLink, ...]:
        return tuple(_make_link("pkg_a", "seq_1", "pkg_b", f"seq_{i}", rank=i) for i in range(1, 6))

    evaluator = RetrievalQualityEvaluator(k=5)
    report = evaluator.evaluate(ground_truth, query_fn, (query,))

    assert report.precision_at_5 == 1.0


def test_no_overlap_precision() -> None:
    """No retrieved results are relevant -> precision@5 = 0.0."""
    query = _make_embedding("pkg_a", "seq_1")
    ground_truth = {"pkg_a/seq_1": {"pkg_b/seq_99"}}

    def query_fn(q: SequenceEmbedding) -> tuple[SimilarityLink, ...]:
        return tuple(_make_link("pkg_a", "seq_1", "pkg_c", f"seq_{i}", rank=i) for i in range(1, 6))

    evaluator = RetrievalQualityEvaluator(k=5)
    report = evaluator.evaluate(ground_truth, query_fn, (query,))

    assert report.precision_at_5 == 0.0


def test_report_includes_latency() -> None:
    """mean_query_latency_ms is non-negative."""
    query = _make_embedding("pkg_a", "seq_1")
    ground_truth: dict[str, set[str]] = {}

    def query_fn(q: SequenceEmbedding) -> tuple[SimilarityLink, ...]:
        return ()

    evaluator = RetrievalQualityEvaluator(k=5)
    report = evaluator.evaluate(ground_truth, query_fn, (query,))

    assert report.mean_query_latency_ms >= 0.0


def test_quality_gate_passes() -> None:
    """High precision and fast query -> passes_quality_gate = True."""
    query = _make_embedding("pkg_a", "seq_1")
    relevant_keys = {f"pkg_b/seq_{i}" for i in range(1, 6)}
    ground_truth = {"pkg_a/seq_1": relevant_keys}

    def query_fn(q: SequenceEmbedding) -> tuple[SimilarityLink, ...]:
        return tuple(_make_link("pkg_a", "seq_1", "pkg_b", f"seq_{i}", rank=i) for i in range(1, 6))

    evaluator = RetrievalQualityEvaluator(k=5, min_precision=0.5, max_latency_ms=1000.0)
    report = evaluator.evaluate(ground_truth, query_fn, (query,))

    assert report.passes_quality_gate is True


def test_quality_gate_fails() -> None:
    """Low precision -> passes_quality_gate = False."""
    query = _make_embedding("pkg_a", "seq_1")
    ground_truth = {"pkg_a/seq_1": {"pkg_b/seq_99"}}

    def query_fn(q: SequenceEmbedding) -> tuple[SimilarityLink, ...]:
        return tuple(_make_link("pkg_a", "seq_1", "pkg_c", f"seq_{i}", rank=i) for i in range(1, 6))

    evaluator = RetrievalQualityEvaluator(k=5, min_precision=0.5, max_latency_ms=1000.0)
    report = evaluator.evaluate(ground_truth, query_fn, (query,))

    assert report.passes_quality_gate is False
