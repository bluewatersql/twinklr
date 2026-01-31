"""Lyrics models for Audio Analyzer v3.0 (Phase 4).

Models for lyrics resolution pipeline:
- LyricWord: Word-level timing
- LyricPhrase: Line/phrase-level timing
- LyricsSource: Source attribution
- LyricsQuality: Quality metrics
- LyricsBundle: Complete lyrics container
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.audio.models.enums import StageStatus


# Source kind constants
class LyricsSourceKind:
    """Lyrics source kind constants."""

    EMBEDDED = "EMBEDDED"
    LOOKUP_SYNCED = "LOOKUP_SYNCED"
    LOOKUP_PLAIN = "LOOKUP_PLAIN"
    WHISPERX_ALIGN = "WHISPERX_ALIGN"
    WHISPERX_TRANSCRIBE = "WHISPERX_TRANSCRIBE"


class LyricWord(BaseModel):
    """Word-level lyrics with timing.

    Args:
        text: Word text
        start_ms: Word start time in milliseconds
        end_ms: Word end time in milliseconds
        speaker: Optional speaker ID (for diarization)
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="Word text")
    start_ms: int = Field(ge=0, description="Word start time (milliseconds)")
    end_ms: int = Field(ge=0, description="Word end time (milliseconds)")
    speaker: str | None = Field(default=None, description="Speaker ID (optional)")


class LyricPhrase(BaseModel):
    """Phrase/line-level lyrics with timing.

    Args:
        text: Phrase text (full line)
        start_ms: Phrase start time in milliseconds
        end_ms: Phrase end time in milliseconds
        words: Optional word-level timing within phrase
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(description="Phrase text (full line)")
    start_ms: int = Field(ge=0, description="Phrase start time (milliseconds)")
    end_ms: int = Field(ge=0, description="Phrase end time (milliseconds)")
    words: list[LyricWord] = Field(default_factory=list, description="Word-level timing")


class LyricsSource(BaseModel):
    """Source attribution for lyrics.

    Args:
        kind: Source kind (EMBEDDED, LOOKUP_SYNCED, LOOKUP_PLAIN, WHISPERX_ALIGN, WHISPERX_TRANSCRIBE)
        provider: Provider name (lrc_file, sylt, uslt, lrclib, genius, whisperx)
        provider_id: Optional provider-specific ID
        confidence: Source confidence (0-1)
    """

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="Source kind")
    provider: str = Field(description="Provider name")
    provider_id: str | None = Field(default=None, description="Provider-specific ID")
    confidence: float = Field(ge=0.0, le=1.0, description="Source confidence (0-1)")


class LyricsQuality(BaseModel):
    """Lyrics quality metrics.

    Computed from word-level timing to assess lyrics quality.

    Coverage is calculated as the percentage of song duration with vocals,
    computed by merging word intervals with small gaps (250ms tolerance).
    This represents "time with vocal phrases" rather than just summing
    individual word durations.

    Args:
        coverage_pct: Percentage of song duration with vocals (0-1, merged intervals)
        monotonicity_violations: Count of timestamps going backward
        overlap_violations: Count of overlapping words
        out_of_bounds_violations: Count of timestamps outside song bounds
        large_gaps_count: Count of large gaps between words
        avg_word_duration_ms: Average word duration in milliseconds
        min_word_duration_ms: Minimum word duration in milliseconds
    """

    model_config = ConfigDict(extra="forbid")

    coverage_pct: float = Field(default=0.0, ge=0.0, le=1.0, description="Coverage percentage")
    monotonicity_violations: int = Field(default=0, ge=0, description="Backward timestamps")
    overlap_violations: int = Field(default=0, ge=0, description="Overlapping words")
    out_of_bounds_violations: int = Field(default=0, ge=0, description="Out-of-bounds timestamps")
    large_gaps_count: int = Field(default=0, ge=0, description="Large gaps between words")
    avg_word_duration_ms: float | None = Field(
        default=None, description="Average word duration (ms)"
    )
    min_word_duration_ms: float | None = Field(
        default=None, description="Minimum word duration (ms)"
    )


class LyricsBundle(BaseModel):
    """Lyrics bundle for Audio Analyzer v3.0.

    Contains resolved lyrics with optional timing, quality metrics, and provenance.

    Args:
        schema_version: Schema version (3.0.0)
        stage_status: Processing status (OK/SKIPPED/FAILED)
        text: Full lyrics text (plain)
        phrases: Phrase-level timing (lines)
        words: Word-level timing
        source: Source attribution
        quality: Quality metrics
        warnings: Processing warnings
        provenance: Processing metadata
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(description="Schema version")
    stage_status: StageStatus = Field(description="Processing status")

    # Lyrics content
    text: str | None = Field(default=None, description="Full lyrics text")
    phrases: list[LyricPhrase] = Field(default_factory=list, description="Phrase-level timing")
    words: list[LyricWord] = Field(default_factory=list, description="Word-level timing")

    # Metadata
    source: LyricsSource | None = Field(default=None, description="Source attribution")
    quality: LyricsQuality | None = Field(default=None, description="Quality metrics")

    # Processing info
    warnings: list[str] = Field(default_factory=list, description="Processing warnings")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Processing metadata")
