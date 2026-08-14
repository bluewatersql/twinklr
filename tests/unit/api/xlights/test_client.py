"""Offline contract tests for the xLights HTTP automation client (P2P-T5)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from twinklr.core.api.xlights import (
    CheckSequenceRequest,
    ExportVideoPreviewRequest,
    GetModelsRequest,
    LoadSequenceRequest,
    RenderAllRequest,
    XLightsAutomationClient,
    XLightsCommandError,
    XLightsInstanceUnavailableError,
    XLightsTimeoutError,
)


@pytest.mark.anyio
async def test_command_serialization() -> None:
    """Every supported command pins its documented ``xlDoAutomation`` wire body."""
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/xlDoAutomation"
        body = json.loads(request.content)
        requests.append(body)
        if body["cmd"] == "loadSequence":
            return httpx.Response(
                200,
                json={
                    "seq": "show.xsq",
                    "fullseq": "/tmp/show.xsq",
                    "framems": 50,
                },
            )
        if body["cmd"] == "exportVideoPreview":
            return httpx.Response(200, json={"output": "/tmp/preview.mp4"})
        if body["cmd"] == "getModels":
            return httpx.Response(200, json={"models": []})
        return httpx.Response(200, json={"msg": "ok"})

    transport = httpx.MockTransport(handler)
    async with XLightsAutomationClient(transport=transport) as client:
        await client.load_sequence(LoadSequenceRequest(Path("/tmp/show.xsq")), timeout_s=10)
        await client.render_all(RenderAllRequest(high_definition=True), timeout_s=10)
        await client.export_video_preview(
            ExportVideoPreviewRequest(Path("/tmp/preview.mp4"), width=1920, height=1080),
            timeout_s=10,
        )
        await client.close_sequence(timeout_s=10)
        await client.get_models(
            GetModelsRequest(include_models=True, include_groups=False), timeout_s=10
        )
        await client.check_sequence(CheckSequenceRequest(Path("/tmp/show.xsq")), timeout_s=10)

    assert requests == [
        {
            "cmd": "loadSequence",
            "seq": "/tmp/show.xsq",
            "promptIssues": "false",
        },
        {"cmd": "renderAll", "highdef": "true"},
        {
            "cmd": "exportVideoPreview",
            "filename": "/tmp/preview.mp4",
            "width": "1920",
            "height": "1080",
        },
        {"cmd": "closeSequence", "quiet": "true", "force": "true"},
        {"cmd": "getModels", "models": "true", "groups": "false"},
        {"cmd": "checkSequence", "seq": "/tmp/show.xsq"},
    ]


@pytest.mark.anyio
async def test_render_preview_workflow_order() -> None:
    """The workflow follows upstream BatchVideoExport.lua's four-command order."""
    commands: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        commands.append(body["cmd"])
        if body["cmd"] == "loadSequence":
            return httpx.Response(
                200,
                json={
                    "seq": "show.xsq",
                    "fullseq": "/tmp/show.xsq",
                    "media": "/tmp/song.mp3",
                    "len": 120000,
                    "framems": 25,
                },
            )
        if body["cmd"] == "exportVideoPreview":
            return httpx.Response(200, json={"output": "/tmp/preview.mp4"})
        return httpx.Response(200, json={"msg": "ok"})

    async with XLightsAutomationClient(transport=httpx.MockTransport(handler)) as client:
        result = await client.render_preview(Path("/tmp/show.xsq"))

    assert commands == ["loadSequence", "renderAll", "exportVideoPreview", "closeSequence"]
    assert result.video_path == Path("/tmp/preview.mp4")
    assert result.frame_rate == 40.0


@pytest.mark.anyio
async def test_sequence_closed_on_export_failure() -> None:
    """A failed export still makes the best-effort close request."""
    commands: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        commands.append(body["cmd"])
        if body["cmd"] == "loadSequence":
            return httpx.Response(
                200,
                json={"seq": "show.xsq", "fullseq": "/tmp/show.xsq", "framems": 50},
            )
        if body["cmd"] == "exportVideoPreview":
            return httpx.Response(503, json={"msg": "export failed"})
        return httpx.Response(200, json={"msg": "ok"})

    async with XLightsAutomationClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(XLightsCommandError, match="export failed"):
            await client.render_preview(Path("/tmp/show.xsq"))

    assert commands == ["loadSequence", "renderAll", "exportVideoPreview", "closeSequence"]


@pytest.mark.anyio
async def test_read_error_is_not_replayed_on_alternate_instance() -> None:
    """An ambiguous post-connect read failure never replays a stateful command."""
    ports: list[int | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ports.append(request.url.port)
        raise httpx.ReadError("connection dropped after send", request=request)

    async with XLightsAutomationClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(XLightsCommandError, match="network failure"):
            await client.render_all(RenderAllRequest(), timeout_s=1)

    assert ports == [49913]


@pytest.mark.anyio
async def test_load_parse_failure_closes_same_selected_instance_and_preserves_error() -> None:
    """A raw HTTP open is owned before parsing, and cleanup cannot mask parse failure."""
    calls: list[tuple[int | None, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        port = request.url.port
        calls.append((port, body["cmd"]))
        if body["cmd"] == "loadSequence" and port == 49913:
            raise httpx.ConnectError("connection refused", request=request)
        if body["cmd"] == "loadSequence":
            # HTTP success means xLights opened this sequence even though the raw body
            # is missing the frame timing required for a typed PreviewResult.
            return httpx.Response(
                200,
                json={"seq": "show.xsq", "fullseq": "/tmp/show.xsq"},
            )
        if body["cmd"] == "closeSequence":
            # Cleanup failure is secondary; callers must still see the parse defect.
            return httpx.Response(503, json={"msg": "close failed"})
        raise AssertionError(f"unexpected command: {body!r}")

    async with XLightsAutomationClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(XLightsCommandError, match="framems"):
            await client.render_preview(Path("/tmp/show.xsq"))

    assert calls == [
        (49913, "loadSequence"),
        (49914, "loadSequence"),
        (49914, "closeSequence"),
    ]


@pytest.mark.anyio
async def test_no_instance_error_message_names_port_and_windowed_requirement() -> None:
    """Connection refusal never leaks an HTTPX traceback to the caller."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with XLightsAutomationClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(XLightsInstanceUnavailableError) as error:
            await client.get_models(timeout_s=1)

    message = str(error.value)
    assert "49913" in message
    assert "49914" in message
    assert "windowed" in message


@pytest.mark.anyio
async def test_timeout_is_typed_error() -> None:
    """Automation timeout is a stable domain error, not an HTTPX exception."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    async with XLightsAutomationClient(
        base_url="http://127.0.0.1:49913", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(XLightsTimeoutError, match="timed out"):
            await client.render_all(RenderAllRequest(), timeout_s=1)


@pytest.mark.anyio
async def test_client_closes_transport() -> None:
    """The async context manager closes all internally owned HTTP pools."""
    client = XLightsAutomationClient(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    assert not client.is_closed
    await client.aclose()
    assert client.is_closed
