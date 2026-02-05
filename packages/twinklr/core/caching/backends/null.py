"""No-op cache for development/testing.

Always reports cache miss, discards all stores.
"""

import asyncio
from typing import TypeVar

from pydantic import BaseModel

from twinklr.core.caching.models import CacheKey

T = TypeVar("T", bound=BaseModel)


class NullCache:
    """
    No-op async cache for development/testing.

    Always reports cache miss, discards all stores.
    TTL parameter in init is ignored (no-op cache).
    """

    def __init__(self, ttl_seconds: float | None = None) -> None:
        """Initialize null cache. TTL is ignored."""
        pass

    async def exists(self, key: CacheKey) -> bool:
        """Always returns False (async)."""
        return False

    async def load(self, key: CacheKey, model_cls: type[T]) -> T | None:
        """Always returns None (async)."""
        return None

    async def store(
        self,
        key: CacheKey,
        artifact: BaseModel,
        compute_ms: float | None = None,
    ) -> None:
        """Discard (async)."""
        pass

    async def invalidate(self, key: CacheKey) -> None:
        """No-op (async)."""
        pass

    async def initialize(self) -> None:
        """No-op (async)."""
        pass


class NullCacheSync:
    """
    Synchronous wrapper around NullCache.
    TTL parameter in init is ignored (no-op cache).
    """

    def __init__(self, ttl_seconds: float | None = None) -> None:
        """Initialize null cache. TTL is ignored."""
        self._async_cache = NullCache()

    def exists(self, key: CacheKey) -> bool:
        """Always returns False (blocking)."""
        return asyncio.run(self._async_cache.exists(key))

    def load(self, key: CacheKey, model_cls: type[T]) -> T | None:
        """Always returns None (blocking)."""
        return asyncio.run(self._async_cache.load(key, model_cls))

    def store(
        self,
        key: CacheKey,
        artifact: BaseModel,
        compute_ms: float | None = None,
    ) -> None:
        """Discard (blocking)."""
        asyncio.run(self._async_cache.store(key, artifact, compute_ms))

    def invalidate(self, key: CacheKey) -> None:
        """No-op (blocking)."""
        asyncio.run(self._async_cache.invalidate(key))

    def initialize(self) -> None:
        """No-op (blocking)."""
        asyncio.run(self._async_cache.initialize())
