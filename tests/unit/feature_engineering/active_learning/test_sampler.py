"""Tests for UncertaintySampler."""

from __future__ import annotations

from twinklr.core.feature_engineering.active_learning.models import (
    UncertaintySamplerOptions,
)
from twinklr.core.feature_engineering.active_learning.sampler import UncertaintySampler
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
)


def _make_phrase(
    phrase_id: str,
    effect_type: str,
    effect_family: str = "wash",
    motion_class: MotionClass = MotionClass.STATIC,
    map_confidence: float = 0.9,
    param_signature: str = "sig_default",
) -> EffectPhrase:
    """Build a minimal EffectPhrase for testing.

    Args:
        phrase_id: Unique phrase identifier.
        effect_type: Effect type string.
        effect_family: Effect family label.
        motion_class: Motion classification.
        map_confidence: Mapping confidence score.
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
        effect_family=effect_family,
        motion_class=motion_class,
        color_class=ColorClass.MONO,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=map_confidence,
        target_name="par_1",
        layer_index=0,
        start_ms=0,
        end_ms=1000,
        duration_ms=1000,
        param_signature=param_signature,
    )


def _make_taxonomy(phrase_id: str) -> PhraseTaxonomyRecord:
    """Build a minimal PhraseTaxonomyRecord for testing.

    Args:
        phrase_id: Phrase identifier to associate.

    Returns:
        A PhraseTaxonomyRecord with empty labels.
    """
    return PhraseTaxonomyRecord(
        schema_version="1.0",
        classifier_version="1.0",
        phrase_id=phrase_id,
        package_id="pkg_test",
        sequence_file_id="seq_test",
        effect_event_id=f"evt_{phrase_id}",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUncertaintySamplerLowConfidence:
    """Low-confidence phrases are selected for review."""

    def test_low_confidence_phrase_is_selected(self) -> None:
        """Phrase with map_confidence below threshold must appear in output."""
        phrase = _make_phrase("p1", "chase", map_confidence=0.3, param_signature="sig_chase")
        taxonomy = (_make_taxonomy("p1"),)
        opts = UncertaintySamplerOptions(max_confidence_threshold=0.5)
        sampler = UncertaintySampler(opts)

        candidates = sampler.sample((phrase,), taxonomy)

        assert len(candidates) == 1
        assert candidates[0].effect_type == "chase"
        assert "low_confidence" in candidates[0].uncertainty_reasons


class TestUncertaintySamplerUnknownFamily:
    """Phrases with unknown effect_family are selected."""

    def test_unknown_family_phrase_is_selected(self) -> None:
        """Phrase with effect_family='unknown' must appear in output."""
        phrase = _make_phrase(
            "p2",
            "mystery_fx",
            effect_family="unknown",
            map_confidence=0.8,
            param_signature="sig_mystery",
        )
        taxonomy = (_make_taxonomy("p2"),)
        opts = UncertaintySamplerOptions(
            max_confidence_threshold=0.5,
            min_frequency_threshold=1,
            include_unknown_families=True,
        )
        sampler = UncertaintySampler(opts)

        candidates = sampler.sample((phrase,), taxonomy)

        assert len(candidates) == 1
        assert "unknown_family" in candidates[0].uncertainty_reasons


class TestUncertaintySamplerUnknownMotion:
    """Phrases with unknown motion_class are selected."""

    def test_unknown_motion_phrase_is_selected(self) -> None:
        """Phrase with motion_class=MotionClass.UNKNOWN must appear in output."""
        phrase = _make_phrase(
            "p3",
            "glitch_fx",
            motion_class=MotionClass.UNKNOWN,
            map_confidence=0.8,
            param_signature="sig_glitch",
        )
        taxonomy = (_make_taxonomy("p3"),)
        opts = UncertaintySamplerOptions(
            max_confidence_threshold=0.5,
            min_frequency_threshold=1,
            include_unknown_motions=True,
        )
        sampler = UncertaintySampler(opts)

        candidates = sampler.sample((phrase,), taxonomy)

        assert len(candidates) == 1
        assert "unknown_motion" in candidates[0].uncertainty_reasons


class TestUncertaintySamplerHighConfidenceExcluded:
    """High-confidence, fully-classified phrases are not selected."""

    def test_high_confidence_phrase_excluded(self) -> None:
        """Phrase with map_confidence above threshold and known classes must not appear."""
        phrase = _make_phrase(
            "p4",
            "wash",
            effect_family="wash",
            motion_class=MotionClass.STATIC,
            map_confidence=0.95,
            param_signature="sig_wash",
        )
        taxonomy = (_make_taxonomy("p4"),)
        opts = UncertaintySamplerOptions(max_confidence_threshold=0.5)
        sampler = UncertaintySampler(opts)

        candidates = sampler.sample((phrase,), taxonomy)

        assert len(candidates) == 0


class TestUncertaintySamplerBatchSizeLimit:
    """max_batch_size is respected."""

    def test_batch_size_limit_applied(self) -> None:
        """When more candidates exist than max_batch_size, only max_batch_size returned."""
        phrases = tuple(
            _make_phrase(
                f"p{i}",
                f"fx_{i}",
                map_confidence=0.1,
                param_signature=f"sig_{i}",
            )
            for i in range(5)
        )
        taxonomy = tuple(_make_taxonomy(f"p{i}") for i in range(5))
        opts = UncertaintySamplerOptions(max_confidence_threshold=0.5, max_batch_size=2)
        sampler = UncertaintySampler(opts)

        candidates = sampler.sample(phrases, taxonomy)

        assert len(candidates) == 2


class TestUncertaintySamplerSortOrder:
    """Candidates are sorted by uncertainty_score descending."""

    def test_sorted_by_uncertainty_score_descending(self) -> None:
        """Candidate with lowest confidence (highest uncertainty) must appear first."""
        high_uncertainty = _make_phrase(
            "p_low", "fx_low", map_confidence=0.1, param_signature="sig_low"
        )
        med_uncertainty = _make_phrase(
            "p_med", "fx_med", map_confidence=0.3, param_signature="sig_med"
        )
        taxonomy = (_make_taxonomy("p_low"), _make_taxonomy("p_med"))
        opts = UncertaintySamplerOptions(max_confidence_threshold=0.5, max_batch_size=10)
        sampler = UncertaintySampler(opts)

        candidates = sampler.sample((high_uncertainty, med_uncertainty), taxonomy)

        assert len(candidates) == 2
        assert candidates[0].uncertainty_score >= candidates[1].uncertainty_score
        assert candidates[0].effect_type == "fx_low"
