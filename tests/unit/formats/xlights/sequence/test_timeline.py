"""Tests for timeline track builder (XSQ timing export)."""

from __future__ import annotations

import pytest

from twinklr.core.audio.models.enums import StageStatus
from twinklr.core.audio.models.lyrics import LyricPhrase, LyricsBundle, LyricWord
from twinklr.core.audio.models.phonemes import Phoneme, PhonemeBundle, PhonemeSource
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


@pytest.fixture
def simple_beat_grid() -> BeatGrid:
    """BeatGrid with 4 bars at 120 BPM (500ms per beat, 2000ms per bar)."""
    bpm = 120.0
    beats_per_bar = 4
    ms_per_beat = 60_000.0 / bpm  # 500ms
    ms_per_bar = ms_per_beat * beats_per_bar  # 2000ms
    total_bars = 4
    total_beats = total_bars * beats_per_bar  # 16

    return BeatGrid(
        bar_boundaries=[i * ms_per_bar for i in range(total_bars + 1)],
        beat_boundaries=[i * ms_per_beat for i in range(total_beats + 1)],
        eighth_boundaries=[i * ms_per_beat / 2 for i in range(total_beats * 2 + 1)],
        sixteenth_boundaries=[i * ms_per_beat / 4 for i in range(total_beats * 4 + 1)],
        tempo_bpm=bpm,
        beats_per_bar=beats_per_bar,
        duration_ms=total_bars * ms_per_bar,
    )


@pytest.fixture
def sample_lyrics() -> LyricsBundle:
    """LyricsBundle with two phrases."""
    return LyricsBundle(
        schema_version="3.0.0",
        stage_status=StageStatus.OK,
        text="hello world goodbye moon",
        phrases=[
            LyricPhrase(
                text="hello world",
                start_ms=500,
                end_ms=1500,
                words=[
                    LyricWord(text="hello", start_ms=500, end_ms=900),
                    LyricWord(text="world", start_ms=1000, end_ms=1500),
                ],
            ),
            LyricPhrase(
                text="goodbye moon",
                start_ms=3000,
                end_ms=4500,
                words=[
                    LyricWord(text="goodbye", start_ms=3000, end_ms=3700),
                    LyricWord(text="moon", start_ms=3800, end_ms=4500),
                ],
            ),
        ],
        words=[
            LyricWord(text="hello", start_ms=500, end_ms=900),
            LyricWord(text="world", start_ms=1000, end_ms=1500),
            LyricWord(text="goodbye", start_ms=3000, end_ms=3700),
            LyricWord(text="moon", start_ms=3800, end_ms=4500),
        ],
    )


@pytest.fixture
def sample_phonemes() -> PhonemeBundle:
    """PhonemeBundle with a few phonemes."""
    return PhonemeBundle(
        phonemes=[
            Phoneme(text="HH", start_ms=500, end_ms=550, phoneme_type="CONSONANT"),
            Phoneme(text="AH", start_ms=550, end_ms=700, phoneme_type="VOWEL"),
            Phoneme(text="L", start_ms=700, end_ms=800, phoneme_type="CONSONANT"),
            Phoneme(text="OW", start_ms=800, end_ms=900, phoneme_type="VOWEL"),
        ],
        visemes=[],
        source=PhonemeSource.G2P,
        confidence=0.85,
        oov_rate=0.0,
        coverage_pct=1.0,
        burst_merge_count=0,
    )


class TestBuildTimelineTracks:
    """Tests for build_timeline_tracks function."""

    def test_beats_track_from_beat_grid(self, simple_beat_grid: BeatGrid) -> None:
        """Beats track creates a marker at each beat boundary."""
        from twinklr.core.formats.xlights.sequence.timeline import (
            TimelineTracksConfig,
            build_timeline_tracks,
        )

        config = TimelineTracksConfig(beats=True, bars=False, sections=False, lyrics=False)
        tracks = build_timeline_tracks(config=config, beat_grid=simple_beat_grid)

        beat_tracks = [t for t in tracks if t.name == "Twinklr Beats"]
        assert len(beat_tracks) == 1

        beat_track = beat_tracks[0]
        # 4 bars x 4 beats = 16 beats + 1 boundary = 17 boundaries
        # but last boundary is at duration end, typically included
        assert len(beat_track.markers) == len(simple_beat_grid.beat_boundaries)

        # First beat at 0ms
        assert beat_track.markers[0].time_ms == 0
        # Second beat at 500ms (120 BPM)
        assert beat_track.markers[1].time_ms == 500

    def test_bars_track_from_beat_grid(self, simple_beat_grid: BeatGrid) -> None:
        """Bars track creates a marker at each bar boundary."""
        from twinklr.core.formats.xlights.sequence.timeline import (
            TimelineTracksConfig,
            build_timeline_tracks,
        )

        config = TimelineTracksConfig(beats=False, bars=True, sections=False, lyrics=False)
        tracks = build_timeline_tracks(config=config, beat_grid=simple_beat_grid)

        bar_tracks = [t for t in tracks if t.name == "Twinklr Bars"]
        assert len(bar_tracks) == 1

        bar_track = bar_tracks[0]
        assert len(bar_track.markers) == len(simple_beat_grid.bar_boundaries)

        # Bar 1 at 0ms, Bar 2 at 2000ms, etc.
        assert bar_track.markers[0].time_ms == 0
        assert bar_track.markers[0].name == "Bar 1"
        assert bar_track.markers[1].time_ms == 2000
        assert bar_track.markers[1].name == "Bar 2"

    def test_lyrics_track_from_bundle(self, sample_lyrics: LyricsBundle) -> None:
        """Lyrics track creates word-level markers with text labels."""
        from twinklr.core.formats.xlights.sequence.timeline import (
            TimelineTracksConfig,
            build_timeline_tracks,
        )

        config = TimelineTracksConfig(beats=False, bars=False, sections=False, lyrics=True)
        tracks = build_timeline_tracks(config=config, lyrics_bundle=sample_lyrics)

        lyric_tracks = [t for t in tracks if t.name == "Twinklr Lyrics"]
        assert len(lyric_tracks) == 1

        lyric_track = lyric_tracks[0]
        assert len(lyric_track.markers) == 4  # 4 words

        assert lyric_track.markers[0].name == "hello"
        assert lyric_track.markers[0].time_ms == 500
        assert lyric_track.markers[0].end_time_ms == 900

    def test_phonemes_track_from_bundle(self, sample_phonemes: PhonemeBundle) -> None:
        """Phonemes track creates markers for each phoneme."""
        from twinklr.core.formats.xlights.sequence.timeline import (
            TimelineTracksConfig,
            build_timeline_tracks,
        )

        config = TimelineTracksConfig(
            beats=False, bars=False, sections=False, lyrics=False, phonemes=True
        )
        tracks = build_timeline_tracks(config=config, phoneme_bundle=sample_phonemes)

        phoneme_tracks = [t for t in tracks if t.name == "Twinklr Phonemes"]
        assert len(phoneme_tracks) == 1

        phoneme_track = phoneme_tracks[0]
        assert len(phoneme_track.markers) == 4

        assert phoneme_track.markers[0].name == "HH"
        assert phoneme_track.markers[0].time_ms == 500
        assert phoneme_track.markers[0].end_time_ms == 550

    def test_config_disables_tracks(self, simple_beat_grid: BeatGrid) -> None:
        """Disabled tracks are not generated."""
        from twinklr.core.formats.xlights.sequence.timeline import (
            TimelineTracksConfig,
            build_timeline_tracks,
        )

        config = TimelineTracksConfig(
            beats=False, bars=False, sections=False, lyrics=False, phonemes=False
        )
        tracks = build_timeline_tracks(config=config, beat_grid=simple_beat_grid)
        assert tracks == []

    def test_missing_data_skips_track(self) -> None:
        """Tracks are skipped when source data is None."""
        from twinklr.core.formats.xlights.sequence.timeline import (
            TimelineTracksConfig,
            build_timeline_tracks,
        )

        config = TimelineTracksConfig(
            beats=True, bars=True, lyrics=True, phonemes=True, sections=True
        )
        # No data provided at all
        tracks = build_timeline_tracks(config=config)
        assert tracks == []

    def test_sections_track(self) -> None:
        """Sections track creates markers from section boundaries."""
        from twinklr.core.formats.xlights.sequence.timeline import (
            TimelineTracksConfig,
            build_timeline_tracks,
        )

        config = TimelineTracksConfig(beats=False, bars=False, sections=True, lyrics=False)
        sections = [
            ("intro", 0, 2000),
            ("verse_1", 2000, 6000),
            ("chorus_1", 6000, 8000),
        ]
        tracks = build_timeline_tracks(config=config, sections=sections)

        section_tracks = [t for t in tracks if t.name == "Twinklr Sections"]
        assert len(section_tracks) == 1

        section_track = section_tracks[0]
        assert len(section_track.markers) == 3
        assert section_track.markers[0].name == "intro"
        assert section_track.markers[0].time_ms == 0
        assert section_track.markers[0].end_time_ms == 2000
        assert section_track.markers[1].name == "verse_1"

    def test_multiple_tracks_combined(
        self,
        simple_beat_grid: BeatGrid,
        sample_lyrics: LyricsBundle,
    ) -> None:
        """Multiple enabled tracks are returned together."""
        from twinklr.core.formats.xlights.sequence.timeline import (
            TimelineTracksConfig,
            build_timeline_tracks,
        )

        config = TimelineTracksConfig(beats=True, bars=True, lyrics=True)
        tracks = build_timeline_tracks(
            config=config,
            beat_grid=simple_beat_grid,
            lyrics_bundle=sample_lyrics,
        )

        track_names = {t.name for t in tracks}
        assert "Twinklr Beats" in track_names
        assert "Twinklr Bars" in track_names
        assert "Twinklr Lyrics" in track_names


class TestTimelineTracksConfig:
    """Tests for TimelineTracksConfig defaults."""

    def test_default_config(self) -> None:
        """Default config enables beats, bars, sections, lyrics but not phonemes."""
        from twinklr.core.formats.xlights.sequence.timeline import TimelineTracksConfig

        config = TimelineTracksConfig()
        assert config.beats is True
        assert config.bars is True
        assert config.sections is True
        assert config.lyrics is True
        assert config.phonemes is False
