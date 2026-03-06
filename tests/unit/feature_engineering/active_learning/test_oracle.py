"""Tests for TaxonomyReviewOracle."""

from __future__ import annotations

import json

from twinklr.core.feature_engineering.active_learning.models import (
    ReviewBatch,
    ReviewItem,
    UncertaintyCandidate,
)
from twinklr.core.feature_engineering.active_learning.oracle import TaxonomyReviewOracle


def _make_candidate(
    candidate_id: str = "cand_001",
    effect_type: str = "sparkle_burst",
    current_family: str = "unknown",
    current_motion: str = "unknown",
    map_confidence: float = 0.2,
) -> UncertaintyCandidate:
    return UncertaintyCandidate(
        candidate_id=candidate_id,
        effect_type=effect_type,
        normalized_key=f"{effect_type}::default",
        current_family=current_family,
        current_motion=current_motion,
        map_confidence=map_confidence,
        occurrence_count=5,
        uncertainty_score=round(1.0 - map_confidence, 10),
        uncertainty_reasons=("low_confidence",),
        sample_phrase_ids=("p1", "p2"),
    )


def _make_item(
    candidate: UncertaintyCandidate,
    context_phrases: tuple[str, ...] = ("burst of sparkle", "glitter flash"),
    suggested_family: str | None = "SPARKLE",
    suggested_motion: str | None = "sparkle",
) -> ReviewItem:
    return ReviewItem(
        candidate=candidate,
        context_phrases=context_phrases,
        suggested_family=suggested_family,
        suggested_motion=suggested_motion,
        suggestion_source="test",
    )


def _make_batch(items: tuple[ReviewItem, ...]) -> ReviewBatch:
    return ReviewBatch(
        batch_id="batch_test_001",
        items=items,
        total_candidates=len(items),
    )


class _MockLLMClient:
    """Mock LLM client that returns a predefined response."""

    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, messages: list[dict[str, str]]) -> str:
        return self._response


class TestTaxonomyReviewOracle:
    def test_valid_batch_returns_approved_corrections(self) -> None:
        """Valid LLM JSON response produces approved TaxonomyCorrectionResult."""
        payload = json.dumps(
            {
                "corrected_family": "SPARKLE",
                "corrected_motion": "sparkle",
                "confidence": 0.92,
                "rationale": "Clearly a sparkle effect based on context.",
                "approved": True,
            }
        )
        client = _MockLLMClient(payload)
        oracle = TaxonomyReviewOracle(client)

        candidate = _make_candidate()
        item = _make_item(candidate)
        batch = _make_batch((item,))

        results = oracle.review(batch)

        assert len(results) == 1
        r = results[0]
        assert r.approved is True
        assert r.candidate_id == candidate.candidate_id
        assert r.corrected_family == "SPARKLE"
        assert r.corrected_motion == "sparkle"
        assert abs(r.correction_confidence - 0.92) < 1e-6

    def test_corrected_family_is_in_known_set(self) -> None:
        """Oracle never returns a corrected_family outside the known taxonomy."""
        payload = json.dumps(
            {
                "corrected_family": "FIREWORKS",
                "corrected_motion": "pulse",
                "confidence": 0.88,
                "rationale": "Looks like fireworks.",
                "approved": True,
            }
        )
        client = _MockLLMClient(payload)
        oracle = TaxonomyReviewOracle(client)

        candidate = _make_candidate(effect_type="big_boom", current_family="unknown")
        item = _make_item(candidate, suggested_family="FIREWORKS", suggested_motion="pulse")
        batch = _make_batch((item,))

        results = oracle.review(batch)

        assert len(results) == 1
        r = results[0]
        known_families = {
            "CHASE",
            "STROBE",
            "STATIC",
            "COLOR",
            "BARS",
            "WAVE",
            "MORPH",
            "BUTTERFLY",
            "SPARKLE",
            "FIREWORKS",
            "LIGHTNING",
            "SHIMMER",
            "WARP",
            "CIRCLES",
            "CUSTOM",
        }
        assert r.corrected_family in known_families

    def test_malformed_llm_response_returns_parse_error_fallback(self) -> None:
        """Non-JSON LLM output produces approved=False and 'parse error' rationale."""
        client = _MockLLMClient("I cannot classify this effect. Sorry!")
        oracle = TaxonomyReviewOracle(client)

        candidate = _make_candidate(candidate_id="cand_bad")
        item = _make_item(candidate)
        batch = _make_batch((item,))

        results = oracle.review(batch)

        assert len(results) == 1
        r = results[0]
        assert r.approved is False
        assert "parse error" in r.rationale.lower()
        assert r.candidate_id == candidate.candidate_id

    def test_unknown_family_in_response_is_discarded(self) -> None:
        """A corrected_family not in the known set is nulled out."""
        payload = json.dumps(
            {
                "corrected_family": "TOTALLY_MADE_UP",
                "corrected_motion": "static",
                "confidence": 0.5,
                "rationale": "invented family",
                "approved": True,
            }
        )
        client = _MockLLMClient(payload)
        oracle = TaxonomyReviewOracle(client)

        candidate = _make_candidate()
        item = _make_item(candidate)
        batch = _make_batch((item,))

        results = oracle.review(batch)

        assert len(results) == 1
        # corrected_family should be None since it was unknown
        assert results[0].corrected_family is None
        # corrected_motion was valid and should remain
        assert results[0].corrected_motion == "static"

    def test_multiple_items_in_batch(self) -> None:
        """Each item in the batch gets its own result."""
        payload = json.dumps(
            {
                "corrected_family": "WAVE",
                "corrected_motion": "sweep",
                "confidence": 0.75,
                "rationale": "Wave pattern.",
                "approved": True,
            }
        )
        client = _MockLLMClient(payload)
        oracle = TaxonomyReviewOracle(client)

        items = tuple(
            _make_item(_make_candidate(candidate_id=f"c{i}", effect_type=f"fx_{i}"))
            for i in range(3)
        )
        batch = _make_batch(items)
        results = oracle.review(batch)

        assert len(results) == 3
        for r in results:
            assert r.corrected_family == "WAVE"
