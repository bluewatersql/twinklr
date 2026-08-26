"""Renderer-neutral xLights effect emission.

The display and moving-head renderers build different settings strings, but everything
after that point is one contract: seeded positional registries, effect-grid timing,
file/live layer translation, XSequence placement, and provenance trace generation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypedDict

from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS, SEQUENCE_TIMING
from twinklr.core.formats.xlights.sequence.models.xsq import (
    ColorPalette,
    Effect,
    EffectDB,
    XSequence,
)
from twinklr.core.formats.xlights.sequence.registry import PositionalRegistry
from twinklr.core.formats.xlights.sequence.trace import EmissionTrace, EmissionTraceEntry

LIVE_LAYER_BASE = 99


class LiveEmissionPayload(TypedDict):
    """Offline representation of the xLights ``addEffect`` delivery fields."""

    target: str
    effect: str
    settings: str
    palette: str
    layer: int
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class EmissionRequest:
    """One renderer-neutral effect request at the shared seam."""

    target: str
    effect: str
    settings: str
    palette: str | None
    start_ms: int
    end_ms: int
    logical_layer: int
    trace: EmissionTrace
    label: str | None = None

    def __post_init__(self) -> None:
        if not self.target or not self.effect:
            raise ValueError("Emission target and effect must be non-empty")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("Emission requires 0 <= start_ms < end_ms")
        if self.logical_layer < 0:
            raise ValueError("Emission logical_layer must be non-negative")


@dataclass(frozen=True)
class EmissionRecord:
    """Resolved file and live representations of one request."""

    target: str
    effect: str
    settings: str
    palette: str | None
    start_ms: int
    end_ms: int
    logical_layer: int
    file_layer: int
    live_layer: int
    ref: int
    palette_ref: int | None
    label: str | None
    trace: EmissionTraceEntry

    @property
    def live_payload(self) -> LiveEmissionPayload:
        """Return live-delivery fields from the exact file-emission resolution."""
        return {
            "target": self.target,
            "effect": self.effect,
            "settings": self.settings,
            "palette": self.palette or "",
            "layer": self.live_layer,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
        }


class EmissionSession:
    """Emit many effects into one sequence while preserving all positional state.

    Existing registry order is immutable. File layers are allocated from a snapshot of
    each target's highest occupied layer, while logical layers remain available for
    renderer blend semantics and translate to reserved live layers starting at 99.
    """

    def __init__(self, sequence: XSequence) -> None:
        if sequence.document_origin == "parsed":
            raise ValueError(
                "P3-T6 emission is fresh-only and will not rewrite a parsed xLights sequence"
            )
        if sequence.head.sequence_timing != SEQUENCE_TIMING:
            raise ValueError(
                f"Emission requires the sole {SEQUENCE_TIMING} timing header; "
                f"got {sequence.head.sequence_timing!r}"
            )
        if sequence.effect_db.entries and sequence.effect_db.entries[0] != "":
            raise ValueError(
                "EffectDB index 0 must be the reserved empty entry; existing entries "
                "are never shifted"
            )
        self.sequence = sequence
        self._effectdb = PositionalRegistry(
            sequence.effect_db.entries,
            reserve_empty_zero=True,
        )
        self._palettes = PositionalRegistry(
            [palette.settings for palette in sequence.color_palettes],
        )
        self._file_layer_bases = {
            element.element_name: self._first_free_layer(element.layers)
            for element in sequence.element_effects
        }
        self._pending: list[EmissionRequest] = []
        self._emitted_intervals: dict[tuple[str, int], list[tuple[int, int, str]]] = {}

    @staticmethod
    def _first_free_layer(layers: Sequence[object]) -> int:
        occupied = [
            index for index, layer in enumerate(layers) if bool(getattr(layer, "effects", ()))
        ]
        return max(occupied, default=-1) + 1

    @staticmethod
    def _quantize(value: int) -> int:
        return ((value + EFFECT_GRID_MS // 2) // EFFECT_GRID_MS) * EFFECT_GRID_MS

    @classmethod
    def quantize_interval(cls, start_ms: int, end_ms: int) -> tuple[int, int]:
        """Snap endpoints to the effect grid without collapsing positive intervals."""
        start = cls._quantize(start_ms)
        end = cls._quantize(end_ms)
        if end <= start:
            end = start + EFFECT_GRID_MS
        return start, end

    def emit(self, request: EmissionRequest) -> EmissionRecord:
        """Resolve and append one effect, returning both delivery representations."""
        return self.emit_batch((request,))[0]

    def queue(self, request: EmissionRequest) -> None:
        """Queue a renderer request for atomic batch timing validation."""
        self._pending.append(request)

    def flush(self) -> tuple[EmissionRecord, ...]:
        """Validate then emit the queued batch; retain it unchanged if validation fails."""
        records = self.emit_batch(tuple(self._pending))
        self._pending.clear()
        return records

    def emit_batch(self, requests: tuple[EmissionRequest, ...]) -> tuple[EmissionRecord, ...]:
        """Prevalidate and append a complete renderer batch without reordering it."""
        resolved = [
            (*self.quantize_interval(item.start_ms, item.end_ms), item) for item in requests
        ]
        by_lane = {key: list(value) for key, value in self._emitted_intervals.items()}
        for start_ms, end_ms, request in resolved:
            key = (request.target, request.logical_layer)
            for prior_start, prior_end, prior_event in by_lane.setdefault(key, []):
                if start_ms < prior_end and prior_start < end_ms:
                    raise ValueError(
                        "20 ms effect-grid quantization creates an overlap on "
                        f"target={request.target!r}, logical_layer={request.logical_layer}: "
                        f"{prior_event!r} -> {prior_start}-{prior_end}ms conflicts with "
                        f"{request.trace['event_id']!r} -> {start_ms}-{end_ms}ms. "
                        "Adjust source timing; emission does not reorder or merge effects."
                    )
            by_lane[key].append((start_ms, end_ms, request.trace["event_id"]))

        records: list[EmissionRecord] = []
        for start_ms, end_ms, request in resolved:
            records.append(self._append_resolved(request, start_ms=start_ms, end_ms=end_ms))
        self._emitted_intervals = by_lane
        return tuple(records)

    def _append_resolved(
        self,
        request: EmissionRequest,
        *,
        start_ms: int,
        end_ms: int,
    ) -> EmissionRecord:
        """Append one already-prevalidated request."""
        ref = self._effectdb.register(request.settings)
        palette_ref = (
            self._palettes.register(request.palette) if request.palette is not None else None
        )
        base = self._file_layer_bases.setdefault(request.target, 0)
        file_layer = base + request.logical_layer
        live_layer = LIVE_LAYER_BASE + request.logical_layer

        self.sequence.effect_db = EffectDB(entries=self._effectdb.get_entries())
        self.sequence.color_palettes = [
            ColorPalette(settings=value) for value in self._palettes.get_entries()
        ]
        self.sequence.add_effect(
            request.target,
            Effect(
                effect_type=request.effect,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
                ref=ref,
                palette=str(palette_ref) if palette_ref is not None else "",
                label=request.label,
            ),
            layer_index=file_layer,
        )

        trace: EmissionTraceEntry = {
            **request.trace,
            "element_name": request.target,
            "effect_name": request.effect,
            "logical_layer": request.logical_layer,
            "file_layer": file_layer,
            "live_layer": live_layer,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "effectdb_ref": ref,
            "palette_ref": palette_ref,
        }
        self.sequence.emission_trace_entries.append(trace)
        return EmissionRecord(
            target=request.target,
            effect=request.effect,
            settings=request.settings,
            palette=request.palette,
            start_ms=start_ms,
            end_ms=end_ms,
            logical_layer=request.logical_layer,
            file_layer=file_layer,
            live_layer=live_layer,
            ref=ref,
            palette_ref=palette_ref,
            label=request.label,
            trace=trace,
        )


__all__ = [
    "LIVE_LAYER_BASE",
    "EmissionRecord",
    "EmissionRequest",
    "EmissionSession",
    "LiveEmissionPayload",
]
