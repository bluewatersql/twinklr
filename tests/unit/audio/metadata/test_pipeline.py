"""Tests for metadata pipeline orchestration (Phase 3).

Testing the full metadata extraction pipeline that orchestrates:
1. Embedded metadata extraction
2. Fingerprinting (chromaprint)
3. AcoustID lookup
4. MusicBrainz lookup
5. Metadata merging
"""

from unittest.mock import MagicMock, patch

import pytest

from blinkb0t.core.audio.metadata.pipeline import MetadataPipeline, PipelineConfig
from blinkb0t.core.audio.models import MetadataBundle
from blinkb0t.core.audio.models.enums import StageStatus
from blinkb0t.core.audio.models.metadata import (
    EmbeddedMetadata,
)


class TestPipelineConfig:
    """Test PipelineConfig model."""

    def test_default_config(self):
        """Default configuration has all features enabled."""
        config = PipelineConfig()

        assert config.enable_acoustid is True
        assert config.enable_musicbrainz is True
        assert config.chromaprint_timeout_s == 30.0

    def test_custom_config(self):
        """Custom configuration."""
        config = PipelineConfig(
            enable_acoustid=False,
            enable_musicbrainz=False,
            chromaprint_timeout_s=10.0,
        )

        assert config.enable_acoustid is False
        assert config.enable_musicbrainz is False
        assert config.chromaprint_timeout_s == 10.0


class TestMetadataPipeline:
    """Test MetadataPipeline orchestration."""

    @pytest.fixture
    def mock_acoustid_client(self):
        """Mock AcoustID client."""
        return MagicMock()

    @pytest.fixture
    def mock_musicbrainz_client(self):
        """Mock MusicBrainz client."""
        return MagicMock()

    @pytest.fixture
    def pipeline(self, mock_acoustid_client, mock_musicbrainz_client):
        """Create pipeline with mock clients."""
        config = PipelineConfig()
        return MetadataPipeline(
            config=config,
            acoustid_client=mock_acoustid_client,
            musicbrainz_client=mock_musicbrainz_client,
        )

    def test_pipeline_embedded_only(self, pipeline):
        """Pipeline with only embedded metadata (no providers)."""
        # Configure to skip providers
        pipeline.config.enable_acoustid = False
        pipeline.config.enable_musicbrainz = False

        # Mock embedded metadata
        with patch(
            "blinkb0t.core.audio.metadata.pipeline.extract_embedded_metadata"
        ) as mock_extract:
            mock_extract.return_value = EmbeddedMetadata(
                title="Test Song",
                artist="Test Artist",
            )

            # Run pipeline
            bundle = pipeline.extract("/test/audio.mp3")

            # Verify bundle
            assert isinstance(bundle, MetadataBundle)
            assert bundle.stage_status == StageStatus.OK
            assert bundle.embedded.title == "Test Song"
            assert bundle.fingerprint is None
            assert bundle.candidates == []
            assert bundle.resolved is not None
            assert bundle.resolved.title == "Test Song"

    def test_pipeline_with_fingerprint(self, pipeline):
        """Pipeline computes fingerprint when enabled."""
        # Configure to skip providers but enable fingerprint
        pipeline.config.enable_acoustid = False
        pipeline.config.enable_musicbrainz = False

        # Mock embedded and fingerprint
        with (
            patch(
                "blinkb0t.core.audio.metadata.pipeline.extract_embedded_metadata"
            ) as mock_extract,
            patch(
                "blinkb0t.core.audio.metadata.pipeline.compute_chromaprint_fingerprint"
            ) as mock_fingerprint,
            patch("blinkb0t.core.audio.metadata.pipeline.compute_file_hash") as mock_hash,
        ):
            mock_extract.return_value = EmbeddedMetadata(title="Test")
            mock_fingerprint.return_value = ("FINGERPRINT123", 180.5)
            mock_hash.return_value = "abc123hash"

            # Run pipeline
            bundle = pipeline.extract("/test/audio.mp3")

            # Verify fingerprint computed
            assert bundle.fingerprint is not None
            assert bundle.fingerprint.audio_fingerprint == "abc123hash"
            assert bundle.fingerprint.chromaprint_fingerprint == "FINGERPRINT123"
            assert bundle.fingerprint.chromaprint_duration_s == 180.5

    def test_pipeline_with_acoustid(self, pipeline, mock_acoustid_client):
        """Pipeline queries AcoustID when enabled."""
        # Configure to enable AcoustID only
        pipeline.config.enable_musicbrainz = False

        # Mock responses
        from blinkb0t.core.api.audio.models import AcoustIDRecording, AcoustIDResponse

        mock_acoustid_client.lookup.return_value = AcoustIDResponse(
            status="ok",
            results=[
                AcoustIDRecording(
                    id="aid-1",
                    score=0.95,
                    title="Provider Song",
                    artists=["Provider Artist"],
                    recording_mbid="rec-123",
                )
            ],
        )

        with (
            patch(
                "blinkb0t.core.audio.metadata.pipeline.extract_embedded_metadata"
            ) as mock_extract,
            patch(
                "blinkb0t.core.audio.metadata.pipeline.compute_chromaprint_fingerprint"
            ) as mock_fingerprint,
            patch("blinkb0t.core.audio.metadata.pipeline.compute_file_hash") as mock_hash,
        ):
            mock_extract.return_value = EmbeddedMetadata(title="Embedded")
            mock_fingerprint.return_value = ("FP123", 180.0)
            mock_hash.return_value = "hash123"

            # Run pipeline
            bundle = pipeline.extract("/test/audio.mp3")

            # Verify AcoustID called
            mock_acoustid_client.lookup.assert_called_once_with(
                fingerprint="FP123",
                duration_s=180.0,
            )

            # Verify candidate added
            assert len(bundle.candidates) == 1
            assert bundle.candidates[0].provider == "acoustid"
            assert bundle.candidates[0].title == "Provider Song"

    def test_pipeline_with_musicbrainz(
        self, pipeline, mock_acoustid_client, mock_musicbrainz_client
    ):
        """Pipeline queries MusicBrainz when MBID available from AcoustID."""
        # Mock AcoustID returning MBID
        from blinkb0t.core.api.audio.models import (
            AcoustIDRecording,
            AcoustIDResponse,
            MusicBrainzRecording,
        )

        mock_acoustid_client.lookup.return_value = AcoustIDResponse(
            status="ok",
            results=[
                AcoustIDRecording(
                    id="aid-1",
                    score=0.95,
                    title="AID Song",
                    recording_mbid="rec-123",
                )
            ],
        )

        mock_musicbrainz_client.lookup_recording.return_value = MusicBrainzRecording(
            id="rec-123",
            title="MB Song",
            artists=["MB Artist"],
            isrc="ISRC123",
        )

        with (
            patch(
                "blinkb0t.core.audio.metadata.pipeline.extract_embedded_metadata"
            ) as mock_extract,
            patch(
                "blinkb0t.core.audio.metadata.pipeline.compute_chromaprint_fingerprint"
            ) as mock_fingerprint,
            patch("blinkb0t.core.audio.metadata.pipeline.compute_file_hash") as mock_hash,
        ):
            mock_extract.return_value = EmbeddedMetadata(title="Embedded")
            mock_fingerprint.return_value = ("FP123", 180.0)
            mock_hash.return_value = "hash123"

            # Run pipeline
            bundle = pipeline.extract("/test/audio.mp3")

            # Verify MusicBrainz called
            mock_musicbrainz_client.lookup_recording.assert_called_once_with(mbid="rec-123")

            # Verify both candidates added
            assert len(bundle.candidates) == 2
            assert bundle.candidates[0].provider == "acoustid"
            assert bundle.candidates[1].provider == "musicbrainz"
            assert bundle.candidates[1].title == "MB Song"

    def test_pipeline_full_flow(self, pipeline, mock_acoustid_client, mock_musicbrainz_client):
        """Pipeline with full flow: embedded + fingerprint + both providers."""
        # Mock responses
        from blinkb0t.core.api.audio.models import (
            AcoustIDRecording,
            AcoustIDResponse,
            MusicBrainzRecording,
        )

        mock_acoustid_client.lookup.return_value = AcoustIDResponse(
            status="ok",
            results=[
                AcoustIDRecording(
                    id="aid-1",
                    score=0.95,
                    title="AID Song",
                    recording_mbid="rec-123",
                )
            ],
        )

        mock_musicbrainz_client.lookup_recording.return_value = MusicBrainzRecording(
            id="rec-123",
            title="MB Song",
            artists=["MB Artist"],
        )

        with (
            patch(
                "blinkb0t.core.audio.metadata.pipeline.extract_embedded_metadata"
            ) as mock_extract,
            patch(
                "blinkb0t.core.audio.metadata.pipeline.compute_chromaprint_fingerprint"
            ) as mock_fingerprint,
            patch("blinkb0t.core.audio.metadata.pipeline.compute_file_hash") as mock_hash,
        ):
            mock_extract.return_value = EmbeddedMetadata(title="Embedded")
            mock_fingerprint.return_value = ("FP123", 180.0)
            mock_hash.return_value = "hash123"

            # Run pipeline
            bundle = pipeline.extract("/test/audio.mp3")

            # Verify both providers called
            mock_acoustid_client.lookup.assert_called_once()
            mock_musicbrainz_client.lookup_recording.assert_called_once()

            # Verify both candidates added
            assert len(bundle.candidates) == 2
            providers = {c.provider for c in bundle.candidates}
            assert providers == {"acoustid", "musicbrainz"}

            # Verify merged result
            assert bundle.resolved is not None
            assert bundle.stage_status == StageStatus.OK

    def test_pipeline_fingerprint_error_handled(self, pipeline):
        """Pipeline handles fingerprint errors gracefully."""
        pipeline.config.enable_acoustid = False
        pipeline.config.enable_musicbrainz = False

        with (
            patch(
                "blinkb0t.core.audio.metadata.pipeline.extract_embedded_metadata"
            ) as mock_extract,
            patch(
                "blinkb0t.core.audio.metadata.pipeline.compute_chromaprint_fingerprint"
            ) as mock_fingerprint,
            patch("blinkb0t.core.audio.metadata.pipeline.compute_file_hash") as mock_hash,
        ):
            mock_extract.return_value = EmbeddedMetadata(title="Test")
            mock_fingerprint.side_effect = Exception("fpcalc error")
            mock_hash.return_value = "hash123"

            # Run pipeline
            bundle = pipeline.extract("/test/audio.mp3")

            # Pipeline succeeds, but fingerprint is partial
            assert bundle.stage_status == StageStatus.OK
            assert bundle.fingerprint is not None
            assert bundle.fingerprint.audio_fingerprint == "hash123"
            assert bundle.fingerprint.chromaprint_fingerprint is None
            assert "fingerprint" in bundle.warnings[0].lower()

    def test_pipeline_acoustid_error_handled(self, pipeline, mock_acoustid_client):
        """Pipeline handles AcoustID errors gracefully."""
        pipeline.config.enable_musicbrainz = False

        # AcoustID fails
        from blinkb0t.core.api.audio.acoustid import AcoustIDError

        mock_acoustid_client.lookup.side_effect = AcoustIDError("API error")

        with (
            patch(
                "blinkb0t.core.audio.metadata.pipeline.extract_embedded_metadata"
            ) as mock_extract,
            patch(
                "blinkb0t.core.audio.metadata.pipeline.compute_chromaprint_fingerprint"
            ) as mock_fingerprint,
            patch("blinkb0t.core.audio.metadata.pipeline.compute_file_hash") as mock_hash,
        ):
            mock_extract.return_value = EmbeddedMetadata(title="Test")
            mock_fingerprint.return_value = ("FP123", 180.0)
            mock_hash.return_value = "hash123"

            # Run pipeline
            bundle = pipeline.extract("/test/audio.mp3")

            # Pipeline succeeds, AcoustID skipped
            assert bundle.stage_status == StageStatus.OK
            assert bundle.candidates == []
            assert "acoustid" in bundle.warnings[0].lower()

    def test_pipeline_musicbrainz_error_handled(
        self, pipeline, mock_acoustid_client, mock_musicbrainz_client
    ):
        """Pipeline handles MusicBrainz errors gracefully."""
        # AcoustID returns MBID but MusicBrainz fails
        from blinkb0t.core.api.audio.models import AcoustIDRecording, AcoustIDResponse
        from blinkb0t.core.api.audio.musicbrainz import MusicBrainzError

        mock_acoustid_client.lookup.return_value = AcoustIDResponse(
            status="ok",
            results=[AcoustIDRecording(id="aid-1", score=0.95, recording_mbid="rec-123")],
        )

        mock_musicbrainz_client.lookup_recording.side_effect = MusicBrainzError("API error")

        with (
            patch(
                "blinkb0t.core.audio.metadata.pipeline.extract_embedded_metadata"
            ) as mock_extract,
            patch(
                "blinkb0t.core.audio.metadata.pipeline.compute_chromaprint_fingerprint"
            ) as mock_fingerprint,
            patch("blinkb0t.core.audio.metadata.pipeline.compute_file_hash") as mock_hash,
        ):
            mock_extract.return_value = EmbeddedMetadata(title="Test")
            mock_fingerprint.return_value = ("FP123", 180.0)
            mock_hash.return_value = "hash123"

            # Run pipeline
            bundle = pipeline.extract("/test/audio.mp3")

            # Pipeline succeeds, MusicBrainz skipped
            assert bundle.stage_status == StageStatus.OK
            assert len(bundle.candidates) == 1  # Only AcoustID
            assert bundle.candidates[0].provider == "acoustid"
            assert "musicbrainz" in bundle.warnings[0].lower()

    def test_pipeline_embedded_extraction_fails(self, pipeline):
        """Pipeline fails if embedded extraction fails."""
        with (
            patch(
                "blinkb0t.core.audio.metadata.pipeline.extract_embedded_metadata"
            ) as mock_extract,
            patch("blinkb0t.core.audio.metadata.pipeline.compute_file_hash") as mock_hash,
        ):
            mock_extract.side_effect = Exception("File read error")
            mock_hash.return_value = "hash123"

            # Run pipeline
            bundle = pipeline.extract("/test/audio.mp3")

            # Pipeline marks as failed
            assert bundle.stage_status == StageStatus.FAILED
            assert "embedded metadata" in bundle.warnings[0].lower()
            assert bundle.embedded.title is None  # Empty fallback
            assert bundle.embedded.artist is None

    def test_pipeline_skips_providers_without_fingerprint(
        self, pipeline, mock_acoustid_client, mock_musicbrainz_client
    ):
        """Pipeline skips AcoustID if chromaprint fails."""
        with (
            patch(
                "blinkb0t.core.audio.metadata.pipeline.extract_embedded_metadata"
            ) as mock_extract,
            patch(
                "blinkb0t.core.audio.metadata.pipeline.compute_chromaprint_fingerprint"
            ) as mock_fingerprint,
            patch("blinkb0t.core.audio.metadata.pipeline.compute_file_hash") as mock_hash,
        ):
            mock_extract.return_value = EmbeddedMetadata(title="Test")
            mock_fingerprint.side_effect = Exception("fpcalc not found")
            mock_hash.return_value = "hash123"

            # Run pipeline
            bundle = pipeline.extract("/test/audio.mp3")

            # AcoustID not called (no chromaprint fingerprint)
            mock_acoustid_client.lookup.assert_not_called()

            # Pipeline still succeeds with embedded only
            assert bundle.stage_status == StageStatus.OK
            assert bundle.resolved is not None
            # Fingerprint has audio hash but no chromaprint
            assert bundle.fingerprint is not None
            assert bundle.fingerprint.audio_fingerprint == "hash123"
            assert bundle.fingerprint.chromaprint_fingerprint is None
