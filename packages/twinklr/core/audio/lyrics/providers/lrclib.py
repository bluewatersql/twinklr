"""LRCLib API client (Phase 4, async in Phase 8).

LRCLib is a free, open-source lyrics provider with synced lyrics support.
No API key required.

API Docs: https://lrclib.net/docs
"""

import logging
from typing import Any
from urllib.parse import urlencode

from blinkb0t.core.audio.lyrics.providers.models import LyricsCandidate, LyricsQuery

logger = logging.getLogger(__name__)


class LRCLibClient:
    """LRCLib API client for synced lyrics (async).

    LRCLib provides free synced lyrics (LRC format) without requiring an API key.

    Args:
        http_client: Framework AsyncApiClient instance
    """

    BASE_URL = "https://lrclib.net/api"

    def __init__(self, *, http_client: Any):
        """Initialize LRCLib client.

        Args:
            http_client: Framework AsyncApiClient
        """
        self.http_client = http_client

    async def search(self, query: LyricsQuery) -> list[LyricsCandidate]:
        """Search for lyrics by metadata (async).

        Args:
            query: Search query with artist, title, etc.

        Returns:
            List of lyrics candidates (synced or plain)
        """
        # Require at least artist or title
        if not query.artist and not query.title:
            logger.debug("LRCLib search requires artist or title")
            return []

        try:
            # Build search URL
            params = {}
            if query.artist:
                params["artist_name"] = query.artist
            if query.title:
                params["track_name"] = query.title
            if query.album:
                params["album_name"] = query.album

            url = f"{self.BASE_URL}/search?{urlencode(params)}"

            # Make async API request (Phase 8)
            response = await self.http_client.get(url)
            results = response.json()

            if not isinstance(results, list):
                logger.warning(f"LRCLib returned non-list response: {type(results)}")
                return []

            # Parse results into candidates
            candidates: list[LyricsCandidate] = []
            for result in results:
                candidate = self._parse_result(result, query)
                if candidate:
                    candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.warning(f"LRCLib search failed: {e}")
            return []

    def _parse_result(
        self,
        result: dict[str, Any],
        query: LyricsQuery,
    ) -> LyricsCandidate | None:
        """Parse LRCLib API result into candidate.

        Args:
            result: API result dict
            query: Original query for confidence scoring

        Returns:
            LyricsCandidate or None if malformed
        """
        try:
            # Required fields
            result_id = result.get("id")
            synced_lyrics = result.get("syncedLyrics")
            plain_lyrics = result.get("plainLyrics")

            if not result_id:
                return None

            # Need at least one type of lyrics
            if not synced_lyrics and not plain_lyrics:
                return None

            # Determine kind and text
            if synced_lyrics:
                kind = "SYNCED"
                text = plain_lyrics if plain_lyrics else self._lrc_to_text(synced_lyrics)
                lrc = synced_lyrics
            else:
                kind = "PLAIN"
                text = plain_lyrics
                lrc = None

            # Compute confidence based on metadata match
            confidence = self._compute_confidence(result, query)

            # Build attribution
            attribution = {
                "source": "lrclib",
                "source_url": f"https://lrclib.net/api/get/{result_id}",
            }

            return LyricsCandidate(
                provider="lrclib",
                provider_id=str(result_id),
                kind=kind,
                text=text,
                lrc=lrc,
                confidence=confidence,
                attribution=attribution,
            )

        except Exception as e:
            logger.warning(f"Failed to parse LRCLib result: {e}")
            return None

    def _compute_confidence(self, result: dict[str, Any], query: LyricsQuery) -> float:
        """Compute confidence score for result.

        Args:
            result: API result
            query: Original query

        Returns:
            Confidence score (0-1)
        """
        confidence = 0.80  # Base confidence for LRCLib (reliable source)

        # Boost if duration matches (within 5 seconds)
        if query.duration_ms and result.get("duration"):
            query_duration_s = query.duration_ms / 1000
            result_duration_s = result.get("duration", 0)
            duration_diff = abs(query_duration_s - result_duration_s)

            if duration_diff <= 5:
                confidence += 0.10  # Exact duration match
            elif duration_diff <= 30:
                confidence += 0.05  # Close duration match

        # Clamp to 0-1
        return min(1.0, max(0.0, confidence))

    def _lrc_to_text(self, lrc: str) -> str:
        """Convert LRC content to plain text.

        Args:
            lrc: LRC content with timestamps

        Returns:
            Plain text (timestamps removed)
        """
        import re

        # Remove timestamps: [mm:ss.xx]
        pattern = re.compile(r"\[\d{2}:\d{2}(?:\.\d{1,2})?\]")
        text = pattern.sub("", lrc)

        # Remove metadata tags: [ar:], [ti:], etc.
        metadata_pattern = re.compile(r"\[(?:ar|ti|al|by|offset):[^\]]*\]")
        text = metadata_pattern.sub("", text)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
