"""Feature engineering bundle contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AudioStatus(str, Enum):
    """Audio discovery status for a sequence."""

    FOUND_IN_PACK = "found_in_pack"
    FOUND_IN_MUSIC_DIR = "found_in_music_dir"
    LOW_CONFIDENCE = "low_confidence"
    MISSING = "missing"


class AudioCandidateOrigin(str, Enum):
    """Source where an audio candidate was found."""

    PACK = "pack"
    MUSIC_REPO = "music_repo"


class AudioCandidate(BaseModel):
    """Ranked audio candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    origin: AudioCandidateOrigin
    score: float
    reason: str


class AudioDiscoveryResult(BaseModel):
    """Audio discovery + optional analyzer execution result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    audio_path: str | None
    audio_status: AudioStatus
    match_confidence: float | None = Field(default=None, ge=0.0, le=5.0)
    match_reason: str | None = None
    cache_hit: bool | None = None
    compute_ms: int | None = Field(default=None, ge=0)
    analyzer_version: str | None = None
    analyzer_error: str | None = None
    candidate_rankings: tuple[AudioCandidate, ...] = ()


class FeatureBundle(BaseModel):
    """Canonical per-sequence feature-engineering output bundle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    source_profile_path: str
    package_id: str
    sequence_file_id: str
    sequence_sha256: str
    song: str
    artist: str
    audio: AudioDiscoveryResult
