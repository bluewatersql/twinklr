"""Tests for metadata models (Phase 2).

Following TDD for Phase 2 - Embedded Metadata.
"""

from twinklr.core.audio.models.enums import StageStatus
from twinklr.core.audio.models.metadata import EmbeddedMetadata, MetadataBundle


class TestEmbeddedMetadata:
    """Test EmbeddedMetadata model."""

    def test_minimal_empty(self):
        """Minimal EmbeddedMetadata with all fields None/empty."""
        meta = EmbeddedMetadata()

        assert meta.title is None
        assert meta.artist is None
        assert meta.album is None
        assert meta.album_artist is None
        assert meta.track_number is None
        assert meta.track_total is None
        assert meta.disc_number is None
        assert meta.disc_total is None
        assert meta.date_raw is None
        assert meta.date_iso is None
        assert meta.year is None
        assert meta.genre == []
        assert meta.comment is None
        assert meta.grouping is None
        assert meta.compilation is None
        assert meta.lyrics_embedded_present is False
        assert meta.artwork_present is False
        assert meta.artwork_mime is None
        assert meta.artwork_hash_sha256 is None
        assert meta.artwork_size_bytes is None
        assert meta.warnings == []

    def test_basic_metadata(self):
        """Basic metadata with common fields."""
        meta = EmbeddedMetadata(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            year=2026,
        )

        assert meta.title == "Test Song"
        assert meta.artist == "Test Artist"
        assert meta.album == "Test Album"
        assert meta.year == 2026

    def test_track_and_disc_numbers(self):
        """Track and disc numbering."""
        meta = EmbeddedMetadata(
            track_number=5,
            track_total=12,
            disc_number=1,
            disc_total=2,
        )

        assert meta.track_number == 5
        assert meta.track_total == 12
        assert meta.disc_number == 1
        assert meta.disc_total == 2

    def test_date_fields(self):
        """Date fields (raw, ISO, year)."""
        meta = EmbeddedMetadata(
            date_raw="2026-01-27",
            date_iso="2026-01-27",
            year=2026,
        )

        assert meta.date_raw == "2026-01-27"
        assert meta.date_iso == "2026-01-27"
        assert meta.year == 2026

    def test_artwork_metadata(self):
        """Artwork metadata (not the artwork itself)."""
        meta = EmbeddedMetadata(
            artwork_present=True,
            artwork_mime="image/jpeg",
            artwork_hash_sha256="abc123def456",
            artwork_size_bytes=102400,
        )

        assert meta.artwork_present is True
        assert meta.artwork_mime == "image/jpeg"
        assert meta.artwork_hash_sha256 == "abc123def456"
        assert meta.artwork_size_bytes == 102400

    def test_serialization_round_trip(self):
        """Serialize and deserialize."""
        original = EmbeddedMetadata(
            title="Test",
            artist="Artist",
            genre=["Rock"],
            year=2026,
            artwork_present=True,
            warnings=["test warning"],
        )

        data = original.model_dump()
        restored = EmbeddedMetadata.model_validate(data)

        assert restored.title == original.title
        assert restored.artist == original.artist
        assert restored.genre == original.genre
        assert restored.year == original.year


class TestMetadataBundle:
    """Test MetadataBundle model (Phase 2 - embedded only)."""

    def test_minimal_embedded_only(self):
        """Minimal MetadataBundle with just embedded metadata."""
        bundle = MetadataBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            embedded=EmbeddedMetadata(title="Test"),
        )

        assert bundle.schema_version == "3.0.0"
        assert bundle.stage_status == StageStatus.OK
        assert bundle.embedded.title == "Test"
        assert bundle.fingerprint is None
        assert bundle.resolved is None
        assert bundle.candidates == []
        assert bundle.provenance == {}
        assert bundle.warnings == []

    def test_status_skipped(self):
        """MetadataBundle with SKIPPED status (feature disabled)."""
        bundle = MetadataBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.SKIPPED,
            embedded=EmbeddedMetadata(),
        )

        assert bundle.stage_status == StageStatus.SKIPPED

    def test_status_failed(self):
        """MetadataBundle with FAILED status."""
        bundle = MetadataBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.FAILED,
            embedded=EmbeddedMetadata(),
            warnings=["Could not read file tags"],
        )

        assert bundle.stage_status == StageStatus.FAILED
        assert len(bundle.warnings) == 1

    def test_provenance_tracking(self):
        """Provenance metadata."""
        bundle = MetadataBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            embedded=EmbeddedMetadata(title="Test"),
            provenance={
                "extracted_at": "2026-01-27T00:00:00Z",
                "mutagen_version": "1.47.0",
            },
        )

        assert "extracted_at" in bundle.provenance
        assert bundle.provenance["mutagen_version"] == "1.47.0"

    def test_serialization_round_trip(self):
        """Serialize and deserialize MetadataBundle."""
        original = MetadataBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            embedded=EmbeddedMetadata(
                title="Test Song",
                artist="Test Artist",
                year=2026,
            ),
            warnings=["Low confidence"],
        )

        data = original.model_dump()
        restored = MetadataBundle.model_validate(data)

        assert restored.schema_version == original.schema_version
        assert restored.stage_status == original.stage_status
        assert restored.embedded.title == original.embedded.title
        assert restored.warnings == original.warnings
