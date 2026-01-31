"""Unit tests for Lyrics agent validation."""

import pytest

from twinklr.core.agents.audio.lyrics.models import (
    KeyPhrase,
    LyricContextModel,
    Severity,
    SilentSection,
    StoryBeat,
)
from twinklr.core.agents.audio.lyrics.validation import validate_lyrics
from twinklr.core.audio.models import LyricsBundle, SongBundle, SongTiming
from twinklr.core.audio.models.enums import StageStatus


class TestValidateLyrics:
    """Test validate_lyrics function."""

    def test_valid_minimal_model(self, minimal_song_bundle):
        """Test validation of minimal valid model."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=False,
            vocal_coverage_pct=0.0,
        )

        issues = validate_lyrics(model, minimal_song_bundle)
        assert len(issues) == 0

    def test_valid_full_model(self, full_song_bundle):
        """Test validation of full valid model."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=True,
            themes=["celebration", "joy"],
            mood_arc="cheerful → exuberant",
            genre_markers=["Christmas", "traditional"],
            has_narrative=True,
            characters=["Santa", "Narrator"],
            story_beats=[
                StoryBeat(
                    section_id="verse_1",
                    timestamp_range=(1000, 10000),
                    beat_type="setup",
                    description="Santa prepares for journey",
                    visual_opportunity="Build anticipation",
                ),
            ],
            key_phrases=[
                KeyPhrase(
                    text=f"Phrase {i}",
                    timestamp_ms=1000 * i,
                    section_id="verse",
                    visual_hint=f"Visual hint {i}",
                )
                for i in range(5)
            ],
            recommended_visual_themes=["Warm colors", "Motion", "Brightness"],
            lyric_density="MED",
            vocal_coverage_pct=0.8,
            silent_sections=[
                SilentSection(start_ms=50000, end_ms=60000, duration_ms=10000, section_id="bridge")
            ],
        )

        issues = validate_lyrics(model, full_song_bundle)
        assert len(issues) == 0

    def test_key_phrase_timestamp_out_of_bounds(self, minimal_song_bundle):
        """Test key phrase timestamp exceeds song duration."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=True,
            themes=["test", "themes"],
            vocal_coverage_pct=0.5,
            key_phrases=[
                KeyPhrase(
                    text="Valid phrase",
                    timestamp_ms=1000,
                    section_id="verse",
                    visual_hint="Visual 1",
                ),
                KeyPhrase(
                    text="Out of bounds phrase",
                    timestamp_ms=200000,  # Exceeds 180000ms duration
                    section_id="verse",
                    visual_hint="Visual 2",
                ),
                KeyPhrase(
                    text="Another phrase",
                    timestamp_ms=2000,
                    section_id="verse",
                    visual_hint="Visual 3",
                ),
                KeyPhrase(
                    text="Phrase 4",
                    timestamp_ms=3000,
                    section_id="verse",
                    visual_hint="Visual 4",
                ),
                KeyPhrase(
                    text="Phrase 5",
                    timestamp_ms=4000,
                    section_id="verse",
                    visual_hint="Visual 5",
                ),
            ],
            recommended_visual_themes=["theme1", "theme2", "theme3"],
        )

        issues = validate_lyrics(model, minimal_song_bundle)

        assert len(issues) == 1
        assert issues[0].code == "TIMESTAMP_OUT_OF_BOUNDS"
        assert issues[0].severity == Severity.ERROR
        assert "200000ms" in issues[0].message

    def test_story_beat_timestamp_out_of_bounds(self, minimal_song_bundle):
        """Test story beat end time exceeds song duration."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=True,
            themes=["test", "themes"],
            has_narrative=True,
            characters=["Character"],
            story_beats=[
                StoryBeat(
                    section_id="verse",
                    timestamp_range=(1000, 200000),  # Exceeds 180000ms
                    beat_type="setup",
                    description="Test description",
                    visual_opportunity="Test visual",
                ),
            ],
            key_phrases=[
                KeyPhrase(
                    text=f"Phrase {i}",
                    timestamp_ms=1000 * i,
                    section_id="verse",
                    visual_hint=f"Visual {i}",
                )
                for i in range(5)
            ],
            recommended_visual_themes=["theme1", "theme2", "theme3"],
            vocal_coverage_pct=0.5,
        )

        issues = validate_lyrics(model, minimal_song_bundle)

        assert len(issues) == 1
        assert issues[0].code == "TIMESTAMP_OUT_OF_BOUNDS"
        assert issues[0].severity == Severity.ERROR

    def test_overlapping_story_beats(self, minimal_song_bundle):
        """Test overlapping story beats trigger warning."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=True,
            themes=["test", "themes"],
            has_narrative=True,
            characters=["Character"],
            story_beats=[
                StoryBeat(
                    section_id="verse_1",
                    timestamp_range=(1000, 10000),
                    beat_type="setup",
                    description="First beat description",
                    visual_opportunity="Visual opportunity 1",
                ),
                StoryBeat(
                    section_id="verse_2",
                    timestamp_range=(8000, 15000),  # Overlaps previous beat
                    beat_type="conflict",
                    description="Second beat description",
                    visual_opportunity="Visual opportunity 2",
                ),
            ],
            key_phrases=[
                KeyPhrase(
                    text=f"Phrase {i}",
                    timestamp_ms=1000 * i,
                    section_id="verse",
                    visual_hint=f"Visual {i}",
                )
                for i in range(5)
            ],
            recommended_visual_themes=["theme1", "theme2", "theme3"],
            vocal_coverage_pct=0.5,
        )

        issues = validate_lyrics(model, minimal_song_bundle)

        assert len(issues) == 1
        assert issues[0].code == "OVERLAPPING_STORY_BEATS"
        assert issues[0].severity == Severity.WARN

    def test_overlapping_silent_sections(self, minimal_song_bundle):
        """Test overlapping silent sections trigger warning."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=True,
            themes=["test", "themes"],
            vocal_coverage_pct=0.5,
            silent_sections=[
                SilentSection(start_ms=10000, end_ms=20000, duration_ms=10000),
                SilentSection(start_ms=18000, end_ms=25000, duration_ms=7000),  # Overlaps
            ],
            key_phrases=[
                KeyPhrase(
                    text=f"Phrase {i}",
                    timestamp_ms=1000 * i,
                    section_id="verse",
                    visual_hint=f"Visual {i}",
                )
                for i in range(5)
            ],
            recommended_visual_themes=["theme1", "theme2", "theme3"],
        )

        issues = validate_lyrics(model, minimal_song_bundle)

        assert len(issues) == 1
        assert issues[0].code == "OVERLAPPING_SILENT_SECTIONS"
        assert issues[0].severity == Severity.WARN

    def test_has_narrative_missing_story_beats(self, minimal_song_bundle):
        """Test has_narrative=True requires story_beats."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=True,
            themes=["test", "themes"],
            has_narrative=True,
            characters=["Character"],
            story_beats=None,  # Missing!
            key_phrases=[
                KeyPhrase(
                    text=f"Phrase {i}",
                    timestamp_ms=1000 * i,
                    section_id="verse",
                    visual_hint=f"Visual {i}",
                )
                for i in range(5)
            ],
            recommended_visual_themes=["theme1", "theme2", "theme3"],
            vocal_coverage_pct=0.5,
        )

        issues = validate_lyrics(model, minimal_song_bundle)

        assert len(issues) == 1
        assert issues[0].code == "NARRATIVE_MISSING_STORY_BEATS"
        assert issues[0].severity == Severity.ERROR

    def test_has_narrative_missing_characters(self, minimal_song_bundle):
        """Test has_narrative=True requires characters (warning)."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=True,
            themes=["test", "themes"],
            has_narrative=True,
            characters=None,  # Missing!
            story_beats=[
                StoryBeat(
                    section_id="verse",
                    timestamp_range=(1000, 10000),
                    beat_type="setup",
                    description="Test beat description here",
                    visual_opportunity="Test visual opportunity",
                ),
            ],
            key_phrases=[
                KeyPhrase(
                    text=f"Phrase {i}",
                    timestamp_ms=1000 * i,
                    section_id="verse",
                    visual_hint=f"Visual {i}",
                )
                for i in range(5)
            ],
            recommended_visual_themes=["theme1", "theme2", "theme3"],
            vocal_coverage_pct=0.5,
        )

        issues = validate_lyrics(model, minimal_song_bundle)

        assert len(issues) == 1
        assert issues[0].code == "NARRATIVE_MISSING_CHARACTERS"
        assert issues[0].severity == Severity.WARN

    def test_no_lyrics_but_key_phrases(self, minimal_song_bundle):
        """Test has_lyrics=False but key_phrases populated."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=False,
            vocal_coverage_pct=0.0,
            key_phrases=[
                KeyPhrase(
                    text=f"Phrase {i}",
                    timestamp_ms=1000 * i,
                    section_id="verse",
                    visual_hint=f"Visual {i}",
                )
                for i in range(5)
            ],
        )

        issues = validate_lyrics(model, minimal_song_bundle)

        assert len(issues) == 1
        assert issues[0].code == "NO_LYRICS_BUT_KEY_PHRASES"
        assert issues[0].severity == Severity.ERROR

    def test_has_lyrics_missing_themes(self, minimal_song_bundle):
        """Test has_lyrics=True but themes is empty (warning)."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=True,
            themes=[],  # Empty!
            vocal_coverage_pct=0.5,
            key_phrases=[
                KeyPhrase(
                    text=f"Phrase {i}",
                    timestamp_ms=1000 * i,
                    section_id="verse",
                    visual_hint=f"Visual {i}",
                )
                for i in range(5)
            ],
            recommended_visual_themes=["theme1", "theme2", "theme3"],
        )

        issues = validate_lyrics(model, minimal_song_bundle)

        assert len(issues) == 1
        assert issues[0].code == "MISSING_THEMES"
        assert issues[0].severity == Severity.WARN

    def test_has_lyrics_missing_key_phrases(self, minimal_song_bundle):
        """Test has_lyrics=True but key_phrases is empty (warning)."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=True,
            themes=["test", "themes"],
            vocal_coverage_pct=0.5,
            key_phrases=[],  # Empty!
            recommended_visual_themes=["theme1", "theme2", "theme3"],
        )

        issues = validate_lyrics(model, minimal_song_bundle)

        assert len(issues) == 1
        assert issues[0].code == "MISSING_KEY_PHRASES"
        assert issues[0].severity == Severity.WARN

    def test_has_lyrics_missing_visual_themes(self, minimal_song_bundle):
        """Test has_lyrics=True but recommended_visual_themes is empty (warning)."""
        model = LyricContextModel(
            run_id="test-123",
            has_lyrics=True,
            themes=["test", "themes"],
            vocal_coverage_pct=0.5,
            key_phrases=[
                KeyPhrase(
                    text=f"Phrase {i}",
                    timestamp_ms=1000 * i,
                    section_id="verse",
                    visual_hint=f"Visual {i}",
                )
                for i in range(5)
            ],
            recommended_visual_themes=[],  # Empty!
        )

        issues = validate_lyrics(model, minimal_song_bundle)

        assert len(issues) == 1
        assert issues[0].code == "MISSING_VISUAL_THEMES"
        assert issues[0].severity == Severity.WARN


# Fixtures


@pytest.fixture
def minimal_song_bundle():
    """Minimal song bundle for testing."""
    return SongBundle(
        schema_version="3.0",
        audio_path="/fake/path.mp3",
        recording_id="test-rec",
        timing=SongTiming(sr=44100, hop_length=512, duration_s=180.0, duration_ms=180000),
        lyrics=None,
        features={},
    )


@pytest.fixture
def full_song_bundle():
    """Full song bundle with lyrics."""
    from twinklr.core.audio.models import LyricPhrase, LyricsQuality, LyricsSource, LyricWord

    lyrics = LyricsBundle(
        schema_version="3.0.0",
        stage_status=StageStatus.OK,
        text="Test lyrics",
        words=[LyricWord(text="Test", start_ms=1000, end_ms=2000)],
        phrases=[LyricPhrase(text="Test lyrics", start_ms=1000, end_ms=3000)],
        source=LyricsSource(kind="WHISPERX_TRANSCRIBE", provider="whisperx", confidence=0.95),
        quality=LyricsQuality(
            coverage_pct=0.8,
            monotonicity_violations=0,
            overlap_violations=0,
            out_of_bounds_violations=0,
            large_gaps_count=0,
        ),
    )

    return SongBundle(
        schema_version="3.0",
        audio_path="/fake/path.mp3",
        recording_id="test-rec",
        timing=SongTiming(sr=44100, hop_length=512, duration_s=180.0, duration_ms=180000),
        lyrics=lyrics,
        features={},
    )
