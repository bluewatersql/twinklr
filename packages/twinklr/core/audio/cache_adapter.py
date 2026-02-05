"""Async cache adapter for audio features (Phase 8).

Replaces audio/cache.py with adapters using core.caching.FSCache.

Functions:
    compute_audio_file_hash: Hash audio file for cache key
    load_audio_features_async: Load cached audio features
    save_audio_features_async: Save audio features to cache

Example:
    >>> from twinklr.core.caching import FSCache
    >>> from twinklr.core.io import RealFileSystem, absolute_path
    >>>
    >>> fs = RealFileSystem()
    >>> cache = FSCache(fs, absolute_path("data/cache"))
    >>> await cache.initialize()
    >>>
    >>> features = await load_audio_features_async("song.mp3", cache, SongBundle)
"""

import hashlib
import logging
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from twinklr.core.caching import CacheKey, FSCache

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def compute_audio_file_hash(audio_path: str) -> str:
    """Compute SHA256 hash of audio file for cache key.

    Uses first 10MB + file size for fast fingerprinting.

    Args:
        audio_path: Path to audio file

    Returns:
        SHA256 hex digest (64 chars)

    Example:
        >>> hash_val = await compute_audio_file_hash("song.mp3")
        >>> len(hash_val)
        64
    """
    hasher = hashlib.sha256()

    audio_file = Path(audio_path)

    # Hash first 10MB for speed
    with audio_file.open("rb") as f:
        chunk = f.read(10 * 1024 * 1024)
        hasher.update(chunk)

    # Include file size
    file_size = audio_file.stat().st_size
    hasher.update(str(file_size).encode())

    return hasher.hexdigest()


async def load_audio_features_async(
    audio_path: str,
    cache: FSCache,
    model_cls: type[T],
    *,
    step_version: str = "3",
) -> T | None:
    """Load cached audio features using core.caching.

    Args:
        audio_path: Path to audio file
        cache: FSCache instance
        model_cls: Pydantic model class (e.g., SongBundle)
        step_version: Schema version (default: "3" for v3.0)

    Returns:
        Cached model or None if not found

    Example:
        >>> features = await load_audio_features_async("song.mp3", cache, SongBundle)
        >>> if features:
        ...     print(f"Tempo: {features.tempo}")
    """
    try:
        # Compute audio hash
        audio_hash = await compute_audio_file_hash(audio_path)

        # Create cache key
        key = CacheKey(
            domain="audio",
            step_id="audio.features",
            step_version=step_version,
            input_fingerprint=audio_hash,
        )

        # Load with Pydantic validation
        result = await cache.load(key, model_cls)
        if result:
            logger.debug(f"Cache hit: {audio_path}")
        return result
    except Exception as e:
        logger.warning(f"Failed to load cache: {e}")
        return None


async def save_audio_features_async(
    audio_path: str,
    cache: FSCache,
    features: BaseModel,
    *,
    step_version: str = "3",
    compute_ms: float | None = None,
) -> None:
    """Save audio features to cache.

    Args:
        audio_path: Path to audio file
        cache: FSCache instance
        features: Pydantic model to cache
        step_version: Schema version
        compute_ms: Optional computation duration in milliseconds

    Example:
        >>> await save_audio_features_async("song.mp3", cache, song_bundle, compute_ms=1500.0)
    """
    try:
        # Compute audio hash
        audio_hash = await compute_audio_file_hash(audio_path)

        # Create cache key
        key = CacheKey(
            domain="audio",
            step_id="audio.features",
            step_version=step_version,
            input_fingerprint=audio_hash,
        )

        # Store with atomic commit
        await cache.store(key, features, compute_ms=compute_ms)
        logger.debug(f"Cached features: {audio_path}")
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")
        # Non-fatal - continue without caching
