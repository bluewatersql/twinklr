"""The contract every audio-provider double must honor.

``AsyncApiClient.get`` returns an undecoded ``httpx.Response``; decoding is a
separate ``json()`` step. Doubles that returned dicts from ``get()`` are what
let a 100% client failure rate ship green (P1-F2).
"""

from __future__ import annotations

import inspect

import httpx

from twinklr.core.api.http.client import AsyncApiClient


async def test_async_api_client_get_returns_httpx_response(json_client):
    """get() yields a Response, and json() is what produces the dict."""
    client = json_client({"ok": True})

    response = await client.get("/v1/ping")

    assert isinstance(response, httpx.Response)
    assert not isinstance(response, dict)
    assert client.json(response) == {"ok": True}


def test_response_does_not_support_dict_membership(json_client):
    """``"key" in response`` raises TypeError — the exact P1-F1 mechanism."""
    response = httpx.Response(200, json={"status": "ok"}, request=httpx.Request("GET", "https://x"))

    try:
        "status" in response  # type: ignore[operator]  # noqa: B015
    except TypeError:
        return
    raise AssertionError("httpx.Response unexpectedly supports 'in'; the contract test is stale")


def test_get_signature_is_annotated_as_response():
    """The declared return type is the contract mypy enforces on call sites."""
    signature = inspect.signature(AsyncApiClient.get)
    assert signature.return_annotation == "httpx.Response"
