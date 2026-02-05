"""Filesystem-backed cache using core.io for all operations.

Provides atomic commit pattern (artifact → meta) for cache correctness.
"""

import asyncio
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from twinklr.core.caching.models import CacheKey, CacheMeta
from twinklr.core.io import AbsolutePath, FileSystem
from twinklr.core.io.utils import sanitize_path_component

T = TypeVar("T", bound=BaseModel)


class FSCache:
    """
    Async filesystem-backed cache using core.io for all operations.

    The cache lazily initializes on first use (thread-safe).
    """

    def __init__(
        self, fs: FileSystem, root: AbsolutePath, ttl_seconds: float | None = None
    ) -> None:
        """
        Initialize filesystem cache.

        Args:
            fs: Async filesystem implementation
            root: Absolute path to cache root directory
        """
        self.fs = fs
        self.root = root
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds

    async def initialize(self) -> None:
        """
        Initialize cache (ensure root exists).

        This is called automatically on first use, but can be called explicitly.
        Safe to call multiple times.
        """
        async with self._init_lock:
            if not self._initialized:
                await self.fs.mkdirs(self.root, exist_ok=True)
                self._initialized = True

    def _entry_dir(self, key: CacheKey) -> AbsolutePath:
        """Compute cache entry directory path (sync)."""

        step_id_safe = sanitize_path_component(key.step_id)

        return self.fs.join(
            self.root,
            step_id_safe,
            key.input_fingerprint,
        )

    def _artifact_path(self, key: CacheKey) -> AbsolutePath:
        """Compute artifact.json path (sync)."""
        return self.fs.join(self._entry_dir(key), "artifact.json")

    def _meta_path(self, key: CacheKey) -> AbsolutePath:
        """Compute meta.json path - commit marker (sync)."""
        return self.fs.join(self._entry_dir(key), "meta.json")

    async def exists(self, key: CacheKey, ttl_seconds: float | None = None) -> bool:
        """
        Check if valid cache entry exists and is not expired (async).

        Args:
            key: Cache key
            ttl_seconds: Optional TTL in seconds. If provided, entry is expired if
                        created_at + ttl_seconds < now()

        Returns:
            True if entry exists, is valid, and not expired
        """
        await self.initialize()  # Lazy initialization
        artifact_path = self._artifact_path(key)
        meta_path = self._meta_path(key)

        # Both must exist for valid entry
        artifact_exists, meta_exists = await asyncio.gather(
            self.fs.exists(artifact_path),
            self.fs.exists(meta_path),
        )

        if not (artifact_exists and meta_exists):
            return False

        # If TTL specified, check expiration
        ttl_seconds = ttl_seconds or self._ttl_seconds
        if ttl_seconds is not None:
            try:
                meta_json = await self.fs.read_text(meta_path)
                meta = CacheMeta.model_validate_json(meta_json)

                # Check if expired
                now = time.time()
                if now > (meta.created_at + ttl_seconds):
                    return False  # Expired

            except (FileNotFoundError, ValidationError, ValueError):
                return False  # Corrupted meta → treat as miss

        return True

    async def load(
        self, key: CacheKey, model_cls: type[T], ttl_seconds: float | None = None
    ) -> T | None:
        """
        Load and validate cached artifact (async).

        Args:
            key: Cache key
            model_cls: Pydantic model class for validation
            ttl_seconds: Optional TTL in seconds. If provided, entry is expired if
                        created_at + ttl_seconds < now()

        Returns:
            Validated artifact model, or None on miss/corruption/validation failure/expiration
        """
        await self.initialize()  # Lazy initialization
        # Check existence and expiration in one call
        if not await self.exists(key, ttl_seconds):
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

            # Double-check expiration (in case exists() check raced with expiration)
            ttl_seconds = ttl_seconds or self._ttl_seconds
            if ttl_seconds is not None:
                now = time.time()
                if now > (meta.created_at + ttl_seconds):
                    return None  # Expired

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
        ttl_seconds: float | None = None,
    ) -> None:
        """
        Store artifact with atomic commit pattern (async).

        Writes artifact.json first, then meta.json (commit marker).

        Args:
            key: Cache key
            artifact: Pydantic model to cache
            compute_ms: Optional computation duration
            ttl_seconds: Optional TTL in seconds (stored in meta for reference)
        """
        await self.initialize()  # Lazy initialization
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
        ttl_seconds = ttl_seconds or self._ttl_seconds

        meta = CacheMeta(
            domain=key.domain,
            session_id=key.session_id,
            step_id=key.step_id,
            step_version=key.step_version,
            input_fingerprint=key.input_fingerprint,
            created_at=time.time(),
            artifact_model=f"{artifact.__class__.__module__}.{artifact.__class__.__name__}",
            artifact_schema_version=artifact_schema_version,
            compute_ms=compute_ms,
            artifact_bytes=artifact_bytes,
            ttl_seconds=ttl_seconds,
        )

        # Write meta last (commit marker, atomic)
        await self.fs.write_text(
            self._meta_path(key),
            meta.model_dump_json(indent=2),
        )

    async def invalidate(self, key: CacheKey) -> None:
        """Invalidate cache entry by removing directory (async)."""
        await self.initialize()  # Lazy initialization
        entry_dir = self._entry_dir(key)
        if await self.fs.exists(entry_dir):
            await self.fs.rmdir(entry_dir, recursive=True)


class FSCacheSync:
    """
    Synchronous wrapper around FSCache.

    Uses asyncio.run() to execute async operations in blocking mode.
    Cache initializes lazily on first use.
    """

    def __init__(
        self,
        fs: FileSystem,
        root: AbsolutePath,
        ttl_seconds: float | None = None,
    ) -> None:
        """
        Initialize sync cache wrapper.

        Args:
            fs: Async filesystem implementation
            root: Absolute path to cache root directory
        """
        self._async_cache = FSCache(fs, root)

    def exists(self, key: CacheKey, ttl_seconds: float | None = None) -> bool:
        """Check if entry exists and not expired (blocking)."""
        return asyncio.run(self._async_cache.exists(key, ttl_seconds))

    def load(self, key: CacheKey, model_cls: type[T], ttl_seconds: float | None = None) -> T | None:
        """Load artifact, None if missing/expired (blocking)."""
        return asyncio.run(self._async_cache.load(key, model_cls, ttl_seconds))

    def store(
        self,
        key: CacheKey,
        artifact: BaseModel,
        compute_ms: float | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        """Store artifact (blocking)."""
        asyncio.run(self._async_cache.store(key, artifact, compute_ms, ttl_seconds))

    def invalidate(self, key: CacheKey) -> None:
        """Invalidate entry (blocking)."""
        asyncio.run(self._async_cache.invalidate(key))

    def initialize(self) -> None:
        """Initialize cache (blocking)."""
        asyncio.run(self._async_cache.initialize())
