"""Cache wrapper functions for pipeline steps.

Provides cached_step() async function and cached_step_sync() convenience wrapper.
"""

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel

from .fingerprint import compute_fingerprint
from .models import CacheKey, CacheOptions
from .protocols import Cache, CacheSync

T = TypeVar("T", bound=BaseModel)


async def cached_step(
    cache: Cache,
    step_id: str,
    step_version: str,
    inputs: dict[str, object],
    model_cls: type[T],
    compute: Callable[[], Awaitable[T]],
    options: CacheOptions | None = None,
) -> T:
    """
    Execute a cacheable pipeline step (async).

    This is the primary entry point for all cache-backed computations.

    Workflow:
    1. Compute cache key from step identity and inputs
    2. Attempt cache load (if enabled and not forced)
    3. On miss: run compute(), store result (if enabled)
    4. Return artifact

    Args:
        cache: Async cache backend
        step_id: Stable step identifier (e.g., "audio.features")
        step_version: Step version (bump on logic changes)
        inputs: Input dict (only values affecting output)
        model_cls: Pydantic model class for artifact
        compute: Async function to compute artifact on cache miss
        options: Optional cache behavior overrides

    Returns:
        Cached or freshly computed artifact

    Example:
        >>> result = await cached_step(
        ...     cache=fs_cache,
        ...     step_id="audio.features",
        ...     step_version="2",
        ...     inputs={"audio_sha256": "abc123"},
        ...     model_cls=SongFeatures,
        ...     compute=lambda: analyze_audio_async(...),
        ... )
    """
    opts = options or CacheOptions()

    # Compute cache key
    fingerprint = compute_fingerprint(step_id, step_version, inputs)
    key = CacheKey(
        step_id=step_id,
        step_version=step_version,
        input_fingerprint=fingerprint,
    )

    # Attempt load (if enabled and not forced)
    if opts.enabled and not opts.force:
        artifact = await cache.load(key, model_cls)
        if artifact is not None:
            return artifact

    # Cache miss: compute
    start = time.perf_counter()
    artifact = await compute()
    compute_ms = (time.perf_counter() - start) * 1000

    # Store (if enabled)
    if opts.enabled:
        await cache.store(key, artifact, compute_ms=compute_ms)

    return artifact


def cached_step_sync(
    cache: CacheSync,
    step_id: str,
    step_version: str,
    inputs: dict[str, object],
    model_cls: type[T],
    compute: Callable[[], T],
    options: CacheOptions | None = None,
) -> T:
    """
    Execute a cacheable pipeline step (sync convenience wrapper).

    Blocking version for simple scripts, tests, and non-async contexts.

    Args:
        cache: Sync cache backend
        step_id: Stable step identifier
        step_version: Step version
        inputs: Input dict
        model_cls: Pydantic model class
        compute: Sync function to compute artifact
        options: Optional cache behavior overrides

    Returns:
        Cached or freshly computed artifact

    Example:
        >>> result = cached_step_sync(
        ...     cache=fs_cache_sync,
        ...     step_id="audio.features",
        ...     step_version="2",
        ...     inputs={"audio_sha256": "abc123"},
        ...     model_cls=SongFeatures,
        ...     compute=lambda: analyze_audio(...),
        ... )
    """
    opts = options or CacheOptions()

    # Compute cache key
    fingerprint = compute_fingerprint(step_id, step_version, inputs)
    key = CacheKey(
        step_id=step_id,
        step_version=step_version,
        input_fingerprint=fingerprint,
    )

    # Attempt load (if enabled and not forced)
    if opts.enabled and not opts.force:
        artifact = cache.load(key, model_cls)
        if artifact is not None:
            return artifact

    # Cache miss: compute
    start = time.perf_counter()
    artifact = compute()
    compute_ms = (time.perf_counter() - start) * 1000

    # Store (if enabled)
    if opts.enabled:
        cache.store(key, artifact, compute_ms=compute_ms)

    return artifact
