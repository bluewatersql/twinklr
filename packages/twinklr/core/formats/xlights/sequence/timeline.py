"""Timeline track builder for XSQ timing export.

Converts audio analysis data (beats, bars, lyrics, phonemes, sections)
into XSQ timing tracks that appear as named timing layers in xLights.

These timing tracks provide visual reference markers when editing
sequences in xLights — beats, bars, lyrics, and phonemes are the
primary aids for reviewing and fine-tuning generated choreography.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.audio.models.lyrics import LyricsBundle
from twinklr.core.audio.models.phonemes import PhonemeBundle
from twinklr.core.formats.xlights.sequence.models.xsq import TimeMarker, TimingTrack
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

logger = logging.getLogger(__name__)


class TimelineTracksConfig(BaseModel):
    """Configuration for which timeline tracks to export to XSQ.

    Controls which timing reference layers are written to the output
    sequence file. Each track appears as a named timing layer in xLights.

    Attributes:
        beats: Include beat markers (from BeatGrid)
        bars: Include bar/downbeat markers (from BeatGrid)
        sections: Include section boundary markers
        lyrics: Include word-level lyric markers (from LyricsBundle)
        phonemes: Include phoneme markers (from PhonemeBundle)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    beats: bool = Field(default=True, description="Include beat markers")
    bars: bool = Field(default=True, description="Include bar/downbeat markers")
    sections: bool = Field(default=True, description="Include section boundary markers")
    lyrics: bool = Field(default=True, description="Include word-level lyric markers")
    phonemes: bool = Field(default=False, description="Include phoneme markers")


def build_timeline_tracks(
    config: TimelineTracksConfig,
    *,
    beat_grid: BeatGrid | None = None,
    lyrics_bundle: LyricsBundle | None = None,
    phoneme_bundle: PhonemeBundle | None = None,
    sections: list[tuple[str, int, int]] | None = None,
) -> list[TimingTrack]:
    """Build XSQ timing tracks from audio analysis data.

    Each enabled track is built only if the corresponding data source
    is provided. Missing data is silently skipped (no error).

    Args:
        config: Controls which tracks to generate.
        beat_grid: Musical timing grid (for beats and bars tracks).
        lyrics_bundle: Word-level lyrics with timing (for lyrics track).
        phoneme_bundle: Phoneme-level data (for phonemes track).
        sections: Section boundaries as (name, start_ms, end_ms) tuples.

    Returns:
        List of TimingTrack objects ready to add to an XSequence.
    """
    tracks: list[TimingTrack] = []

    if config.beats and beat_grid is not None:
        tracks.append(_build_beats_track(beat_grid))

    if config.bars and beat_grid is not None:
        tracks.append(_build_bars_track(beat_grid))

    if config.sections and sections is not None:
        tracks.append(_build_sections_track(sections))

    if config.lyrics and lyrics_bundle is not None and lyrics_bundle.words:
        tracks.append(_build_lyrics_track(lyrics_bundle))

    if config.phonemes and phoneme_bundle is not None and phoneme_bundle.phonemes:
        tracks.append(_build_phonemes_track(phoneme_bundle))

    logger.debug("Built %d timeline tracks: %s", len(tracks), [t.name for t in tracks])
    return tracks


def _build_beats_track(beat_grid: BeatGrid) -> TimingTrack:
    """Build timing track with a marker at each beat position.

    Args:
        beat_grid: Musical timing grid with beat boundaries.

    Returns:
        TimingTrack named "Twinklr Beats".
    """
    markers: list[TimeMarker] = []
    beats_per_bar = beat_grid.beats_per_bar

    for i, time_ms in enumerate(beat_grid.beat_boundaries):
        beat_in_bar = (i % beats_per_bar) + 1
        bar_num = (i // beats_per_bar) + 1
        markers.append(
            TimeMarker(
                name=f"{bar_num}.{beat_in_bar}",
                time_ms=int(time_ms),
            )
        )

    return TimingTrack(name="Twinklr Beats", markers=markers)


def _build_bars_track(beat_grid: BeatGrid) -> TimingTrack:
    """Build timing track with a marker at each bar (downbeat) position.

    Args:
        beat_grid: Musical timing grid with bar boundaries.

    Returns:
        TimingTrack named "Twinklr Bars".
    """
    markers: list[TimeMarker] = []

    for i, time_ms in enumerate(beat_grid.bar_boundaries):
        bar_num = i + 1
        markers.append(
            TimeMarker(
                name=f"Bar {bar_num}",
                time_ms=int(time_ms),
            )
        )

    return TimingTrack(name="Twinklr Bars", markers=markers)


def _build_sections_track(sections: list[tuple[str, int, int]]) -> TimingTrack:
    """Build timing track with section boundary markers.

    Args:
        sections: List of (section_name, start_ms, end_ms) tuples.

    Returns:
        TimingTrack named "Twinklr Sections".
    """
    markers: list[TimeMarker] = []

    for name, start_ms, end_ms in sections:
        markers.append(
            TimeMarker(
                name=name,
                time_ms=start_ms,
                end_time_ms=end_ms,
            )
        )

    return TimingTrack(name="Twinklr Sections", markers=markers)


def _build_lyrics_track(lyrics_bundle: LyricsBundle) -> TimingTrack:
    """Build timing track with word-level lyric markers.

    Uses word-level timing for maximum granularity in xLights.

    Args:
        lyrics_bundle: Lyrics with word-level timing.

    Returns:
        TimingTrack named "Twinklr Lyrics".
    """
    markers: list[TimeMarker] = []

    for word in lyrics_bundle.words:
        markers.append(
            TimeMarker(
                name=word.text,
                time_ms=word.start_ms,
                end_time_ms=word.end_ms,
            )
        )

    return TimingTrack(name="Twinklr Lyrics", markers=markers)


def _build_phonemes_track(phoneme_bundle: PhonemeBundle) -> TimingTrack:
    """Build timing track with phoneme markers.

    Uses ARPAbet phoneme labels at phoneme-level timing.

    Args:
        phoneme_bundle: Phoneme data with per-phoneme timing.

    Returns:
        TimingTrack named "Twinklr Phonemes".
    """
    markers: list[TimeMarker] = []

    for phoneme in phoneme_bundle.phonemes:
        markers.append(
            TimeMarker(
                name=phoneme.text,
                time_ms=phoneme.start_ms,
                end_time_ms=phoneme.end_ms,
            )
        )

    return TimingTrack(name="Twinklr Phonemes", markers=markers)
