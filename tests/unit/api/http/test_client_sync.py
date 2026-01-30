"""Tests for ApiClient (synchronous HTTP client)."""

from __future__ import annotations

import httpx
import pytest

from twinklr.core.api.http.client import ApiClient
from twinklr.core.api.http.config import HttpClientConfig
from twinklr.core.api.http.errors import ClientError
from twinklr.core.api.http.retry import RetryPolicy


def test_sync_success_json() -> None:
    """Test successful sync GET request with JSON response."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"})

    transport = httpx.MockTransport(handler)
    cfg = HttpClientConfig(base_url="https://example.test")
    with ApiClient(cfg, transport=transport) as c:
        resp = c.get("/v1/ping")
        assert c.json(resp) == {"ok": True}


def test_sync_http_4xx_maps_to_client_error() -> None:
    """Test that 4xx errors raise ClientError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": "bad"}, headers={"content-type": "application/json"}
        )

    transport = httpx.MockTransport(handler)
    cfg = HttpClientConfig(base_url="https://example.test")
    with ApiClient(cfg, transport=transport) as c:
        with pytest.raises(ClientError) as ei:
            c.get("/v1/bad")
        assert ei.value.status_code == 400


def test_sync_retry_after_429() -> None:
    """Test automatic retry on 429 rate limit with Retry-After header."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429,
                json={"error": "rate"},
                headers={"content-type": "application/json", "Retry-After": "0"},
            )
        return httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"})

    transport = httpx.MockTransport(handler)
    cfg = HttpClientConfig(base_url="https://example.test")
    policy = RetryPolicy(max_attempts=2, base_delay_s=0.0, jitter=0.0)

    with ApiClient(cfg, transport=transport, retry_policy=policy) as c:
        resp = c.get("/v1/rate")
        assert resp.status_code == 200
        assert calls["n"] == 2
