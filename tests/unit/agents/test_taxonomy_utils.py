"""Tests for taxonomy utils."""

from twinklr.core.agents.taxonomy_utils import (
    get_supported_motif_ids,
    get_theming_catalog_dict,
    get_theming_ids,
)


def test_get_supported_motif_ids():
    """Test that get_supported_motif_ids returns only motifs with template support."""
    supported = get_supported_motif_ids()

    # Should return a set
    assert isinstance(supported, set)

    # Should have at least some motifs (we know templates have motif tags)
    assert len(supported) > 0

    # All returned motifs should be strings without 'motif.' prefix
    for motif_id in supported:
        assert isinstance(motif_id, str)
        assert not motif_id.startswith("motif.")


def test_theming_catalog_filters_orphaned_motifs():
    """Test that get_theming_catalog_dict filters motifs to only those with templates."""
    from twinklr.core.sequencer.theming import MOTIF_REGISTRY

    catalog = get_theming_catalog_dict()
    supported = get_supported_motif_ids()

    # Catalog motifs should only include supported ones
    catalog_motif_ids = {m["id"] for m in catalog["motifs"]}
    assert catalog_motif_ids == supported

    # Should be fewer than total motifs in registry (unless all have templates)
    all_motif_ids = set(MOTIF_REGISTRY.list_ids())
    assert len(catalog_motif_ids) <= len(all_motif_ids)


def test_theming_ids_filters_orphaned_motifs():
    """Test that get_theming_ids filters motif_ids to only those with templates."""
    ids = get_theming_ids()
    supported = get_supported_motif_ids()

    # motif_ids should only include supported ones
    assert set(ids["motif_ids"]) == supported

    # Should be a sorted list
    assert ids["motif_ids"] == sorted(ids["motif_ids"])


def test_motif_filtering_consistency():
    """Test that all three functions return consistent motif filtering."""
    supported = get_supported_motif_ids()
    catalog = get_theming_catalog_dict()
    ids = get_theming_ids()

    # All should agree on which motifs are supported
    catalog_motifs = {m["id"] for m in catalog["motifs"]}
    ids_motifs = set(ids["motif_ids"])

    assert catalog_motifs == supported
    assert ids_motifs == supported
