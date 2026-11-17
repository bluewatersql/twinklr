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
import logging
import re

from twinklr.core.sequencer.display.brightness import intensity_to_brightness
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import RenderEvent
from twinklr.core.sequencer.display.models.render_plan import RenderPlan
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

logger = logging.getLogger(__name__)


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
# Lowest scale budget normalisation may give a role: halfway to the role below it.
# A busy group is dimmed toward the next role down and never reaches it, and a lead is
# never taken near-dark by a brief resting event.  The scale multiplies each event's
# own planned brightness, so LEAD > SUPPORT > REST holds between events planned at the
# same intensity; a lead planned quieter than its support can still render dimmer.
# REST is bounded by the export's own resting floor.
_ROLE_SCALE_FLOOR = {
    FocalRoleKind.LEAD: (_ROLE_SCALE[FocalRoleKind.LEAD] + _ROLE_SCALE[FocalRoleKind.SUPPORT]) / 2,
    FocalRoleKind.SUPPORT: (_ROLE_SCALE[FocalRoleKind.SUPPORT] + _ROLE_SCALE[FocalRoleKind.REST])
    / 2,
    FocalRoleKind.REST: 0.0,
}
# Display RecipeCompiler raw IDs always terminate in a 64-character SHA-256 hex
# digest (and overlay/tail variants add non-coordinator suffixes).  Therefore only
# this exact terminal form is coordinator-owned; template/local/FE IDs may safely
# contain ``|coord-`` anywhere inside the compiler-generated prefix.
_COORDINATED_EVENT_SUFFIX = re.compile(r"\|coord-\d+$")


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


def _event_brightness(event: RenderEvent) -> float:
    """Brightness fraction an event renders at, before role dimming floors apply."""
    return intensity_to_brightness(event.intensity) * event.brightness_scale


def _normalize_display_role_budgets(
    render_plan: RenderPlan,
    macro_plan: MacroPlan,
    graph: ChoreographyGraph,
) -> RenderPlan:
    """Make every concrete target obey LEAD > SUPPORT > REST despite event counts.

    Raw activation is ``sum(brightness * duration_ms)`` per section/target, where
    brightness is the lit brightness the event's intensity maps to.  A common
    per-section base is the minimum ``raw / role_weight`` across emitted targets, and
    each target is scaled down to ``base * role_weight``.  This preserves the declared
    1.0/0.65/0.15 category semantics without increasing or clipping provider output.

    The scale is recorded as ``brightness_scale`` and leaves ``intensity`` alone, so
    the export applies it to the lit brightness instead of having the visible-brightness
    floor flatten it.
    A target is never scaled below ``_ROLE_SCALE_FLOOR`` for its role, so the budget
    ratios are exact only while no target reaches that bound.  The scale is relative
    to each event's planned intensity; it orders roles planned at the same intensity
    and does not reorder a lead the planner made quieter than its support.
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
                totals[key] = totals.get(key, 0.0) + _event_brightness(event) * duration

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
                        update={
                            "brightness_scale": min(
                                1.0,
                                max(_ROLE_SCALE_FLOOR[role], event.brightness_scale * multiplier),
                            )
                        },
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
                        "brightness_scale": _ROLE_SCALE[role],
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


def moving_head_dark_spans(
    macro_plan: MacroPlan,
    beat_grid: BeatGrid,
    graph: ChoreographyGraph,
    *,
    moving_head_target_ids: set[str],
) -> tuple[tuple[int, int], ...]:
    """Where the coordination schedule rests the moving heads, for the moving-head renderer.

    Each macro section's time that no window of the schedule activates a moving-head
    target in (a call/response phase answered by others, a sequenced or ripple step on
    another target), merged and in time order; empty when every section keeps them
    active throughout. The renderer plans the heads dark there before it plans
    section entry and repositioning (`RenderingPipeline(dark_spans=...)`).
    """
    schedule = coordination_schedule(macro_plan, beat_grid, graph)
    spans: list[tuple[int, int]] = []
    for section in macro_plan.sections:
        cursor = section.section.start_ms
        active = sorted(
            {
                window
                for target_id in moving_head_target_ids
                for window in _windows_for(schedule, section, target_id)
            }
        )
        for start, end in [*active, (section.section.end_ms, section.section.end_ms)]:
            if start > cursor:
                if spans and spans[-1][1] == cursor:
                    spans[-1] = (spans[-1][0], start)
                else:
                    spans.append((cursor, start))
            cursor = max(cursor, end)
    return tuple(spans)


def moving_head_focal_roles(
    macro_plan: MacroPlan,
    graph: ChoreographyGraph,
    *,
    moving_head_target_ids: set[str],
) -> dict[str, str]:
    """The moving heads' focal role (LEAD, SUPPORT or REST) in each macro section, by song
    section id, for the moving-head renderer (`RenderingPipeline(focal_roles=...)`), which
    adjusts the section's intensity by it, and the planner, who is told so.

    The renderer adjusts the whole rig's intensity, so a role applies only where every
    moving-head target holds it. A section that names no role for them is left out
    silently (the planner's intensity plays); one that names different roles for
    different targets, or a role for some and none for others, is left out with a
    warning: applying it to all would change heads the macro plan did not name.
    """
    expander = TargetExpander(graph)
    roles: dict[str, str] = {}
    for section in macro_plan.sections:
        named = _role_map(section, expander)
        found = {named.get(target_id) for target_id in moving_head_target_ids}
        if found == {None}:
            continue
        if len(found) == 1:
            role = found.pop()
            assert role is not None
            roles[section.section.section_id] = role.value
            continue
        logger.warning(
            "section %r: the macro plan gives the moving-head targets different focal roles "
            "(%s); the heads render as one rig, so no focal role adjusts their intensity",
            section.section.section_id,
            ", ".join(
                f"{target_id} {named[target_id].value if target_id in named else 'none'}"
                for target_id in sorted(moving_head_target_ids)
            ),
        )
    return roles


__all__ = [
    "CoordinationWindow",
    "coordinate_display_render_plan",
    "coordination_schedule",
    "moving_head_dark_spans",
    "moving_head_focal_roles",
    "validate_macro_coordination",
]
