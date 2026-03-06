"""Tests for EffectAliasResolver."""

from __future__ import annotations

import json
from pathlib import Path

from twinklr.core.feature_engineering.normalization.models import AliasReviewResult
from twinklr.core.feature_engineering.normalization.resolver import EffectAliasResolver

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_review_result(
    cluster_id: str = "c-1",
    approved: bool = True,
    canonical_label: str = "Chase",
    confidence: float = 0.9,
    members: tuple[str, ...] = ("Chase", "CHASE", "chase"),
    effect_family: str | None = "pattern",
    motion_class: str | None = "sweep",
) -> AliasReviewResult:
    return AliasReviewResult(
        cluster_id=cluster_id,
        approved=approved,
        canonical_label=canonical_label,
        confidence=confidence,
        rationale="Test rationale.",
        members=members,
        suggested_effect_family=effect_family,
        suggested_motion_class=motion_class,
    )


def _make_resolver_with_chase() -> EffectAliasResolver:
    result = _make_review_result()
    return EffectAliasResolver.from_review_results((result,))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestKnownAliasResolved:
    """test_known_alias_resolved: resolve returns correct ResolvedEffect."""

    def test_exact_case_resolves(self) -> None:
        resolver = _make_resolver_with_chase()
        resolved = resolver.resolve("Chase")
        assert resolved is not None
        assert resolved.canonical_name == "Chase"
        assert resolved.original_effect_type == "Chase"

    def test_uppercase_resolves(self) -> None:
        resolver = _make_resolver_with_chase()
        resolved = resolver.resolve("CHASE")
        assert resolved is not None
        assert resolved.canonical_name == "Chase"

    def test_lowercase_resolves(self) -> None:
        resolver = _make_resolver_with_chase()
        resolved = resolver.resolve("chase")
        assert resolved is not None
        assert resolved.canonical_name == "Chase"

    def test_effect_family_populated(self) -> None:
        resolver = _make_resolver_with_chase()
        resolved = resolver.resolve("Chase")
        assert resolved is not None
        assert resolved.effect_family == "pattern"

    def test_motion_class_populated(self) -> None:
        resolver = _make_resolver_with_chase()
        resolved = resolver.resolve("chase")
        assert resolved is not None
        assert resolved.motion_class == "sweep"

    def test_confidence_populated(self) -> None:
        resolver = _make_resolver_with_chase()
        resolved = resolver.resolve("Chase")
        assert resolved is not None
        assert resolved.confidence == 0.9


class TestUnknownEffectReturnsNone:
    """test_unknown_effect_returns_none."""

    def test_completely_unknown(self) -> None:
        resolver = _make_resolver_with_chase()
        assert resolver.resolve("Shimmer") is None

    def test_empty_resolver(self) -> None:
        resolver = EffectAliasResolver({}, {}, {}, {})
        assert resolver.resolve("Anything") is None

    def test_partial_match_not_resolved(self) -> None:
        resolver = _make_resolver_with_chase()
        # "Chaser" normalizes to "chaser", not "chase"
        assert resolver.resolve("Chaser") is None


class TestRoundTripJson:
    """test_round_trip_json: to_json then from_json -> identical behavior."""

    def test_round_trip_resolves_same(self, tmp_path: Path) -> None:
        resolver = _make_resolver_with_chase()
        json_path = tmp_path / "aliases.json"
        resolver.to_json(json_path)
        loaded = EffectAliasResolver.from_json(json_path)
        assert loaded.resolve("Chase") is not None
        assert loaded.resolve("CHASE") is not None

    def test_round_trip_unknown_still_none(self, tmp_path: Path) -> None:
        resolver = _make_resolver_with_chase()
        json_path = tmp_path / "aliases.json"
        resolver.to_json(json_path)
        loaded = EffectAliasResolver.from_json(json_path)
        assert loaded.resolve("Shimmer") is None

    def test_round_trip_canonical_preserved(self, tmp_path: Path) -> None:
        resolver = _make_resolver_with_chase()
        json_path = tmp_path / "aliases.json"
        resolver.to_json(json_path)
        loaded = EffectAliasResolver.from_json(json_path)
        resolved = loaded.resolve("chase")
        assert resolved is not None
        assert resolved.canonical_name == "Chase"

    def test_json_file_written(self, tmp_path: Path) -> None:
        resolver = _make_resolver_with_chase()
        json_path = tmp_path / "aliases.json"
        resolver.to_json(json_path)
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert "alias_map" in data
        assert "confidence_map" in data


class TestFromReviewResultsFiltersApprovedOnly:
    """test_from_review_results_filters_approved_only."""

    def test_rejected_not_in_resolver(self) -> None:
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
        resolver = EffectAliasResolver.from_review_results((approved, rejected))
        assert resolver.resolve("Chase") is not None
        assert resolver.resolve("Shimmer") is None

    def test_all_rejected_empty_resolver(self) -> None:
        rejected = _make_review_result(approved=False)
        resolver = EffectAliasResolver.from_review_results((rejected,))
        assert resolver.resolve("Chase") is None

    def test_empty_results_empty_resolver(self) -> None:
        resolver = EffectAliasResolver.from_review_results(())
        assert resolver.resolve("Chase") is None

    def test_all_members_of_approved_cluster_mapped(self) -> None:
        result = _make_review_result(
            approved=True,
            canonical_label="Chase",
            members=("Chase", "CHASE", "chase", "Ch@se"),
        )
        resolver = EffectAliasResolver.from_review_results((result,))
        # All should normalize and resolve
        for member in ("Chase", "CHASE", "chase"):
            assert resolver.resolve(member) is not None
