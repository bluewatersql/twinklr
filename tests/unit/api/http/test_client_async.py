"""Tests for AsyncApiClient.

Uses anyio for async test support (pytest-anyio).
"""

from __future__ import annotations

import httpx
import pytest

from twinklr.core.api.http.client import AsyncApiClient
from twinklr.core.api.http.config import HttpClientConfig
from twinklr.core.api.http.retry import RetryPolicy


@pytest.mark.anyio
async def test_async_success_json() -> None:
    """Test successful async GET request with JSON response."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"})

    transport = httpx.MockTransport(handler)
    cfg = HttpClientConfig(base_url="https://example.test")
    async with AsyncApiClient(cfg, transport=transport) as c:
        resp = await c.get("/v1/ping")
        assert c.json(resp) == {"ok": True}


@pytest.mark.anyio
async def test_async_retry_500_then_ok() -> None:
    """Test automatic retry on 500 error."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"})

    transport = httpx.MockTransport(handler)
    cfg = HttpClientConfig(base_url="https://example.test")
    policy = RetryPolicy(max_attempts=2, base_delay_s=0.0, jitter=0.0)

    async with AsyncApiClient(cfg, transport=transport, retry_policy=policy) as c:
        resp = await c.get("/v1/flaky")
        assert resp.status_code == 200
        assert calls["n"] == 2
