"""Unit tests for SimilarityIndex."""

from __future__ import annotations

from pathlib import Path

from twinklr.core.feature_engineering.embeddings.models import SequenceEmbedding
from twinklr.core.feature_engineering.embeddings.similarity_index import SimilarityIndex


def _make_embedding(pkg: str, seq: str, values: tuple[float, ...]) -> SequenceEmbedding:
    return SequenceEmbedding(
        package_id=pkg,
        sequence_file_id=seq,
        embedding=values,
        dimensionality=len(values),
        strategy="passthrough",
    )


def test_self_not_in_results() -> None:
    """Querying with an indexed embedding excludes itself from results."""
    embs = (
        _make_embedding("pkg1", "seq1", (1.0, 0.0, 0.0)),
        _make_embedding("pkg1", "seq2", (0.9, 0.1, 0.0)),
        _make_embedding("pkg1", "seq3", (0.0, 1.0, 0.0)),
    )
    idx = SimilarityIndex()
    idx.build(embs)
    links = idx.query(embs[0])
    for link in links:
        assert not (link.target_package_id == "pkg1" and link.target_sequence_id == "seq1"), (
            "Self should be excluded from results"
        )


def test_similar_sequences_rank_higher() -> None:
    """A sequence with a nearly identical vector ranks higher than a dissimilar one."""
    query = _make_embedding("pkg1", "query", (1.0, 0.0, 0.0))
    similar = _make_embedding("pkg2", "similar", (0.99, 0.01, 0.0))
    dissimilar = _make_embedding("pkg3", "dissimilar", (0.0, 0.0, 1.0))
    idx = SimilarityIndex(n_neighbors=5)
    idx.build((query, similar, dissimilar))
    links = idx.query(query, k=2)
    assert len(links) == 2
    assert links[0].target_sequence_id == "similar"
    assert links[1].target_sequence_id == "dissimilar"
    assert links[0].rank == 1
    assert links[1].rank == 2
    assert links[0].similarity > links[1].similarity


def test_cross_package_links_above_threshold() -> None:
    """build_cross_package_links only returns links with cross-package + threshold."""
    embs = (
        _make_embedding("pkgA", "s1", (1.0, 0.0)),
        _make_embedding("pkgA", "s2", (0.99, 0.01)),  # same package, high sim
        _make_embedding("pkgB", "s3", (0.98, 0.02)),  # cross-package, high sim
        _make_embedding("pkgB", "s4", (0.0, 1.0)),  # cross-package, low sim
    )
    idx = SimilarityIndex(n_neighbors=5)
    links = idx.build_cross_package_links(embs, min_similarity=0.9)
    for link in links:
        assert link.source_package_id != link.target_package_id, "All links must be cross-package"
        assert link.similarity >= 0.9, "All links must meet min_similarity"


def test_save_load_round_trip(tmp_path: Path) -> None:
    """Save then load produces identical query results."""
    embs = (
        _make_embedding("pkg1", "seq1", (1.0, 0.0, 0.0)),
        _make_embedding("pkg1", "seq2", (0.0, 1.0, 0.0)),
        _make_embedding("pkg2", "seq3", (0.5, 0.5, 0.0)),
    )
    idx = SimilarityIndex(metric="cosine", n_neighbors=3)
    idx.build(embs)

    save_path = tmp_path / "index.json"
    idx.save(save_path)
    assert save_path.exists()

    loaded = SimilarityIndex.load(save_path)
    query = _make_embedding("pkg1", "seq1", (1.0, 0.0, 0.0))
    original_links = idx.query(query, k=2)
    loaded_links = loaded.query(query, k=2)

    assert len(original_links) == len(loaded_links)
    for orig, load in zip(original_links, loaded_links, strict=True):
        assert orig.target_package_id == load.target_package_id
        assert orig.target_sequence_id == load.target_sequence_id
        assert abs(orig.similarity - load.similarity) < 1e-9


def test_empty_index_returns_empty() -> None:
    """Querying an empty index returns an empty tuple."""
    idx = SimilarityIndex()
    idx.build(())
    query = _make_embedding("pkg1", "seq1", (1.0, 0.0))
    result = idx.query(query)
    assert result == ()
