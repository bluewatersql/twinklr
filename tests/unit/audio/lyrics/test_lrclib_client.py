"""Tests for LRCLib API client (Phase 4).

Testing LRCLib synced lyrics provider.
"""

from unittest.mock import MagicMock

import pytest

from blinkb0t.core.audio.lyrics.providers.lrclib import LRCLibClient
from blinkb0t.core.audio.lyrics.providers.models import LyricsQuery


class TestLRCLibClient:
    """Test LRCLib API client."""

    @pytest.fixture
    def http_client(self):
        """Mock HTTP client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def lrclib_client(self, http_client):
        """LRCLib client with mock HTTP client."""
        return LRCLibClient(http_client=http_client)

    def test_search_with_artist_and_title(self, lrclib_client, http_client):
        """Search with artist and title."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        # Mock API response
        http_client.get.return_value.json.return_value = [
            {
                "id": 12345,
                "name": "Test Song",
                "artistName": "Test Artist",
                "albumName": "Test Album",
                "duration": 180,
                "plainLyrics": "Line 1\nLine 2",
                "syncedLyrics": "[00:12.00]Line 1\n[00:15.00]Line 2",
            }
        ]

        candidates = lrclib_client.search(query)

        assert len(candidates) == 1
        assert candidates[0].provider == "lrclib"
        assert candidates[0].provider_id == "12345"
        assert candidates[0].kind == "SYNCED"
        assert candidates[0].text == "Line 1\nLine 2"
        assert candidates[0].lrc == "[00:12.00]Line 1\n[00:15.00]Line 2"
        assert candidates[0].confidence > 0.7

    def test_search_multiple_results(self, lrclib_client, http_client):
        """Search returns multiple results."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        # Mock API response with multiple results
        http_client.get.return_value.json.return_value = [
            {
                "id": 1,
                "name": "Test Song",
                "artistName": "Test Artist",
                "duration": 180,
                "syncedLyrics": "[00:12.00]Line 1",
            },
            {
                "id": 2,
                "name": "Test Song (Live)",
                "artistName": "Test Artist",
                "duration": 200,
                "syncedLyrics": "[00:12.00]Line 1 Live",
            },
        ]

        candidates = lrclib_client.search(query)

        assert len(candidates) == 2
        assert candidates[0].provider_id == "1"
        assert candidates[1].provider_id == "2"

    def test_search_with_duration_filter(self, lrclib_client, http_client):
        """Search with duration filter improves confidence."""
        query = LyricsQuery(
            artist="Test Artist",
            title="Test Song",
            duration_ms=180000,  # 3 minutes
        )

        # Mock API response
        http_client.get.return_value.json.return_value = [
            {
                "id": 1,
                "name": "Test Song",
                "artistName": "Test Artist",
                "duration": 180,  # Exact match
                "syncedLyrics": "[00:12.00]Line 1",
            },
            {
                "id": 2,
                "name": "Test Song",
                "artistName": "Test Artist",
                "duration": 240,  # 1 minute off
                "syncedLyrics": "[00:12.00]Line 1",
            },
        ]

        candidates = lrclib_client.search(query)

        # First result should have higher confidence (duration match)
        assert candidates[0].confidence > candidates[1].confidence

    def test_search_plain_lyrics_only(self, lrclib_client, http_client):
        """Search returns plain lyrics when synced not available."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        # Mock API response without synced lyrics
        http_client.get.return_value.json.return_value = [
            {
                "id": 12345,
                "name": "Test Song",
                "artistName": "Test Artist",
                "duration": 180,
                "plainLyrics": "Line 1\nLine 2",
                "syncedLyrics": None,
            }
        ]

        candidates = lrclib_client.search(query)

        assert len(candidates) == 1
        assert candidates[0].kind == "PLAIN"
        assert candidates[0].lrc is None
        assert candidates[0].text == "Line 1\nLine 2"

    def test_search_no_results(self, lrclib_client, http_client):
        """Search with no results returns empty list."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        # Mock empty API response
        http_client.get.return_value.json.return_value = []

        candidates = lrclib_client.search(query)

        assert candidates == []

    def test_search_missing_artist_or_title(self, lrclib_client, http_client):
        """Search requires artist or title."""
        query = LyricsQuery(album="Test Album")  # No artist or title

        candidates = lrclib_client.search(query)

        # Should return empty, not query API
        assert candidates == []
        http_client.get.assert_not_called()

    def test_search_api_error(self, lrclib_client, http_client):
        """Search handles API errors gracefully."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        # Mock API error
        http_client.get.side_effect = Exception("API error")

        candidates = lrclib_client.search(query)

        # Should return empty list, not raise
        assert candidates == []

    def test_search_malformed_response(self, lrclib_client, http_client):
        """Search handles malformed API responses."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        # Mock malformed API response
        http_client.get.return_value.json.return_value = [
            {"id": 1}  # Missing required fields
        ]

        candidates = lrclib_client.search(query)

        # Should skip malformed entries
        assert candidates == []

    def test_search_includes_attribution(self, lrclib_client, http_client):
        """Search includes attribution metadata."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        http_client.get.return_value.json.return_value = [
            {
                "id": 12345,
                "name": "Test Song",
                "artistName": "Test Artist",
                "duration": 180,
                "syncedLyrics": "[00:12.00]Line 1",
            }
        ]

        candidates = lrclib_client.search(query)

        assert len(candidates) == 1
        assert "source_url" in candidates[0].attribution
        assert "lrclib.net" in candidates[0].attribution["source_url"]

    def test_search_builds_correct_url(self, lrclib_client, http_client):
        """Search builds correct API URL."""
        query = LyricsQuery(
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
        )

        http_client.get.return_value.json.return_value = []

        lrclib_client.search(query)

        # Verify HTTP client called with correct URL
        http_client.get.assert_called_once()
        call_url = http_client.get.call_args[0][0]
        assert "lrclib.net/api/search" in call_url
        assert "artist_name=Test+Artist" in call_url or "artist_name=Test%20Artist" in call_url
        assert "track_name=Test+Song" in call_url or "track_name=Test%20Song" in call_url
