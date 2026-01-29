"""Tests for Genius API client (Phase 4).

Testing Genius plain lyrics provider.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from blinkb0t.core.audio.lyrics.providers.genius import GeniusClient
from blinkb0t.core.audio.lyrics.providers.models import LyricsQuery


class TestGeniusClient:
    """Test Genius API client."""

    @pytest.fixture
    def http_client(self):
        """Mock HTTP client."""
        client = MagicMock()
        client.get = AsyncMock()
        return client

    @pytest.fixture
    def genius_client_with_token(self, http_client):
        """Genius client with access token."""
        return GeniusClient(http_client=http_client, access_token="test_token")

    @pytest.fixture
    def genius_client_no_token(self, http_client):
        """Genius client without access token."""
        return GeniusClient(http_client=http_client, access_token=None)

    @pytest.mark.asyncio
    async def test_search_with_token(self, genius_client_with_token, http_client):
        """Search with valid access token."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        # Create separate response mocks for each call
        response1 = MagicMock()
        response1.json.return_value = {
            "response": {
                "hits": [
                    {
                        "result": {
                            "id": 12345,
                            "title": "Test Song",
                            "primary_artist": {"name": "Test Artist"},
                            "url": "https://genius.com/Test-artist-test-song-lyrics",
                        }
                    }
                ]
            }
        }
        response2 = MagicMock()
        response2.json.return_value = {"lyrics": {"body": {"plain": "Line 1\nLine 2\nLine 3"}}}

        http_client.get.side_effect = [response1, response2]

        candidates = await genius_client_with_token.search(query)

        assert len(candidates) == 1
        assert candidates[0].provider == "genius"
        assert candidates[0].provider_id == "12345"
        assert candidates[0].kind == "PLAIN"
        assert candidates[0].text == "Line 1\nLine 2\nLine 3"
        assert candidates[0].lrc is None

    @pytest.mark.asyncio
    async def test_search_without_token(self, genius_client_no_token, http_client):
        """Search without token returns empty."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        candidates = await genius_client_no_token.search(query)

        assert candidates == []
        http_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_no_hits(self, genius_client_with_token, http_client):
        """Search with no results."""
        query = LyricsQuery(artist="Test Artist", title="Unknown Song")

        http_client.get.return_value.json.return_value = {"response": {"hits": []}}

        candidates = await genius_client_with_token.search(query)

        assert candidates == []

    @pytest.mark.asyncio
    async def test_search_missing_artist_or_title(self, genius_client_with_token, http_client):
        """Search requires artist or title."""
        query = LyricsQuery(album="Test Album")  # No artist or title

        candidates = await genius_client_with_token.search(query)

        assert candidates == []
        http_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_api_error(self, genius_client_with_token, http_client):
        """Search handles API errors gracefully."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        http_client.get.side_effect = Exception("API error")

        candidates = await genius_client_with_token.search(query)

        assert candidates == []

    @pytest.mark.asyncio
    async def test_search_includes_authorization_header(
        self, genius_client_with_token, http_client
    ):
        """Search includes Authorization header."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        http_client.get.return_value.json.return_value = {"response": {"hits": []}}

        await genius_client_with_token.search(query)

        # Verify Authorization header set
        http_client.get.assert_called()
        call_headers = http_client.get.call_args[1].get("headers", {})
        assert "Authorization" in call_headers
        assert "Bearer test_token" in call_headers["Authorization"]

    @pytest.mark.asyncio
    async def test_search_includes_attribution(self, genius_client_with_token, http_client):
        """Search includes attribution metadata."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        # Create separate response mocks for each call
        response1 = MagicMock()
        response1.json.return_value = {
            "response": {
                "hits": [
                    {
                        "result": {
                            "id": 12345,
                            "title": "Test Song",
                            "url": "https://genius.com/Test-song-lyrics",
                        }
                    }
                ]
            }
        }
        response2 = MagicMock()
        response2.json.return_value = {"lyrics": {"body": {"plain": "Test lyrics"}}}

        http_client.get.side_effect = [response1, response2]

        candidates = await genius_client_with_token.search(query)

        assert len(candidates) == 1
        assert "source_url" in candidates[0].attribution
        assert "genius.com" in candidates[0].attribution["source_url"]

    @pytest.mark.asyncio
    async def test_search_confidence_scoring(self, genius_client_with_token, http_client):
        """Search assigns confidence based on match quality."""
        query = LyricsQuery(artist="Test Artist", title="Test Song")

        # Create separate response mocks for each call
        response1 = MagicMock()
        response1.json.return_value = {
            "response": {
                "hits": [
                    {
                        "result": {
                            "id": 1,
                            "title": "Test Song",
                            "primary_artist": {"name": "Test Artist"},
                        }
                    },
                    {
                        "result": {
                            "id": 2,
                            "title": "Test Song (Live)",
                            "primary_artist": {"name": "Test Artist"},
                        }
                    },
                ]
            }
        }
        response2 = MagicMock()
        response2.json.return_value = {"lyrics": {"body": {"plain": "Lyrics 1"}}}
        response3 = MagicMock()
        response3.json.return_value = {"lyrics": {"body": {"plain": "Lyrics 2"}}}

        http_client.get.side_effect = [response1, response2, response3]

        candidates = await genius_client_with_token.search(query)

        # First result should have higher confidence (exact title match)
        assert len(candidates) == 2
        assert candidates[0].confidence >= candidates[1].confidence
