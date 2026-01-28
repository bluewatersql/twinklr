"""Tests for AudioAnalyzer metadata integration (Phase 3).

Tests the integration of the metadata pipeline into AudioAnalyzer.
"""

from unittest.mock import patch

import pytest

from blinkb0t.core.audio.analyzer import AudioAnalyzer
from blinkb0t.core.audio.models import MetadataBundle
from blinkb0t.core.audio.models.enums import StageStatus
from blinkb0t.core.audio.models.metadata import EmbeddedMetadata, ResolvedMetadata
from blinkb0t.core.config.models import AppConfig, AudioEnhancementConfig, JobConfig


class TestAudioAnalyzerMetadataIntegration:
    """Test AudioAnalyzer metadata pipeline integration."""

    @pytest.fixture
    def app_config(self):
        """Create app config with metadata enabled."""
        config = AppConfig()
        config.audio_processing.enhancements = AudioEnhancementConfig(
            enable_metadata=True,
            enable_acoustid=False,
            enable_musicbrainz=False,
        )
        return config

    @pytest.fixture
    def job_config(self):
        """Create job config."""
        return JobConfig(checkpoint=False)

    @pytest.fixture
    def analyzer(self, app_config, job_config):
        """Create analyzer instance."""
        return AudioAnalyzer(app_config, job_config)

    def test_metadata_disabled_returns_skipped(self, app_config, job_config):
        """Metadata extraction returns SKIPPED when disabled."""
        app_config.audio_processing.enhancements.enable_metadata = False
        analyzer = AudioAnalyzer(app_config, job_config)

        bundle = analyzer._extract_metadata_if_enabled("/test/audio.mp3")

        assert bundle.stage_status == StageStatus.SKIPPED
        assert bundle.embedded.title is None

    def test_metadata_embedded_only(self, analyzer):
        """Metadata extraction with only embedded tags."""
        with patch("blinkb0t.core.audio.analyzer.MetadataPipeline") as MockPipeline:
            mock_pipeline = MockPipeline.return_value
            mock_pipeline.extract.return_value = MetadataBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.OK,
                embedded=EmbeddedMetadata(title="Test Song", artist="Test Artist"),
                resolved=ResolvedMetadata(
                    confidence=0.85,
                    title="Test Song",
                    title_confidence=0.85,
                ),
            )

            bundle = analyzer._extract_metadata_if_enabled("/test/audio.mp3")

            assert bundle.stage_status == StageStatus.OK
            assert bundle.embedded.title == "Test Song"
            assert bundle.resolved is not None
            assert bundle.resolved.title == "Test Song"

    def test_metadata_with_acoustid_enabled(self, app_config, job_config):
        """Metadata extraction with AcoustID enabled."""
        app_config.audio_processing.enhancements.enable_acoustid = True
        analyzer = AudioAnalyzer(app_config, job_config)

        with patch("blinkb0t.core.audio.analyzer.MetadataPipeline") as MockPipeline:
            mock_pipeline = MockPipeline.return_value
            mock_pipeline.extract.return_value = MetadataBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.OK,
                embedded=EmbeddedMetadata(title="Embedded"),
                resolved=ResolvedMetadata(
                    confidence=0.95,
                    title="Provider Song",
                    title_confidence=0.95,
                ),
            )

            bundle = analyzer._extract_metadata_if_enabled("/test/audio.mp3")

            # Verify pipeline configured with AcoustID enabled
            MockPipeline.assert_called_once()
            call_kwargs = MockPipeline.call_args.kwargs
            assert call_kwargs["config"].enable_acoustid is True
            assert call_kwargs["config"].enable_musicbrainz is False

            assert bundle.stage_status == StageStatus.OK
            assert bundle.resolved is not None
            assert bundle.resolved.title == "Provider Song"

    def test_metadata_with_both_providers_enabled(self, app_config, job_config):
        """Metadata extraction with both providers enabled."""
        app_config.audio_processing.enhancements.enable_acoustid = True
        app_config.audio_processing.enhancements.enable_musicbrainz = True
        analyzer = AudioAnalyzer(app_config, job_config)

        with patch("blinkb0t.core.audio.analyzer.MetadataPipeline") as MockPipeline:
            mock_pipeline = MockPipeline.return_value
            mock_pipeline.extract.return_value = MetadataBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.OK,
                embedded=EmbeddedMetadata(title="Embedded"),
                resolved=ResolvedMetadata(
                    confidence=0.98,
                    title="MusicBrainz Song",
                    title_confidence=0.98,
                ),
            )

            bundle = analyzer._extract_metadata_if_enabled("/test/audio.mp3")

            # Verify pipeline configured with both enabled
            MockPipeline.assert_called_once()
            call_kwargs = MockPipeline.call_args.kwargs
            assert call_kwargs["config"].enable_acoustid is True
            assert call_kwargs["config"].enable_musicbrainz is True

            assert bundle.stage_status == StageStatus.OK
            assert bundle.resolved is not None
            assert bundle.resolved.title == "MusicBrainz Song"

    def test_metadata_extraction_failure_handled(self, analyzer):
        """Metadata extraction failures are handled gracefully."""
        with patch("blinkb0t.core.audio.analyzer.MetadataPipeline") as MockPipeline:
            mock_pipeline = MockPipeline.return_value
            mock_pipeline.extract.side_effect = Exception("Pipeline error")

            bundle = analyzer._extract_metadata_if_enabled("/test/audio.mp3")

            assert bundle.stage_status == StageStatus.FAILED
            assert len(bundle.warnings) > 0
            assert "pipeline error" in bundle.warnings[0].lower()

    def test_api_clients_initialized_when_needed(self, app_config, job_config):
        """API clients are initialized when providers are enabled."""
        app_config.audio_processing.enhancements.enable_acoustid = True
        app_config.audio_processing.enhancements.enable_musicbrainz = True
        app_config.audio_processing.enhancements.acoustid_api_key = "test-key"
        analyzer = AudioAnalyzer(app_config, job_config)

        with (
            patch("blinkb0t.core.audio.analyzer.AcoustIDClient") as MockAcoustID,
            patch("blinkb0t.core.audio.analyzer.MusicBrainzClient") as MockMB,
            patch("blinkb0t.core.audio.analyzer.ApiClient") as MockApiClient,
            patch("blinkb0t.core.audio.analyzer.MetadataPipeline") as MockPipeline,
        ):
            mock_pipeline = MockPipeline.return_value
            mock_pipeline.extract.return_value = MetadataBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.OK,
                embedded=EmbeddedMetadata(),
            )

            analyzer._extract_metadata_if_enabled("/test/audio.mp3")

            # Verify API client created
            MockApiClient.assert_called_once()

            # Verify both clients initialized
            MockAcoustID.assert_called_once()
            MockMB.assert_called_once()

            # Verify pipeline received clients
            MockPipeline.assert_called_once()
            call_kwargs = MockPipeline.call_args.kwargs
            assert call_kwargs["acoustid_client"] is not None
            assert call_kwargs["musicbrainz_client"] is not None

    def test_api_clients_none_when_disabled(self, app_config, job_config):
        """API clients are None when providers are disabled."""
        app_config.audio_processing.enhancements.enable_acoustid = False
        app_config.audio_processing.enhancements.enable_musicbrainz = False
        analyzer = AudioAnalyzer(app_config, job_config)

        with patch("blinkb0t.core.audio.analyzer.MetadataPipeline") as MockPipeline:
            mock_pipeline = MockPipeline.return_value
            mock_pipeline.extract.return_value = MetadataBundle(
                schema_version="3.0.0",
                stage_status=StageStatus.OK,
                embedded=EmbeddedMetadata(),
            )

            analyzer._extract_metadata_if_enabled("/test/audio.mp3")

            # Verify pipeline received None for clients
            MockPipeline.assert_called_once()
            call_kwargs = MockPipeline.call_args.kwargs
            assert call_kwargs["acoustid_client"] is None
            assert call_kwargs["musicbrainz_client"] is None
