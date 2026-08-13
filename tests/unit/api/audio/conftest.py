"""Shared transport-level doubles for audio provider client tests.

Provider clients are driven through a real ``AsyncApiClient`` wired to an
``httpx.MockTransport``. Nothing here performs live network I/O: every request
is answered by an in-process handler, so the clients exercise the real
request/decode contract instead of a hand-written stand-in for it.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from twinklr.core.api.http.client import AsyncApiClient
from twinklr.core.api.http.config import HttpClientConfig
from twinklr.core.api.http.retry import RetryPolicy

Handler = Callable[[httpx.Request], httpx.Response]
ClientFactory = Callable[..., AsyncApiClient]


def _build(handler: Handler, *, max_attempts: int = 1) -> AsyncApiClient:
    return AsyncApiClient(
        HttpClientConfig(base_url="https://provider.test"),
        transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=max_attempts, base_delay_s=0.0, jitter=0.0),
    )


@pytest.fixture
def transport_client() -> ClientFactory:
    """Factory building a real AsyncApiClient over an in-process handler.

    Retries default to a single attempt so error-path tests do not sleep.
    """
    return _build


@pytest.fixture
def json_client() -> Callable[..., AsyncApiClient]:
    """Factory building a client that answers every request with a JSON payload.

    Pass ``requests`` to capture the inbound ``httpx.Request`` objects.
    """

    def factory(payload: object, *, requests: list[httpx.Request] | None = None) -> AsyncApiClient:
        def handler(request: httpx.Request) -> httpx.Response:
            if requests is not None:
                requests.append(request)
            return httpx.Response(200, json=payload)

        return _build(handler)

    return factory
