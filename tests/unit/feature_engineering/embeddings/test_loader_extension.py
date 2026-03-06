"""Tests for FEArtifactBundle similarity_links and sequence_embedding fields."""

from __future__ import annotations

from twinklr.core.feature_engineering.embeddings.models import SimilarityLink
from twinklr.core.feature_engineering.loader import FEArtifactBundle


def test_bundle_without_similarity_data() -> None:
    """Default FEArtifactBundle has empty similarity_links and None sequence_embedding."""
    bundle = FEArtifactBundle()

    assert bundle.similarity_links == ()
    assert bundle.sequence_embedding is None


def test_bundle_with_similarity_data() -> None:
    """FEArtifactBundle created with SimilarityLink data exposes it correctly."""
    link = SimilarityLink(
        source_package_id="pkg_a",
        source_sequence_id="seq_1",
        target_package_id="pkg_b",
        target_sequence_id="seq_2",
        similarity=0.85,
        rank=1,
    )
    embedding = (0.1, 0.2, 0.3)

    bundle = FEArtifactBundle(
        similarity_links=(link,),
        sequence_embedding=embedding,
    )

    assert len(bundle.similarity_links) == 1
    assert bundle.similarity_links[0] is link
    assert bundle.sequence_embedding == embedding
