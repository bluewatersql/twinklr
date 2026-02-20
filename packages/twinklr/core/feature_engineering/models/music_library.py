"""Music library index models for metadata-based audio matching."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MusicLibraryEntry(BaseModel):
    """Single audio file with extracted metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration_s: float = Field(default=0.0, ge=0.0)


class MusicLibraryIndex(BaseModel):
    """Index of all audio files with their embedded metadata.

    Built by scanning audio directories and reading ID3/Vorbis/etc. tags
    via ``mutagen``.  Persisted as JSON for reuse across pipeline runs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1"
    source_dirs: tuple[str, ...] = ()
    entries: tuple[MusicLibraryEntry, ...] = ()
