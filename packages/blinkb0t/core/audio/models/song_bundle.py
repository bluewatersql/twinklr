"""SongBundle model - aggregate container for all audio analysis results (v3.0)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SongTiming(BaseModel):
    """Basic timing information for audio file."""

    model_config = ConfigDict(extra="forbid")

    sr: int = Field(gt=0, description="Sample rate (Hz)")
    hop_length: int = Field(gt=0, description="Hop length for frame processing")
    duration_s: float = Field(gt=0.0, description="Duration in seconds")
    duration_ms: int = Field(gt=0, description="Duration in milliseconds")


class SongBundle(BaseModel):
    """Aggregate bundle containing all audio analysis results.

    Schema version: 3.0 (Major.Minor for structural changes)

    This bundle contains:
    - features: Complete v2.3 features dict (backward compatible)
    - timing: Basic timing information
    - metadata: Optional metadata enrichment (MetadataBundle)
    - lyrics: Optional lyrics resolution (LyricsBundle)
    - phonemes: Optional phoneme/viseme generation (PhonemeBundle)

    When all enhancement features are disabled, only features and timing
    are populated (features-only mode).
    """

    model_config = ConfigDict(extra="forbid")

    # Schema and identification
    schema_version: str = Field(description="Bundle schema version (e.g., '3.0')")
    audio_path: str = Field(description="Path to audio file")
    recording_id: str = Field(description="Unique recording identifier")

    # Core analysis (always present)
    features: dict[str, Any] = Field(
        description="Complete v2.3 features dict (backward compatible)"
    )
    timing: SongTiming = Field(description="Basic timing information")

    # Enhancement bundles (optional, require feature flags)
    metadata: Any | None = Field(default=None, description="Metadata enrichment (MetadataBundle)")
    lyrics: Any | None = Field(default=None, description="Lyrics resolution (LyricsBundle)")
    phonemes: Any | None = Field(
        default=None, description="Phoneme/viseme generation (PhonemeBundle)"
    )

    # Metadata
    warnings: list[str] = Field(default_factory=list, description="Processing warnings")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Processing provenance")
