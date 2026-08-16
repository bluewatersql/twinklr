"""Deterministic cross-backend consumption of typed macro choreography.

This module is deliberately an in-memory policy seam.  It does not write an XSQ,
invent timing from nominal tempo, or alter either backend's template selector.  It
projects one ``MacroPlan`` and the authoritative ``BeatGrid`` onto already-produced
branch plans immediately before rendering/export.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
import re

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    ColorIntent,
    ColorIntentKind,
    ExplicitColorIntent,
)
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import RenderEvent
from twinklr.core.sequencer.display.models.render_plan import RenderPlan
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.libraries.color import ColorPreset
from twinklr.core.sequencer.planning.models import (
    FocalRoleKind,
    MacroPlan,
    MacroSection,
)
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.templates.group.target_expander import TargetExpander
from twinklr.core.sequencer.theming import get_palette
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import CoordinationMode, StepUnit


@dataclass(frozen=True)
class CoordinationWindow:
    """One immutable, grid-derived activation window for concrete targets."""

    start_ms: int
    end_ms: int
    target_ids: tuple[str, ...]
    phase: str


_ROLE_SCALE = {
    FocalRoleKind.LEAD: 1.0,
    FocalRoleKind.SUPPORT: 0.65,
    FocalRoleKind.REST: 0.15,
}
_ROLE_MH_INTENSITY = {
    FocalRoleKind.LEAD: Intensity.INTENSE,
    FocalRoleKind.SUPPORT: Intensity.SMOOTH,
    FocalRoleKind.REST: Intensity.SLOW,
}

# Display RecipeCompiler raw IDs always terminate in a 64-character SHA-256 hex
# digest (and overlay/tail variants add non-coordinator suffixes).  Therefore only
# this exact terminal form is coordinator-owned; template/local/FE IDs may safely
# contain ``|coord-`` anywhere inside the compiler-generated prefix.
_COORDINATED_EVENT_SUFFIX = re.compile(r"\|coord-\d+$")

# Stable RGB representatives for the fixture-neutral wheel vocabulary.  Exact DMX
# positions remain fixture-adapter owned; this table only performs palette projection.
_PRESET_RGB: tuple[tuple[ColorPreset, tuple[int, int, int]], ...] = (
    (ColorPreset.RED, (255, 0, 0)),
    (ColorPreset.BLUE, (0, 0, 255)),
    (ColorPreset.GREEN, (0, 255, 0)),
    (ColorPreset.YELLOW, (255, 255, 0)),
    (ColorPreset.MAGENTA, (255, 0, 255)),
    (ColorPreset.CYAN, (0, 255, 255)),
    (ColorPreset.ORANGE, (255, 128, 0)),
    (ColorPreset.PURPLE, (128, 0, 128)),
    (ColorPreset.AMBER, (255, 191, 0)),
    (ColorPreset.LIME, (191, 255, 0)),
    (ColorPreset.WHITE, (255, 255, 255)),
    (ColorPreset.WARM_WHITE, (245, 241, 232)),
    (ColorPreset.COOL_WHITE, (220, 240, 255)),
    (ColorPreset.UV, (110, 0, 255)),
)


def _expand(expander: TargetExpander, target: PlanTarget) -> tuple[str, ...]:
    resolved = tuple(expander.expand_target(target))
    if not resolved:
        raise ValueError(f"Macro target '{target.type.value}:{target.id}' resolves to no groups")
    return resolved


def validate_macro_coordination(macro_plan: MacroPlan, graph: ChoreographyGraph) -> None:
    """Fail closed on unknown, empty, overlapping, or contradictory target teams."""

    expander = TargetExpander(graph)
    for assignment in macro_plan.focal_arc:
        _expand(expander, assignment.lead_target)
    for section in macro_plan.sections:
        has_pairs = bool(section.call_response_pairs)
        is_pair_mode = section.coordination_intent == CoordinationMode.CALL_RESPONSE
        if has_pairs and not is_pair_mode:
            raise ValueError(
                f"Section '{section.section.section_id}' call_response_pairs are only valid "
                "with CALL_RESPONSE coordination_intent"
            )
        if is_pair_mode and not has_pairs:
            raise ValueError(
                f"CALL_RESPONSE section '{section.section.section_id}' requires at least "
                "one typed pair"
            )
        role_owner: dict[str, FocalRoleKind] = {}
        for role in section.focal_roles:
            for target_id in _expand(expander, role.target):
                previous = role_owner.setdefault(target_id, role.role)
                if previous != role.role:
                    raise ValueError(
                        f"Concrete target '{target_id}' has conflicting focal roles in "
                        f"section '{section.section.section_id}'"
                    )

        paired_targets: set[str] = set()
        for pair in section.call_response_pairs:
            call = set(_expand(expander, pair.call))
            response = set(_expand(expander, pair.response))
            overlap = sorted(call & response)
            if overlap:
                raise ValueError(f"Call/response teams overlap after expansion: {overlap}")
            reused = sorted((call | response) & paired_targets)
            if reused:
                raise ValueError(
                    f"Concrete target(s) {reused} occur in more than one call/response pair"
                )
            paired_targets.update(call | response)


def _section_boundaries(
    section: MacroSection,
    beat_grid: BeatGrid,
    unit: StepUnit,
    duration: int,
) -> list[int]:
    start = section.section.start_ms
    end = section.section.end_ms
    if unit == StepUnit.BEAT:
        raw = beat_grid.beat_boundaries
        stride = duration
    elif unit == StepUnit.BAR:
        raw = beat_grid.bar_boundaries
        stride = duration
    else:
        raw = beat_grid.bar_boundaries
        stride = duration * 4

    inside = [round(value) for value in raw if start < value < end]
    base = [start, *inside, end]
    selected = [base[0]]
    cursor = stride
    while cursor < len(base) - 1:
        selected.append(base[cursor])
        cursor += stride
    if selected[-1] != end:
        selected.append(end)
    return selected


def _alternating_windows(
    section: MacroSection,
    beat_grid: BeatGrid,
    call_ids: tuple[str, ...],
    response_ids: tuple[str, ...],
    unit: StepUnit,
    duration: int,
) -> list[CoordinationWindow]:
    boundaries = _section_boundaries(section, beat_grid, unit, duration)
    if len(boundaries) < 2:
        raise ValueError(f"Section '{section.section.section_id}' is too short to coordinate")
    windows: list[CoordinationWindow] = []
    for index, (start, end) in enumerate(pairwise(boundaries)):
        if end <= start:
            continue
        is_call = index % 2 == 0
        windows.append(
            CoordinationWindow(
                start_ms=start,
                end_ms=end,
                target_ids=call_ids if is_call else response_ids,
                phase="call" if is_call else "response",
            )
        )
    phases = {window.phase for window in windows}
    if phases != {"call", "response"}:
        raise ValueError(
            f"Section '{section.section.section_id}' is too short for both call and "
            f"response phases at {unit.value} x {duration}"
        )
    return windows


def coordination_schedule(
    macro_plan: MacroPlan,
    beat_grid: BeatGrid,
    graph: ChoreographyGraph,
) -> tuple[CoordinationWindow, ...]:
    """Derive an immutable schedule solely from macro intent and detected boundaries."""

    validate_macro_coordination(macro_plan, graph)
    expander = TargetExpander(graph)
    all_target_ids = tuple(group.id for group in graph.groups)
    windows: list[CoordinationWindow] = []
    for section in macro_plan.sections:
        if section.call_response_pairs:
            paired: set[str] = set()
            for pair in section.call_response_pairs:
                call_ids = _expand(expander, pair.call)
                response_ids = _expand(expander, pair.response)
                paired.update(call_ids)
                paired.update(response_ids)
                windows.extend(
                    _alternating_windows(
                        section,
                        beat_grid,
                        call_ids,
                        response_ids,
                        pair.step_unit,
                        pair.step_duration,
                    )
                )
            unpaired = tuple(target_id for target_id in all_target_ids if target_id not in paired)
            if unpaired:
                windows.append(
                    CoordinationWindow(
                        section.section.start_ms,
                        section.section.end_ms,
                        unpaired,
                        "unpaired_support",
                    )
                )
            continue

        targets = list(all_target_ids)
        if section.coordination_intent in {
            CoordinationMode.UNIFIED,
            CoordinationMode.COMPLEMENTARY,
        }:
            windows.append(
                CoordinationWindow(
                    section.section.start_ms,
                    section.section.end_ms,
                    tuple(targets),
                    section.coordination_intent.value.lower(),
                )
            )
            continue
        if section.coordination_intent == CoordinationMode.CALL_RESPONSE:
            raise ValueError(
                f"CALL_RESPONSE section '{section.section.section_id}' requires a typed pair"
            )

        boundaries = _section_boundaries(section, beat_grid, StepUnit.BEAT, 1)
        for index, (start, end) in enumerate(pairwise(boundaries)):
            if section.coordination_intent == CoordinationMode.SEQUENCED:
                active: tuple[str, ...] = (targets[index % len(targets)],)
            else:  # RIPPLE: current target overlaps the previous propagation position.
                active = tuple(
                    dict.fromkeys(
                        (targets[index % len(targets)], targets[(index - 1) % len(targets)])
                    )
                )
            windows.append(
                CoordinationWindow(start, end, active, section.coordination_intent.value.lower())
            )
    return tuple(windows)


def _role_map(section: MacroSection, expander: TargetExpander) -> dict[str, FocalRoleKind]:
    result: dict[str, FocalRoleKind] = {}
    for role in section.focal_roles:
        for target_id in _expand(expander, role.target):
            result[target_id] = role.role
    return result


def _resolved_palette(macro_plan: MacroPlan, section_id: str) -> ResolvedPalette:
    palette_ref = macro_plan.palette_for_section(section_id)
    palette = get_palette(palette_ref.palette_id)
    colors = [stop.hex[:7].upper() for stop in palette.stops[:8]]
    return ResolvedPalette(colors=colors, active_slots=list(range(1, len(colors) + 1)))


def _windows_for(
    schedule: Iterable[CoordinationWindow],
    section: MacroSection,
    target_id: str,
) -> list[tuple[int, int]]:
    return [
        (window.start_ms, window.end_ms)
        for window in schedule
        if section.section.start_ms <= window.start_ms < section.section.end_ms
        and target_id in window.target_ids
    ]


def _macro_sections_for_emitted_id(
    emitted_section_id: str,
    macro_plan: MacroPlan,
    metadata: dict[str, str] | None = None,
) -> tuple[MacroSection, ...]:
    """Resolve compiler-flattened and generated transition identities to macro sections."""

    by_id = {section.section.section_id: section for section in macro_plan.sections}
    resolved: list[MacroSection] = []

    def add(identifier: str | None) -> None:
        if not identifier:
            return
        section = by_id.get(identifier) or by_id.get(identifier.split("|", 1)[0])
        if section is not None and section not in resolved:
            resolved.append(section)

    add(emitted_section_id)
    if metadata:
        add(metadata.get("source_id"))
        add(metadata.get("target_id"))
    if emitted_section_id.startswith("transition_"):
        for source_id in by_id:
            for target_id in by_id:
                if emitted_section_id == f"transition_{source_id}_to_{target_id}":
                    add(source_id)
                    add(target_id)
    if not resolved:
        raise ValueError(
            f"Emitted moving-head section '{emitted_section_id}' does not map to a macro section"
        )
    return tuple(resolved)


def _normalize_display_role_budgets(
    render_plan: RenderPlan,
    macro_plan: MacroPlan,
    graph: ChoreographyGraph,
) -> RenderPlan:
    """Make every concrete target obey LEAD > SUPPORT > REST despite event counts.

    Raw activation is ``sum(intensity * duration_ms)`` per section/target.  A common
    per-section base is the minimum ``raw / role_weight`` across emitted targets, and
    each target is scaled down to ``base * role_weight``.  This preserves the declared
    1.0/0.65/0.15 category semantics without increasing or clipping provider output.
    """

    expander = TargetExpander(graph)
    sections = {item.section.section_id: item for item in macro_plan.sections}
    totals: dict[tuple[str, str, FocalRoleKind], float] = {}
    for group in render_plan.groups:
        for layer in group.layers:
            for event in layer.events:
                section = sections[event.source.section_id]
                role = _role_map(section, expander).get(
                    event.source.group_id, FocalRoleKind.SUPPORT
                )
                key = (event.source.section_id, event.source.group_id, role)
                duration = max(0, event.end_ms - event.start_ms)
                totals[key] = totals.get(key, 0.0) + event.intensity * duration

    multipliers: dict[tuple[str, str, FocalRoleKind], float] = {}
    for section_id in sections:
        present = {
            key: total for key, total in totals.items() if key[0] == section_id and total > 0
        }
        if not present:
            continue
        common_budget = min(total / _ROLE_SCALE[key[2]] for key, total in present.items())
        for key, total in present.items():
            multipliers[key] = common_budget * _ROLE_SCALE[key[2]] / total

    groups = []
    for group in render_plan.groups:
        layers = []
        for layer in group.layers:
            events = []
            for event in layer.events:
                section = sections[event.source.section_id]
                role = _role_map(section, expander).get(
                    event.source.group_id, FocalRoleKind.SUPPORT
                )
                multiplier = multipliers.get(
                    (event.source.section_id, event.source.group_id, role), 1.0
                )
                if abs(multiplier - 1.0) < 1e-12:
                    multiplier = 1.0
                events.append(
                    event.model_copy(
                        update={"intensity": min(1.0, event.intensity * multiplier)},
                        deep=True,
                    )
                )
            layers.append(layer.model_copy(update={"events": events}, deep=True))
        groups.append(group.model_copy(update={"layers": layers}, deep=True))
    return render_plan.model_copy(update={"groups": groups}, deep=True)


def _slice_event(event: RenderEvent, windows: list[tuple[int, int]]) -> list[RenderEvent]:
    result: list[RenderEvent] = []
    for index, (window_start, window_end) in enumerate(windows):
        start = max(event.start_ms, window_start)
        end = min(event.end_ms, window_end)
        if start < end:
            result.append(
                event.model_copy(
                    update={
                        "event_id": f"{event.event_id}|coord-{index}",
                        "start_ms": start,
                        "end_ms": end,
                    },
                    deep=True,
                )
            )
    return result


def coordinate_display_render_plan(
    render_plan: RenderPlan,
    macro_plan: MacroPlan,
    beat_grid: BeatGrid,
    graph: ChoreographyGraph,
    *,
    moving_head_target_ids: set[str],
) -> RenderPlan:
    """Deep-copy and normalize display events for role, palette, timing, and ownership."""

    schedule = coordination_schedule(macro_plan, beat_grid, graph)
    expander = TargetExpander(graph)
    sections = {item.section.section_id: item for item in macro_plan.sections}
    groups = []
    for group in render_plan.groups:
        layers = []
        for layer in group.layers:
            events: list[RenderEvent] = []
            for event in layer.events:
                target_id = event.source.group_id
                if target_id in moving_head_target_ids:
                    continue
                if _COORDINATED_EVENT_SUFFIX.search(event.event_id):
                    events.append(event.model_copy(deep=True))
                    continue
                section = sections.get(event.source.section_id)
                if section is None:
                    raise ValueError(
                        f"Display event references unknown section '{event.source.section_id}'"
                    )
                roles = _role_map(section, expander)
                role = roles.get(target_id, FocalRoleKind.SUPPORT)
                normalized = event.model_copy(
                    update={
                        "intensity": min(1.0, event.intensity * _ROLE_SCALE[role]),
                        "palette": _resolved_palette(macro_plan, event.source.section_id),
                    },
                    deep=True,
                )
                active = _windows_for(schedule, section, target_id)
                events.extend(_slice_event(normalized, active))
            layers.append(layer.model_copy(update={"events": events}, deep=True))
        if any(layer.events for layer in layers):
            groups.append(group.model_copy(update={"layers": layers}, deep=True))
    coordinated = render_plan.model_copy(update={"groups": groups}, deep=True)
    return _normalize_display_role_budgets(coordinated, macro_plan, graph)


def _closest_preset(hex_color: str) -> ColorPreset:
    rgb = tuple(int(hex_color[index : index + 2], 16) for index in (1, 3, 5))
    return min(
        _PRESET_RGB,
        key=lambda item: sum((left - right) ** 2 for left, right in zip(rgb, item[1], strict=True)),
    )[0]


def coordinate_moving_head_plan(
    plan: ChoreographyPlan,
    macro_plan: MacroPlan,
    beat_grid: BeatGrid,
    moving_head_target_ids: set[str],
    available_template_ids: Iterable[str] | None = None,
    coordination_graph: ChoreographyGraph | None = None,
) -> ChoreographyPlan:
    """Project shared palette and role intent without changing MH template selection."""

    del beat_grid, available_template_ids
    graph_target_ids = set(moving_head_target_ids)
    expander = TargetExpander(coordination_graph) if coordination_graph is not None else None
    updated = []
    for planned in plan.sections:
        macro_section = _macro_sections_for_emitted_id(planned.section_name, macro_plan)[0]
        palette = _resolved_palette(macro_plan, macro_section.section.section_id)
        preset = _closest_preset(palette.colors[0])
        role = FocalRoleKind.SUPPORT
        for focal in macro_section.focal_roles:
            resolved = (
                set(_expand(expander, focal.target)) if expander is not None else {focal.target.id}
            )
            if resolved & graph_target_ids:
                role = focal.role
                break
        section_payload = planned.model_dump(mode="python")
        section_payload.update(
            {
                "intensity": _ROLE_MH_INTENSITY[role],
                "color_intent": ColorIntent(
                    selection=ExplicitColorIntent(
                        kind=ColorIntentKind.EXPLICIT,
                        palette_role=None,
                        explicit_color=preset,
                    )
                ),
            }
        )
        # Revalidation intentionally flips the private legacy-intent provenance marker:
        # these fields are now explicit macro-derived renderer intent, not compatibility
        # defaults inherited from the provider fixture.
        updated.append(planned.__class__.model_validate(section_payload))
    return plan.model_copy(update={"sections": updated}, deep=True)


def coordinate_moving_head_segments(
    segments: list[FixtureSegment],
    macro_plan: MacroPlan,
    beat_grid: BeatGrid,
    graph: ChoreographyGraph,
    *,
    moving_head_target_ids: set[str],
) -> list[FixtureSegment]:
    """Slice emitted MH segments against the same immutable coordination schedule."""

    schedule = coordination_schedule(macro_plan, beat_grid, graph)
    result: list[FixtureSegment] = []
    for segment in segments:
        if segment.metadata.get("coordination_source") == "macro_plan+beat_grid":
            result.append(segment.model_copy(deep=True))
            continue
        windows: list[tuple[int, int]] = []
        macro_sections = _macro_sections_for_emitted_id(
            segment.section_id, macro_plan, segment.metadata
        )
        for macro_section in macro_sections:
            for target_id in sorted(moving_head_target_ids):
                windows.extend(_windows_for(schedule, macro_section, target_id))
        for index, (window_start, window_end) in enumerate(sorted(set(windows))):
            start = max(segment.t0_ms, window_start)
            end = min(segment.t1_ms, window_end)
            if start < end:
                metadata = dict(segment.metadata)
                metadata["coordination_source"] = "macro_plan+beat_grid"
                result.append(
                    segment.model_copy(
                        update={
                            "segment_id": f"{segment.segment_id}|coord-{index}",
                            "t0_ms": start,
                            "t1_ms": end,
                            "metadata": metadata,
                        },
                        deep=True,
                    )
                )
    return result


__all__ = [
    "CoordinationWindow",
    "coordinate_display_render_plan",
    "coordinate_moving_head_plan",
    "coordinate_moving_head_segments",
    "coordination_schedule",
    "validate_macro_coordination",
]
