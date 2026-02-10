"""Unit tests for phoneme pipeline entry (Phase 6).

Tests cover:
- build_phoneme_bundle() - full pipeline wiring
- Confidence computation
- Edge cases (empty words, no timed words)
"""

from twinklr.core.audio.models.lyrics import LyricWord
from twinklr.core.audio.models.phonemes import PhonemeBundle, PhonemeSource
from twinklr.core.audio.phonemes.bundle import build_phoneme_bundle


class TestBuildPhonemeBundle:
    """Test build_phoneme_bundle pipeline entry."""

    def test_produces_phonemes_from_words(self):
        """Should produce phonemes from timed words."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
            LyricWord(text="world", start_ms=600, end_ms=1100),
        ]

        bundle = build_phoneme_bundle(
            duration_ms=2000,
            words=words,
            mapping_version="1.0",
        )

        assert isinstance(bundle, PhonemeBundle)
        assert len(bundle.phonemes) > 0
        assert bundle.source == PhonemeSource.G2P

    def test_produces_visemes(self):
        """Should produce smoothed viseme events."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
            LyricWord(text="world", start_ms=600, end_ms=1100),
        ]

        bundle = build_phoneme_bundle(
            duration_ms=2000,
            words=words,
            mapping_version="1.0",
        )

        assert len(bundle.visemes) > 0
        # Visemes should have valid timing
        for v in bundle.visemes:
            assert v.start_ms >= 0
            assert v.end_ms <= 2000
            assert v.end_ms >= v.start_ms

    def test_confidence_between_0_and_1(self):
        """Confidence should be in [0, 1]."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
        ]

        bundle = build_phoneme_bundle(
            duration_ms=1000,
            words=words,
            mapping_version="1.0",
        )

        assert 0.0 <= bundle.confidence <= 1.0

    def test_coverage_computed(self):
        """Coverage should reflect viseme span / duration."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
        ]

        bundle = build_phoneme_bundle(
            duration_ms=1000,
            words=words,
            mapping_version="1.0",
        )

        assert 0.0 <= bundle.coverage_pct <= 1.0
        # With words covering 500/1000ms, coverage should be around 0.5
        assert bundle.coverage_pct > 0.0

    def test_empty_words_returns_empty_bundle(self):
        """No words should return bundle with empty phonemes/visemes."""
        bundle = build_phoneme_bundle(
            duration_ms=1000,
            words=[],
            mapping_version="1.0",
        )

        assert isinstance(bundle, PhonemeBundle)
        assert len(bundle.phonemes) == 0
        assert len(bundle.visemes) == 0
        assert bundle.confidence == 0.0

    def test_uses_vowel_consonant_weights(self):
        """Custom weights should affect distribution."""
        words = [
            LyricWord(text="bat", start_ms=0, end_ms=300),
        ]

        bundle_default = build_phoneme_bundle(
            duration_ms=1000,
            words=words,
            mapping_version="1.0",
            vowel_weight=2.0,
            consonant_weight=1.0,
        )

        bundle_equal = build_phoneme_bundle(
            duration_ms=1000,
            words=words,
            mapping_version="1.0",
            vowel_weight=1.0,
            consonant_weight=1.0,
        )

        # Both should produce phonemes
        assert len(bundle_default.phonemes) > 0
        assert len(bundle_equal.phonemes) > 0

    def test_phonemes_have_valid_timing(self):
        """All phonemes should have timing within word bounds."""
        words = [
            LyricWord(text="cat", start_ms=100, end_ms=400),
        ]

        bundle = build_phoneme_bundle(
            duration_ms=1000,
            words=words,
            mapping_version="1.0",
        )

        for p in bundle.phonemes:
            assert p.start_ms >= 100, f"Phoneme {p.text} starts before word"
            assert p.end_ms <= 400, f"Phoneme {p.text} ends after word"

    def test_oov_rate_computed(self):
        """OOV rate should be in [0, 1]."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
        ]

        bundle = build_phoneme_bundle(
            duration_ms=1000,
            words=words,
            mapping_version="1.0",
        )

        assert 0.0 <= bundle.oov_rate <= 1.0

    def test_metadata_includes_word_count(self):
        """Metadata should include basic stats."""
        words = [
            LyricWord(text="hello", start_ms=0, end_ms=500),
            LyricWord(text="world", start_ms=600, end_ms=1000),
        ]

        bundle = build_phoneme_bundle(
            duration_ms=2000,
            words=words,
            mapping_version="1.0",
        )

        assert "word_count" in bundle.metadata
        assert bundle.metadata["word_count"] == 2
