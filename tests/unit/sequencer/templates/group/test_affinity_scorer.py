"""Tests for AffinityScorer — computed template-context compatibility."""

from __future__ import annotations

from twinklr.core.sequencer.templates.group.affinity import (
    AffinityQuery,
    AffinityScorer,
)
from twinklr.core.sequencer.templates.group.library import TemplateInfo
from twinklr.core.sequencer.vocabulary import (
    GroupTemplateType,
    GroupVisualIntent,
)


def _make_info(
    *,
    template_id: str = "gtpl_base_starfield_slow",
    template_type: GroupTemplateType = GroupTemplateType.BASE,
    visual_intent: GroupVisualIntent = GroupVisualIntent.ABSTRACT,
    tags: tuple[str, ...] = ("stars", "sparkle", "slow"),
) -> TemplateInfo:
    return TemplateInfo(
        template_id=template_id,
        version="1.0.0",
        name="Starfield Slow",
        template_type=template_type,
        visual_intent=visual_intent,
        tags=tags,
    )


# -- Motif matching --


def test_motif_match_exact_tag() -> None:
    """Template with tag 'stars' matches motif 'stars'."""
    info = _make_info(tags=("stars", "sparkle"))
    query = AffinityQuery(motif_ids=["stars"])
    result = AffinityScorer.score(info, query)
    assert result.motif_score > 0.0


def test_motif_match_partial_overlap() -> None:
    """Template with tag 'sparkle' partially matches motifs ['sparkles', 'grid']."""
    info = _make_info(tags=("sparkles", "shimmer"))
    query = AffinityQuery(motif_ids=["sparkles", "grid"])
    result = AffinityScorer.score(info, query)
    assert result.motif_score > 0.0


def test_motif_no_match() -> None:
    """Template with no overlapping tags returns 0 motif score."""
    info = _make_info(tags=("fire", "flame"))
    query = AffinityQuery(motif_ids=["grid", "wave_bands"])
    result = AffinityScorer.score(info, query)
    assert result.motif_score == 0.0


def test_no_motifs_in_query() -> None:
    """Empty motif_ids returns 0 motif score."""
    info = _make_info(tags=("stars",))
    query = AffinityQuery(motif_ids=[])
    result = AffinityScorer.score(info, query)
    assert result.motif_score == 0.0


# -- Overall score --


def test_overall_score_bounded() -> None:
    """Overall score is between 0.0 and 1.0."""
    info = _make_info()
    query = AffinityQuery(motif_ids=["stars"])
    result = AffinityScorer.score(info, query)
    assert 0.0 <= result.overall <= 1.0


def test_overall_score_zero_for_empty_query() -> None:
    """Empty query returns 0.0 overall."""
    info = _make_info()
    query = AffinityQuery()
    result = AffinityScorer.score(info, query)
    assert result.overall == 0.0


# -- Derived affinity tags (backward compatibility) --


def test_derived_affinity_tags_from_tags() -> None:
    """derive_affinity_tags generates motif.* tags from template tags."""
    info = _make_info(tags=("stars", "sparkle", "slow"))
    tags = AffinityScorer.derive_affinity_tags(info)
    assert "motif.stars" in tags
    assert "motif.sparkle" in tags


def test_derived_affinity_tags_include_style() -> None:
    """derive_affinity_tags includes style tags from visual_intent."""
    info = _make_info(visual_intent=GroupVisualIntent.ABSTRACT)
    tags = AffinityScorer.derive_affinity_tags(info)
    assert any(t.startswith("style.") for t in tags)


# -- has_motif_affinity (convenience for filtering) --


def test_has_motif_affinity_true() -> None:
    """has_motif_affinity returns True when template tags match motif."""
    info = _make_info(tags=("grid", "geometric"))
    assert AffinityScorer.has_motif_affinity(info, motif_ids=["grid"])


def test_has_motif_affinity_false() -> None:
    """has_motif_affinity returns False when no tag matches."""
    info = _make_info(tags=("fire", "flame"))
    assert not AffinityScorer.has_motif_affinity(info, motif_ids=["grid"])


def test_has_motif_affinity_empty_motifs() -> None:
    """has_motif_affinity returns False when motif_ids is empty."""
    info = _make_info(tags=("grid",))
    assert not AffinityScorer.has_motif_affinity(info, motif_ids=[])
