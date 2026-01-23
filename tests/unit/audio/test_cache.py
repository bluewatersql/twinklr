"""Tests for audio caching functionality."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import MagicMock

from blinkb0t.core.audio.cache import (
    compute_audio_fingerprint,
    get_cache_dir,
    load_cached_features,
    save_cached_features,
)


class TestComputeAudioFingerprint:
    """Tests for compute_audio_fingerprint function."""

    def test_same_file_same_fingerprint(self) -> None:
        """Same file should produce same fingerprint."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(b"test audio content" * 1000)
            path = f.name

        try:
            fp1 = compute_audio_fingerprint(path)
            fp2 = compute_audio_fingerprint(path)
            assert fp1 == fp2
        finally:
            Path(path).unlink()

    def test_different_files_different_fingerprints(self) -> None:
        """Different files should produce different fingerprints."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f1:
            f1.write(b"test audio content A" * 1000)
            path1 = f1.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f2:
            f2.write(b"test audio content B" * 1000)
            path2 = f2.name

        try:
            fp1 = compute_audio_fingerprint(path1)
            fp2 = compute_audio_fingerprint(path2)
            assert fp1 != fp2
        finally:
            Path(path1).unlink()
            Path(path2).unlink()

    def test_fingerprint_length(self) -> None:
        """Fingerprint should be 16 characters (truncated hash)."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(b"test content")
            path = f.name

        try:
            fp = compute_audio_fingerprint(path)
            assert len(fp) == 16
        finally:
            Path(path).unlink()

    def test_fingerprint_is_hex(self) -> None:
        """Fingerprint should be hexadecimal."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(b"test content")
            path = f.name

        try:
            fp = compute_audio_fingerprint(path)
            # Should not raise ValueError
            int(fp, 16)
        finally:
            Path(path).unlink()


class TestGetCacheDir:
    """Tests for get_cache_dir function."""

    def test_creates_cache_directory(self) -> None:
        """Cache directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test audio file
            audio_path = Path(tmpdir) / "test.mp3"
            with Path(audio_path).open("wb") as f:
                f.write(b"test content")

            cache_root = Path(tmpdir) / "cache"

            cache_dir = get_cache_dir(audio_path, cache_root=cache_root)

            assert cache_dir.exists()
            assert cache_dir.parent == Path(cache_root)

    def test_uses_fingerprint_as_subdir(self) -> None:
        """Cache dir uses fingerprint as subdirectory name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.mp3"
            with Path(audio_path).open("wb") as f:
                f.write(b"test content")

            cache_root = Path(tmpdir) / "cache"

            cache_dir = get_cache_dir(audio_path, cache_root=cache_root)
            fingerprint = compute_audio_fingerprint(audio_path)

            assert cache_dir.name == fingerprint


class TestLoadCachedFeatures:
    """Tests for load_cached_features function."""

    def test_missing_cache_returns_none(self) -> None:
        """Missing cache file returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.mp3"
            with Path(audio_path).open("wb") as f:
                f.write(b"test content")

            mock_config = MagicMock()
            mock_config.cache_dir = Path(tmpdir) / "nonexistent_cache"

            result = load_cached_features(audio_path, app_config=mock_config)
            assert result is None

    def test_loads_valid_cache(self) -> None:
        """Valid cache file is loaded correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.mp3"
            with Path(audio_path).open("wb") as f:
                f.write(b"test content")

            mock_config = MagicMock()
            mock_config.cache_dir = Path(tmpdir) / "cache"

            # Create cache file
            cache_dir = get_cache_dir(audio_path, cache_root=mock_config.cache_dir)
            cache_file = cache_dir / "features.json"
            cache_data = {"schema_version": "2.3", "tempo_bpm": 120}
            with cache_file.open("w") as f:
                json.dump(cache_data, f)

            result = load_cached_features(audio_path, app_config=mock_config)
            assert result is not None
            assert result["tempo_bpm"] == 120

    def test_old_schema_rejected(self) -> None:
        """Cache with old schema version is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.mp3"
            with Path(audio_path).open("wb") as f:
                f.write(b"test content")

            mock_config = MagicMock()
            mock_config.cache_dir = Path(tmpdir) / "cache"

            # Create cache file with old schema
            cache_dir = get_cache_dir(audio_path, cache_root=mock_config.cache_dir)
            cache_file = cache_dir / "features.json"
            cache_data = {"schema_version": "1.0", "tempo_bpm": 120}
            with cache_file.open("w") as f:
                json.dump(cache_data, f)

            result = load_cached_features(audio_path, app_config=mock_config)
            assert result is None

    def test_invalid_json_returns_none(self) -> None:
        """Invalid JSON cache file returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.mp3"
            with Path(audio_path).open("wb") as f:
                f.write(b"test content")

            mock_config = MagicMock()
            mock_config.cache_dir = Path(tmpdir) / "cache"

            # Create invalid cache file
            cache_dir = get_cache_dir(audio_path, cache_root=mock_config.cache_dir)
            cache_file = cache_dir / "features.json"
            with cache_file.open("w") as f:
                f.write("not valid json{{{")

            result = load_cached_features(audio_path, app_config=mock_config)
            assert result is None

    def test_non_dict_cache_returns_none(self) -> None:
        """Non-dict JSON cache returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.mp3"
            with Path(audio_path).open("wb") as f:
                f.write(b"test content")

            mock_config = MagicMock()
            mock_config.cache_dir = Path(tmpdir) / "cache"

            # Create cache file with array instead of dict
            cache_dir = get_cache_dir(audio_path, cache_root=mock_config.cache_dir)
            cache_file = cache_dir / "features.json"
            with cache_file.open("w") as f:
                json.dump([1, 2, 3], f)

            result = load_cached_features(audio_path, app_config=mock_config)
            assert result is None


class TestSaveCachedFeatures:
    """Tests for save_cached_features function."""

    def test_saves_features_to_cache(self) -> None:
        """Features are saved to cache file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.mp3"
            with Path(audio_path).open("wb") as f:
                f.write(b"test content")

            mock_config = MagicMock()
            mock_config.cache_dir = Path(tmpdir) / "cache"

            features: dict[str, Any] = {"schema_version": "2.3", "tempo_bpm": 120}
            save_cached_features(audio_path, "features", features, app_config=mock_config)

            # Verify file was created
            cache_dir = get_cache_dir(audio_path, cache_root=mock_config.cache_dir)
            cache_file = cache_dir / "features.json"
            assert cache_file.exists()

            # Verify content
            with cache_file.open() as f:
                loaded = json.load(f)
            assert loaded["tempo_bpm"] == 120

    def test_handles_write_error_gracefully(self) -> None:
        """Write errors are handled gracefully without raising."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.mp3"
            with Path(audio_path).open("wb") as f:
                f.write(b"test content")

            mock_config = MagicMock()
            # Use a read-only directory
            mock_config.cache_dir = "/nonexistent/readonly/path"

            features: dict[str, Any] = {"schema_version": "2.3", "tempo_bpm": 120}

            # Should not raise, just log warning
            save_cached_features(audio_path, "features", features, app_config=mock_config)

    def test_custom_feature_type(self) -> None:
        """Custom feature types are saved to separate files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.mp3"
            with Path(audio_path).open("wb") as f:
                f.write(b"test content")

            mock_config = MagicMock()
            mock_config.cache_dir = Path(tmpdir) / "cache"

            features: dict[str, Any] = {"data": "custom"}
            save_cached_features(audio_path, "custom_type", features, app_config=mock_config)

            cache_dir = get_cache_dir(audio_path, cache_root=mock_config.cache_dir)
            cache_file = cache_dir / "custom_type.json"
            assert cache_file.exists()
