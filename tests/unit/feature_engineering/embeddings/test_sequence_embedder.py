"""Unit tests for SequenceEmbedder."""

from __future__ import annotations

from twinklr.core.feature_engineering.embeddings.models import (
    SequenceFeatureVector,
)
from twinklr.core.feature_engineering.embeddings.sequence_embedder import (
    SequenceEmbedder,
)


def _make_vector(
    pkg: str,
    seq: str,
    values: tuple[float, ...],
) -> SequenceFeatureVector:
    return SequenceFeatureVector(
        package_id=pkg,
        sequence_file_id=seq,
        feature_names=tuple(f"f{i}" for i in range(len(values))),
        values=values,
        dimensionality=len(values),
    )


def test_passthrough_preserves_vector() -> None:
    """Passthrough strategy produces embedding equal to input values."""
    vec = _make_vector("pkg1", "seq1", (0.1, 0.2, 0.3, 0.4))
    embedder = SequenceEmbedder(strategy="passthrough")
    (result,) = embedder.embed((vec,))
    assert result.embedding == vec.values
    assert result.dimensionality == 4
    assert result.strategy == "passthrough"
    assert result.package_id == "pkg1"
    assert result.sequence_file_id == "seq1"


def test_pca_reduces_dimensionality() -> None:
    """PCA with target_dim=4 reduces 10-dimensional vectors to 4 dimensions."""
    import numpy as np

    rng = np.random.default_rng(42)
    vectors = tuple(
        _make_vector("pkg1", f"seq{i}", tuple(float(x) for x in rng.random(10))) for i in range(20)
    )
    embedder = SequenceEmbedder(strategy="pca", target_dim=4)
    embedder.fit(vectors)
    results = embedder.embed(vectors)
    assert len(results) == 20
    for result in results:
        assert result.dimensionality == 4
        assert len(result.embedding) == 4
        assert result.strategy == "pca"


def test_batch_embedding_correct_count() -> None:
    """Five input vectors produce exactly five output embeddings."""
    vectors = tuple(
        _make_vector("pkg1", f"seq{i}", (float(i), float(i + 1), float(i + 2))) for i in range(5)
    )
    embedder = SequenceEmbedder(strategy="passthrough")
    results = embedder.embed(vectors)
    assert len(results) == 5
    for i, result in enumerate(results):
        assert result.sequence_file_id == f"seq{i}"


def test_pca_deterministic() -> None:
    """Same input produces identical PCA embeddings on repeated calls."""
    import numpy as np

    rng = np.random.default_rng(0)
    vectors = tuple(
        _make_vector("pkg1", f"seq{i}", tuple(float(x) for x in rng.random(8))) for i in range(15)
    )
    embedder = SequenceEmbedder(strategy="pca", target_dim=3)
    embedder.fit(vectors)

    results_a = embedder.embed(vectors)
    results_b = embedder.embed(vectors)

    for a, b in zip(results_a, results_b, strict=True):
        assert a.embedding == b.embedding
