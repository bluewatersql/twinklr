"""Tests for audio API client models (Phase 3).

Testing AcoustID and MusicBrainz request/response models.
"""

from twinklr.core.api.audio.models import (
    AcoustIDRecording,
    AcoustIDResponse,
    MusicBrainzRecording,
    MusicBrainzRelease,
)


class TestAcoustIDRecording:
    """Test AcoustIDRecording model."""

    def test_minimal_recording(self):
        """Minimal AcoustID recording with just ID."""
        recording = AcoustIDRecording(
            id="acoustid-123",
            score=0.95,
        )

        assert recording.id == "acoustid-123"
        assert recording.score == 0.95
        assert recording.title is None
        assert recording.artists == []
        assert recording.duration_ms is None
        assert recording.recording_mbid is None

    def test_complete_recording(self):
        """Complete AcoustID recording with all fields."""
        recording = AcoustIDRecording(
            id="acoustid-123",
            score=0.95,
            title="Test Song",
            artists=["Artist 1", "Artist 2"],
            duration_ms=180000,
            recording_mbid="rec-mbid-123",
            release_mbid="rel-mbid-456",
        )

        assert recording.id == "acoustid-123"
        assert recording.score == 0.95
        assert recording.title == "Test Song"
        assert recording.artists == ["Artist 1", "Artist 2"]
        assert recording.duration_ms == 180000
        assert recording.recording_mbid == "rec-mbid-123"
        assert recording.release_mbid == "rel-mbid-456"

    def test_empty_response(self):
        """Empty AcoustID response with no results."""
        response = AcoustIDResponse(
            status="ok",
            results=[],
        )

        assert response.status == "ok"
        assert response.results == []

    def test_response_with_results(self):
        """AcoustID response with multiple results."""
        response = AcoustIDResponse(
            status="ok",
            results=[
                AcoustIDRecording(id="aid-1", score=0.95, title="Song 1"),
                AcoustIDRecording(id="aid-2", score=0.88, title="Song 2"),
            ],
        )

        assert response.status == "ok"
        assert len(response.results) == 2
        assert response.results[0].title == "Song 1"
        assert response.results[1].title == "Song 2"

    def test_error_response(self):
        """AcoustID error response."""
        response = AcoustIDResponse(
            status="error",
            results=[],
            error="Invalid API key",
        )

        assert response.status == "error"
        assert response.error == "Invalid API key"


class TestMusicBrainzRelease:
    """Test MusicBrainzRelease model."""

    def test_minimal_release(self):
        """Minimal MusicBrainz release."""
        release = MusicBrainzRelease(
            id="rel-123",
            title="Test Album",
        )

        assert release.id == "rel-123"
        assert release.title == "Test Album"
        assert release.date is None
        assert release.country is None

    def test_complete_release(self):
        """Complete MusicBrainz release."""
        release = MusicBrainzRelease(
            id="rel-123",
            title="Test Album",
            date="2024-01-15",
            country="US",
        )

        assert release.id == "rel-123"
        assert release.title == "Test Album"
        assert release.date == "2024-01-15"
        assert release.country == "US"


class TestMusicBrainzRecording:
    """Test MusicBrainzRecording model."""

    def test_minimal_recording(self):
        """Minimal MusicBrainz recording with just ID and title."""
        recording = MusicBrainzRecording(
            id="rec-123",
            title="Test Song",
        )

        assert recording.id == "rec-123"
        assert recording.title == "Test Song"
        assert recording.artists == []
        assert recording.length_ms is None
        assert recording.isrc is None
        assert recording.releases == []

    def test_complete_recording(self):
        """Complete MusicBrainz recording with all fields."""
        recording = MusicBrainzRecording(
            id="rec-123",
            title="Test Song",
            artists=["Artist 1", "Artist 2"],
            length_ms=180000,
            isrc="US1234567890",
            releases=[
                MusicBrainzRelease(id="rel-1", title="Album 1"),
                MusicBrainzRelease(id="rel-2", title="Album 2", date="2024-01-01"),
            ],
        )

        assert recording.id == "rec-123"
        assert recording.title == "Test Song"
        assert recording.artists == ["Artist 1", "Artist 2"]
        assert recording.length_ms == 180000
        assert recording.isrc == "US1234567890"
        assert len(recording.releases) == 2
        assert recording.releases[0].title == "Album 1"
        assert recording.releases[1].date == "2024-01-01"
