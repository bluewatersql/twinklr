"""Feature store configuration and shared models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class FeatureStoreConfig(BaseModel):
    """Configuration for a feature store backend.

    Args:
        backend: Storage backend to use. ``"null"`` is a no-op in-memory stub;
            ``"sqlite"`` persists to a local SQLite file.
        db_path: Path to the SQLite database file. Required when ``backend="sqlite"``.
        schema_dir: Directory containing SQL schema migration files.
        reference_data_dir: Directory containing reference JSON data to bootstrap.
        auto_bootstrap: Whether to run schema bootstrap on first connect.
        enable_wal: Enable SQLite WAL journal mode for better concurrency.
        schema_version: Expected schema version string for the store.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: Literal["sqlite", "null"] = "null"
    db_path: Path | None = None
    schema_dir: Path | None = None
    reference_data_dir: Path | None = None
    auto_bootstrap: bool = True
    enable_wal: bool = True
    schema_version: str = "1.0.0"


class CorpusStats(BaseModel):
    """Aggregate statistics for a feature store corpus.

    All counts default to zero so callers can safely read any field
    even on an empty store.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    phrase_count: int = 0
    template_count: int = 0
    stack_count: int = 0
    transition_count: int = 0
    recipe_count: int = 0
    taxonomy_count: int = 0
    propensity_count: int = 0
    profile_count: int = 0


class ProfileRecord(BaseModel):
    """Profile of a profiled sequence and its FE processing status.

    Args:
        profile_id: Composite primary key ``{package_id}/{sequence_file_id}``.
        package_id: Vendor package identifier.
        sequence_file_id: Sequence file identifier within the package.
        profile_path: Filesystem path to the profile JSON.
        zip_sha256: SHA-256 hash of the source ZIP archive.
        sequence_sha256: SHA-256 hash of the sequence content.
        song: Song title from profile metadata.
        artist: Artist name from profile metadata.
        duration_ms: Song duration in milliseconds.
        effect_total_events: Total effect event count in the sequence.
        schema_version: Profile schema version string.
        fe_status: Feature-engineering status (``pending``, ``complete``, ``error``).
        fe_error: Error message when ``fe_status`` is ``error``.
        profiled_at: ISO timestamp when the profile was created.
        fe_completed_at: ISO timestamp when FE completed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str
    package_id: str
    sequence_file_id: str
    profile_path: str
    zip_sha256: str | None = None
    sequence_sha256: str | None = None
    song: str | None = None
    artist: str | None = None
    duration_ms: int | None = None
    effect_total_events: int | None = None
    schema_version: str = ""
    fe_status: str = "pending"
    fe_error: str | None = None
    profiled_at: str | None = None
    fe_completed_at: str | None = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FeatureStoreError(Exception):
    """Base exception for all feature store errors."""


class FeatureStoreSchemaError(FeatureStoreError):
    """Raised when the store schema is missing, invalid, or incompatible."""


class FeatureStoreConnectionError(FeatureStoreError):
    """Raised when the store cannot open or maintain its backend connection."""
