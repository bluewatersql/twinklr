"""Tests for the AcoustID API client.

Every test drives the client through a real ``AsyncApiClient`` backed by
``httpx.MockTransport``, so the client sees the same ``httpx.Response`` objects
production hands it. Doubles that returned decoded dicts from ``get()`` hid a
100% failure rate in this client; see P1P-T7.
"""

from __future__ import annotations

import httpx
import pytest

from twinklr.core.api.audio.acoustid import AcoustIDClient, AcoustIDError
from twinklr.core.api.audio.errors import ProviderFailureCategory
from twinklr.core.api.audio.models import AcoustIDResponse

# Recorded shape of an AcoustID /v2/lookup response with recording metadata.
LOOKUP_PAYLOAD = {
    "status": "ok",
    "results": [
        {
            "id": "acoustid-1",
            "score": 0.95,
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


def test_init_requires_api_key(json_client):
    """API key is required."""
    http = json_client(LOOKUP_PAYLOAD)

    with pytest.raises(ValueError, match="API key is required"):
        AcoustIDClient(api_key="", http_client=http)

    with pytest.raises(ValueError, match="API key is required"):
        AcoustIDClient(api_key=None, http_client=http)


async def test_acoustid_parses_real_response_object(json_client):
    """A real httpx.Response is decoded before parsing (P1-F1 mechanism).

    Against the pre-fix client this raises TypeError inside ``_parse_response``
    (``"status" not in <Response>``), surfaced as AcoustIDError.
    """
    requests: list[httpx.Request] = []
    client = AcoustIDClient(
        api_key="test_api_key_123",
        http_client=json_client(LOOKUP_PAYLOAD, requests=requests),
    )

    response = await client.lookup(fingerprint="AQADtEmRJkqRJEqS", duration_s=180.5)

    assert isinstance(response, AcoustIDResponse)
    assert response.status == "ok"
    assert len(response.results) == 1
    result = response.results[0]
    assert result.id == "acoustid-1"
    assert result.score == 0.95
    assert result.title == "Test Song"
    assert result.artists == ["Artist 1", "Artist 2"]
    assert result.duration_ms == 180000
    assert result.recording_mbid == "rec-mbid-123"
    assert result.release_mbid == "rel-mbid-456"

    # The request reached the transport with the documented query parameters.
    assert len(requests) == 1
    sent = requests[0]
    assert sent.url.path == "/v2/lookup"
    assert sent.url.params["client"] == "test_api_key_123"
    assert sent.url.params["fingerprint"] == "AQADtEmRJkqRJEqS"
    assert sent.url.params["duration"] == "180"
    assert sent.url.params["meta"] == "recordings"


async def test_lookup_no_results(json_client):
    """Lookup with no matching fingerprints."""
    client = AcoustIDClient(api_key="k", http_client=json_client({"status": "ok", "results": []}))

    response = await client.lookup(fingerprint="fp", duration_s=180.0)

    assert response.status == "ok"
    assert response.results == []


async def test_lookup_multiple_results(json_client):
    """Lookup returns multiple candidates without recording metadata."""
    payload = {
        "status": "ok",
        "results": [
            {"id": "aid-1", "score": 0.98},
            {"id": "aid-2", "score": 0.85},
            {"id": "aid-3", "score": 0.72},
        ],
    }
    client = AcoustIDClient(api_key="k", http_client=json_client(payload))

    response = await client.lookup(fingerprint="fp", duration_s=180.0)

    assert [r.score for r in response.results] == [0.98, 0.85, 0.72]


async def test_lookup_duration_is_truncated_to_seconds(json_client):
    """Duration is sent as integer seconds (AcoustID requirement)."""
    requests: list[httpx.Request] = []
    client = AcoustIDClient(
        api_key="k",
        http_client=json_client({"status": "ok", "results": []}, requests=requests),
    )

    for duration_s in (180.4, 180.5, 180.9):
        await client.lookup(fingerprint="fp", duration_s=duration_s)

    assert [r.url.params["duration"] for r in requests] == ["180", "180", "180"]


async def test_lookup_api_error(json_client):
    """A provider-reported error is distinct from a decode or transport fault."""
    payload = {"status": "error", "error": {"message": "Invalid API key"}}
    client = AcoustIDClient(api_key="k", http_client=json_client(payload))

    with pytest.raises(AcoustIDError, match="AcoustID API error: Invalid API key") as exc_info:
        await client.lookup(fingerprint="fp", duration_s=180.0)

    assert exc_info.value.category == ProviderFailureCategory.PROVIDER_ERROR


async def test_lookup_missing_status_field(json_client):
    """A payload without 'status' is a contract violation, not a transport fault."""
    client = AcoustIDClient(api_key="k", http_client=json_client({"invalid": "response"}))

    with pytest.raises(AcoustIDError, match="Invalid response from AcoustID") as exc_info:
        await client.lookup(fingerprint="fp", duration_s=180.0)

    assert exc_info.value.category == ProviderFailureCategory.PARSE


async def test_provider_failure_message_distinguishes_parse_from_transport(transport_client):
    """Non-JSON body (parse) and a 500 (transport) report different categories."""

    def html_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>maintenance</html>")

    parse_client = AcoustIDClient(api_key="k", http_client=transport_client(html_handler))
    with pytest.raises(AcoustIDError) as parse_exc:
        await parse_client.lookup(fingerprint="fp", duration_s=1.0)

    def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport_fault_client = AcoustIDClient(api_key="k", http_client=transport_client(server_error))
    with pytest.raises(AcoustIDError) as transport_exc:
        await transport_fault_client.lookup(fingerprint="fp", duration_s=1.0)

    assert parse_exc.value.category == ProviderFailureCategory.PARSE
    assert transport_exc.value.category == ProviderFailureCategory.TRANSPORT
    assert str(parse_exc.value) != str(transport_exc.value)
    assert "decode" in str(parse_exc.value).lower()


async def test_lookup_auth_error_is_credential_category(transport_client):
    """A 401 is a credential failure, distinct from both parse and transport."""

    def unauthorized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    client = AcoustIDClient(api_key="k", http_client=transport_client(unauthorized))

    with pytest.raises(AcoustIDError) as exc_info:
        await client.lookup(fingerprint="fp", duration_s=1.0)

    assert exc_info.value.category == ProviderFailureCategory.CREDENTIAL


async def test_lookup_timeout(transport_client):
    """Request timeouts are reported as transport failures."""

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow", request=request)

    client = AcoustIDClient(api_key="k", http_client=transport_client(timeout))

    with pytest.raises(AcoustIDError, match="AcoustID request timed out") as exc_info:
        await client.lookup(fingerprint="fp", duration_s=1.0)

    assert exc_info.value.category == ProviderFailureCategory.TRANSPORT


class TestParseRecording:
    """Recording-level parsing, exercised directly on decoded payloads."""

    @pytest.fixture
    def client(self, json_client):
        return AcoustIDClient(api_key="k", http_client=json_client({}))

    def test_parse_recording_minimal(self, client):
        result = client._parse_recording(
            acoustid_id="aid-1", score=0.9, recording={"id": "rec-123", "title": "Song"}
        )

        assert result.id == "aid-1"
        assert result.score == 0.9
        assert result.title == "Song"
        assert result.recording_mbid == "rec-123"
        assert result.artists == []
        assert result.duration_ms is None
        assert result.release_mbid is None

    def test_parse_recording_full(self, client):
        result = client._parse_recording(
            acoustid_id="aid-1",
            score=0.95,
            recording={
                "id": "rec-123",
                "title": "Full Song",
                "artists": [{"name": "A1"}, {"name": "A2"}],
                "duration": 240,
                "releasegroups": [{"id": "rel-456"}],
            },
        )

        assert result.title == "Full Song"
        assert result.artists == ["A1", "A2"]
        assert result.duration_ms == 240000
        assert result.release_mbid == "rel-456"
