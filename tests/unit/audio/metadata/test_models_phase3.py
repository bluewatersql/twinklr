"""Tests for Phase 3 metadata models.

Testing FingerprintInfo, ResolvedMBIDs, ResolvedMetadata, MetadataCandidate.
"""

from twinklr.core.audio.models.enums import StageStatus
from twinklr.core.audio.models.metadata import (
    FingerprintInfo,
    MetadataCandidate,
    ResolvedMBIDs,
    ResolvedMetadata,
)


class TestFingerprintInfo:
    """Test FingerprintInfo model."""

    def test_minimal_fingerprint_info(self):
        """Minimal FingerprintInfo with just audio_fingerprint."""
        info = FingerprintInfo(audio_fingerprint="abc123")

        assert info.audio_fingerprint == "abc123"
        assert info.chromaprint_fingerprint is None
        assert info.chromaprint_duration_s is None
        assert info.chromaprint_duration_bucket is None

    def test_complete_fingerprint_info(self):
        """Complete FingerprintInfo with chromaprint data."""
        info = FingerprintInfo(
            audio_fingerprint="abc123",
            chromaprint_fingerprint="AQADtE...",
            chromaprint_duration_s=180.5,
            chromaprint_duration_bucket=180.5,
        )

        assert info.audio_fingerprint == "abc123"
        assert info.chromaprint_fingerprint == "AQADtE..."
        assert info.chromaprint_duration_s == 180.5
        assert info.chromaprint_duration_bucket == 180.5

    def test_empty_mbids(self):
        """Empty ResolvedMBIDs with no IDs."""
        mbids = ResolvedMBIDs()

        assert mbids.recording_mbid is None
        assert mbids.release_mbid is None
        assert mbids.artist_mbids == []
        assert mbids.work_mbid is None

    def test_complete_mbids(self):
        """Complete ResolvedMBIDs with all IDs."""
        mbids = ResolvedMBIDs(
            recording_mbid="rec-1234",
            release_mbid="rel-5678",
            artist_mbids=["art-1111", "art-2222"],
            work_mbid="work-9999",
        )

        assert mbids.recording_mbid == "rec-1234"
        assert mbids.release_mbid == "rel-5678"
        assert mbids.artist_mbids == ["art-1111", "art-2222"]
        assert mbids.work_mbid == "work-9999"

    def test_minimal_resolved_metadata(self):
        """Minimal ResolvedMetadata."""
        resolved = ResolvedMetadata(
            confidence=0.85,
            title="Test Song",
            title_confidence=0.90,
        )

        assert resolved.confidence == 0.85
        assert resolved.title == "Test Song"
        assert resolved.title_confidence == 0.90
        # Default values
        assert resolved.artist is None
        assert resolved.album is None
        assert resolved.mbids == ResolvedMBIDs()

    def test_complete_resolved_metadata(self):
        """Complete ResolvedMetadata with all fields."""
        resolved = ResolvedMetadata(
            confidence=0.92,
            title="Complete Song",
            title_confidence=0.95,
            artist="Test Artist",
            artist_confidence=0.93,
            album="Test Album",
            album_confidence=0.88,
            duration_ms=180000,
            duration_confidence=0.95,
            mbids=ResolvedMBIDs(
                recording_mbid="rec-123",
                release_mbid="rel-456",
            ),
            acoustid_id="acoustid-789",
            isrc="US1234567890",
        )

        assert resolved.title == "Complete Song"
        assert resolved.artist == "Test Artist"
        assert resolved.album == "Test Album"
        assert resolved.duration_ms == 180000
        assert resolved.mbids.recording_mbid == "rec-123"
        assert resolved.acoustid_id == "acoustid-789"
        assert resolved.isrc == "US1234567890"

    def test_minimal_candidate(self):
        """Minimal MetadataCandidate."""
        candidate = MetadataCandidate(
            provider="acoustid",
            provider_id="acoustid-123",
            score=0.75,
        )

        assert candidate.provider == "acoustid"
        assert candidate.provider_id == "acoustid-123"
        assert candidate.score == 0.75
        # Defaults
        assert candidate.duration_ms is None
        assert candidate.title is None
        assert candidate.mbids == ResolvedMBIDs()
        assert candidate.raw == {}

    def test_complete_candidate(self):
        """Complete MetadataCandidate with all fields."""
        candidate = MetadataCandidate(
            provider="musicbrainz",
            provider_id="mb-rec-123",
            score=0.92,
            duration_ms=180000,
            title="Candidate Song",
            artist="Candidate Artist",
            album="Candidate Album",
            mbids=ResolvedMBIDs(recording_mbid="rec-123"),
            acoustid_id="acoustid-789",
            isrc="US1234567890",
            raw={"source": "test"},
        )

        assert candidate.provider == "musicbrainz"
        assert candidate.score == 0.92
        assert candidate.title == "Candidate Song"
        assert candidate.artist == "Candidate Artist"
        assert candidate.album == "Candidate Album"
        assert candidate.duration_ms == 180000
        assert candidate.mbids.recording_mbid == "rec-123"
        assert candidate.acoustid_id == "acoustid-789"
        assert candidate.isrc == "US1234567890"
        assert candidate.raw == {"source": "test"}

    def test_metadata_bundle_with_fingerprint(self):
        """MetadataBundle includes fingerprint."""
        from twinklr.core.audio.models.metadata import EmbeddedMetadata, MetadataBundle

        bundle = MetadataBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            embedded=EmbeddedMetadata(),
            fingerprint=FingerprintInfo(
                audio_fingerprint="abc123",
                chromaprint_fingerprint="AQADtE...",
                chromaprint_duration_s=180.5,
            ),
        )

        assert bundle.fingerprint is not None
        assert bundle.fingerprint.audio_fingerprint == "abc123"
        assert bundle.fingerprint.chromaprint_fingerprint == "AQADtE..."

    def test_metadata_bundle_with_resolved(self):
        """MetadataBundle includes resolved metadata."""
        from twinklr.core.audio.models.metadata import EmbeddedMetadata, MetadataBundle

        resolved = ResolvedMetadata(
            confidence=0.92,
            title="Resolved Song",
            title_confidence=0.95,
            artist="Resolved Artist",
            artist_confidence=0.93,
        )

        bundle = MetadataBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            embedded=EmbeddedMetadata(),
            fingerprint=FingerprintInfo(audio_fingerprint="abc123"),
            resolved=resolved,
        )

        assert bundle.resolved is not None
        assert bundle.resolved.title == "Resolved Song"
        assert bundle.resolved.artist == "Resolved Artist"
        assert bundle.resolved.confidence == 0.92

    def test_metadata_bundle_with_candidates(self):
        """MetadataBundle includes candidate list."""
        from twinklr.core.audio.models.metadata import EmbeddedMetadata, MetadataBundle

        candidates = [
            MetadataCandidate(
                provider="acoustid",
                provider_id="aid-123",
                score=0.88,
                title="Candidate 1",
            ),
            MetadataCandidate(
                provider="musicbrainz",
                provider_id="mb-456",
                score=0.92,
                title="Candidate 2",
            ),
        ]

        bundle = MetadataBundle(
            schema_version="3.0.0",
            stage_status=StageStatus.OK,
            embedded=EmbeddedMetadata(),
            fingerprint=FingerprintInfo(audio_fingerprint="abc123"),
            candidates=candidates,
        )

        assert len(bundle.candidates) == 2
        assert bundle.candidates[0].title == "Candidate 1"
        assert bundle.candidates[1].title == "Candidate 2"
