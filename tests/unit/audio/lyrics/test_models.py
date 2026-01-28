"""Tests for lyrics models (Phase 4).

Testing LyricsBundle, LyricWord, LyricPhrase, and related models.
"""

from pydantic import ValidationError
import pytest

from blinkb0t.core.audio.models.enums import StageStatus
from blinkb0t.core.audio.models.lyrics import (
    LyricPhrase,
    LyricsBundle,
    LyricsQuality,
    LyricsSource,
    LyricWord,
)


class TestLyricWord:
    """Test LyricWord model."""

    def test_minimal_word(self):
        """Word with just text and timing."""
        word = LyricWord(
            text="hello",
            start_ms=1000,
            end_ms=1500,
        )

        assert word.text == "hello"
        assert word.start_ms == 1000
        assert word.end_ms == 1500
        assert word.speaker is None

    def test_word_with_speaker(self):
        """Word with speaker attribution."""
        word = LyricWord(
            text="world",
            start_ms=2000,
            end_ms=2300,
            speaker="vocalist_1",
        )

        assert word.speaker == "vocalist_1"

    def test_word_timing_validation(self):
        """Word timing must be non-negative and ordered."""
        # Valid
        LyricWord(text="test", start_ms=0, end_ms=100)
        LyricWord(text="test", start_ms=100, end_ms=100)  # Equal is ok

        # Invalid: negative start
        with pytest.raises(ValidationError):
            LyricWord(text="test", start_ms=-1, end_ms=100)

        # Invalid: negative end
        with pytest.raises(ValidationError):
            LyricWord(text="test", start_ms=0, end_ms=-1)

    def test_word_forbids_extra_fields(self):
        """Word model forbids extra fields."""
        with pytest.raises(ValidationError):
            LyricWord(  # type: ignore[call-arg]
                text="test",
                start_ms=0,
                end_ms=100,
                extra_field="not_allowed",
            )


class TestLyricPhrase:
    """Test LyricPhrase model."""

    def test_minimal_phrase(self):
        """Phrase with just text and timing."""
        phrase = LyricPhrase(
            text="Hello world",
            start_ms=1000,
            end_ms=2000,
        )

        assert phrase.text == "Hello world"
        assert phrase.start_ms == 1000
        assert phrase.end_ms == 2000
        assert phrase.words == []

    def test_phrase_with_words(self):
        """Phrase with word-level timing."""
        phrase = LyricPhrase(
            text="Hello world",
            start_ms=1000,
            end_ms=2000,
            words=[
                LyricWord(text="Hello", start_ms=1000, end_ms=1500),
                LyricWord(text="world", start_ms=1600, end_ms=2000),
            ],
        )

        assert len(phrase.words) == 2
        assert phrase.words[0].text == "Hello"
        assert phrase.words[1].text == "world"

    def test_phrase_timing_validation(self):
        """Phrase timing must be non-negative and ordered."""
        # Valid
        LyricPhrase(text="test", start_ms=0, end_ms=100)

        # Invalid: negative start
        with pytest.raises(ValidationError):
            LyricPhrase(text="test", start_ms=-1, end_ms=100)


class TestLyricsSource:
    """Test LyricsSource model."""

    def test_embedded_source(self):
        """Source from embedded extraction."""
        source = LyricsSource(
            kind="EMBEDDED",
            provider="lrc_file",
            confidence=0.95,
        )

        assert source.kind == "EMBEDDED"
        assert source.provider == "lrc_file"
        assert source.confidence == 0.95

    def test_lookup_synced_source(self):
        """Source from synced lookup."""
        source = LyricsSource(
            kind="LOOKUP_SYNCED",
            provider="lrclib",
            provider_id="12345",
            confidence=0.85,
        )

        assert source.kind == "LOOKUP_SYNCED"
        assert source.provider == "lrclib"
        assert source.provider_id == "12345"

    def test_lookup_plain_source(self):
        """Source from plain lookup."""
        source = LyricsSource(
            kind="LOOKUP_PLAIN",
            provider="genius",
            confidence=0.75,
        )

        assert source.kind == "LOOKUP_PLAIN"

    def test_source_confidence_range(self):
        """Source confidence must be 0-1."""
        # Valid
        LyricsSource(kind="EMBEDDED", provider="test", confidence=0.0)
        LyricsSource(kind="EMBEDDED", provider="test", confidence=1.0)

        # Invalid: below 0
        with pytest.raises(ValidationError):
            LyricsSource(kind="EMBEDDED", provider="test", confidence=-0.1)

        # Invalid: above 1
        with pytest.raises(ValidationError):
            LyricsSource(kind="EMBEDDED", provider="test", confidence=1.1)


class TestLyricsQuality:
    """Test LyricsQuality model."""

    def test_default_quality(self):
        """Quality with default values."""
        quality = LyricsQuality()

        assert quality.coverage_pct == 0.0
        assert quality.monotonicity_violations == 0
        assert quality.overlap_violations == 0
        assert quality.out_of_bounds_violations == 0
        assert quality.large_gaps_count == 0
        assert quality.avg_word_duration_ms is None
        assert quality.min_word_duration_ms is None

    def test_quality_with_metrics(self):
        """Quality with computed metrics."""
        quality = LyricsQuality(
            coverage_pct=0.85,
            monotonicity_violations=0,
            overlap_violations=0,
            out_of_bounds_violations=0,
            large_gaps_count=2,
            avg_word_duration_ms=350.5,
            min_word_duration_ms=50.0,
        )

        assert quality.coverage_pct == 0.85
        assert quality.large_gaps_count == 2
        assert quality.avg_word_duration_ms == 350.5

    def test_quality_ranges(self):
        """Quality metrics have valid ranges."""
        # Coverage must be 0-1
        with pytest.raises(ValidationError):
            LyricsQuality(coverage_pct=-0.1)
        with pytest.raises(ValidationError):
            LyricsQuality(coverage_pct=1.1)

        # Violations must be non-negative
        with pytest.raises(ValidationError):
            LyricsQuality(monotonicity_violations=-1)


class TestLyricsBundle:
    """Test LyricsBundle model."""

    def test_minimal_bundle(self):
        """Bundle with minimal fields."""
        bundle = LyricsBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
        )

        assert bundle.schema_version == "3.0.0"
        assert bundle.stage_status == StageStatus.OK
        assert bundle.text is None
        assert bundle.phrases == []
        assert bundle.words == []

    def test_bundle_with_plain_lyrics(self):
        """Bundle with plain text only."""
        bundle = LyricsBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            text="Verse 1\nHello world\nHow are you",
            source=LyricsSource(
                kind="LOOKUP_PLAIN",
                provider="genius",
                confidence=0.75,
            ),
        )

        assert bundle.text is not None
        assert "Hello world" in bundle.text
        assert bundle.source is not None
        assert bundle.source.kind == "LOOKUP_PLAIN"

    def test_bundle_with_synced_lyrics(self):
        """Bundle with word/phrase timing."""
        bundle = LyricsBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            text="Hello world",
            phrases=[
                LyricPhrase(
                    text="Hello world",
                    start_ms=1000,
                    end_ms=2000,
                ),
            ],
            words=[
                LyricWord(text="Hello", start_ms=1000, end_ms=1500),
                LyricWord(text="world", start_ms=1600, end_ms=2000),
            ],
            source=LyricsSource(
                kind="LOOKUP_SYNCED",
                provider="lrclib",
                confidence=0.85,
            ),
            quality=LyricsQuality(
                coverage_pct=0.90,
                avg_word_duration_ms=400.0,
            ),
        )

        assert len(bundle.phrases) == 1
        assert len(bundle.words) == 2
        assert bundle.quality is not None
        assert bundle.quality.coverage_pct == 0.90

    def test_bundle_skipped_status(self):
        """Bundle with SKIPPED status."""
        bundle = LyricsBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.SKIPPED,
        )

        assert bundle.stage_status == StageStatus.SKIPPED
        assert bundle.text is None

    def test_bundle_failed_status(self):
        """Bundle with FAILED status and warnings."""
        bundle = LyricsBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.FAILED,
            warnings=["Extraction failed", "No providers available"],
        )

        assert bundle.stage_status == StageStatus.FAILED
        assert len(bundle.warnings) == 2

    def test_bundle_with_provenance(self):
        """Bundle with provenance tracking."""
        bundle = LyricsBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            provenance={
                "extracted_at": "2026-01-28T12:00:00Z",
                "pipeline_version": "3.0.0",
                "providers_tried": ["lrclib", "genius"],
            },
        )

        assert "pipeline_version" in bundle.provenance
        assert bundle.provenance["pipeline_version"] == "3.0.0"

    def test_bundle_forbids_extra_fields(self):
        """Bundle forbids extra fields."""
        with pytest.raises(ValidationError):
            LyricsBundle(  # type: ignore[call-arg]
                schema_version="3.0.0",
                stage_status=StageStatus.OK,
                extra_field="not_allowed",
            )
