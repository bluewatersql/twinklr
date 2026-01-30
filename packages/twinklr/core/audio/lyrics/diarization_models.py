"""Diarization models for speaker attribution (Phase 5).

Models for speaker diarization:
- DiarizationConfig: Configuration for diarization service
- SpeakerSegment: Speaker segment with timing
- DiarizationResult: Complete diarization result

Example:
    >>> config = DiarizationConfig(min_speakers=2, max_speakers=4)
    >>> result = DiarizationResult(
    ...     segments=[
    ...         SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=5000, confidence=0.95)
    ...     ],
    ...     num_speakers=1
    ... )
"""

from pydantic import BaseModel, ConfigDict, Field


class DiarizationConfig(BaseModel):
    """Configuration for diarization service.

    Attributes:
        min_speakers: Minimum number of speakers (None = auto-detect)
        max_speakers: Maximum number of speakers (None = auto-detect)
        suggest_threshold: Confidence threshold for suggesting diarization
        auto_enable_threshold: Confidence threshold for auto-enabling diarization

    Example:
        >>> config = DiarizationConfig(min_speakers=2, max_speakers=4)
        >>> config.suggest_threshold
        0.85
    """

    model_config = ConfigDict(extra="forbid")

    min_speakers: int | None = Field(
        default=None, gt=0, description="Minimum speakers (None = auto)"
    )
    max_speakers: int | None = Field(
        default=None, gt=0, description="Maximum speakers (None = auto)"
    )
    suggest_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Confidence threshold for suggestion"
    )
    auto_enable_threshold: float = Field(
        default=0.90, ge=0.0, le=1.0, description="Confidence threshold for auto-enable"
    )


class SpeakerSegment(BaseModel):
    """Speaker segment with timing.

    Represents a continuous segment where one speaker is active.

    Attributes:
        speaker: Speaker ID (e.g., "SPEAKER_01", "SPEAKER_02")
        start_ms: Segment start time in milliseconds
        end_ms: Segment end time in milliseconds
        confidence: Speaker attribution confidence (0-1)

    Example:
        >>> segment = SpeakerSegment(
        ...     speaker="SPEAKER_01",
        ...     start_ms=0,
        ...     end_ms=5000,
        ...     confidence=0.95
        ... )
        >>> segment.speaker
        'SPEAKER_01'
    """

    model_config = ConfigDict(extra="forbid")

    speaker: str = Field(description="Speaker ID")
    start_ms: int = Field(ge=0, description="Segment start time (milliseconds)")
    end_ms: int = Field(ge=0, description="Segment end time (milliseconds)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Attribution confidence")


class DiarizationResult(BaseModel):
    """Result from diarization service.

    Contains speaker segments and metadata.

    Attributes:
        segments: List of speaker segments
        num_speakers: Number of unique speakers detected
        metadata: Additional metadata (model info, warnings, etc.)

    Example:
        >>> result = DiarizationResult(
        ...     segments=[
        ...         SpeakerSegment(speaker="SPEAKER_01", start_ms=0, end_ms=5000, confidence=0.95),
        ...         SpeakerSegment(speaker="SPEAKER_02", start_ms=5000, end_ms=10000, confidence=0.92)
        ...     ],
        ...     num_speakers=2,
        ...     metadata={"model": "pyannote"}
        ... )
        >>> result.num_speakers
        2
    """

    model_config = ConfigDict(extra="forbid")

    segments: list[SpeakerSegment]
    num_speakers: int = Field(ge=0, description="Number of unique speakers")
    metadata: dict[str, object] = Field(default_factory=dict)
