"""Tests for AudioAnalyzer returning SongBundle (Phase 1).

Tests that AudioAnalyzer.analyze() returns SongBundle and that
analyze_dict() provides backward compatibility.
"""

from unittest.mock import patch

import pytest

from blinkb0t.core.audio.analyzer import AudioAnalyzer
from blinkb0t.core.audio.models import SongBundle
from blinkb0t.core.config.models import AppConfig, JobConfig


@pytest.fixture
def app_config():
    """Create test app config."""
    return AppConfig()


@pytest.fixture
def job_config():
    """Create test job config."""
    return JobConfig(
        name="test_job",
        audio_path="test.mp3",
        xsq_path="test.xsq",
        fixture_config_path="fixtures.json",
    )


@pytest.fixture
def mock_process_audio():
    """Mock the _process_audio method to return v2.3 features."""
    return {
        "schema_version": "2.3",
        "tempo_bpm": 120.0,
        "beats_s": [0.5, 1.0, 1.5],
        "bars": [[0.5, 1]],
        "sr": 22050,
        "hop_length": 512,
        "duration_s": 3.0,
    }


class TestAudioAnalyzerReturnsSongBundle:
    """Test that AudioAnalyzer.analyze() returns SongBundle."""

    @pytest.mark.asyncio
    async def test_analyze_returns_song_bundle(self, app_config, job_config, mock_process_audio):
        """analyze() should return SongBundle instance."""
        analyzer = AudioAnalyzer(app_config, job_config)

        with (
            patch.object(analyzer, "_process_audio", return_value=mock_process_audio),
            patch("blinkb0t.core.audio.cache_adapter.load_audio_features_async", return_value=None),
            patch("blinkb0t.core.audio.cache_adapter.save_audio_features_async"),
        ):
            result = await analyzer.analyze("test.mp3")

        # Should return SongBundle
        assert isinstance(result, SongBundle)
        assert result.schema_version == "3.0"
        assert result.audio_path == "test.mp3"

    @pytest.mark.asyncio
    async def test_bundle_contains_v23_features(self, app_config, job_config, mock_process_audio):
        """SongBundle.features should contain v2.3 features dict."""
        analyzer = AudioAnalyzer(app_config, job_config)

        with (
            patch.object(analyzer, "_process_audio", return_value=mock_process_audio),
            patch("blinkb0t.core.audio.cache_adapter.load_audio_features_async", return_value=None),
            patch("blinkb0t.core.audio.cache_adapter.save_audio_features_async"),
        ):
            result = await analyzer.analyze("test.mp3")

        # Should preserve v2.3 features in bundle
        assert result.features["schema_version"] == "2.3"
        assert result.features["tempo_bpm"] == 120.0
        assert result.features["beats_s"] == [0.5, 1.0, 1.5]

    @pytest.mark.asyncio
    async def test_bundle_timing_populated(self, app_config, job_config, mock_process_audio):
        """SongBundle.timing should be populated from features."""
        analyzer = AudioAnalyzer(app_config, job_config)

        with (
            patch.object(analyzer, "_process_audio", return_value=mock_process_audio),
            patch("blinkb0t.core.audio.cache_adapter.load_audio_features_async", return_value=None),
            patch("blinkb0t.core.audio.cache_adapter.save_audio_features_async"),
        ):
            result = await analyzer.analyze("test.mp3")

        # Timing extracted from features
        assert result.timing.sr == 22050
        assert result.timing.hop_length == 512
        assert result.timing.duration_s == 3.0
        assert result.timing.duration_ms == 3000

    @pytest.mark.asyncio
    async def test_enhancements_none_when_disabled(
        self, app_config, job_config, mock_process_audio
    ):
        """Enhancement bundles populated but with SKIPPED status when disabled."""
        # Disable metadata for this test
        app_config.audio_processing.enhancements.enable_metadata = False
        analyzer = AudioAnalyzer(app_config, job_config)

        with (
            patch.object(analyzer, "_process_audio", return_value=mock_process_audio),
            patch("blinkb0t.core.audio.cache_adapter.load_audio_features_async", return_value=None),
            patch("blinkb0t.core.audio.cache_adapter.save_audio_features_async"),
        ):
            result = await analyzer.analyze("test.mp3")

        # Phase 2: Metadata always populated (SKIPPED when disabled)
        from blinkb0t.core.audio.models.enums import StageStatus

        assert result.metadata is not None
        assert result.metadata.stage_status == StageStatus.SKIPPED
        # Lyrics populated with SKIPPED status
        assert result.lyrics is not None
        assert result.lyrics.stage_status == StageStatus.SKIPPED
        # Phonemes not yet implemented
        assert result.phonemes is None


class TestAudioAnalyzerBackwardCompat:
    """Test AudioAnalyzer.analyze_dict() backward compatibility."""

    def test_analyze_dict_returns_v23_dict(self, app_config, job_config, mock_process_audio):
        """analyze_dict() should return v2.3 dict for backward compatibility."""
        analyzer = AudioAnalyzer(app_config, job_config)

        with (
            patch.object(analyzer, "_process_audio", return_value=mock_process_audio),
            patch("blinkb0t.core.audio.cache_adapter.load_audio_features_async", return_value=None),
            patch("blinkb0t.core.audio.cache_adapter.save_audio_features_async"),
        ):
            result = analyzer.analyze_dict("test.mp3")

        # Should return v2.3 dict
        assert isinstance(result, dict)
        assert result["schema_version"] == "2.3"
        assert result["tempo_bpm"] == 120.0
        assert result["beats_s"] == [0.5, 1.0, 1.5]

    def test_analyze_dict_equivalent_to_old_analyze(
        self, app_config, job_config, mock_process_audio
    ):
        """analyze_dict() should return same format as old analyze() method."""
        analyzer = AudioAnalyzer(app_config, job_config)

        with (
            patch.object(analyzer, "_process_audio", return_value=mock_process_audio),
            patch("blinkb0t.core.audio.cache_adapter.load_audio_features_async", return_value=None),
            patch("blinkb0t.core.audio.cache_adapter.save_audio_features_async"),
        ):
            dict_result = analyzer.analyze_dict("test.mp3")

        # Should match the old dict format exactly
        assert dict_result == mock_process_audio
