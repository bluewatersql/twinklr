"""No-op cache for development/testing.

Always reports cache miss, discards all stores.
"""

import asyncio
from typing import TypeVar

from pydantic import BaseModel

from ..models import CacheKey

T = TypeVar("T", bound=BaseModel)


class NullCache:
    """
    No-op async cache for development/testing.

    Always reports cache miss, discards all stores.
    """

    async def exists(self, key: CacheKey, ttl_seconds: float | None = None) -> bool:
        """Always returns False (async)."""
        return False

    async def load(
        self, key: CacheKey, model_cls: type[T], ttl_seconds: float | None = None
    ) -> T | None:
        """Always returns None (async)."""
        return None

    async def store(
        self,
        key: CacheKey,
        artifact: BaseModel,
        compute_ms: float | None = None,
        ttl_seconds: float | None = None,
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
    """

    def __init__(self) -> None:
        self._async_cache = NullCache()

    def exists(self, key: CacheKey, ttl_seconds: float | None = None) -> bool:
        """Always returns False (blocking)."""
        return asyncio.run(self._async_cache.exists(key, ttl_seconds))

    def load(self, key: CacheKey, model_cls: type[T], ttl_seconds: float | None = None) -> T | None:
        """Always returns None (blocking)."""
        return asyncio.run(self._async_cache.load(key, model_cls, ttl_seconds))

    def store(
        self,
        key: CacheKey,
        artifact: BaseModel,
        compute_ms: float | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        """Discard (blocking)."""
        asyncio.run(self._async_cache.store(key, artifact, compute_ms, ttl_seconds))

    def invalidate(self, key: CacheKey) -> None:
        """No-op (blocking)."""
        asyncio.run(self._async_cache.invalidate(key))

    def initialize(self) -> None:
        """No-op (blocking)."""
        asyncio.run(self._async_cache.initialize())
