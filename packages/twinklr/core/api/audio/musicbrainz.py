"""MusicBrainz API client (Phase 3, async in Phase 8).

Client for MusicBrainz music metadata database.
Uses framework async HTTP client for requests.

MusicBrainz Rate Limiting:
- Limit: 1 request per second
- Higher limits available with MusicBrainz account
- See: https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting
"""

import logging
from typing import Any

from twinklr.core.api.audio.models import MusicBrainzRecording, MusicBrainzRelease
from twinklr.core.api.http.errors import ApiError, TimeoutError

logger = logging.getLogger(__name__)


class MusicBrainzError(RuntimeError):
    """MusicBrainz API error."""

    pass


class MusicBrainzClient:
    """MusicBrainz API client (async).

    Client for looking up music metadata from MusicBrainz database.
    Uses framework async HTTP client for retry/error handling.

    Rate Limiting:
        MusicBrainz enforces 1 request/second rate limit for anonymous requests.
        Client relies on framework HTTP client for retry/backoff.

    Args:
        http_client: Framework AsyncApiClient instance
        user_agent: User agent string (required by MusicBrainz)

    Example:
        >>> client = MusicBrainzClient(http_client=http, user_agent="app/1.0")
        >>> recording = await client.lookup_recording(mbid="...")
        >>> print(recording.title, recording.artists)
    """

    API_BASE_URL = "https://musicbrainz.org/ws/2"

    def __init__(self, http_client: Any, user_agent: str | None):
        """Initialize MusicBrainz client.

        Args:
            http_client: Framework HTTP client
            user_agent: User agent string (required by MusicBrainz API guidelines)

        Raises:
            ValueError: If user_agent is empty or None
        """
        if not user_agent:
            raise ValueError("MusicBrainz user agent is required")

        self.http_client = http_client
        self.user_agent = user_agent

    async def lookup_recording(self, *, mbid: str) -> MusicBrainzRecording:
        """Look up recording by MusicBrainz ID (async).

        Args:
            mbid: MusicBrainz recording ID (MBID)

        Returns:
            MusicBrainzRecording with metadata

        Raises:
            MusicBrainzError: If API returns error or request fails
        """
        # Build request
        url = f"{self.API_BASE_URL}/recording/{mbid}"
        params = {
            "fmt": "json",
            "inc": "artists+releases+isrcs",  # Include related data
        }
        headers = {
            "User-Agent": self.user_agent,
        }

        try:
            # Make async API request (Phase 8)
            logger.debug(f"MusicBrainz lookup: mbid={mbid} (note: 1 req/sec rate limit applies)")
            response_data = await self.http_client.get(
                url,
                params=params,
                headers=headers,
            )

            # Parse response
            return self._parse_recording(response_data)

        except TimeoutError as e:
            raise MusicBrainzError(f"MusicBrainz request timed out: {e}") from e
        except ApiError as e:
            raise MusicBrainzError(f"MusicBrainz HTTP error: {e}") from e
        except Exception as e:
            raise MusicBrainzError(f"MusicBrainz lookup failed: {e}") from e

    def _parse_recording(self, data: dict[str, Any]) -> MusicBrainzRecording:
        """Parse MusicBrainz recording response.

        Args:
            data: Raw API response dictionary

        Returns:
            Parsed MusicBrainzRecording

        Raises:
            MusicBrainzError: If response is invalid or missing required fields
        """
        # Check for required fields
        if "id" not in data or "title" not in data:
            raise MusicBrainzError(
                "Invalid response from MusicBrainz: missing 'id' or 'title' field"
            )

        recording_id = data["id"]
        title = data["title"]

        # Parse length (milliseconds)
        length_ms = data.get("length")

        # Parse artist credit
        artist_credit = data.get("artist-credit", [])
        artists = self._parse_artist_credit(artist_credit)

        # Parse ISRC (use first if multiple)
        isrcs = data.get("isrcs", [])
        isrc = isrcs[0] if isrcs else None

        # Parse releases
        releases = []
        for release_data in data.get("releases", []):
            try:
                release = MusicBrainzRelease(
                    id=release_data.get("id", ""),
                    title=release_data.get("title", ""),
                    date=release_data.get("date"),
                    country=release_data.get("country"),
                )
                releases.append(release)
            except Exception as e:
                logger.warning(f"Skipping invalid release: {e}")
                continue

        return MusicBrainzRecording(
            id=recording_id,
            title=title,
            artists=artists,
            length_ms=length_ms,
            isrc=isrc,
            releases=releases,
        )

    def _parse_artist_credit(self, artist_credit: list[dict[str, Any]]) -> list[str]:
        """Parse artist credit list to artist names.

        Args:
            artist_credit: List of artist credit dictionaries

        Returns:
            List of artist names
        """
        artists = []
        for item in artist_credit:
            if isinstance(item, dict) and "name" in item:
                artists.append(item["name"])
        return artists
