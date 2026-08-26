"""Backend-neutral deterministic xLights emission trace-v2 sidecars."""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict


class _BaseEmissionTrace(TypedDict):
    event_id: str
    section_id: str
    lane: str
    group_id: str
    template_id: str
    placement_id: NotRequired[str | None]
    placement_index: NotRequired[int]
    fallback_substitution: NotRequired[dict[str, str]]


class DisplayEmissionTrace(_BaseEmissionTrace):
    backend: Literal["display"]


class MovingHeadSource(TypedDict):
    fixture_id: str
    segment_id: str
    step_id: str


class MovingHeadEmissionTrace(_BaseEmissionTrace):
    backend: Literal["moving_head"]
    sources: list[MovingHeadSource]


type EmissionTrace = DisplayEmissionTrace | MovingHeadEmissionTrace


class EmissionTraceEntry(TypedDict):
    element_name: str
    effect_name: str
    logical_layer: int
    file_layer: int
    live_layer: int
    start_ms: int
    end_ms: int
    effectdb_ref: int
    palette_ref: int | None
    backend: Literal["display", "moving_head"]
    event_id: str
    section_id: str
    lane: str
    group_id: str
    template_id: str
    placement_id: NotRequired[str | None]
    placement_index: NotRequired[int]
    fallback_substitution: NotRequired[dict[str, str]]
    sources: NotRequired[list[MovingHeadSource]]


def build_xsq_trace_payload(
    entries: Iterable[EmissionTraceEntry],
    *,
    fallback_substitutions: int = 0,
) -> dict[str, Any]:
    """Build the stable trace-v2 document shared by MH, display, and combined shows."""
    rows = [dict(entry) for entry in entries]
    return {
        "schema_version": "twinklr-xsq-trace.v2",
        "entry_count": len(rows),
        "fallback_substitutions": fallback_substitutions,
        "entries": rows,
    }


def write_xsq_trace_sidecar(
    xsq_path: Path,
    entries: Iterable[EmissionTraceEntry],
    *,
    fallback_substitutions: int = 0,
) -> Path:
    """Write one trace-v2 document next to an XSQ artifact."""
    path = Path(f"{xsq_path}.trace.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_xsq_trace_payload(
                entries,
                fallback_substitutions=fallback_substitutions,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


__all__ = [
    "DisplayEmissionTrace",
    "EmissionTrace",
    "EmissionTraceEntry",
    "MovingHeadEmissionTrace",
    "MovingHeadSource",
    "build_xsq_trace_payload",
    "write_xsq_trace_sidecar",
]
