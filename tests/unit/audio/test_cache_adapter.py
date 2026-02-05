"""Tests for audio cache adapter (Phase 8 async)."""

from __future__ import annotations

from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from twinklr.core.audio.cache_adapter import (
    compute_audio_file_hash,
    load_audio_features_async,
    save_audio_features_async,
)
from twinklr.core.audio.models import SongBundle, SongTiming
from twinklr.core.caching import CacheKey, FSCache


class TestComputeAudioHash:
    """Tests for compute_audio_file_hash()."""

    @pytest.mark.asyncio
    async def test_computes_sha256_hash(self) -> None:
        """Hash is computed from file content."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(b"fake audio content")
            audio_path = f.name

        try:
            audio_hash = await compute_audio_file_hash(audio_path)

            # Verify hash format
            assert isinstance(audio_hash, str)
            assert len(audio_hash) == 64  # SHA256 hex digest

            # Verify deterministic (same file = same hash)
            audio_hash2 = await compute_audio_file_hash(audio_path)
            assert audio_hash == audio_hash2
        finally:
            Path(audio_path).unlink()

    @pytest.mark.asyncio
    async def test_different_files_different_hashes(self) -> None:
        """Different files produce different hashes."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f1:
            f1.write(b"audio 1")
            path1 = f1.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f2:
            f2.write(b"audio 2")
            path2 = f2.name

        try:
            hash1 = await compute_audio_file_hash(path1)
            hash2 = await compute_audio_file_hash(path2)

            assert hash1 != hash2
        finally:
            Path(path1).unlink()
            Path(path2).unlink()


class TestLoadAudioFeatures:
    """Tests for load_audio_features_async()."""

    @pytest.mark.asyncio
    async def test_returns_none_on_cache_miss(self) -> None:
        """Returns None when cache has no entry."""
        with tempfile.TemporaryDirectory() as cache_dir:
            from twinklr.core.io import RealFileSystem

            fs = RealFileSystem()
            cache = FSCache(fs, cache_dir)
            await cache.initialize()

            # Mock hash computation (using AsyncMock for async function)
            with patch(
                "twinklr.core.audio.cache_adapter.compute_audio_file_hash",
                new=AsyncMock(return_value="abc123"),
            ):
                result = await load_audio_features_async("/fake/audio.mp3", cache, SongBundle)

            assert result is None

    @pytest.mark.asyncio
    async def test_loads_cached_bundle(self) -> None:
        """Loads and validates cached SongBundle."""
        with tempfile.TemporaryDirectory() as cache_dir:
            from twinklr.core.io import RealFileSystem

            fs = RealFileSystem()
            cache = FSCache(fs, cache_dir)
            await cache.initialize()

            # Create test bundle
            bundle = SongBundle(
                schema_version="3.0",
                audio_path="/test.mp3",
                recording_id="test123",
                features={"tempo_bpm": 120.0},
                timing=SongTiming(sr=22050, hop_length=512, duration_s=10.0, duration_ms=10000),
            )

            # Mock hash and save bundle
            audio_hash = "test_hash"
            with patch(
                "twinklr.core.audio.cache_adapter.compute_audio_file_hash",
                return_value=audio_hash,
            ):
                key = CacheKey(
                    domain="audio",
                    step_id="audio.features",
                    step_version="3",
                    input_fingerprint=audio_hash,
                )
                await cache.store(key, bundle)

                # Load bundle
                loaded = await load_audio_features_async("/test.mp3", cache, SongBundle)

            assert loaded is not None
            assert loaded.audio_path == "/test.mp3"
            assert loaded.features["tempo_bpm"] == 120.0


class TestSaveAudioFeatures:
    """Tests for save_audio_features_async()."""

    @pytest.mark.asyncio
    async def test_saves_bundle_to_cache(self) -> None:
        """Saves SongBundle to cache with correct key."""
        with tempfile.TemporaryDirectory() as cache_dir:
            from twinklr.core.io import RealFileSystem

            fs = RealFileSystem()
            cache = FSCache(fs, cache_dir)
            await cache.initialize()

            bundle = SongBundle(
                schema_version="3.0",
                audio_path="/test.mp3",
                recording_id="test123",
                features={"tempo_bpm": 140.0},
                timing=SongTiming(sr=22050, hop_length=512, duration_s=15.0, duration_ms=15000),
            )

            audio_hash = "save_test_hash"
            with patch(
                "twinklr.core.audio.cache_adapter.compute_audio_file_hash",
                new=AsyncMock(return_value=audio_hash),
            ):
                await save_audio_features_async("/test.mp3", cache, bundle)

                # Verify saved
                loaded = await load_audio_features_async("/test.mp3", cache, SongBundle)

            assert loaded is not None
            assert loaded.features["tempo_bpm"] == 140.0

    @pytest.mark.asyncio
    async def test_compute_ms_optional(self) -> None:
        """compute_ms parameter is optional."""
        with tempfile.TemporaryDirectory() as cache_dir:
            from twinklr.core.io import RealFileSystem

            fs = RealFileSystem()
            cache = FSCache(fs, cache_dir)
            await cache.initialize()

            bundle = SongBundle(
                schema_version="3.0",
                audio_path="/test.mp3",
                recording_id="test123",
                features={},
                timing=SongTiming(sr=22050, hop_length=512, duration_s=5.0, duration_ms=5000),
            )

            with patch(
                "twinklr.core.audio.cache_adapter.compute_audio_file_hash",
                return_value="hash",
            ):
                # Should not raise
                await save_audio_features_async("/test.mp3", cache, bundle)
                await save_audio_features_async("/test.mp3", cache, bundle, compute_ms=1000.0)
