"""Tests for AudioAnalyzer orchestration."""

from __future__ import annotations

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from blinkb0t.core.audio.analyzer import AudioAnalyzer


class TestAudioAnalyzer:
    """Tests for AudioAnalyzer class."""

    @pytest.fixture
    def mock_configs(self) -> tuple[MagicMock, MagicMock]:
        """Create mock app and job configs."""
        app_config = MagicMock()
        app_config.audio_processing.hop_length = 512
        app_config.audio_processing.frame_length = 2048
        app_config.cache_dir = tempfile.mkdtemp()

        job_config = MagicMock()
        job_config.checkpoint_dir = tempfile.mkdtemp()

        return app_config, job_config

    @pytest.mark.skip(reason="Rewriting for async cache in Day 3")
    def test_cache_integration(
        self,
        mock_configs: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test async cache integration."""

    @pytest.mark.skip(reason="Rewriting for async cache in Day 3")
    def test_cache_hit(
        self,
        mock_configs: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test cache hit scenario."""
        app_config, job_config = mock_configs

        # Mock checkpoint to return existing features
        mock_checkpoint = MagicMock()
        mock_checkpoint.read_checkpoint.return_value = {
            "schema_version": "2.3",
            "tempo_bpm": 120.0,
        }

        analyzer = AudioAnalyzer(app_config, job_config)
        result = analyzer.analyze("/fake/path.mp3")

        # analyze() now returns SongBundle
        from blinkb0t.core.audio.models import SongBundle

        assert isinstance(result, SongBundle)
        assert result.features["tempo_bpm"] == 120.0
        mock_checkpoint.read_checkpoint.assert_called_once()

    @pytest.mark.skip(reason="Rewriting for async cache in Day 3")
    @patch("blinkb0t.core.audio.cache_adapter.load_audio_features_async")
    def test_cache_miss_and_save(
        self,
        mock_load_cache: MagicMock,
        mock_configs: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test cache miss and save scenario."""
        app_config, job_config = mock_configs

        # Mock cache to return features
        mock_load_cache.return_value = {
            "schema_version": "2.3",
            "tempo_bpm": 100.0,
        }

        analyzer = AudioAnalyzer(app_config, job_config)
        result = analyzer.analyze("/fake/path.mp3")

        # analyze() now returns SongBundle
        from blinkb0t.core.audio.models import SongBundle

        assert isinstance(result, SongBundle)
        assert result.features["tempo_bpm"] == 100.0
        mock_load_cache.assert_called_once()

    @pytest.mark.skip(reason="Phase 8: Migrating to async cache, will update in Day 3")
    @patch("blinkb0t.core.audio.cache_adapter.load_audio_features_async")
    def test_force_reprocess_skips_cache(
        self,
        mock_load_cache: MagicMock,
        mock_configs: tuple[MagicMock, MagicMock],
    ) -> None:
        """force_reprocess=True skips cache check (DEPRECATED Phase 8)."""
        app_config, job_config = mock_configs

        analyzer = AudioAnalyzer(app_config, job_config)

        # This would fail if it tried to actually process, but we just
        # verify cache was not called
        with pytest.raises(Exception):  # Will fail on librosa.load  # noqa: B017
            analyzer.analyze("/fake/path.mp3", force_reprocess=True)

        mock_load_cache.assert_not_called()

    @pytest.mark.skip(reason="Rewriting for async in Day 3")
    def test_short_audio(
        self,
        mock_configs: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test short audio handling."""
        app_config, job_config = mock_configs

        # Create very short audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            import wave

            with wave.open(f.name, "w") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(22050)
                # 2 seconds of silence
                wav.writeframes(b"\x00" * 22050 * 2 * 2)
            audio_path = f.name

        try:
            # Mock checkpoint to return None
            with patch("blinkb0t.core.audio.analyzer.CheckpointManager") as mock_cp:
                mock_cp.return_value.read_checkpoint.return_value = None

                with (
                    patch("blinkb0t.core.audio.analyzer.load_cached_features", return_value=None),
                    patch("blinkb0t.core.audio.analyzer.save_cached_features"),
                ):
                    analyzer = AudioAnalyzer(app_config, job_config)
                    result = analyzer.analyze(audio_path)

                    # analyze() now returns SongBundle
                    from blinkb0t.core.audio.models import SongBundle

                    assert isinstance(result, SongBundle)
                    assert result.features["schema_version"] == "2.3"
                    assert result.features["tempo_bpm"] == 0.0
                    # Warnings in features dict for v2.3 compatibility
                    assert "warnings" in result.features
        finally:
            Path(audio_path).unlink()

    def test_static_minimal_features_structure(self) -> None:
        """_minimal_features returns expected structure."""
        y = np.zeros(22050, dtype=np.float32)  # 1 second
        result = AudioAnalyzer._minimal_features(
            audio_path="/test/path.mp3",
            y=y,
            sr=22050,
            duration=1.0,
        )

        assert result["schema_version"] == "2.3"
        assert result["audio_path"] == "/test/path.mp3"
        assert result["sr"] == 22050
        assert result["duration_s"] == 1.0
        assert result["tempo_bpm"] == 0.0
        assert result["beats_s"] == []
        assert result["bars_s"] == []
        assert "warnings" in result


class TestAudioAnalyzerIntegration:
    """Integration tests for AudioAnalyzer with real audio processing.

    These tests require librosa and process actual audio data.
    """

    @pytest.fixture
    def test_audio_file(self, sample_rate: int) -> str:
        """Create a test audio file with 15 seconds of audio."""
        import wave

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            with wave.open(f.name, "w") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)

                # 15 seconds of audio with beats
                duration = 15.0
                n_samples = int(sample_rate * duration)
                t = np.linspace(0, duration, n_samples)

                # Create audio with harmonic content
                audio = np.sin(2 * np.pi * 440 * t) * 0.5
                # Add some amplitude modulation (beat-like)
                audio *= 0.5 + 0.5 * np.sin(2 * np.pi * 2 * t)  # 2Hz modulation

                # Convert to 16-bit
                audio_int = (audio * 32767).astype(np.int16)
                wav.writeframes(audio_int.tobytes())

            return f.name

    @pytest.mark.skip(reason="Rewriting for async in Day 3")
    @pytest.mark.slow
    def test_integration(
        self,
        test_audio_file: str,
        mock_app_config: MagicMock,
        mock_job_config: MagicMock,
    ) -> None:
        """Full analysis on test audio file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_config.cache_dir = tmpdir

            with patch("blinkb0t.core.audio.analyzer.CheckpointManager") as mock_cp:
                mock_cp.return_value.read_checkpoint.return_value = None

                with (
                    patch("blinkb0t.core.audio.analyzer.load_cached_features", return_value=None),
                    patch("blinkb0t.core.audio.analyzer.save_cached_features"),
                ):
                    analyzer = AudioAnalyzer(mock_app_config, mock_job_config)
                    result = analyzer.analyze(test_audio_file)

                    # analyze() now returns SongBundle
                    from blinkb0t.core.audio.models import SongBundle

                    assert isinstance(result, SongBundle)
                    # Verify structure
                    assert result.features["schema_version"] == "2.3"
                    assert result.features["duration_s"] > 10.0  # Should be ~15s
                    assert result.features["tempo_bpm"] > 0  # Should detect some tempo
                    assert "beats_s" in result.features
                    assert "bars_s" in result.features
                    assert "energy" in result.features
                    assert "spectral" in result.features
                    assert "structure" in result.features
                    # timeline is an optional field in v2.3, may not always be present
                    # (check in features dict, not in SongBundle)

        # Clean up test file
        Path(test_audio_file).unlink()
