"""Lyrics provider models (Phase 4).

Models for lyrics API queries and responses.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LyricsQuery(BaseModel):
    """Query parameters for lyrics lookup.

    Args:
        artist: Artist name
        title: Song title
        album: Album name
        duration_ms: Song duration in milliseconds
        ids: External IDs (musicbrainz, spotify, etc.)
    """

    model_config = ConfigDict(extra="forbid")

    artist: str | None = Field(default=None, description="Artist name")
    title: str | None = Field(default=None, description="Song title")
    album: str | None = Field(default=None, description="Album name")
    duration_ms: int | None = Field(default=None, ge=0, description="Song duration (milliseconds)")
    ids: dict[str, str] = Field(default_factory=dict, description="External IDs")


class LyricsCandidate(BaseModel):
    """Lyrics candidate from provider.

    Args:
        provider: Provider name (lrclib, genius, etc.)
        provider_id: Provider-specific ID
        kind: Lyrics kind (SYNCED or PLAIN)
        text: Full lyrics text
        lrc: LRC content (if SYNCED)
        confidence: Match confidence (0-1)
        attribution: Source attribution metadata
        warnings: Provider warnings
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(description="Provider name")
    provider_id: str | None = Field(default=None, description="Provider-specific ID")
    kind: str = Field(description="Lyrics kind (SYNCED or PLAIN)")
    text: str = Field(description="Full lyrics text")
    lrc: str | None = Field(default=None, description="LRC content (if SYNCED)")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Match confidence (0-1)")
    attribution: dict[str, Any] = Field(
        default_factory=dict, description="Source attribution metadata"
    )
    warnings: list[str] = Field(default_factory=list, description="Provider warnings")
