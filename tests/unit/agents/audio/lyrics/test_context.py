"""Unit tests for Lyrics agent context shaping."""

import pytest

from twinklr.core.agents.audio.lyrics.context import shape_lyrics_context
from twinklr.core.audio.models import (
    LyricPhrase,
    LyricsBundle,
    LyricsQuality,
    LyricsSource,
    LyricWord,
    SongBundle,
    SongTiming,
)


class TestShapeLyricsContext:
    """Test shape_lyrics_context function."""

    def test_shape_context_no_lyrics(self, minimal_bundle_no_lyrics):
        """Test shaping context when lyrics are None."""
        context = shape_lyrics_context(minimal_bundle_no_lyrics)

        assert context == {"has_lyrics": False, "reason": "No lyrics available"}

    def test_shape_context_no_lyrics_text(self, minimal_bundle_no_lyrics_text):
        """Test shaping context when lyrics.text is None."""
        context = shape_lyrics_context(minimal_bundle_no_lyrics_text)

        assert context == {"has_lyrics": False, "reason": "No lyrics available"}

    def test_shape_context_with_lyrics(self, full_bundle_with_lyrics):
        """Test shaping context with full lyrics."""
        context = shape_lyrics_context(full_bundle_with_lyrics)

        assert context["has_lyrics"] is True
        assert context["text"] == "Jingle bells jingle bells\nJingle all the way"
        assert len(context["words"]) == 8
        assert len(context["phrases"]) == 2
        assert len(context["sections"]) == 2
        assert context["duration_ms"] == 180000

        # Check word structure
        assert context["words"][0] == {"text": "Jingle", "start_ms": 1000, "end_ms": 1500}

        # Check phrase structure
        assert context["phrases"][0] == {
            "text": "Jingle bells jingle bells",
            "start_ms": 1000,
            "end_ms": 5000,
        }

        # Check section structure
        assert context["sections"][0] == {
            "section_id": "verse_0",
            "name": "verse",
            "start_ms": 0,
            "end_ms": 60000,
        }

        # Check quality metrics
        assert context["quality"]["coverage_pct"] == 0.8
        assert context["quality"]["source_confidence"] == 0.95

    def test_shape_context_without_quality_metrics(self, bundle_no_quality):
        """Test shaping context when quality metrics are missing."""
        context = shape_lyrics_context(bundle_no_quality)

        assert context["has_lyrics"] is True
        assert context["quality"]["coverage_pct"] == 0.0
        assert context["quality"]["source_confidence"] == 0.0

    def test_shape_context_without_sections(self, bundle_no_sections):
        """Test shaping context when structure sections are missing."""
        context = shape_lyrics_context(bundle_no_sections)

        assert context["has_lyrics"] is True
        assert context["sections"] == []

    def test_shape_context_empty_words_and_phrases(self, bundle_empty_words):
        """Test shaping context with empty words and phrases lists."""
        context = shape_lyrics_context(bundle_empty_words)

        assert context["has_lyrics"] is True
        assert context["text"] == "Test lyrics"
        assert context["words"] == []
        assert context["phrases"] == []


# Fixtures


@pytest.fixture
def minimal_bundle_no_lyrics():
    """Bundle with no lyrics."""
    return SongBundle(
        schema_version="3.0",
        audio_path="/fake/path.mp3",
        recording_id="test-rec-1",
        timing=SongTiming(sr=44100, hop_length=512, duration_s=180.0, duration_ms=180000),
        lyrics=None,
        features={},
    )


@pytest.fixture
def minimal_bundle_no_lyrics_text():
    """Bundle with lyrics object but no text."""
    from twinklr.core.audio.models.enums import StageStatus

    return SongBundle(
        schema_version="3.0",
        audio_path="/fake/path.mp3",
        recording_id="test-rec-2",
        timing=SongTiming(sr=44100, hop_length=512, duration_s=180.0, duration_ms=180000),
        lyrics=LyricsBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            text=None,
            words=[],
            phrases=[],
            source=None,
            quality=None,
        ),
        features={},
    )


@pytest.fixture
def full_bundle_with_lyrics():
    """Bundle with full lyrics data."""
    from twinklr.core.audio.models.enums import StageStatus

    words = [
        LyricWord(text="Jingle", start_ms=1000, end_ms=1500),
        LyricWord(text="bells", start_ms=1500, end_ms=2000),
        LyricWord(text="jingle", start_ms=2000, end_ms=2500),
        LyricWord(text="bells", start_ms=2500, end_ms=3000),
        LyricWord(text="Jingle", start_ms=5000, end_ms=5500),
        LyricWord(text="all", start_ms=5500, end_ms=6000),
        LyricWord(text="the", start_ms=6000, end_ms=6500),
        LyricWord(text="way", start_ms=6500, end_ms=7000),
    ]

    phrases = [
        LyricPhrase(text="Jingle bells jingle bells", start_ms=1000, end_ms=5000),
        LyricPhrase(text="Jingle all the way", start_ms=5000, end_ms=10000),
    ]

    source = LyricsSource(kind="WHISPERX_TRANSCRIBE", provider="whisperx", confidence=0.95)

    quality = LyricsQuality(
        coverage_pct=0.8,
        monotonicity_violations=0,
        overlap_violations=0,
        out_of_bounds_violations=0,
        large_gaps_count=0,
    )

    lyrics = LyricsBundle(
        schema_version="3.0.0",
        stage_status=StageStatus.OK,
        text="Jingle bells jingle bells\nJingle all the way",
        words=words,
        phrases=phrases,
        source=source,
        quality=quality,
    )

    features = {
        "structure": {
            "sections": [
                {"label": "verse", "start_s": 0.0, "end_s": 60.0},
                {"label": "chorus", "start_s": 60.0, "end_s": 120.0},
            ]
        }
    }

    return SongBundle(
        schema_version="3.0",
        audio_path="/fake/path.mp3",
        recording_id="test-rec-3",
        timing=SongTiming(sr=44100, hop_length=512, duration_s=180.0, duration_ms=180000),
        lyrics=lyrics,
        features=features,
    )


@pytest.fixture
def bundle_no_quality():
    """Bundle with lyrics but no quality metrics."""
    from twinklr.core.audio.models.enums import StageStatus

    lyrics = LyricsBundle(
        schema_version="3.0.0",
        stage_status=StageStatus.OK,
        text="Test lyrics",
        words=[LyricWord(text="Test", start_ms=1000, end_ms=2000)],
        phrases=[LyricPhrase(text="Test lyrics", start_ms=1000, end_ms=3000)],
        source=None,
        quality=None,
    )

    features = {
        "structure": {
            "sections": [
                {"label": "verse", "start_s": 0.0, "end_s": 60.0},
            ]
        }
    }

    return SongBundle(
        schema_version="3.0",
        audio_path="/fake/path.mp3",
        recording_id="test-rec-4",
        timing=SongTiming(sr=44100, hop_length=512, duration_s=180.0, duration_ms=180000),
        lyrics=lyrics,
        features=features,
    )


@pytest.fixture
def bundle_no_sections():
    """Bundle with lyrics but no structure sections."""
    from twinklr.core.audio.models.enums import StageStatus

    lyrics = LyricsBundle(
        schema_version="3.0.0",
        stage_status=StageStatus.OK,
        text="Test lyrics",
        words=[LyricWord(text="Test", start_ms=1000, end_ms=2000)],
        phrases=[LyricPhrase(text="Test lyrics", start_ms=1000, end_ms=3000)],
        source=LyricsSource(kind="LOOKUP_PLAIN", provider="test", confidence=0.9),
        quality=LyricsQuality(
            coverage_pct=1.0,
            monotonicity_violations=0,
            overlap_violations=0,
            out_of_bounds_violations=0,
            large_gaps_count=0,
        ),
    )

    return SongBundle(
        schema_version="3.0",
        audio_path="/fake/path.mp3",
        recording_id="test-rec-5",
        timing=SongTiming(sr=44100, hop_length=512, duration_s=180.0, duration_ms=180000),
        lyrics=lyrics,
        features={},
    )


@pytest.fixture
def bundle_empty_words():
    """Bundle with lyrics text but empty words/phrases."""
    from twinklr.core.audio.models.enums import StageStatus

    lyrics = LyricsBundle(
        schema_version="3.0.0",
        stage_status=StageStatus.OK,
        text="Test lyrics",
        words=[],
        phrases=[],
        source=LyricsSource(kind="LOOKUP_PLAIN", provider="test", confidence=0.9),
        quality=LyricsQuality(
            coverage_pct=1.0,
            monotonicity_violations=0,
            overlap_violations=0,
            out_of_bounds_violations=0,
            large_gaps_count=0,
        ),
    )

    features = {
        "structure": {
            "sections": [
                {"label": "verse", "start_s": 0.0, "end_s": 60.0},
            ]
        }
    }

    return SongBundle(
        schema_version="3.0",
        audio_path="/fake/path.mp3",
        recording_id="test-rec-6",
        timing=SongTiming(sr=44100, hop_length=512, duration_s=180.0, duration_ms=180000),
        lyrics=lyrics,
        features=features,
    )
