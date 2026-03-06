"""Tests for NumPy-only alias clustering."""

from __future__ import annotations

import numpy as np
import pytest

from twinklr.core.feature_engineering.normalization.clustering import AliasClustering
from twinklr.core.feature_engineering.normalization.models import (
    AliasClusteringOptions,
    UnknownEffectEntry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(effect_type: str, count: int = 1) -> UnknownEffectEntry:
    return UnknownEffectEntry(
        effect_type=effect_type,
        normalized_key=effect_type.lower().replace(" ", "_"),
        count=count,
        context_text=effect_type,
    )


def _unit_vec(*components: float) -> tuple[float, ...]:
    """Return L2-normalised version of *components* as a float tuple."""
    arr = np.array(components, dtype=np.float64)
    norm = np.linalg.norm(arr)
    if norm == 0.0:
        return tuple(float(x) for x in arr)
    return tuple(float(x) for x in arr / norm)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_similar_names_cluster_together() -> None:
    """Entries with near-identical embeddings end up in the same cluster."""
    e1 = _entry("strobe flash", count=3)
    e2 = _entry("flash strobe", count=2)
    # Nearly identical unit vectors — cosine similarity ≈ 1.0
    v1 = _unit_vec(1.0, 0.01, 0.0)
    v2 = _unit_vec(1.0, 0.02, 0.0)

    options = AliasClusteringOptions(min_cluster_size=2, min_similarity=0.75)
    groups = AliasClustering(options).cluster((e1, e2), (v1, v2))

    assert len(groups) == 1
    assert set(groups[0].members) == {"strobe flash", "flash strobe"}


def test_dissimilar_names_different_clusters() -> None:
    """Entries with orthogonal embeddings produce no shared cluster."""
    e1 = _entry("strobe", count=5)
    e2 = _entry("rainbow sweep", count=5)
    # Orthogonal unit vectors — cosine similarity = 0.0
    v1 = _unit_vec(1.0, 0.0, 0.0)
    v2 = _unit_vec(0.0, 1.0, 0.0)

    options = AliasClusteringOptions(min_cluster_size=2, min_similarity=0.75)
    groups = AliasClustering(options).cluster((e1, e2), (v1, v2))

    # Both entries are singletons — filtered out by min_cluster_size.
    assert groups == ()


def test_single_entry_excluded() -> None:
    """A single entry produces no cluster (min_cluster_size=2)."""
    e1 = _entry("lone_effect")
    v1 = _unit_vec(1.0, 0.0)

    options = AliasClusteringOptions(min_cluster_size=2, min_similarity=0.75)
    groups = AliasClustering(options).cluster((e1,), (v1,))

    assert groups == ()


def test_suggested_canonical_is_most_frequent() -> None:
    """suggested_canonical is the member with the highest count."""
    e1 = _entry("flash", count=10)
    e2 = _entry("strobe flash", count=3)
    e3 = _entry("flash strobe", count=7)
    # All near-identical vectors
    v1 = _unit_vec(1.0, 0.01, 0.0)
    v2 = _unit_vec(1.0, 0.015, 0.0)
    v3 = _unit_vec(1.0, 0.02, 0.0)

    options = AliasClusteringOptions(min_cluster_size=2, min_similarity=0.75)
    groups = AliasClustering(options).cluster((e1, e2, e3), (v1, v2, v3))

    assert len(groups) == 1
    assert groups[0].suggested_canonical == "flash"


def test_centroid_similarity_within_bounds() -> None:
    """centroid_similarity is always in [0.0, 1.0]."""
    entries = tuple(_entry(f"effect_{i}", count=i + 1) for i in range(4))
    # Build a 2D embedding: all vectors point in roughly the same direction.
    base = np.array([1.0, 0.0], dtype=np.float64)
    perturbations = [0.0, 0.05, 0.1, 0.15]
    raw_vecs = [base + np.array([0.0, p]) for p in perturbations]
    embeddings = tuple(tuple(float(x) for x in v / np.linalg.norm(v)) for v in raw_vecs)

    options = AliasClusteringOptions(min_cluster_size=2, min_similarity=0.9)
    groups = AliasClustering(options).cluster(entries, embeddings)

    for group in groups:
        assert 0.0 <= group.centroid_similarity <= 1.0


def test_empty_entries_returns_empty() -> None:
    """No entries produces no clusters."""
    groups = AliasClustering().cluster((), ())
    assert groups == ()


def test_mismatched_lengths_raises() -> None:
    """Mismatched entries/embeddings raises ValueError."""
    e1 = _entry("x")
    v1 = _unit_vec(1.0, 0.0)
    v2 = _unit_vec(0.0, 1.0)

    with pytest.raises(ValueError, match="equal length"):
        AliasClustering().cluster((e1,), (v1, v2))


def test_cluster_ids_are_unique() -> None:
    """Each returned cluster has a distinct cluster_id."""
    # Three entries: two similar, two similar — but only if split into two pairs.
    e1 = _entry("a", count=1)
    e2 = _entry("b", count=1)
    e3 = _entry("c", count=1)
    e4 = _entry("d", count=1)
    # Two orthogonal subspaces with high intra-group similarity.
    v1 = _unit_vec(1.0, 0.01, 0.0, 0.0)
    v2 = _unit_vec(1.0, 0.02, 0.0, 0.0)
    v3 = _unit_vec(0.0, 0.0, 1.0, 0.01)
    v4 = _unit_vec(0.0, 0.0, 1.0, 0.02)

    options = AliasClusteringOptions(min_cluster_size=2, min_similarity=0.75)
    groups = AliasClustering(options).cluster((e1, e2, e3, e4), (v1, v2, v3, v4))

    ids = [g.cluster_id for g in groups]
    assert len(ids) == len(set(ids)), "cluster_ids must be unique"
