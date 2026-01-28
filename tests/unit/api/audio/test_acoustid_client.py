"""Tests for AcoustID API client (Phase 3).

Testing AcoustID fingerprint lookup with mocked HTTP responses.
"""

from unittest.mock import MagicMock

import pytest

from blinkb0t.core.api.audio.acoustid import AcoustIDClient, AcoustIDError
from blinkb0t.core.api.audio.models import AcoustIDResponse


class TestAcoustIDClient:
    """Test AcoustIDClient."""

    @pytest.fixture
    def mock_http_client(self):
        """Mock HTTP client."""
        return MagicMock()

    @pytest.fixture
    def client(self, mock_http_client):
        """Create AcoustID client with mock HTTP client."""
        return AcoustIDClient(
            api_key="test_api_key_123",
            http_client=mock_http_client,
        )

    def test_init_requires_api_key(self, mock_http_client):
        """API key is required."""
        with pytest.raises(ValueError, match="API key is required"):
            AcoustIDClient(api_key="", http_client=mock_http_client)

        with pytest.raises(ValueError, match="API key is required"):
            AcoustIDClient(api_key=None, http_client=mock_http_client)

    def test_lookup_successful(self, client, mock_http_client):
        """Successful fingerprint lookup."""
        # Mock HTTP response
        mock_response = {
            "status": "ok",
            "results": [
                {
                    "id": "acoustid-1",
                    "score": 0.95,
                    "recordings": [
                        {
                            "id": "rec-mbid-123",
                            "title": "Test Song",
                            "artists": [{"name": "Artist 1"}],
                            "duration": 180,
                        }
                    ],
                }
            ],
        }
        mock_http_client.get.return_value = mock_response

        # Call lookup
        response = client.lookup(
            fingerprint="AQADtEmRJkqRJEqSJEqRJEqS",
            duration_s=180.5,
        )

        # Verify HTTP call
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert call_args[0][0] == "https://api.acoustid.org/v2/lookup"
        params = call_args[1]["params"]
        assert params["client"] == "test_api_key_123"
        assert params["fingerprint"] == "AQADtEmRJkqRJEqSJEqRJEqS"
        assert params["duration"] == 180
        assert params["meta"] == "recordings"

        # Verify response
        assert isinstance(response, AcoustIDResponse)
        assert response.status == "ok"
        assert len(response.results) == 1
        assert response.results[0].id == "acoustid-1"
        assert response.results[0].score == 0.95

    def test_lookup_with_metadata(self, client, mock_http_client):
        """Lookup with full metadata extraction."""
        # Mock HTTP response with rich metadata
        mock_response = {
            "status": "ok",
            "results": [
                {
                    "id": "acoustid-1",
                    "score": 0.98,
                    "recordings": [
                        {
                            "id": "rec-mbid-123",
                            "title": "Test Song",
                            "artists": [{"name": "Artist 1"}, {"name": "Artist 2"}],
                            "duration": 180,
                            "releasegroups": [{"id": "rel-mbid-456"}],
                        }
                    ],
                }
            ],
        }
        mock_http_client.get.return_value = mock_response

        response = client.lookup(
            fingerprint="AQADtEmRJkqRJEqSJEqRJEqS",
            duration_s=180.0,
        )

        # Verify parsed response
        assert len(response.results) == 1
        result = response.results[0]
        assert result.title == "Test Song"
        assert result.artists == ["Artist 1", "Artist 2"]
        assert result.duration_ms == 180000
        assert result.recording_mbid == "rec-mbid-123"
        assert result.release_mbid == "rel-mbid-456"

    def test_lookup_no_results(self, client, mock_http_client):
        """Lookup with no matching fingerprints."""
        mock_response = {"status": "ok", "results": []}
        mock_http_client.get.return_value = mock_response

        response = client.lookup(
            fingerprint="AQADtEmRJkqRJEqSJEqRJEqS",
            duration_s=180.0,
        )

        assert response.status == "ok"
        assert response.results == []

    def test_lookup_multiple_results(self, client, mock_http_client):
        """Lookup returns multiple candidates."""
        mock_response = {
            "status": "ok",
            "results": [
                {"id": "aid-1", "score": 0.98},
                {"id": "aid-2", "score": 0.85},
                {"id": "aid-3", "score": 0.72},
            ],
        }
        mock_http_client.get.return_value = mock_response

        response = client.lookup(
            fingerprint="AQADtEmRJkqRJEqSJEqRJEqS",
            duration_s=180.0,
        )

        assert len(response.results) == 3
        assert response.results[0].score == 0.98
        assert response.results[1].score == 0.85
        assert response.results[2].score == 0.72

    def test_lookup_api_error(self, client, mock_http_client):
        """AcoustID API returns error response."""
        mock_response = {
            "status": "error",
            "error": {"message": "Invalid API key"},
        }
        mock_http_client.get.return_value = mock_response

        with pytest.raises(AcoustIDError, match="AcoustID API error: Invalid API key"):
            client.lookup(
                fingerprint="AQADtEmRJkqRJEqSJEqRJEqS",
                duration_s=180.0,
            )

    def test_lookup_http_error(self, client, mock_http_client):
        """HTTP request fails."""
        from blinkb0t.core.api.http.errors import ApiError

        mock_http_client.get.side_effect = ApiError(
            message="Network error",
            method="GET",
            url="https://api.acoustid.org/v2/lookup",
            status_code=500,
        )

        with pytest.raises(AcoustIDError, match="AcoustID HTTP error"):
            client.lookup(
                fingerprint="AQADtEmRJkqRJEqSJEqRJEqS",
                duration_s=180.0,
            )

    def test_lookup_invalid_response(self, client, mock_http_client):
        """API returns invalid/malformed response."""
        # Missing required fields
        mock_http_client.get.return_value = {"invalid": "response"}

        with pytest.raises(AcoustIDError, match="Invalid response from AcoustID"):
            client.lookup(
                fingerprint="AQADtEmRJkqRJEqSJEqRJEqS",
                duration_s=180.0,
            )

    def test_lookup_timeout(self, client, mock_http_client):
        """Request times out."""
        from blinkb0t.core.api.http.errors import TimeoutError as HTTPTimeoutError

        mock_http_client.get.side_effect = HTTPTimeoutError(
            message="Request timed out",
            method="GET",
            url="https://api.acoustid.org/v2/lookup",
        )

        with pytest.raises(AcoustIDError, match="AcoustID request timed out"):
            client.lookup(
                fingerprint="AQADtEmRJkqRJEqSJEqRJEqS",
                duration_s=180.0,
            )

    def test_lookup_duration_bucketing(self, client, mock_http_client):
        """Duration is rounded to integer seconds."""
        mock_response = {"status": "ok", "results": []}
        mock_http_client.get.return_value = mock_response

        # Test various durations
        client.lookup(fingerprint="test", duration_s=180.4)
        assert mock_http_client.get.call_args[1]["params"]["duration"] == 180

        client.lookup(fingerprint="test", duration_s=180.5)
        assert mock_http_client.get.call_args[1]["params"]["duration"] == 180

        client.lookup(fingerprint="test", duration_s=180.9)
        assert mock_http_client.get.call_args[1]["params"]["duration"] == 180

    def test_parse_recording_minimal(self, client):
        """Parse recording with minimal fields."""
        raw_recording = {
            "id": "rec-123",
            "title": "Song",
        }

        result = client._parse_recording(
            acoustid_id="aid-1",
            score=0.9,
            recording=raw_recording,
        )

        assert result.id == "aid-1"
        assert result.score == 0.9
        assert result.title == "Song"
        assert result.recording_mbid == "rec-123"
        assert result.artists == []
        assert result.duration_ms is None

    def test_parse_recording_full(self, client):
        """Parse recording with all fields."""
        raw_recording = {
            "id": "rec-123",
            "title": "Full Song",
            "artists": [{"name": "A1"}, {"name": "A2"}],
            "duration": 240,
            "releasegroups": [{"id": "rel-456"}],
        }

        result = client._parse_recording(
            acoustid_id="aid-1",
            score=0.95,
            recording=raw_recording,
        )

        assert result.id == "aid-1"
        assert result.title == "Full Song"
        assert result.artists == ["A1", "A2"]
        assert result.duration_ms == 240000
        assert result.recording_mbid == "rec-123"
        assert result.release_mbid == "rel-456"

    def test_parse_recording_no_artists(self, client):
        """Parse recording with empty/missing artists."""
        raw_recording = {"id": "rec-123", "title": "Song"}

        result = client._parse_recording(
            acoustid_id="aid-1",
            score=0.9,
            recording=raw_recording,
        )

        assert result.artists == []

    def test_parse_recording_no_release(self, client):
        """Parse recording with no release groups."""
        raw_recording = {"id": "rec-123", "title": "Song"}

        result = client._parse_recording(
            acoustid_id="aid-1",
            score=0.9,
            recording=raw_recording,
        )

        assert result.release_mbid is None
