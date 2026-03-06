"""Tests for EffectAliasResolver.generate_taxonomy_patches."""

from __future__ import annotations

from twinklr.core.feature_engineering.normalization.models import AliasReviewResult
from twinklr.core.feature_engineering.normalization.resolver import EffectAliasResolver

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_review_result(
    cluster_id: str = "c-1",
    approved: bool = True,
    canonical_label: str = "Chase",
    confidence: float = 0.88,
    members: tuple[str, ...] = ("Chase", "CHASE"),
    effect_family: str | None = "pattern",
    motion_class: str | None = "sweep",
) -> AliasReviewResult:
    return AliasReviewResult(
        cluster_id=cluster_id,
        approved=approved,
        canonical_label=canonical_label,
        confidence=confidence,
        rationale="Test.",
        members=members,
        suggested_effect_family=effect_family,
        suggested_motion_class=motion_class,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPatchesFollowSchema:
    """test_patches_follow_schema: generated patches have correct TaxonomyRulePatch fields."""

    def test_patch_effect_type_is_member(self) -> None:
        result = _make_review_result(members=("Chase", "CHASE"))
        patches = EffectAliasResolver.generate_taxonomy_patches((result,))
        effect_types = {p.effect_type for p in patches}
        assert "Chase" in effect_types
        assert "CHASE" in effect_types

    def test_patch_canonical_name_matches_result(self) -> None:
        result = _make_review_result(canonical_label="Chase")
        patches = EffectAliasResolver.generate_taxonomy_patches((result,))
        for patch in patches:
            assert patch.canonical_name == "Chase"

    def test_patch_effect_family_propagated(self) -> None:
        result = _make_review_result(effect_family="pattern")
        patches = EffectAliasResolver.generate_taxonomy_patches((result,))
        for patch in patches:
            assert patch.effect_family == "pattern"

    def test_patch_motion_class_propagated(self) -> None:
        result = _make_review_result(motion_class="sweep")
        patches = EffectAliasResolver.generate_taxonomy_patches((result,))
        for patch in patches:
            assert patch.motion_class == "sweep"

    def test_patch_source_cluster_id_matches(self) -> None:
        result = _make_review_result(cluster_id="c-99")
        patches = EffectAliasResolver.generate_taxonomy_patches((result,))
        for patch in patches:
            assert patch.source_cluster_id == "c-99"

    def test_patch_confidence_matches(self) -> None:
        result = _make_review_result(confidence=0.77)
        patches = EffectAliasResolver.generate_taxonomy_patches((result,))
        for patch in patches:
            assert patch.confidence == 0.77

    def test_patch_count_equals_member_count(self) -> None:
        result = _make_review_result(members=("A", "B", "C"))
        patches = EffectAliasResolver.generate_taxonomy_patches((result,))
        assert len(patches) == 3


class TestPatchesReferenceOnlyApproved:
    """test_patches_reference_only_approved."""

    def test_rejected_members_not_in_patches(self) -> None:
        approved = _make_review_result(
            cluster_id="c-1",
            approved=True,
            canonical_label="Chase",
            members=("Chase", "CHASE"),
        )
        rejected = _make_review_result(
            cluster_id="c-2",
            approved=False,
            canonical_label="Shimmer",
            members=("Shimmer", "SHIMMER"),
        )
        patches = EffectAliasResolver.generate_taxonomy_patches((approved, rejected))
        effect_types = {p.effect_type for p in patches}
        assert "Shimmer" not in effect_types
        assert "SHIMMER" not in effect_types
        assert "Chase" in effect_types

    def test_only_approved_cluster_ids_in_patches(self) -> None:
        approved = _make_review_result(cluster_id="c-approved", approved=True)
        rejected = _make_review_result(cluster_id="c-rejected", approved=False)
        patches = EffectAliasResolver.generate_taxonomy_patches((approved, rejected))
        cluster_ids = {p.source_cluster_id for p in patches}
        assert "c-approved" in cluster_ids
        assert "c-rejected" not in cluster_ids

    def test_all_rejected_yields_no_patches(self) -> None:
        r1 = _make_review_result(approved=False)
        r2 = _make_review_result(cluster_id="c-2", approved=False)
        patches = EffectAliasResolver.generate_taxonomy_patches((r1, r2))
        assert len(patches) == 0


class TestEmptyResultsEmptyPatches:
    """test_empty_results_empty_patches."""

    def test_empty_tuple_returns_empty_tuple(self) -> None:
        patches = EffectAliasResolver.generate_taxonomy_patches(())
        assert patches == ()

    def test_return_type_is_tuple(self) -> None:
        patches = EffectAliasResolver.generate_taxonomy_patches(())
        assert isinstance(patches, tuple)
