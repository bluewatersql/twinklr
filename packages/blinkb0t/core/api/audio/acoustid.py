"""AcoustID API client (Phase 3, async in Phase 8).

Client for AcoustID audio fingerprinting service.
Uses framework async HTTP client for requests.
"""

import logging
from typing import Any

from blinkb0t.core.api.audio.models import AcoustIDRecording, AcoustIDResponse
from blinkb0t.core.api.http.errors import ApiError, TimeoutError

logger = logging.getLogger(__name__)


class AcoustIDError(RuntimeError):
    """AcoustID API error."""

    pass


class AcoustIDClient:
    """AcoustID API client (async).

    Client for looking up audio fingerprints via AcoustID API.
    Uses framework async HTTP client for retry/error handling.

    Args:
        api_key: AcoustID API key (from https://acoustid.org/api-key)
        http_client: Framework AsyncApiClient instance

    Example:
        >>> client = AcoustIDClient(api_key="...", http_client=http)
        >>> response = await client.lookup(fingerprint="...", duration_s=180.5)
        >>> for result in response.results:
        ...     print(result.title, result.score)
    """

    API_BASE_URL = "https://api.acoustid.org/v2"

    def __init__(self, api_key: str | None, http_client: Any):
        """Initialize AcoustID client.

        Args:
            api_key: AcoustID API key
            http_client: Framework HTTP client

        Raises:
            ValueError: If api_key is empty or None
        """
        if not api_key:
            raise ValueError("AcoustID API key is required")

        self.api_key = api_key
        self.http_client = http_client

    async def lookup(self, *, fingerprint: str, duration_s: float) -> AcoustIDResponse:
        """Look up audio fingerprint (async).

        Args:
            fingerprint: Chromaprint fingerprint string
            duration_s: Audio duration in seconds

        Returns:
            AcoustIDResponse with matching recordings

        Raises:
            AcoustIDError: If API returns error or request fails
        """
        # Round duration to integer seconds (AcoustID requirement)
        duration_int = int(duration_s)

        # Build request parameters
        params = {
            "client": self.api_key,
            "fingerprint": fingerprint,
            "duration": duration_int,
            "meta": "recordings",  # Request recording metadata
        }

        try:
            # Make async API request (Phase 8)
            logger.debug(f"AcoustID lookup: duration={duration_int}s")
            response_data = await self.http_client.get(
                f"{self.API_BASE_URL}/lookup",
                params=params,
            )

            # Parse response
            return self._parse_response(response_data)

        except TimeoutError as e:
            raise AcoustIDError(f"AcoustID request timed out: {e}") from e
        except ApiError as e:
            raise AcoustIDError(f"AcoustID HTTP error: {e}") from e
        except Exception as e:
            raise AcoustIDError(f"AcoustID lookup failed: {e}") from e

    def _parse_response(self, data: dict[str, Any]) -> AcoustIDResponse:
        """Parse AcoustID API response.

        Args:
            data: Raw API response dictionary

        Returns:
            Parsed AcoustIDResponse

        Raises:
            AcoustIDError: If response is invalid or contains error
        """
        # Check for required fields
        if "status" not in data:
            raise AcoustIDError("Invalid response from AcoustID: missing 'status' field")

        status = data["status"]

        # Handle error response
        if status == "error":
            error_msg = "Unknown error"
            if "error" in data:
                if isinstance(data["error"], dict) and "message" in data["error"]:
                    error_msg = data["error"]["message"]
                elif isinstance(data["error"], str):
                    error_msg = data["error"]
            raise AcoustIDError(f"AcoustID API error: {error_msg}")

        # Parse results
        results = []
        for item in data.get("results", []):
            acoustid_id = item.get("id")
            score = item.get("score")

            if acoustid_id is None or score is None:
                logger.warning(f"Skipping AcoustID result with missing id/score: {item}")
                continue

            # Parse recordings (if present)
            recordings = item.get("recordings", [])
            if recordings:
                # Use first recording (best match)
                recording = recordings[0]
                result = self._parse_recording(
                    acoustid_id=acoustid_id,
                    score=score,
                    recording=recording,
                )
            else:
                # No recording metadata
                result = AcoustIDRecording(
                    id=acoustid_id,
                    score=score,
                )

            results.append(result)

        return AcoustIDResponse(
            status=status,
            results=results,
        )

    def _parse_recording(
        self,
        *,
        acoustid_id: str,
        score: float,
        recording: dict[str, Any],
    ) -> AcoustIDRecording:
        """Parse recording metadata from AcoustID result.

        Args:
            acoustid_id: AcoustID identifier
            score: Match confidence score
            recording: Raw recording dictionary

        Returns:
            Parsed AcoustIDRecording
        """
        # Extract basic fields
        title = recording.get("title")
        recording_mbid = recording.get("id")

        # Parse artists
        artists = []
        for artist_data in recording.get("artists", []):
            if isinstance(artist_data, dict) and "name" in artist_data:
                artists.append(artist_data["name"])

        # Parse duration (seconds -> milliseconds)
        duration_ms = None
        if "duration" in recording:
            duration_s = recording["duration"]
            if duration_s is not None:
                duration_ms = int(duration_s * 1000)

        # Parse release MBID (first release group)
        release_mbid = None
        releasegroups = recording.get("releasegroups", [])
        if releasegroups and isinstance(releasegroups[0], dict):
            release_mbid = releasegroups[0].get("id")

        return AcoustIDRecording(
            id=acoustid_id,
            score=score,
            title=title,
            artists=artists,
            duration_ms=duration_ms,
            recording_mbid=recording_mbid,
            release_mbid=release_mbid,
        )
