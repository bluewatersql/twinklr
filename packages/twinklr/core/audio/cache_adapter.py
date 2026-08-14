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
    >>> cache = FSCache(fs, anchored_path(project_root, "data/cache"))
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
from twinklr.core.config.models import AudioProcessingConfig

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Cache-invalidation version for the stored SongBundle payload. Bump whenever the
# cached shape changes, not only when SongBundle's own schema_version does: entries
# written before the bump are rejected on load (CacheKey.step_version mismatch).
# "5" — source selection and source-separation add explicit provenance/stem
# status and change rhythm, structure, build/drop, vocal, and lyrics-gating inputs.
AUDIO_FEATURES_CACHE_VERSION = "5"

_MIR_SOURCE_VERSIONS = {
    "dsp": "twinklr-dsp-v1",
    "beat_this": "1.1.0",
    "allinone": "1.0.6",
}


def audio_analysis_fingerprint(config: AudioProcessingConfig) -> str:
    """Return the cache identity for selected timing/structure implementations."""
    rhythm = config.rhythm_source.value
    structure = config.structure_source.value
    return (
        f"rhythm={rhythm}@{_MIR_SOURCE_VERSIONS[rhythm]};"
        f"structure={structure}@{_MIR_SOURCE_VERSIONS[structure]}"
    )


async def compute_audio_file_hash(audio_path: str, *, analysis_identity: str = "") -> str:
    """Compute SHA256 hash of audio file for cache key.

    Uses full-file content to reduce collision risk for cache keys.

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

    # Hash full file contents for robust cache fingerprinting
    with audio_file.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)

    if analysis_identity:
        hasher.update(b"\0twinklr-analysis-identity\0")
        hasher.update(analysis_identity.encode("utf-8"))

    return hasher.hexdigest()


async def load_audio_features_async[T: BaseModel](
    audio_path: str,
    cache: FSCache,
    model_cls: type[T],
    *,
    step_version: str = AUDIO_FEATURES_CACHE_VERSION,
    analysis_identity: str = "",
) -> T | None:
    """Load cached audio features using core.caching.

    Args:
        audio_path: Path to audio file
        cache: FSCache instance
        model_cls: Pydantic model class (e.g., SongBundle)
        step_version: Cache-invalidation version (default: AUDIO_FEATURES_CACHE_VERSION)

    Returns:
        Cached model or None if not found

    Example:
        >>> features = await load_audio_features_async("song.mp3", cache, SongBundle)
        >>> if features:
        ...     print(f"Tempo: {features.tempo}")
    """
    try:
        # Compute audio hash
        audio_hash = await compute_audio_file_hash(audio_path, analysis_identity=analysis_identity)

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
    step_version: str = AUDIO_FEATURES_CACHE_VERSION,
    analysis_identity: str = "",
    compute_ms: float | None = None,
) -> None:
    """Save audio features to cache.

    Args:
        audio_path: Path to audio file
        cache: FSCache instance
        features: Pydantic model to cache
        step_version: Cache-invalidation version (default: AUDIO_FEATURES_CACHE_VERSION)
        compute_ms: Optional computation duration in milliseconds

    Example:
        >>> await save_audio_features_async("song.mp3", cache, song_bundle, compute_ms=1500.0)
    """
    try:
        # Compute audio hash
        audio_hash = await compute_audio_file_hash(audio_path, analysis_identity=analysis_identity)

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
