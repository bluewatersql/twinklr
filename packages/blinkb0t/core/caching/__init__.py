"""Caching system for BlinkB0t pipeline steps.

Provides deterministic, filesystem-backed caching for expensive computations.

Example (async):
    >>> from blinkb0t.core.io import RealFileSystem, absolute_path
    >>> from blinkb0t.core.caching import FSCache, cached_step, CacheKey
    >>>
    >>> fs = RealFileSystem()
    >>> cache = FSCache(fs, absolute_path("/.cache"))
    >>> await cache.initialize()
    >>>
    >>> async def compute():
    ...     return MyArtifact(value="computed")
    >>>
    >>> result = await cached_step(
    ...     cache=cache,
    ...     step_id="my.step",
    ...     step_version="1",
    ...     inputs={"param": "value"},
    ...     model_cls=MyArtifact,
    ...     compute=compute,
    ... )

Example (sync):
    >>> from blinkb0t.core.io import RealFileSystem, absolute_path
    >>> from blinkb0t.core.caching import FSCacheSync, cached_step_sync
    >>>
    >>> fs = RealFileSystem()
    >>> cache = FSCacheSync(fs, absolute_path("/.cache"))
    >>>
    >>> def compute():
    ...     return MyArtifact(value="computed")
    >>>
    >>> result = cached_step_sync(
    ...     cache=cache,
    ...     step_id="my.step",
    ...     step_version="1",
    ...     inputs={"param": "value"},
    ...     model_cls=MyArtifact,
    ...     compute=compute,
    ... )
"""

from .backends import FSCache, FSCacheSync, NullCache, NullCacheSync
from .fingerprint import compute_fingerprint
from .models import CacheKey, CacheMeta, CacheOptions
from .protocols import Cache, CacheSync
from .wrapper import cached_step, cached_step_sync

__all__ = [
    # Models
    "CacheKey",
    "CacheMeta",
    "CacheOptions",
    # Protocols
    "Cache",
    "CacheSync",
    # Async backends
    "FSCache",
    "NullCache",
    # Sync wrappers
    "FSCacheSync",
    "NullCacheSync",
    # Wrapper functions
    "cached_step",
    "cached_step_sync",
    # Utilities
    "compute_fingerprint",
]
