"""Metadata models for audio enhancement (v3.0)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.audio.models.enums import StageStatus


class FingerprintInfo(BaseModel):
    """Audio fingerprint information.

    Contains both the basic audio fingerprint (hash of file path + params)
    and optional chromaprint fingerprint for AcoustID lookups.
    """

    model_config = ConfigDict(extra="forbid")

    audio_fingerprint: str = Field(description="Basic audio fingerprint (file hash)")
    chromaprint_fingerprint: str | None = Field(
        default=None, description="Chromaprint fingerprint string (for AcoustID)"
    )
    chromaprint_duration_s: float | None = Field(
        default=None, gt=0, description="Duration from chromaprint (seconds)"
    )
    chromaprint_duration_bucket: float | None = Field(
        default=None, description="Bucketed duration for caching (round to 0.1s)"
    )


class ResolvedMBIDs(BaseModel):
    """MusicBrainz identifiers."""

    model_config = ConfigDict(extra="forbid")

    recording_mbid: str | None = Field(default=None, description="Recording MBID")
    release_mbid: str | None = Field(default=None, description="Release MBID")
    artist_mbids: list[str] = Field(default_factory=list, description="Artist MBIDs")
    work_mbid: str | None = Field(default=None, description="Work MBID (if applicable)")


class ResolvedMetadata(BaseModel):
    """Resolved metadata from providers with per-field confidence.

    This is the merged result from embedded metadata + provider candidates.
    """

    model_config = ConfigDict(extra="forbid")

    # Overall confidence
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence score")

    # Display strings
    title: str | None = Field(default=None, description="Song title")
    title_confidence: float = Field(description="Title confidence")
    artist: str | None = Field(default=None, description="Primary artist")
    artist_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Artist confidence"
    )
    album: str | None = Field(default=None, description="Album name")
    album_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Album confidence"
    )

    # Duration
    duration_ms: int | None = Field(default=None, gt=0, description="Duration in milliseconds")
    duration_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Duration confidence"
    )

    # Stable IDs
    mbids: ResolvedMBIDs = Field(default_factory=ResolvedMBIDs, description="MusicBrainz IDs")
    acoustid_id: str | None = Field(default=None, description="AcoustID identifier")
    isrc: str | None = Field(default=None, description="ISRC code")


class MetadataCandidate(BaseModel):
    """Metadata candidate from a provider."""

    model_config = ConfigDict(extra="forbid")

    # Provider info
    provider: str = Field(description="Provider name (e.g., 'acoustid', 'musicbrainz')")
    provider_id: str = Field(description="Provider-specific ID")

    # Score (computed by merge policy)
    score: float = Field(ge=0.0, le=1.0, description="Candidate score (0-1)")

    # Metadata fields
    duration_ms: int | None = Field(default=None, gt=0, description="Duration in milliseconds")
    title: str | None = Field(default=None, description="Song title")
    artist: str | None = Field(default=None, description="Primary artist")
    album: str | None = Field(default=None, description="Album name")

    # Stable IDs
    mbids: ResolvedMBIDs = Field(default_factory=ResolvedMBIDs, description="MusicBrainz IDs")
    acoustid_id: str | None = Field(default=None, description="AcoustID identifier")
    isrc: str | None = Field(default=None, description="ISRC code")

    # Raw provider response (for debugging/audit)
    raw: dict[str, Any] = Field(default_factory=dict, description="Raw provider response")


class EmbeddedMetadata(BaseModel):
    """Metadata extracted from embedded audio file tags.

    Uses mutagen for format-agnostic tag reading.
    Normalized to canonical field names.
    """

    model_config = ConfigDict(extra="forbid")

    # Basic metadata
    title: str | None = Field(default=None, description="Song title")
    artist: str | None = Field(default=None, description="Artist name")
    album: str | None = Field(default=None, description="Album name")
    album_artist: str | None = Field(default=None, description="Album artist")

    # Track/disc numbering
    track_number: int | None = Field(default=None, gt=0, description="Track number")
    track_total: int | None = Field(default=None, gt=0, description="Total tracks")
    disc_number: int | None = Field(default=None, gt=0, description="Disc number")
    disc_total: int | None = Field(default=None, gt=0, description="Total discs")

    # Date information
    date_raw: str | None = Field(default=None, description="Raw date string from tags")
    date_iso: str | None = Field(
        default=None, description="ISO date (YYYY or YYYY-MM or YYYY-MM-DD)"
    )
    year: int | None = Field(default=None, ge=1000, le=9999, description="Year")

    # Additional metadata
    genre: list[str] = Field(default_factory=list, description="Genre tags")
    comment: str | None = Field(default=None, description="Comment field")
    grouping: str | None = Field(default=None, description="Grouping/content group")
    compilation: bool | None = Field(default=None, description="Compilation album flag")

    # Embedded content flags
    lyrics_embedded_present: bool = Field(
        default=False, description="Lyrics present in tags (SYLT/USLT)"
    )

    # Artwork metadata (not the artwork itself)
    artwork_present: bool = Field(default=False, description="Artwork present in tags")
    artwork_mime: str | None = Field(default=None, description="Artwork MIME type")
    artwork_hash_sha256: str | None = Field(default=None, description="Artwork SHA256 hash")
    artwork_size_bytes: int | None = Field(default=None, ge=0, description="Artwork size in bytes")

    # Processing metadata
    warnings: list[str] = Field(default_factory=list, description="Extraction warnings")


class MetadataBundle(BaseModel):
    """Metadata bundle containing embedded and optional resolved metadata.

    Schema version: 3.0.0 (Major.Minor.Patch for sub-bundles)

    Phase 2: Only embedded metadata populated.
    Phase 3+: fingerprint, resolved, candidates added.
    """

    model_config = ConfigDict(extra="forbid")

    # Schema and status
    schema_version: str = Field(description="Sub-bundle schema version (e.g., '3.0.0')")
    stage_status: StageStatus = Field(description="Processing stage status")

    # Embedded metadata (Phase 2)
    embedded: EmbeddedMetadata = Field(description="Embedded tag metadata")

    # Network metadata (Phase 3+, optional)
    fingerprint: FingerprintInfo | None = Field(
        default=None, description="Fingerprint info - Phase 3+"
    )
    resolved: ResolvedMetadata | None = Field(
        default=None, description="Resolved merged metadata - Phase 3+"
    )
    candidates: list[MetadataCandidate] = Field(
        default_factory=list, description="Metadata candidates with scores - Phase 3+"
    )

    # Processing metadata
    provenance: dict[str, Any] = Field(default_factory=dict, description="Processing provenance")
    warnings: list[str] = Field(default_factory=list, description="Processing warnings")
