"""Unified caching system for Twinklr.

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
"""

from twinklr.core.caching.backends.fs import FSCache, FSCacheSync
from twinklr.core.caching.backends.null import NullCache, NullCacheSync
from twinklr.core.caching.fingerprint import compute_fingerprint
from twinklr.core.caching.models import CacheKey, CacheMeta, CacheOptions
from twinklr.core.caching.protocols import Cache, CacheSync

__all__ = [
    # Core
    "Cache",
    "CacheSync",
    "CacheKey",
    "CacheMeta",
    "CacheOptions",
    # Backends
    "FSCache",
    "FSCacheSync",
    "NullCache",
    "NullCacheSync",
    # Utils
    "compute_fingerprint",
]
