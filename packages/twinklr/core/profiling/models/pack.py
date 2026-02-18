"""Package ingest models for profiling."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from twinklr.core.profiling.models.enums import FileKind


class FileEntry(BaseModel):
    """Leaf file metadata discovered during package ingestion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_id: str
    filename: str
    ext: str
    size: int
    sha256: str
    kind: FileKind
    original_ext: str | None = None


class PackageManifest(BaseModel):
    """Manifest of files and key IDs in a profiled package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_id: str
    zip_sha256: str
    source_extensions: frozenset[str]
    files: tuple[FileEntry, ...]
    sequence_file_id: str | None
    rgb_effects_file_id: str | None
