"""Typed xlDo command and result models for xLights automation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from twinklr.core.api.xlights.errors import XLightsCommandError


def _wire_bool(value: bool) -> str:
    """Render booleans in the string form used by xLights' xlDo documentation."""
    return "true" if value else "false"


@dataclass(frozen=True)
class LoadSequenceRequest:
    """Request to load a sequence into xLights' windowed sequencer."""

    sequence_path: Path
    prompt_issues: bool = False

    def to_wire(self) -> dict[str, str]:
        """Return the documented ``loadSequence`` JSON body."""
        return {
            "cmd": "loadSequence",
            "seq": str(self.sequence_path),
            "promptIssues": _wire_bool(self.prompt_issues),
        }


@dataclass(frozen=True)
class RenderAllRequest:
    """Request to render the currently open sequence."""

    high_definition: bool = False

    def to_wire(self) -> dict[str, str]:
        """Return the documented ``renderAll`` JSON body."""
        return {"cmd": "renderAll", "highdef": _wire_bool(self.high_definition)}


@dataclass(frozen=True)
class ExportVideoPreviewRequest:
    """Request a House Preview video export from the open sequence."""

    output_path: Path | None = None
    width: int | None = None
    height: int | None = None

    def to_wire(self) -> dict[str, str]:
        """Return the documented ``exportVideoPreview`` JSON body."""
        body = {"cmd": "exportVideoPreview"}
        if self.output_path is not None:
            body["filename"] = str(self.output_path)
        if self.width is not None:
            body["width"] = str(self.width)
        if self.height is not None:
            body["height"] = str(self.height)
        return body


@dataclass(frozen=True)
class CloseSequenceRequest:
    """Request that the current sequence is closed without saving it."""

    quiet: bool = True
    force: bool = True

    def to_wire(self) -> dict[str, str]:
        """Return the documented ``closeSequence`` JSON body."""
        return {
            "cmd": "closeSequence",
            "quiet": _wire_bool(self.quiet),
            "force": _wire_bool(self.force),
        }


@dataclass(frozen=True)
class GetModelsRequest:
    """Request xLights model and/or group names from the current layout."""

    include_models: bool = True
    include_groups: bool = True

    def to_wire(self) -> dict[str, str]:
        """Return the documented ``getModels`` JSON body."""
        return {
            "cmd": "getModels",
            "models": _wire_bool(self.include_models),
            "groups": _wire_bool(self.include_groups),
        }


@dataclass(frozen=True)
class GetViewsRequest:
    """Request view names from the currently open sequence."""

    def to_wire(self) -> dict[str, str]:
        return {"cmd": "getViews"}


@dataclass(frozen=True)
class GetOpenSequenceRequest:
    """Request the identity of the currently open sequence."""

    def to_wire(self) -> dict[str, str]:
        return {"cmd": "getOpenSequence"}


@dataclass(frozen=True)
class GetEffectIdsRequest:
    """Request all effect IDs, grouped by layer, for one model."""

    model: str

    def to_wire(self) -> dict[str, str]:
        return {"cmd": "getEffectIDs", "model": self.model}


@dataclass(frozen=True)
class GetEffectSettingsRequest:
    """Request one effect's settings from a model layer."""

    model: str
    layer: int
    effect_id: str

    def to_wire(self) -> dict[str, str]:
        return {
            "cmd": "getEffectSettings",
            "model": self.model,
            "layer": str(self.layer),
            "id": self.effect_id,
        }


@dataclass(frozen=True)
class AddEffectRequest:
    """Add one effect to the currently open sequence."""

    target: str
    effect: str
    settings: str
    palette: str
    layer: int
    start_ms: int
    end_ms: int

    def to_wire(self) -> dict[str, str]:
        return {
            "cmd": "addEffect",
            "target": self.target,
            "effect": self.effect,
            "settings": self.settings,
            "palette": self.palette,
            "layer": str(self.layer),
            "startTime": str(self.start_ms),
            "endTime": str(self.end_ms),
        }


@dataclass(frozen=True)
class DeleteEffectRequest:
    """Delete one known effect from the currently open sequence."""

    model: str
    layer: int
    effect_id: str

    def to_wire(self) -> dict[str, str]:
        return {
            "cmd": "deleteEffect",
            "model": self.model,
            "layer": str(self.layer),
            "id": self.effect_id,
        }


@dataclass(frozen=True)
class CheckSequenceRequest:
    """Request xLights' built-in check for one sequence path."""

    sequence_path: Path

    def to_wire(self) -> dict[str, str]:
        """Return the documented ``checkSequence`` JSON body."""
        return {"cmd": "checkSequence", "seq": str(self.sequence_path)}


@dataclass(frozen=True)
class CommandResult:
    """The common result fields xLights returns for a successful command."""

    result_code: int
    message: str | None = None


@dataclass(frozen=True)
class LoadSequenceResult(CommandResult):
    """Details returned by ``loadSequence`` for a successfully opened sequence."""

    sequence_name: str = ""
    sequence_path: Path = Path()
    media_path: Path | None = None
    duration_ms: int | None = None
    frame_ms: float = 0.0

    @property
    def frame_rate(self) -> float:
        """Sequence frame rate derived from xLights' documented ``framems`` field."""
        return 1000.0 / self.frame_ms


@dataclass(frozen=True)
class ExportVideoPreviewResult(CommandResult):
    """Result of an ``exportVideoPreview`` operation."""

    output_path: Path = Path()


@dataclass(frozen=True)
class GetModelsResult(CommandResult):
    """Layout element names reported by ``getModels``."""

    models: tuple[str, ...] = ()


@dataclass(frozen=True)
class GetViewsResult(CommandResult):
    views: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpenSequenceResult(CommandResult):
    sequence_name: str = ""
    sequence_path: Path = Path()
    frame_ms: float | None = None


@dataclass(frozen=True)
class EffectIdsResult(CommandResult):
    layers: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class EffectSettingsResult(CommandResult):
    model: str = ""
    layer: int = 0
    effect_id: str = ""
    name: str = ""
    settings: str | dict[str, str] = ""
    palette: str | dict[str, str] = ""
    start_ms: int = 0
    end_ms: int = 0


@dataclass(frozen=True)
class CheckSequenceResult(CommandResult):
    """Result of ``checkSequence`` including the generated report, if any."""

    output_path: Path | None = None


@dataclass(frozen=True)
class PreviewResult:
    """A locally rendered preview and the sequence rate used to sample it."""

    video_path: Path
    frame_rate: float
    frame_ms: float


def command_result(status_code: int, body: dict[str, Any]) -> CommandResult:
    """Build a common result from the raw server's authoritative HTTP status."""
    message = body.get("msg")
    if message is not None and not isinstance(message, str):
        message = str(message)
    return CommandResult(result_code=status_code, message=message)


def required_text(body: dict[str, Any], key: str, command: str) -> str:
    """Extract a non-empty response string or raise a stable protocol error."""
    value = body.get(key)
    if not isinstance(value, str) or not value:
        raise XLightsCommandError(
            f"xLights {command} response omitted required non-empty {key!r}: {body!r}"
        )
    return value


def optional_path(body: dict[str, Any], key: str) -> Path | None:
    """Convert an optional xLights path field without inventing a relative base."""
    value = body.get(key)
    if value in (None, ""):
        return None
    return Path(str(value))
