"""Filesystem-backed cache using core.io for all operations.

Provides atomic commit pattern (artifact → meta) for cache correctness.
"""

import asyncio
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from twinklr.core.io import AbsolutePath, FileSystem
from twinklr.core.io.utils import sanitize_path_component

from ..models import CacheKey, CacheMeta

T = TypeVar("T", bound=BaseModel)


class FSCache:
    """
    Async filesystem-backed cache using core.io for all operations.

    Layout:
        {root}/
          {step_id}/
            {step_version}/
              {input_fingerprint}/
                artifact.json
                meta.json (commit marker)
    """

    def __init__(
        self,
        fs: FileSystem,
        root: AbsolutePath,
    ) -> None:
        """
        Initialize filesystem cache.

        Args:
            fs: Async filesystem implementation
            root: Absolute path to cache root directory
        """
        self.fs = fs
        self.root = root

    async def initialize(self) -> None:
        """
        Initialize cache (ensure root exists).

        Call this once after construction in async context.
        """
        await self.fs.mkdirs(self.root, exist_ok=True)

    def _entry_dir(self, key: CacheKey) -> AbsolutePath:
        """Compute cache entry directory path (sync)."""
        step_id_safe = sanitize_path_component(key.step_id)
        version_safe = sanitize_path_component(key.step_version)

        return self.fs.join(
            self.root,
            step_id_safe,
            version_safe,
            key.input_fingerprint,
        )

    def _artifact_path(self, key: CacheKey) -> AbsolutePath:
        """Compute artifact.json path (sync)."""
        return self.fs.join(self._entry_dir(key), "artifact.json")

    def _meta_path(self, key: CacheKey) -> AbsolutePath:
        """Compute meta.json path - commit marker (sync)."""
        return self.fs.join(self._entry_dir(key), "meta.json")

    async def exists(self, key: CacheKey) -> bool:
        """Check if valid cache entry exists (async)."""
        artifact_path = self._artifact_path(key)
        meta_path = self._meta_path(key)

        # Both must exist for valid entry
        artifact_exists, meta_exists = await asyncio.gather(
            self.fs.exists(artifact_path),
            self.fs.exists(meta_path),
        )

        return artifact_exists and meta_exists

    async def load(self, key: CacheKey, model_cls: type[T]) -> T | None:
        """
        Load and validate cached artifact (async).

        Returns None on cache miss, corruption, or validation failure.
        """
        if not await self.exists(key):
            return None

        try:
            # Load meta and artifact concurrently
            meta_json, artifact_json = await asyncio.gather(
                self.fs.read_text(self._meta_path(key)),
                self.fs.read_text(self._artifact_path(key)),
            )

            # Validate meta
            meta = CacheMeta.model_validate_json(meta_json)

            # Verify meta matches key
            if (
                meta.step_id != key.step_id
                or meta.step_version != key.step_version
                or meta.input_fingerprint != key.input_fingerprint
            ):
                # Meta mismatch → treat as miss
                return None

            # Validate artifact
            artifact = model_cls.model_validate_json(artifact_json)

            return artifact

        except (FileNotFoundError, ValidationError, ValueError):
            # Any error → cache miss
            return None

    async def store(
        self,
        key: CacheKey,
        artifact: BaseModel,
        compute_ms: float | None = None,
    ) -> None:
        """
        Store artifact with atomic commit pattern (async).

        Writes artifact.json first, then meta.json (commit marker).
        """
        entry_dir = self._entry_dir(key)
        await self.fs.mkdirs(entry_dir, exist_ok=True)

        # Serialize artifact
        artifact_json = artifact.model_dump_json(indent=2)
        artifact_bytes = len(artifact_json.encode("utf-8"))

        # Write artifact first (atomic)
        await self.fs.write_text(
            self._artifact_path(key),
            artifact_json,
        )

        # Build metadata
        artifact_schema_version = getattr(artifact, "schema_version", None)

        meta = CacheMeta(
            step_id=key.step_id,
            step_version=key.step_version,
            input_fingerprint=key.input_fingerprint,
            created_at=time.time(),
            artifact_model=f"{artifact.__class__.__module__}.{artifact.__class__.__name__}",
            artifact_schema_version=artifact_schema_version,
            compute_ms=compute_ms,
            artifact_bytes=artifact_bytes,
        )

        # Write meta last (commit marker, atomic)
        await self.fs.write_text(
            self._meta_path(key),
            meta.model_dump_json(indent=2),
        )

    async def invalidate(self, key: CacheKey) -> None:
        """Invalidate cache entry by removing directory (async)."""
        entry_dir = self._entry_dir(key)
        if await self.fs.exists(entry_dir):
            await self.fs.rmdir(entry_dir, recursive=True)


class FSCacheSync:
    """
    Synchronous wrapper around FSCache.

    Uses asyncio.run() to execute async operations in blocking mode.
    """

    def __init__(
        self,
        fs: FileSystem,
        root: AbsolutePath,
    ) -> None:
        """
        Initialize sync cache wrapper.

        Args:
            fs: Async filesystem implementation
            root: Absolute path to cache root directory
        """
        self._async_cache = FSCache(fs, root)
        # Initialize synchronously
        asyncio.run(self._async_cache.initialize())

    def exists(self, key: CacheKey) -> bool:
        """Check if entry exists (blocking)."""
        return asyncio.run(self._async_cache.exists(key))

    def load(self, key: CacheKey, model_cls: type[T]) -> T | None:
        """Load artifact (blocking)."""
        return asyncio.run(self._async_cache.load(key, model_cls))

    def store(
        self,
        key: CacheKey,
        artifact: BaseModel,
        compute_ms: float | None = None,
    ) -> None:
        """Store artifact (blocking)."""
        asyncio.run(self._async_cache.store(key, artifact, compute_ms))

    def invalidate(self, key: CacheKey) -> None:
        """Invalidate entry (blocking)."""
        asyncio.run(self._async_cache.invalidate(key))
