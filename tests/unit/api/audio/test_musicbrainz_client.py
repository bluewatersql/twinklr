"""Tests for MusicBrainz API client (Phase 3).

Testing MusicBrainz recording lookup with mocked HTTP responses.
"""

from unittest.mock import AsyncMock

import pytest

from twinklr.core.api.audio.models import MusicBrainzRecording
from twinklr.core.api.audio.musicbrainz import MusicBrainzClient, MusicBrainzError


class TestMusicBrainzClient:
    """Test MusicBrainzClient."""

    @pytest.fixture
    def mock_http_client(self):
        """Mock async HTTP client."""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def client(self, mock_http_client):
        """Create MusicBrainz client with mock HTTP client."""
        return MusicBrainzClient(
            http_client=mock_http_client,
            user_agent="twinklr-test/1.0",
        )

    def test_init_requires_user_agent(self, mock_http_client):
        """User agent is required."""
        with pytest.raises(ValueError, match="user agent is required"):
            MusicBrainzClient(http_client=mock_http_client, user_agent="")

        with pytest.raises(ValueError, match="user agent is required"):
            MusicBrainzClient(http_client=mock_http_client, user_agent=None)

    async def test_lookup_recording_successful(self, client, mock_http_client):
        """Successful recording lookup by MBID."""
        # Mock HTTP response
        mock_response = {
            "id": "rec-mbid-123",
            "title": "Test Song",
            "length": 180000,
            "artist-credit": [
                {"name": "Artist 1"},
                {"name": "Artist 2"},
            ],
            "isrcs": ["US1234567890"],
            "releases": [
                {
                    "id": "rel-mbid-456",
                    "title": "Test Album",
                    "date": "2024-01-15",
                    "country": "US",
                }
            ],
        }
        mock_http_client.get.return_value = mock_response

        # Call lookup
        recording = await client.lookup_recording(mbid="rec-mbid-123")

        # Verify HTTP call
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert "https://musicbrainz.org/ws/2/recording/rec-mbid-123" in call_args[0][0]
        params = call_args[1]["params"]
        assert params["fmt"] == "json"
        assert params["inc"] == "artists+releases+isrcs"

        headers = call_args[1]["headers"]
        assert headers["User-Agent"] == "twinklr-test/1.0"

        # Verify response
        assert isinstance(recording, MusicBrainzRecording)
        assert recording.id == "rec-mbid-123"
        assert recording.title == "Test Song"
        assert recording.length_ms == 180000
        assert recording.artists == ["Artist 1", "Artist 2"]
        assert recording.isrc == "US1234567890"
        assert len(recording.releases) == 1
        assert recording.releases[0].title == "Test Album"

    async def test_lookup_recording_minimal(self, client, mock_http_client):
        """Lookup recording with minimal fields."""
        mock_response = {
            "id": "rec-123",
            "title": "Minimal Song",
        }
        mock_http_client.get.return_value = mock_response

        recording = await client.lookup_recording(mbid="rec-123")

        assert recording.id == "rec-123"
        assert recording.title == "Minimal Song"
        assert recording.artists == []
        assert recording.length_ms is None
        assert recording.isrc is None
        assert recording.releases == []

    async def test_lookup_recording_multiple_artists(self, client, mock_http_client):
        """Recording with multiple artists."""
        mock_response = {
            "id": "rec-123",
            "title": "Collab Song",
            "artist-credit": [
                {"name": "A1"},
                {"name": "A2"},
                {"name": "A3"},
            ],
        }
        mock_http_client.get.return_value = mock_response

        recording = await client.lookup_recording(mbid="rec-123")

        assert recording.artists == ["A1", "A2", "A3"]

    async def test_lookup_recording_multiple_releases(self, client, mock_http_client):
        """Recording appears on multiple releases."""
        mock_response = {
            "id": "rec-123",
            "title": "Popular Song",
            "releases": [
                {"id": "rel-1", "title": "Album 1", "date": "2024-01-01"},
                {"id": "rel-2", "title": "Album 2", "date": "2024-06-01"},
                {"id": "rel-3", "title": "Compilation"},
            ],
        }
        mock_http_client.get.return_value = mock_response

        recording = await client.lookup_recording(mbid="rec-123")

        assert len(recording.releases) == 3
        assert recording.releases[0].title == "Album 1"
        assert recording.releases[1].date == "2024-06-01"
        assert recording.releases[2].date is None

    async def test_lookup_recording_multiple_isrcs(self, client, mock_http_client):
        """Recording has multiple ISRCs (use first)."""
        mock_response = {
            "id": "rec-123",
            "title": "Song",
            "isrcs": ["ISRC1", "ISRC2", "ISRC3"],
        }
        mock_http_client.get.return_value = mock_response

        recording = await client.lookup_recording(mbid="rec-123")

        # Use first ISRC
        assert recording.isrc == "ISRC1"

    async def test_lookup_recording_no_isrcs(self, client, mock_http_client):
        """Recording has no ISRCs."""
        mock_response = {
            "id": "rec-123",
            "title": "Song",
            "isrcs": [],
        }
        mock_http_client.get.return_value = mock_response

        recording = await client.lookup_recording(mbid="rec-123")

        assert recording.isrc is None

    async def test_lookup_recording_api_error(self, client, mock_http_client):
        """MusicBrainz API returns error response."""
        from twinklr.core.api.http.errors import ClientError

        mock_http_client.get.side_effect = ClientError(
            message="Recording not found",
            method="GET",
            url="https://musicbrainz.org/ws/2/recording/invalid",
            status_code=404,
        )

        with pytest.raises(MusicBrainzError, match="MusicBrainz HTTP error"):
            await client.lookup_recording(mbid="invalid-mbid")

    async def test_lookup_recording_http_error(self, client, mock_http_client):
        """HTTP request fails."""
        from twinklr.core.api.http.errors import ServerError

        mock_http_client.get.side_effect = ServerError(
            message="Server error",
            method="GET",
            url="https://musicbrainz.org/ws/2/recording/rec-123",
            status_code=500,
        )

        with pytest.raises(MusicBrainzError, match="MusicBrainz HTTP error"):
            await client.lookup_recording(mbid="rec-123")

    async def test_lookup_recording_timeout(self, client, mock_http_client):
        """Request times out."""
        from twinklr.core.api.http.errors import TimeoutError as HTTPTimeoutError

        mock_http_client.get.side_effect = HTTPTimeoutError(
            message="Request timed out",
            method="GET",
            url="https://musicbrainz.org/ws/2/recording/rec-123",
        )

        with pytest.raises(MusicBrainzError, match="MusicBrainz request timed out"):
            await client.lookup_recording(mbid="rec-123")

    async def test_lookup_recording_invalid_response(self, client, mock_http_client):
        """API returns invalid/malformed response."""
        # Missing required fields
        mock_http_client.get.return_value = {"invalid": "response"}

        with pytest.raises(MusicBrainzError, match="Invalid response from MusicBrainz"):
            await client.lookup_recording(mbid="rec-123")

    async def test_lookup_recording_rate_limit_warning(self, client, mock_http_client, caplog):
        """Rate limiting is mentioned in documentation."""
        import logging

        caplog.set_level(logging.DEBUG)

        mock_response = {"id": "rec-123", "title": "Song"}
        mock_http_client.get.return_value = mock_response

        await client.lookup_recording(mbid="rec-123")

        # Check that rate limiting is mentioned in debug logs
        assert any("rate limit" in record.message.lower() for record in caplog.records)

    def test_parse_artist_credit_multiple(self, client):
        """Parse multiple artists."""
        artist_credit = [
            {"name": "Artist 1"},
            {"name": "Artist 2"},
            {"name": "Artist 3"},
        ]
        artists = client._parse_artist_credit(artist_credit)
        assert artists == ["Artist 1", "Artist 2", "Artist 3"]

    def test_parse_artist_credit_missing_name(self, client):
        """Skip artist entries without name."""
        artist_credit = [
            {"name": "Artist 1"},
            {"invalid": "no-name"},
            {"name": "Artist 2"},
        ]
        artists = client._parse_artist_credit(artist_credit)
        assert artists == ["Artist 1", "Artist 2"]
