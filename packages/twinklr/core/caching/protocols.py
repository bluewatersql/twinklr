"""Protocols for cache backends.

Defines async-first Cache protocol and sync convenience wrapper protocol.
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

from .models import CacheKey

T = TypeVar("T", bound=BaseModel)


class Cache(Protocol):
    """
    Protocol for cache backends (async-first).

    All implementations must support:
    - Atomic writes (artifact → meta commit pattern)
    - Pydantic model validation on load
    - Miss-on-error semantics (corruption → cache miss)

    Async methods are primary; sync wrappers available via CacheSync.
    """

    async def exists(self, key: CacheKey, ttl_seconds: float | None = None) -> bool:
        """
        Check if valid cache entry exists for key (async).

        Args:
            key: Cache key
            ttl_seconds: Optional TTL in seconds. If provided, entry is considered
                        expired if created_at + ttl_seconds < now()

        Returns:
            True if both artifact and meta exist, are valid, and not expired
        """
        ...

    async def load(
        self, key: CacheKey, model_cls: type[T], ttl_seconds: float | None = None
    ) -> T | None:
        """
        Load and validate cached artifact (async).

        Args:
            key: Cache key
            model_cls: Pydantic model class for validation
            ttl_seconds: Optional TTL in seconds. If provided, entry is considered
                        expired if created_at + ttl_seconds < now()

        Returns:
            Validated artifact model, or None on miss/error/expiration
        """
        ...

    async def store(
        self,
        key: CacheKey,
        artifact: BaseModel,
        compute_ms: float | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        """
        Store artifact with atomic commit (async).

        Writes artifact.json first, then meta.json (commit marker).

        Args:
            key: Cache key
            artifact: Pydantic model to cache
            compute_ms: Optional computation duration
            ttl_seconds: Optional TTL in seconds (stored in meta for reference,
                        enforced during load/exists)

        Raises:
            IOError: On write failure
        """
        ...

    async def invalidate(self, key: CacheKey) -> None:
        """
        Invalidate (delete) cache entry (async).

        Args:
            key: Cache key
        """
        ...


class CacheSync(Protocol):
    """
    Synchronous convenience wrapper protocol.

    Provides blocking versions of Cache operations for
    simple scripts, tests, and non-async contexts.
    """

    def exists(self, key: CacheKey, ttl_seconds: float | None = None) -> bool:
        """Check if entry exists and not expired (blocking)."""
        ...

    def load(self, key: CacheKey, model_cls: type[T], ttl_seconds: float | None = None) -> T | None:
        """Load artifact, None if missing/expired (blocking)."""
        ...

    def store(
        self,
        key: CacheKey,
        artifact: BaseModel,
        compute_ms: float | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        """Store artifact (blocking)."""
        ...

    def invalidate(self, key: CacheKey) -> None:
        """Invalidate entry (blocking)."""
        ...
