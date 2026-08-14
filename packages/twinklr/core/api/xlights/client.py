"""Async client for xLights' unauthenticated, local-only HTTP automation API.

The API is exposed by a *windowed* xLights instance at ``/xlDoAutomation``. xLights
documents no authentication for this port, so any local process can drive an instance
while the operator has enabled the API. Twinklr never enables, binds, proxies, launches,
or quits xLights; use this client only on a trusted local machine and disable the API
when the LOCAL-ONLY preview workflow is finished.

Manual smoke test (requires xLights 2026.15, windowed, and API enabled):

    TWINKLR_XLIGHTS_PREVIEW_SEQUENCE=/absolute/path/show.xsq \\
      uv run pytest -m local_only -k preview -q
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import httpx

from twinklr.core.api.http import AsyncApiClient, HttpClientConfig
from twinklr.core.api.http.errors import ApiError, NetworkError
from twinklr.core.api.http.errors import TimeoutError as HttpTimeoutError
from twinklr.core.api.http.retry import RetryPolicy
from twinklr.core.api.xlights.errors import (
    XLightsAutomationError,
    XLightsClientClosedError,
    XLightsCommandError,
    XLightsInstanceUnavailableError,
    XLightsTimeoutError,
)
from twinklr.core.api.xlights.models import (
    CheckSequenceRequest,
    CheckSequenceResult,
    CloseSequenceRequest,
    CommandResult,
    ExportVideoPreviewRequest,
    ExportVideoPreviewResult,
    GetModelsRequest,
    GetModelsResult,
    LoadSequenceRequest,
    LoadSequenceResult,
    PreviewResult,
    RenderAllRequest,
    command_result,
    optional_path,
    required_text,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URLS = ("http://127.0.0.1:49913", "http://127.0.0.1:49914")
"""xLights' default and alternate local automation ports."""

DEFAULT_COMMAND_TIMEOUT_S = 30.0
DEFAULT_RENDER_TIMEOUT_S = 15 * 60.0
DEFAULT_EXPORT_TIMEOUT_S = 15 * 60.0


@dataclass(frozen=True)
class _RawAutomationResponse:
    """Successful raw HTTP response and the exact instance that returned it."""

    client_index: int
    response: httpx.Response


class XLightsAutomationClient:
    """Typed, async xlDo client with one framework-owned retry policy.

    ``AsyncApiClient`` supplies the repository's only retry/error stack. Its explicit
    one-attempt policy never replays a POST that might alter the user's xLights state.
    A connection refusal instead tries the documented alternate local port once, then
    raises one actionable domain error.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        base_urls: Iterable[str] = (base_url,) if base_url is not None else DEFAULT_BASE_URLS
        self._base_urls = tuple(url.rstrip("/") for url in base_urls)
        self._retry_policy = RetryPolicy(max_attempts=1)
        self._clients = tuple(
            AsyncApiClient(
                HttpClientConfig(
                    base_url=url,
                    user_agent="twinklr-xlights-automation/0.2",
                ),
                retry_policy=self._retry_policy,
                transport=transport,
            )
            for url in self._base_urls
        )
        self._active_client_index = 0
        self._pinned_client_index: int | None = None
        self._closed = False

    @property
    def is_closed(self) -> bool:
        """Whether all internally owned HTTP connection pools have been closed."""
        return self._closed

    async def __aenter__(self) -> XLightsAutomationClient:
        """Enter an async context owning the client's HTTP pools."""
        self._ensure_open()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close every internally owned HTTP pool."""
        await self.aclose()

    async def aclose(self) -> None:
        """Release connection pools; safe to call more than once."""
        if self._closed:
            return
        self._closed = True
        for client in self._clients:
            await client.aclose()

    async def load_sequence(
        self,
        request: LoadSequenceRequest,
        *,
        timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S,
        cleanup_timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S,
    ) -> LoadSequenceResult:
        """Load a sequence and return its actual frame timing from xLights."""
        raw = await self._send(request.to_wire(), timeout_s=timeout_s)
        # HTTP success is the ownership boundary: xLights may now have opened the
        # sequence even if its response cannot be parsed into our typed result.
        self._pinned_client_index = raw.client_index
        try:
            body = _response_body(raw, "loadSequence")
            common = command_result(raw.response.status_code, body)
            frame_ms = _required_positive_float(body, "framems", "loadSequence")
            duration_value = body.get("len")
            duration_ms = _optional_int(duration_value, "len", "loadSequence")
            return LoadSequenceResult(
                result_code=common.result_code,
                message=common.message,
                sequence_name=required_text(body, "seq", "loadSequence"),
                sequence_path=Path(required_text(body, "fullseq", "loadSequence")),
                media_path=optional_path(body, "media"),
                duration_ms=duration_ms,
                frame_ms=frame_ms,
            )
        except XLightsAutomationError as primary_error:
            await self._close_after_load_parse_failure(
                primary_error,
                timeout_s=cleanup_timeout_s,
            )
            raise

    async def render_all(
        self,
        request: RenderAllRequest,
        *,
        timeout_s: float = DEFAULT_RENDER_TIMEOUT_S,
    ) -> CommandResult:
        """Render every effect in the currently open sequence."""
        raw = await self._send(request.to_wire(), timeout_s=timeout_s)
        body = _response_body(raw, "renderAll")
        return command_result(raw.response.status_code, body)

    async def export_video_preview(
        self,
        request: ExportVideoPreviewRequest,
        *,
        timeout_s: float = DEFAULT_EXPORT_TIMEOUT_S,
    ) -> ExportVideoPreviewResult:
        """Export the windowed House Preview video for the current sequence."""
        raw = await self._send(request.to_wire(), timeout_s=timeout_s)
        body = _response_body(raw, "exportVideoPreview")
        common = command_result(raw.response.status_code, body)
        return ExportVideoPreviewResult(
            result_code=common.result_code,
            message=common.message,
            output_path=Path(required_text(body, "output", "exportVideoPreview")),
        )

    async def close_sequence(
        self,
        request: CloseSequenceRequest | None = None,
        *,
        timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S,
    ) -> CommandResult:
        """Close the current sequence without saving it by default."""
        raw = await self._send((request or CloseSequenceRequest()).to_wire(), timeout_s=timeout_s)
        body = _response_body(raw, "closeSequence")
        result = command_result(raw.response.status_code, body)
        self._pinned_client_index = None
        return result

    async def get_models(
        self,
        request: GetModelsRequest | None = None,
        *,
        timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S,
    ) -> GetModelsResult:
        """Read the current xLights layout's requested model/group names."""
        raw = await self._send((request or GetModelsRequest()).to_wire(), timeout_s=timeout_s)
        body = _response_body(raw, "getModels")
        common = command_result(raw.response.status_code, body)
        models = body.get("models", [])
        if not isinstance(models, list) or not all(isinstance(name, str) for name in models):
            raise XLightsCommandError(f"xLights getModels response has invalid 'models': {body!r}")
        return GetModelsResult(
            result_code=common.result_code,
            message=common.message,
            models=tuple(models),
        )

    async def check_sequence(
        self,
        request: CheckSequenceRequest,
        *,
        timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S,
    ) -> CheckSequenceResult:
        """Run xLights' checker for a sequence and return its generated report path."""
        raw = await self._send(request.to_wire(), timeout_s=timeout_s)
        body = _response_body(raw, "checkSequence")
        common = command_result(raw.response.status_code, body)
        return CheckSequenceResult(
            result_code=common.result_code,
            message=common.message,
            output_path=optional_path(body, "output"),
        )

    async def render_preview(
        self,
        sequence_path: Path,
        *,
        output_path: Path | None = None,
        load_timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S,
        render_timeout_s: float = DEFAULT_RENDER_TIMEOUT_S,
        export_timeout_s: float = DEFAULT_EXPORT_TIMEOUT_S,
        close_timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S,
    ) -> PreviewResult:
        """Load, render, export, and close one preview using upstream's command order."""
        opened = False
        workflow_error: BaseException | None = None
        try:
            loaded = await self.load_sequence(
                LoadSequenceRequest(sequence_path),
                timeout_s=load_timeout_s,
                cleanup_timeout_s=close_timeout_s,
            )
            opened = True
            await self.render_all(RenderAllRequest(), timeout_s=render_timeout_s)
            exported = await self.export_video_preview(
                ExportVideoPreviewRequest(output_path),
                timeout_s=export_timeout_s,
            )
            return PreviewResult(
                video_path=exported.output_path,
                frame_rate=loaded.frame_rate,
                frame_ms=loaded.frame_ms,
            )
        except BaseException as exc:
            workflow_error = exc
            raise
        finally:
            if opened:
                try:
                    await self.close_sequence(timeout_s=close_timeout_s)
                except XLightsAutomationError as close_error:
                    if workflow_error is None:
                        raise
                    logger.warning(
                        "xLights preview cleanup failed after %s: %s",
                        type(workflow_error).__name__,
                        close_error,
                    )

    async def _send(self, payload: dict[str, str], *, timeout_s: float) -> _RawAutomationResponse:
        """Send once per instance, falling back only on a pre-send connect error."""
        self._ensure_open()
        if timeout_s <= 0:
            raise ValueError("xLights command timeout_s must be greater than zero")
        command = payload["cmd"]
        attempted_urls: list[str] = []
        for index in self._candidate_indexes():
            client = self._clients[index]
            base_url = self._base_urls[index]
            attempted_urls.append(base_url)
            try:
                response = await client.post(
                    "/xlDoAutomation",
                    json_body=payload,
                    timeout=httpx.Timeout(timeout_s),
                )
            except HttpTimeoutError as exc:
                raise XLightsTimeoutError(
                    f"xLights {command} timed out after {timeout_s:g}s at {base_url}."
                ) from exc
            except NetworkError as exc:
                if self._pinned_client_index is None and isinstance(exc.cause, httpx.ConnectError):
                    continue
                raise XLightsCommandError(
                    f"xLights {command} network failure at {base_url}; the stateful "
                    "command was not replayed on another instance."
                ) from exc
            except ApiError as exc:
                detail = (
                    f" Response: {exc.response_body_snippet}" if exc.response_body_snippet else ""
                )
                raise XLightsCommandError(
                    f"xLights {command} request failed at {base_url}: {exc}.{detail}"
                ) from exc
            self._active_client_index = index
            return _RawAutomationResponse(client_index=index, response=response)
        ports = ", ".join(url.rsplit(":", maxsplit=1)[-1] for url in attempted_urls)
        raise XLightsInstanceUnavailableError(
            "Unable to reach xLights' local automation API on port(s) "
            f"{ports}. Start a windowed xLights instance, enable its HTTP automation API, "
            "and retry; headless xLights cannot export a video preview."
        )

    def _candidate_indexes(self) -> tuple[int, ...]:
        """Try the last successful port first, then the remaining documented port."""
        if self._pinned_client_index is not None:
            return (self._pinned_client_index,)
        return (
            self._active_client_index,
            *(index for index in range(len(self._clients)) if index != self._active_client_index),
        )

    def _ensure_open(self) -> None:
        """Reject accidental reuse after connection pools have been released."""
        if self._closed:
            raise XLightsClientClosedError("xLights automation client is closed")

    async def _close_after_load_parse_failure(
        self,
        primary_error: XLightsAutomationError,
        *,
        timeout_s: float,
    ) -> None:
        """Close an HTTP-opened sequence without replacing its primary parse error."""
        try:
            await self.close_sequence(timeout_s=timeout_s)
        except XLightsAutomationError as close_error:
            logger.warning(
                "xLights loadSequence cleanup failed after %s: %s",
                type(primary_error).__name__,
                close_error,
            )


def _response_body(raw: _RawAutomationResponse, command: str) -> dict[str, Any]:
    """Decode one successful raw HTTP body without assuming a synthetic ``res`` field."""
    try:
        body = raw.response.json()
    except ValueError as exc:
        raise XLightsCommandError(
            f"xLights {command} returned invalid JSON at {raw.response.request.url}: {exc}"
        ) from exc
    if not isinstance(body, dict):
        raise XLightsCommandError(
            f"xLights {command} returned a non-object JSON response at "
            f"{raw.response.request.url}: {body!r}"
        )
    return body


def _required_positive_float(body: dict[str, Any], key: str, command: str) -> float:
    """Parse a required positive numeric response field."""
    try:
        value = float(body[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise XLightsCommandError(
            f"xLights {command} response omitted valid {key!r}: {body!r}"
        ) from exc
    if value <= 0:
        raise XLightsCommandError(f"xLights {command} response has non-positive {key!r}: {body!r}")
    return value


def _optional_int(value: Any, key: str, command: str) -> int | None:
    """Parse an optional integral response field while rejecting malformed values."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise XLightsCommandError(
            f"xLights {command} response has invalid {key!r}: {value!r}"
        ) from exc
