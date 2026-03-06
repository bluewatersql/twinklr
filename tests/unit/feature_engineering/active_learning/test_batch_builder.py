"""Tests for ReviewBatchBuilder."""

from __future__ import annotations

from unittest.mock import MagicMock

from twinklr.core.feature_engineering.active_learning.batch_builder import (
    ReviewBatchBuilder,
)
from twinklr.core.feature_engineering.active_learning.models import (
    UncertaintyCandidate,
)
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.normalization.resolver import EffectAliasResolver


def _make_phrase(
    phrase_id: str,
    effect_type: str,
    param_signature: str = "sig_default",
) -> EffectPhrase:
    """Build a minimal EffectPhrase for testing.

    Args:
        phrase_id: Unique phrase identifier.
        effect_type: Effect type string.
        param_signature: Parameter signature hash.

    Returns:
        A fully populated EffectPhrase instance.
    """
    return EffectPhrase(
        schema_version="1.0",
        phrase_id=phrase_id,
        package_id="pkg_test",
        sequence_file_id="seq_test",
        effect_event_id=f"evt_{phrase_id}",
        effect_type=effect_type,
        effect_family="wash",
        motion_class=MotionClass.STATIC,
        color_class=ColorClass.MONO,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.3,
        target_name="par_1",
        layer_index=0,
        start_ms=0,
        end_ms=1000,
        duration_ms=1000,
        param_signature=param_signature,
    )


def _make_candidate(effect_type: str, candidate_id: str = "cand_1") -> UncertaintyCandidate:
    """Build a minimal UncertaintyCandidate for testing.

    Args:
        effect_type: Effect type for the candidate.
        candidate_id: Unique candidate identifier.

    Returns:
        A UncertaintyCandidate instance.
    """
    return UncertaintyCandidate(
        candidate_id=candidate_id,
        effect_type=effect_type,
        normalized_key=f"{effect_type}::sig_default",
        current_family="wash",
        current_motion="static",
        map_confidence=0.3,
        occurrence_count=1,
        uncertainty_score=0.7,
        uncertainty_reasons=("low_confidence",),
        sample_phrase_ids=("p1",),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReviewBatchBuilderContextPhrases:
    """Batch items include context_phrases from matching effect_type phrases."""

    def test_context_phrases_included_for_matching_effect_type(self) -> None:
        """ReviewItem.context_phrases should list param_signatures of matching phrases."""
        candidate = _make_candidate("chase")
        phrase_a = _make_phrase("p1", "chase", param_signature="sig_chase_a")
        phrase_b = _make_phrase("p2", "chase", param_signature="sig_chase_b")
        phrase_other = _make_phrase("p3", "wash", param_signature="sig_wash")

        builder = ReviewBatchBuilder()
        batch = builder.build(
            (candidate,),
            (phrase_a, phrase_b, phrase_other),
            resolver=None,
        )

        assert len(batch.items) == 1
        item = batch.items[0]
        assert "sig_chase_a" in item.context_phrases
        assert "sig_chase_b" in item.context_phrases
        assert "sig_wash" not in item.context_phrases


class TestReviewBatchBuilderResolverSuggestions:
    """Resolver suggestions are applied when a resolver is provided."""

    def test_resolver_suggestion_applied(self) -> None:
        """When resolver.resolve() returns a result, suggested_family/motion are set."""
        from twinklr.core.feature_engineering.normalization.models import ResolvedEffect

        candidate = _make_candidate("unknown_fx")
        phrase = _make_phrase("p1", "unknown_fx")

        mock_resolver = MagicMock(spec=EffectAliasResolver)
        mock_resolver.resolve.return_value = ResolvedEffect(
            original_effect_type="unknown_fx",
            canonical_name="chase",
            effect_family="chase",
            motion_class="sweep",
            confidence=0.85,
        )

        builder = ReviewBatchBuilder()
        batch = builder.build((candidate,), (phrase,), resolver=mock_resolver)

        assert len(batch.items) == 1
        item = batch.items[0]
        assert item.suggested_family == "chase"
        assert item.suggested_motion == "sweep"
        assert item.suggestion_source == "alias_resolver"
        mock_resolver.resolve.assert_called_once_with("unknown_fx")


class TestReviewBatchBuilderEmptyCandidates:
    """Empty candidates produce a batch with zero items."""

    def test_empty_candidates_returns_empty_batch(self) -> None:
        """build() with zero candidates must return ReviewBatch with empty items."""
        phrase = _make_phrase("p1", "wash")

        builder = ReviewBatchBuilder()
        batch = builder.build((), (phrase,), resolver=None)

        assert len(batch.items) == 0
        assert batch.total_candidates == 0
