"""WhisperX configuration and result models.

This module defines Pydantic models for WhisperX service configuration
and result structures (align and transcribe operations).

Models:
    WhisperXConfig: Configuration for WhisperX operations
    WhisperXAlignResult: Result from align operation
    WhisperXTranscribeResult: Result from transcribe operation
"""

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.audio.models.lyrics import LyricWord


class WhisperXConfig(BaseModel):
    """Configuration for WhisperX transcription and alignment.

    Attributes:
        device: Compute device ("cpu", "cuda", "mps")
        model: WhisperX model size ("tiny", "base", "small", "medium", "large")
        batch_size: Batch size for processing (must be > 0)
        language: ISO language code for transcription (None = auto-detect)
        return_char_alignments: Whether to return character-level alignments

    Example:
        >>> config = WhisperXConfig(device="cuda", model="large")
        >>> config.batch_size
        16
    """

    model_config = ConfigDict(extra="forbid")

    device: str = "cpu"
    model: str = "base"
    batch_size: int = Field(default=16, gt=0)
    language: str | None = None
    return_char_alignments: bool = False


class WhisperXAlignResult(BaseModel):
    """Result from WhisperX align operation.

    Align takes existing lyrics text and aligns it to audio timing.

    Attributes:
        words: List of word-level timings
        mismatch_ratio: Token-level edit distance ratio (0.0-1.0)
                       >0.25 indicates significant mismatch
        metadata: Additional metadata (model info, warnings, etc.)

    Example:
        >>> result = WhisperXAlignResult(
        ...     words=[LyricWord(text="hello", start_ms=0, end_ms=500)],
        ...     mismatch_ratio=0.1,
        ...     metadata={"model": "base"}
        ... )
        >>> result.mismatch_ratio < 0.25  # Good alignment
        True
    """

    model_config = ConfigDict(extra="forbid")

    words: list[LyricWord]
    mismatch_ratio: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, object] = Field(default_factory=dict)


class WhisperXTranscribeResult(BaseModel):
    """Result from WhisperX transcribe operation.

    Transcribe generates lyrics from audio (no reference text needed).

    Attributes:
        text: Full transcribed text
        words: List of word-level timings
        metadata: Additional metadata (model info, language, etc.)

    Example:
        >>> result = WhisperXTranscribeResult(
        ...     text="hello world",
        ...     words=[
        ...         LyricWord(text="hello", start_ms=0, end_ms=500),
        ...         LyricWord(text="world", start_ms=500, end_ms=1000)
        ...     ],
        ...     metadata={"language": "en"}
        ... )
        >>> len(result.words)
        2
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    words: list[LyricWord]
    metadata: dict[str, object] = Field(default_factory=dict)
