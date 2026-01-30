"""Genius API client (Phase 4, async in Phase 8).

Genius provides plain text lyrics (no timing) and requires an access token.

API Docs: https://docs.genius.com/
"""

import logging
from typing import Any
from urllib.parse import quote

from twinklr.core.audio.lyrics.providers.models import LyricsCandidate, LyricsQuery

logger = logging.getLogger(__name__)


class GeniusClient:
    """Genius API client for plain lyrics (async).

    Genius provides plain text lyrics without timing. Requires free API token.

    Args:
        http_client: Framework AsyncApiClient instance
        access_token: Genius API access token (from https://genius.com/api-clients)
    """

    BASE_URL = "https://api.genius.com"

    def __init__(self, *, http_client: Any, access_token: str | None):
        """Initialize Genius client.

        Args:
            http_client: Framework AsyncApiClient
            access_token: Genius API access token (optional)
        """
        self.http_client = http_client
        self.access_token = access_token

    async def search(self, query: LyricsQuery) -> list[LyricsCandidate]:
        """Search for lyrics by metadata (async).

        Args:
            query: Search query with artist, title, etc.

        Returns:
            List of lyrics candidates (plain text only)
        """
        # Require access token
        if not self.access_token:
            logger.debug("Genius search requires access token (GENIUS_ACCESS_TOKEN)")
            return []

        # Require at least artist or title
        if not query.artist and not query.title:
            logger.debug("Genius search requires artist or title")
            return []

        try:
            # Build search query
            search_terms = []
            if query.artist:
                search_terms.append(query.artist)
            if query.title:
                search_terms.append(query.title)
            search_query = " ".join(search_terms)

            # Search for songs (async - Phase 8)
            headers = {"Authorization": f"Bearer {self.access_token}"}
            search_url = f"{self.BASE_URL}/search?q={quote(search_query)}"

            logger.debug(f"Genius API search URL: {search_url}")
            response = await self.http_client.get(search_url, headers=headers)
            logger.debug(
                f"Response status: {response.status_code}, content-type: {response.headers.get('content-type')}"
            )
            logger.debug(f"Response body (first 200 chars): {response.text[:200]}")
            result = response.json()

            hits = result.get("response", {}).get("hits", [])
            logger.debug(f"Genius API returned {len(hits)} hits")
            if not hits:
                logger.debug(f"Genius API response: {result}")
                return []

            # Fetch lyrics for each hit (limit to top 3)
            candidates: list[LyricsCandidate] = []
            for i, hit in enumerate(hits[:3]):
                result_data = hit.get("result", {})
                song_title = result_data.get("title", "Unknown")
                artist_name = result_data.get("primary_artist", {}).get("name", "Unknown")
                logger.debug(f"Genius hit {i + 1}: '{song_title}' by {artist_name}")

                candidate = await self._fetch_lyrics(result_data, query, headers)
                if candidate:
                    logger.debug(f"Successfully fetched lyrics for hit {i + 1}")
                    candidates.append(candidate)
                else:
                    logger.debug(f"Failed to fetch lyrics for hit {i + 1}")

            logger.debug(f"Returning {len(candidates)} candidates")
            return candidates

        except Exception as e:
            import traceback

            logger.error(f"Genius search failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def _fetch_lyrics(
        self,
        result: dict[str, Any],
        query: LyricsQuery,
        headers: dict[str, str],
    ) -> LyricsCandidate | None:
        """Fetch lyrics for a specific song (async).

        Args:
            result: Genius search result
            query: Original query
            headers: Request headers with auth

        Returns:
            LyricsCandidate or None if failed
        """
        try:
            song_id = result.get("id")
            if not song_id:
                return None

            # Fetch lyrics using Genius lyrics endpoint
            # Note: Genius API doesn't have a direct lyrics endpoint in free tier
            # This is a simplified implementation for Phase 4
            lyrics_url = f"{self.BASE_URL}/songs/{song_id}/lyrics"

            try:
                response = await self.http_client.get(lyrics_url, headers=headers)
                lyrics_data = response.json()
                lyrics_text = lyrics_data.get("lyrics", {}).get("body", {}).get("plain", "")
            except Exception:
                # Fallback: no lyrics available
                logger.debug(f"Genius lyrics not available for song {song_id}")
                return None

            if not lyrics_text:
                return None

            # Compute confidence
            confidence = self._compute_confidence(result, query)

            # Build attribution
            source_url = result.get("url", f"https://genius.com/songs/{song_id}")
            attribution = {
                "source": "genius",
                "source_url": source_url,
            }

            return LyricsCandidate(
                provider="genius",
                provider_id=str(song_id),
                kind="PLAIN",
                text=lyrics_text,
                lrc=None,
                confidence=confidence,
                attribution=attribution,
            )

        except Exception as e:
            logger.warning(f"Failed to fetch Genius lyrics: {e}")
            return None

    def _compute_confidence(self, result: dict[str, Any], query: LyricsQuery) -> float:
        """Compute confidence score for result.

        Args:
            result: Genius search result
            query: Original query

        Returns:
            Confidence score (0-1)
        """
        confidence = 0.75  # Base confidence for Genius (reliable but no timing)

        # Check title match
        result_title = result.get("title", "").lower()
        query_title = (query.title or "").lower()

        if query_title and result_title:
            if result_title == query_title:
                confidence += 0.10  # Exact title match
            elif query_title in result_title or result_title in query_title:
                confidence += 0.05  # Partial title match

        # Check artist match
        result_artist = result.get("primary_artist", {}).get("name", "").lower()
        query_artist = (query.artist or "").lower()

        if query_artist and result_artist:
            if result_artist == query_artist:
                confidence += 0.05  # Exact artist match

        # Clamp to 0-1
        return min(1.0, max(0.0, confidence))
