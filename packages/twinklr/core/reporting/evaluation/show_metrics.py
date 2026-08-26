"""Deterministic display/moving-head show metrics from trace-v2 truth."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.reporting.evaluation.show_manifest import (
    ShowEvaluationManifest,
    ShowTraceEntry,
    ShowTraceV2,
    load_show_evaluation_manifest,
    load_show_trace,
)
from twinklr.core.reporting.evaluation.sync_metrics import (
    DeterministicSyncMetrics,
    EffectInterval,
    OffsetDistribution,
    StructureSection,
    beat_grid_from_xsq,
    score_sync_metrics,
)
from twinklr.core.sequencer.show_coordination import coordination_schedule
from twinklr.core.sequencer.templates.group.target_expander import TargetExpander
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


class ExpectedEmissionAlignment(BaseModel):
    """One schedule start compared with the emitted start for its concrete team."""

    section_id: str
    pair_index: int = Field(ge=0)
    phase: Literal["call", "response"]
    target_ids: list[str]
    expected_start_ms: int = Field(ge=0)
    observed_start_ms: int | None = Field(default=None, ge=0)
    signed_error_ms: int | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class PairAlignment(BaseModel):
    """Truthful applicability and offsets for one declared call/response pair."""

    section_id: str
    pair_index: int = Field(ge=0)
    applicable: bool
    excluded_reason: str | None = None
    expected: list[ExpectedEmissionAlignment] = Field(default_factory=list)
    offsets: OffsetDistribution
    unmatched_expected_count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class SectionBoundaryAgreement(BaseModel):
    """Earliest emitted start for both parts at one declared section boundary."""

    section_id: str
    expected_boundary_ms: int = Field(ge=0)
    moving_head_start_ms: int | None = Field(default=None, ge=0)
    display_start_ms: int | None = Field(default=None, ge=0)
    signed_offset_ms: int | None = None
    status: Literal["observed", "missing_moving_head", "missing_display", "missing_both"]

    model_config = ConfigDict(extra="forbid", frozen=True)


class CrossPartAlignmentMetrics(BaseModel):
    """Cross-part schedule and section-boundary agreement; never VLM-authored."""

    applicable: bool
    excluded_reason: str | None = None
    pair_alignments: list[PairAlignment]
    section_boundaries: list[SectionBoundaryAgreement]
    emitted_entry_count: int = Field(ge=0)
    deduplicated_entry_count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class ShowMetrics(BaseModel):
    """Existing musical-grid metrics plus deterministic cross-part truth."""

    sync: DeterministicSyncMetrics
    cross_part: CrossPartAlignmentMetrics

    model_config = ConfigDict(extra="forbid", frozen=True)


def score_show_metrics(
    manifest_path: Path,
) -> tuple[ShowEvaluationManifest, ShowMetrics]:
    """Strictly load one show manifest and compute the zero-external deterministic tier."""
    manifest = load_show_evaluation_manifest(manifest_path)
    trace = load_show_trace(manifest_path.parent / manifest.trace_path)
    beat_grid = beat_grid_from_xsq(manifest_path.parent / manifest.xsq_path)
    entries = _deduplicate(trace.entries)
    sections = [
        StructureSection(
            name=section.section.name,
            start_ms=section.section.start_ms,
            end_ms=section.section.end_ms,
            bars=max(
                0.001,
                (section.section.end_ms - section.section.start_ms)
                / ((60_000 / beat_grid.tempo_bpm) * beat_grid.beats_per_bar),
            ),
        )
        for section in manifest.macro_plan.sections
    ]
    effects = [
        EffectInterval(
            start_ms=entry.start_ms,
            end_ms=entry.end_ms,
            element_name=entry.element_name,
            layer_index=entry.file_layer,
        )
        for entry in entries
    ]
    return manifest, ShowMetrics(
        sync=score_sync_metrics(beat_grid=beat_grid, effects=effects, sections=sections),
        cross_part=score_cross_part_alignment(
            manifest=manifest,
            trace=trace,
            beat_grid=beat_grid,
        ),
    )


def score_cross_part_alignment(
    *,
    manifest: ShowEvaluationManifest,
    trace: ShowTraceV2,
    beat_grid: BeatGrid,
) -> CrossPartAlignmentMetrics:
    """Compare schedule-derived starts with deduplicated trace-v2 emissions."""
    entries = _deduplicate(trace.entries)
    normalized = [_normalize_group(entry, manifest) for entry in entries]
    if not manifest.capability.cross_part_applicable:
        return CrossPartAlignmentMetrics(
            applicable=False,
            excluded_reason="cross-part metrics require both display and moving-head emissions",
            pair_alignments=[],
            section_boundaries=_section_boundaries(manifest, normalized),
            emitted_entry_count=len(trace.entries),
            deduplicated_entry_count=len(entries),
        )

    expander = TargetExpander(manifest.choreography_graph)
    mh_ids = set(manifest.moving_head_target_ids)
    schedule = coordination_schedule(
        manifest.macro_plan,
        beat_grid,
        manifest.choreography_graph,
    )
    pair_results: list[PairAlignment] = []
    for section in manifest.macro_plan.sections:
        section_id = section.section.section_id
        for pair_index, pair in enumerate(section.call_response_pairs):
            call_ids = tuple(expander.expand_target(pair.call))
            response_ids = tuple(expander.expand_target(pair.response))
            pair_ids = set(call_ids) | set(response_ids)
            spans_parts = bool(pair_ids & mh_ids) and bool(pair_ids - mh_ids)
            if not spans_parts:
                pair_results.append(
                    PairAlignment(
                        section_id=section_id,
                        pair_index=pair_index,
                        applicable=False,
                        excluded_reason="declared pair does not span moving-head and display parts",
                        offsets=_offset_distribution([]),
                        unmatched_expected_count=0,
                    )
                )
                continue
            expected_rows: list[ExpectedEmissionAlignment] = []
            signed: list[float] = []
            unmatched = 0
            for window in schedule:
                if window.phase not in {"call", "response"}:
                    continue
                ids = call_ids if window.phase == "call" else response_ids
                if set(window.target_ids) != set(ids):
                    continue
                if not (section.section.start_ms <= window.start_ms < section.section.end_ms):
                    continue
                candidates = [
                    entry.start_ms
                    for entry in normalized
                    if entry.section_id == section_id
                    and entry.group_id in ids
                    and window.start_ms <= entry.start_ms < window.end_ms
                ]
                observed = min(candidates) if candidates else None
                error = observed - window.start_ms if observed is not None else None
                if error is None:
                    unmatched += 1
                else:
                    signed.append(float(error))
                expected_rows.append(
                    ExpectedEmissionAlignment(
                        section_id=section_id,
                        pair_index=pair_index,
                        phase=cast("Literal['call', 'response']", window.phase),
                        target_ids=sorted(ids),
                        expected_start_ms=window.start_ms,
                        observed_start_ms=observed,
                        signed_error_ms=error,
                    )
                )
            pair_results.append(
                PairAlignment(
                    section_id=section_id,
                    pair_index=pair_index,
                    applicable=True,
                    expected=expected_rows,
                    offsets=_offset_distribution(signed),
                    unmatched_expected_count=unmatched,
                )
            )
    return CrossPartAlignmentMetrics(
        applicable=True,
        pair_alignments=pair_results,
        section_boundaries=_section_boundaries(manifest, normalized),
        emitted_entry_count=len(trace.entries),
        deduplicated_entry_count=len(entries),
    )


def _normalize_group(entry: ShowTraceEntry, manifest: ShowEvaluationManifest) -> ShowTraceEntry:
    graph_ids = {group.id for group in manifest.choreography_graph.groups}
    if entry.group_id in graph_ids:
        return entry
    reverse: dict[str, str] = {}
    for mapping in manifest.xlights_mapping.entries:
        for name in manifest.xlights_mapping.resolve(mapping.choreo_id):
            if name in reverse:
                raise ValueError(f"xLights element name {name!r} maps to multiple choreography ids")
            reverse[name] = mapping.choreo_id
    resolved = reverse.get(entry.group_id) or reverse.get(entry.element_name)
    if resolved is None and entry.backend == "moving_head":
        owned = sorted(manifest.moving_head_target_ids)
        if len(owned) == 1:
            resolved = owned[0]
    if resolved is None:
        raise ValueError(
            f"trace entry cannot be normalized to choreography graph: {entry.group_id}"
        )
    return cast("ShowTraceEntry", entry.model_copy(update={"group_id": resolved}))


def _deduplicate(entries: list[ShowTraceEntry]) -> list[ShowTraceEntry]:
    unique: dict[tuple[object, ...], ShowTraceEntry] = {}
    for entry in entries:
        key = (
            entry.backend,
            entry.event_id,
            entry.element_name,
            entry.file_layer,
            entry.start_ms,
            entry.end_ms,
        )
        unique.setdefault(key, entry)
    return sorted(
        unique.values(),
        key=lambda item: (item.start_ms, item.backend, item.element_name, item.event_id),
    )


def _section_boundaries(
    manifest: ShowEvaluationManifest,
    entries: list[ShowTraceEntry],
) -> list[SectionBoundaryAgreement]:
    by_section_backend: dict[tuple[str, str], list[int]] = defaultdict(list)
    for entry in entries:
        by_section_backend[(entry.section_id, entry.backend)].append(entry.start_ms)
    result = []
    for section in manifest.macro_plan.sections:
        section_id = section.section.section_id
        mh_values = by_section_backend.get((section_id, "moving_head"), [])
        display_values = by_section_backend.get((section_id, "display"), [])
        mh_start = min(mh_values) if mh_values else None
        display_start = min(display_values) if display_values else None
        status: Literal["observed", "missing_moving_head", "missing_display", "missing_both"]
        if mh_start is None and display_start is None:
            status = "missing_both"
        elif mh_start is None:
            status = "missing_moving_head"
        elif display_start is None:
            status = "missing_display"
        else:
            status = "observed"
        result.append(
            SectionBoundaryAgreement(
                section_id=section_id,
                expected_boundary_ms=section.section.start_ms,
                moving_head_start_ms=mh_start,
                display_start_ms=display_start,
                signed_offset_ms=(display_start - mh_start)
                if mh_start is not None and display_start is not None
                else None,
                status=status,
            )
        )
    return result


def _offset_distribution(offsets: list[float]) -> OffsetDistribution:
    # Reuse the public metric shape while keeping this module provider-free.
    if not offsets:
        return OffsetDistribution(count=0, signed_offsets_ms=[])
    absolute = sorted(abs(value) for value in offsets)
    import statistics

    p95_index = max(0, min(len(absolute) - 1, round(0.95 * len(absolute) + 0.5) - 1))
    return OffsetDistribution(
        count=len(offsets),
        signed_offsets_ms=offsets,
        mean_absolute_ms=statistics.fmean(absolute),
        median_absolute_ms=statistics.median(absolute),
        p95_absolute_ms=absolute[p95_index],
        mean_signed_ms=statistics.fmean(offsets),
        standard_deviation_ms=statistics.pstdev(offsets),
    )


__all__ = [
    "CrossPartAlignmentMetrics",
    "ExpectedEmissionAlignment",
    "PairAlignment",
    "SectionBoundaryAgreement",
    "ShowMetrics",
    "score_cross_part_alignment",
    "score_show_metrics",
]
