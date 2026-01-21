"""Audio analysis caching to avoid reprocessing."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from blinkb0t.core.config import load_app_config
from blinkb0t.core.config.models import AppConfig

logger = logging.getLogger(__name__)


def compute_audio_fingerprint(audio_path: str) -> str:
    """Generate fingerprint (hash) of audio file."""
    hasher = hashlib.sha256()

    with Path(audio_path).open("rb") as f:
        # Hash first 10MB for speed
        chunk = f.read(10 * 1024 * 1024)
        hasher.update(chunk)

    # Include file size
    file_size = os.path.getsize(audio_path)
    hasher.update(str(file_size).encode())

    return hasher.hexdigest()[:16]


def get_cache_dir(
    audio_path: str,
    *,
    cache_root: str | None = None,
    app_config: AppConfig | None = None,
) -> Path:
    """Get cache directory for audio file.

    Args:
        audio_path: Path to audio file
        cache_root: Cache root directory (overrides app_config if provided)
        app_config: App configuration (loads from file if None and cache_root is None)

    Returns:
        Path to cache directory for this audio file
    """
    if cache_root is None:
        if app_config is None:
            app_config = load_app_config()
        cache_root = app_config.cache_dir

    fingerprint = compute_audio_fingerprint(audio_path)
    cache_dir = Path(cache_root) / fingerprint
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def load_cached_features(
    audio_path: str,
    feature_type: str = "features",
    *,
    app_config: AppConfig | None = None,
) -> dict[str, Any] | None:
    """Load cached analysis if available.

    Args:
        audio_path: Path to audio file
        feature_type: Type of cached features to load
        app_config: Optional app configuration (loads from file if None)

    Returns:
        Cached features dict or None if not found/invalid
    """
    try:
        cache_dir = get_cache_dir(audio_path, app_config=app_config)
        cache_file = cache_dir / f"{feature_type}.json"

        if cache_file.exists():
            with cache_file.open() as f:
                data: Any = json.load(f)

            if not isinstance(data, dict):
                return None
            schema = data.get("schema_version", "1.0")
            if schema >= "2.0":
                logger.debug(f"Loaded cached {feature_type} (schema {schema})")
                return data
            else:
                logger.debug(f"Cache outdated (schema {schema}, need 2.0+)")
                return None
    except Exception as e:
        logger.warning(f"Failed to load cache: {e}")

    return None


def save_cached_features(
    audio_path: str,
    feature_type: str,
    data: dict[str, Any],
    *,
    app_config: AppConfig | None = None,
) -> None:
    """Save analysis to cache.

    Args:
        audio_path: Path to audio file
        feature_type: Type of features being cached
        data: Features data to save
        app_config: Optional app configuration (loads from file if None)
    """
    try:
        cache_dir = get_cache_dir(audio_path, app_config=app_config)
        cache_file = cache_dir / f"{feature_type}.json"

        with cache_file.open("w") as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Cached {feature_type}")
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")
