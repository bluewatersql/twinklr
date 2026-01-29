"""Unified caching system for BlinkB0t.

This module provides async-first caching using core.io abstractions:
- Audio analysis features (replaces audio/cache.py)
- Agent orchestration checkpoints (replaces utils/checkpoint.py)
- Sequence analysis data

Key features:
- Async file I/O using core.io FileSystem
- Type-safe cache keys (step_id + version + input fingerprint)
- Pydantic model validation
- Atomic commit pattern (artifact + meta)
- Graceful error handling

Example:
    >>> from blinkb0t.core.caching import FSCache, CacheKey
    >>> from blinkb0t.core.io import RealFileSystem, absolute_path
    >>>
    >>> fs = RealFileSystem()
    >>> cache = FSCache(fs, absolute_path("data/cache"))
    >>> await cache.initialize()
    >>>
    >>> key = CacheKey(
    ...     step_id="audio.features",
    ...     step_version="1",
    ...     input_fingerprint="abc123..."
    ... )
    >>> await cache.store(key, my_pydantic_model)
    >>> result = await cache.load(key, MyModel)
"""

from blinkb0t.core.caching.backends.fs import FSCache
from blinkb0t.core.caching.fingerprint import compute_fingerprint
from blinkb0t.core.caching.models import CacheKey, CacheMeta, CacheOptions
from blinkb0t.core.caching.protocols import Cache, CacheSync
from blinkb0t.core.caching.wrapper import cached_step, cached_step_sync

__all__ = [
    # Core
    "Cache",
    "CacheSync",
    "CacheKey",
    "CacheMeta",
    "CacheOptions",
    # Backends
    "FSCache",
    # Utils
    "compute_fingerprint",
    "cached_step",
    "cached_step_sync",
]
