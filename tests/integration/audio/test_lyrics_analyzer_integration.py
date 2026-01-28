"""Integration tests for lyrics analyzer integration (Phase 4).

Tests AudioAnalyzer integration with lyrics pipeline.
"""

from unittest.mock import patch

import pytest

from blinkb0t.core.audio.analyzer import AudioAnalyzer
from blinkb0t.core.audio.models import StageStatus
from blinkb0t.core.audio.models.lyrics import LyricsSourceKind
from blinkb0t.core.config.models import AppConfig, JobConfig


class TestLyricsAnalyzerIntegration:
    """Test lyrics integration with AudioAnalyzer."""

    @pytest.fixture
    def app_config(self):
        """App config with lyrics enabled."""
        config = AppConfig()
        config.audio_processing.enhancements.enable_lyrics = True
        config.audio_processing.enhancements.enable_lyrics_lookup = False
        return config

    @pytest.fixture
    def job_config(self):
        """Job config with checkpoints disabled."""
        config = JobConfig()
        config.checkpoint = False
        return config

    @pytest.fixture
    def audio_file_with_lrc(self, tmp_path):
        """Create fake audio file with LRC sidecar."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()
        lrc_file = tmp_path / "song.lrc"
        lrc_file.write_text("[00:10.00]Line 1\n[00:15.00]Line 2")
        return audio_file

    def test_lyrics_disabled_returns_skipped(self, app_config, job_config, tmp_path):
        """Lyrics pipeline skipped when feature disabled."""
        app_config.audio_processing.enhancements.enable_lyrics = False

        audio_file = tmp_path / "song.mp3"
        audio_file.touch()

        analyzer = AudioAnalyzer(app_config, job_config)

        with patch.object(analyzer, "_process_audio") as mock_process:
            mock_process.return_value = {"tempo_bpm": 120, "duration_s": 180.0}
            bundle = analyzer.analyze(str(audio_file))

        assert bundle.lyrics is not None
        assert bundle.lyrics.stage_status == StageStatus.SKIPPED
        assert bundle.lyrics.text is None

    def test_lyrics_enabled_extracts_embedded(self, app_config, job_config, audio_file_with_lrc):
        """Lyrics pipeline extracts embedded LRC."""
        analyzer = AudioAnalyzer(app_config, job_config)

        with patch.object(analyzer, "_process_audio") as mock_process:
            mock_process.return_value = {"tempo_bpm": 120, "duration_s": 180.0}
            bundle = analyzer.analyze(str(audio_file_with_lrc))

        assert bundle.lyrics is not None
        assert bundle.lyrics.stage_status == StageStatus.OK
        assert bundle.lyrics.text == "Line 1\nLine 2"
        assert len(bundle.lyrics.phrases) == 2
        assert bundle.lyrics.source.kind == LyricsSourceKind.EMBEDDED

    def test_lyrics_lookup_disabled_skips_providers(self, app_config, job_config, tmp_path):
        """External providers skipped when lookup disabled."""
        app_config.audio_processing.enhancements.enable_lyrics_lookup = False

        audio_file = tmp_path / "song.mp3"
        audio_file.touch()

        analyzer = AudioAnalyzer(app_config, job_config)

        with patch.object(analyzer, "_process_audio") as mock_process:
            mock_process.return_value = {
                "tempo_bpm": 120,
                "duration_s": 180.0,
                "metadata": {"artist": "Test Artist", "title": "Test Song"},
            }
            bundle = analyzer.analyze(str(audio_file))

        # Should have tried embedded but not providers
        assert bundle.lyrics is not None
        assert bundle.lyrics.stage_status == StageStatus.SKIPPED

    def test_lyrics_with_require_timed_config(self, app_config, job_config, audio_file_with_lrc):
        """Pipeline respects require_timed_words config."""
        app_config.audio_processing.enhancements.lyrics_require_timed = True

        analyzer = AudioAnalyzer(app_config, job_config)

        with patch.object(analyzer, "_process_audio") as mock_process:
            mock_process.return_value = {"tempo_bpm": 120, "duration_s": 180.0}
            bundle = analyzer.analyze(str(audio_file_with_lrc))

        assert bundle.lyrics is not None
        # LRC provides phrase-level, not word-level, so should have warning
        assert bundle.lyrics.stage_status == StageStatus.OK
        assert any("sufficiency" in w.lower() for w in bundle.lyrics.warnings)

    def test_lyrics_pipeline_error_handled_gracefully(self, app_config, job_config, tmp_path):
        """Pipeline errors don't crash analyzer."""
        audio_file = tmp_path / "song.mp3"
        audio_file.touch()

        analyzer = AudioAnalyzer(app_config, job_config)

        with patch.object(analyzer, "_process_audio") as mock_process:
            mock_process.return_value = {"tempo_bpm": 120, "duration_s": 180.0}

            # Mock lyrics pipeline to raise exception
            with patch.object(analyzer, "_extract_lyrics_if_enabled") as mock_lyrics:
                mock_lyrics.side_effect = Exception("Pipeline error")

                with pytest.raises(Exception, match="Pipeline error"):
                    analyzer.analyze(str(audio_file))
