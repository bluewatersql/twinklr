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


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FeatureStoreError(Exception):
    """Base exception for all feature store errors."""


class FeatureStoreSchemaError(FeatureStoreError):
    """Raised when the store schema is missing, invalid, or incompatible."""


class FeatureStoreConnectionError(FeatureStoreError):
    """Raised when the store cannot open or maintain its backend connection."""
