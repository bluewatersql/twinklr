"""Tests for the MusicBrainz API client.

Driven through a real ``AsyncApiClient`` over ``httpx.MockTransport`` so the
client sees production's ``httpx.Response`` objects. Also pins MusicBrainz's
documented 1 req/s, no-concurrency policy (P2-F13), which becomes live the
moment AcoustID starts returning MBIDs.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from twinklr.core.api.audio.errors import ProviderFailureCategory
from twinklr.core.api.audio.models import MusicBrainzRecording
from twinklr.core.api.audio.musicbrainz import MusicBrainzClient, MusicBrainzError
from twinklr.core.api.audio.rate_limit import AsyncRateLimiter

# Recorded shape of a MusicBrainz /ws/2/recording/<mbid> response.
RECORDING_PAYLOAD = {
    "id": "mbid-123",
    "title": "Test Recording",
    "length": 180000,
    "artist-credit": [{"name": "Artist One"}, {"name": "Artist Two"}],
    "isrcs": ["USRC17607839", "USRC17607840"],
    "releases": [
        {"id": "rel-1", "title": "Album One", "date": "2020-01-01", "country": "US"},
        {"id": "rel-2", "title": "Album Two", "date": "2021-06-15", "country": "GB"},
    ],
}


class FakeClock:
    """Monotonic clock that only advances when the paired sleep is awaited."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        await asyncio.sleep(0)  # yield, so concurrent tasks get a chance to interleave


def unlimited() -> AsyncRateLimiter:
    """Limiter that serializes but never waits (keeps unrelated tests fast)."""
    clock = FakeClock()
    return AsyncRateLimiter(rate_per_second=1.0, monotonic=clock.monotonic, sleep=clock.sleep)


def test_init_requires_user_agent(json_client):
    """MusicBrainz requires an identifying user agent."""
    http = json_client(RECORDING_PAYLOAD)

    with pytest.raises(ValueError, match="user agent is required"):
        MusicBrainzClient(http_client=http, user_agent="")

    with pytest.raises(ValueError, match="user agent is required"):
        MusicBrainzClient(http_client=http, user_agent=None)


async def test_musicbrainz_parses_real_response_object(json_client):
    """A real httpx.Response is decoded before parsing (P1-F1 mechanism).

    Against the pre-fix client this raises TypeError inside ``_parse_recording``
    (``"id" not in <Response>``), surfaced as MusicBrainzError.
    """
    requests: list[httpx.Request] = []
    client = MusicBrainzClient(
        http_client=json_client(RECORDING_PAYLOAD, requests=requests),
        user_agent="twinklr-test/1.0",
        rate_limiter=unlimited(),
    )

    recording = await client.lookup_recording(mbid="mbid-123")

    assert isinstance(recording, MusicBrainzRecording)
    assert recording.id == "mbid-123"
    assert recording.title == "Test Recording"
    assert recording.artists == ["Artist One", "Artist Two"]
    assert recording.length_ms == 180000
    assert recording.isrc == "USRC17607839"
    assert [r.title for r in recording.releases] == ["Album One", "Album Two"]

    assert len(requests) == 1
    sent = requests[0]
    assert sent.url.path == "/ws/2/recording/mbid-123"
    assert sent.url.params["fmt"] == "json"
    assert sent.headers["User-Agent"] == "twinklr-test/1.0"


async def test_lookup_minimal_recording(json_client):
    """Recording with only the required fields parses."""
    client = MusicBrainzClient(
        http_client=json_client({"id": "mbid-1", "title": "Bare"}),
        user_agent="twinklr-test/1.0",
        rate_limiter=unlimited(),
    )

    recording = await client.lookup_recording(mbid="mbid-1")

    assert recording.title == "Bare"
    assert recording.artists == []
    assert recording.isrc is None
    assert recording.releases == []


async def test_lookup_missing_required_fields(json_client):
    """A payload without id/title is a contract violation, not a transport fault."""
    client = MusicBrainzClient(
        http_client=json_client({"unexpected": "shape"}),
        user_agent="twinklr-test/1.0",
        rate_limiter=unlimited(),
    )

    with pytest.raises(MusicBrainzError, match="Invalid response from MusicBrainz") as exc_info:
        await client.lookup_recording(mbid="mbid-1")

    assert exc_info.value.category == ProviderFailureCategory.PARSE


async def test_provider_failure_message_distinguishes_parse_from_transport(transport_client):
    """Non-JSON body (parse) and a 503 (transport) report different categories."""

    def html_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>maintenance</html>")

    parse_client = MusicBrainzClient(
        http_client=transport_client(html_handler),
        user_agent="twinklr-test/1.0",
        rate_limiter=unlimited(),
    )
    with pytest.raises(MusicBrainzError) as parse_exc:
        await parse_client.lookup_recording(mbid="mbid-1")

    def unavailable(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    transport_fault_client = MusicBrainzClient(
        http_client=transport_client(unavailable),
        user_agent="twinklr-test/1.0",
        rate_limiter=unlimited(),
    )
    with pytest.raises(MusicBrainzError) as transport_exc:
        await transport_fault_client.lookup_recording(mbid="mbid-1")

    assert parse_exc.value.category == ProviderFailureCategory.PARSE
    assert transport_exc.value.category == ProviderFailureCategory.TRANSPORT
    assert "decode" in str(parse_exc.value).lower()


async def test_lookup_timeout(transport_client):
    """Request timeouts are reported as transport failures."""

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    client = MusicBrainzClient(
        http_client=transport_client(timeout),
        user_agent="twinklr-test/1.0",
        rate_limiter=unlimited(),
    )

    with pytest.raises(MusicBrainzError, match="MusicBrainz request timed out") as exc_info:
        await client.lookup_recording(mbid="mbid-1")

    assert exc_info.value.category == ProviderFailureCategory.TRANSPORT


async def test_musicbrainz_requests_are_sequential_and_paced(transport_client):
    """Concurrent lookups are serialized and spaced by the configured rate.

    Uses a fake clock: no wall-clock sleeping, so the assertion is on the
    limiter's arithmetic rather than on timing luck.
    """
    clock = FakeClock()
    in_flight = 0
    max_in_flight = 0
    start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        start_times.append(clock.now)
        # Yield twice: a second task allowed to run would overlap with this one.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        in_flight -= 1
        return httpx.Response(200, json={"id": request.url.path.rsplit("/", 1)[-1], "title": "T"})

    client = MusicBrainzClient(
        http_client=transport_client(handler),
        user_agent="twinklr-test/1.0",
        rate_limiter=AsyncRateLimiter(
            rate_per_second=1.0, monotonic=clock.monotonic, sleep=clock.sleep
        ),
    )

    mbids = ["mbid-1", "mbid-2", "mbid-3"]
    results = await asyncio.gather(*(client.lookup_recording(mbid=m) for m in mbids))

    assert [r.id for r in results] == mbids
    assert max_in_flight == 1, "MusicBrainz requests must never overlap"
    assert start_times == [0.0, 1.0, 2.0], "requests must be spaced by 1/rate seconds"


async def test_rate_limiter_honors_configured_rate(transport_client):
    """A 2 req/s configuration spaces requests by 0.5 s, not 1 s."""
    clock = FakeClock()
    start_times: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        start_times.append(clock.now)
        return httpx.Response(200, json={"id": "mbid", "title": "T"})

    client = MusicBrainzClient(
        http_client=transport_client(handler),
        user_agent="twinklr-test/1.0",
        rate_limiter=AsyncRateLimiter(
            rate_per_second=2.0, monotonic=clock.monotonic, sleep=clock.sleep
        ),
    )

    for _ in range(3):
        await client.lookup_recording(mbid="mbid")

    assert start_times == [0.0, 0.5, 1.0]


class TestParseArtistCredit:
    """Artist-credit parsing, exercised directly on decoded payloads."""

    @pytest.fixture
    def client(self, json_client):
        return MusicBrainzClient(
            http_client=json_client({}),
            user_agent="twinklr-test/1.0",
            rate_limiter=unlimited(),
        )

    def test_parses_names_in_order(self, client):
        credit = [{"name": "First"}, {"name": "Second"}]
        assert client._parse_artist_credit(credit) == ["First", "Second"]

    def test_skips_malformed_entries(self, client):
        credit = [{"name": "First"}, "and", {"no_name": True}]
        assert client._parse_artist_credit(credit) == ["First"]
