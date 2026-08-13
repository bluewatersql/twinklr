"""MusicBrainz API client (Phase 3, async in Phase 8).

Client for MusicBrainz music metadata database.
Uses framework async HTTP client for requests.

MusicBrainz Rate Limiting:
- Limit: 1 request per second, no concurrent requests
- Higher limits available with MusicBrainz account
- See: https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting

The policy is enforced by an AsyncRateLimiter held across each request, so
every call site inherits the pacing.
"""

import logging
from typing import Any

from twinklr.core.api.audio.errors import ProviderFailureCategory, ProviderLookupError
from twinklr.core.api.audio.models import MusicBrainzRecording, MusicBrainzRelease
from twinklr.core.api.audio.rate_limit import AsyncRateLimiter
from twinklr.core.api.http.client import AsyncApiClient
from twinklr.core.api.http.errors import ApiError, AuthError, DecodeError, TimeoutError

logger = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT_RPS = 1.0
"""MusicBrainz's documented anonymous rate limit."""


class MusicBrainzError(ProviderLookupError):
    """MusicBrainz API error, categorized by failure kind."""


class MusicBrainzClient:
    """MusicBrainz API client (async).

    Client for looking up music metadata from MusicBrainz database.
    Uses framework async HTTP client for retry/error handling.

    Rate Limiting:
        MusicBrainz allows 1 request/second and no concurrent requests for
        anonymous clients. Every request is issued while holding the rate
        limiter, which both serializes and paces them.

    Args:
        http_client: Framework AsyncApiClient instance
        user_agent: User agent string (required by MusicBrainz)
        rate_limiter: Pacing limiter; defaults to the documented 1 req/s

    Example:
        >>> client = MusicBrainzClient(http_client=http, user_agent="app/1.0")
        >>> recording = await client.lookup_recording(mbid="...")
        >>> print(recording.title, recording.artists)
    """

    API_BASE_URL = "https://musicbrainz.org/ws/2"

    def __init__(
        self,
        http_client: AsyncApiClient,
        user_agent: str | None,
        rate_limiter: AsyncRateLimiter | None = None,
    ):
        """Initialize MusicBrainz client.

        Args:
            http_client: Framework HTTP client
            user_agent: User agent string (required by MusicBrainz API guidelines)
            rate_limiter: Pacing limiter shared by all calls on this client

        Raises:
            ValueError: If user_agent is empty or None
        """
        if not user_agent:
            raise ValueError("MusicBrainz user agent is required")

        self.http_client = http_client
        self.user_agent = user_agent
        self.rate_limiter = rate_limiter or AsyncRateLimiter(rate_per_second=DEFAULT_RATE_LIMIT_RPS)

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
        # httpx normalizes header names to lower case, and the framework merges
        # request headers over the client defaults with a plain dict update. Use
        # the normalized casing so this replaces the default User-Agent rather
        # than being appended to it — MusicBrainz requires an identifying agent.
        headers = {
            "user-agent": self.user_agent,
        }

        try:
            logger.debug(f"MusicBrainz lookup: mbid={mbid}")

            # The limiter is held for the whole request: 1 req/s, never concurrent
            async with self.rate_limiter:
                response = await self.http_client.get(
                    url,
                    params=params,
                    headers=headers,
                )

            # get() returns an undecoded httpx.Response; decoding is a separate step
            data = self.http_client.json(response)
            if not isinstance(data, dict):
                raise MusicBrainzError(
                    f"Invalid response from MusicBrainz: expected a JSON object, "
                    f"got {type(data).__name__}",
                    category=ProviderFailureCategory.PARSE,
                )

            return self._parse_recording(data)

        except MusicBrainzError:
            raise
        except TimeoutError as e:
            raise MusicBrainzError(
                f"MusicBrainz request timed out: {e}",
                category=ProviderFailureCategory.TRANSPORT,
            ) from e
        except AuthError as e:
            raise MusicBrainzError(
                f"MusicBrainz rejected the credentials: {e}",
                category=ProviderFailureCategory.CREDENTIAL,
            ) from e
        except DecodeError as e:
            raise MusicBrainzError(
                f"MusicBrainz response could not be decoded: {e}",
                category=ProviderFailureCategory.PARSE,
            ) from e
        except ApiError as e:
            raise MusicBrainzError(
                f"MusicBrainz HTTP error: {e}",
                category=ProviderFailureCategory.TRANSPORT,
            ) from e
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
                "Invalid response from MusicBrainz: missing 'id' or 'title' field",
                category=ProviderFailureCategory.PARSE,
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
