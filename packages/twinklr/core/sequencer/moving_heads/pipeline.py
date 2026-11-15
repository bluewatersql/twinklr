from __future__ import annotations

import bisect
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from fractions import Fraction
import hashlib
from itertools import pairwise
import json
import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel

    from twinklr.core.formats.xlights.layout.models.rgb_effects import Model
    from twinklr.core.sequencer.models.context import FixtureContext
    from twinklr.core.sequencer.models.template import TemplateDoc, TemplatePreset

from twinklr.core.agents.sequencer.moving_heads import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.models import PlanSection, flatten_plan_segment
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup, InitialFixtureState
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import (
    UnsupportedRenderModeError,
    preflight_render_policy,
)
from twinklr.core.curves.generator import CurveGenerator
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS, resolve_media_file
from twinklr.core.formats.xlights.sequence.models.xsq import (
    TimeMarker,
    TimingTrack,
)
from twinklr.core.sequencer.models.context import (
    SectionRenderIntent,
    TemplateCompileContext,
    TimedChannelIntent,
)
from twinklr.core.sequencer.models.enum import ChannelName, Intensity
from twinklr.core.sequencer.models.moving_heads.physical import (
    AXIS_KEYS,
    DISCRETE_KEYS,
    ContinuousTrajectory,
    DiscreteTrajectory,
    PhysicalChannelError,
    PhysicalPoint,
    RenderLock,
    TransitionDiagnostic,
)
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.moving_heads.topology import rig_topology
from twinklr.core.sequencer.models.template import RepeatMode
from twinklr.core.sequencer.models.transition import TransitionRegistry
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.channel_blender import ChannelBlender
from twinklr.core.sequencer.moving_heads.compile.physical import is_physical_template
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    FALLBACK_METADATA_KEY,
    FailureMode,
    HeadFollow,
    entry_feasible,
    follow_cues,
    plan_prepositions,
    worst_case_entry_ms,
)
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    apply_entry_window,
    compile_physical_template,
    compile_template,
)
from twinklr.core.sequencer.moving_heads.compile.transition_detector import TransitionDetector
from twinklr.core.sequencer.moving_heads.compile.transition_planner import TransitionPlanner
from twinklr.core.sequencer.moving_heads.compile.transition_segment_compiler import (
    TransitionSegmentCompiler,
)
from twinklr.core.sequencer.moving_heads.delivery import (
    DeliveryArtifacts,
    build_physical_sequence,
    export_delivery,
    export_physical_delivery,
)
from twinklr.core.sequencer.moving_heads.diagnostics import MHDiagnostic, audit_legacy_controls
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    ENCODER_VERSION,
    EncodedFixtureFrame,
    coalesce_frames,
    encode_fixture_frames,
    frame_times,
    quantized_cues,
)
from twinklr.core.sequencer.moving_heads.export.xsq_adapter import (
    check_physical_models,
    physical_run_requests,
)
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.moving_heads.identity import (
    LEGACY_BACKEND_ID,
    LEGACY_RENDERER_REVISION,
    PHYSICAL_RENDERER_REVISION,
    render_fingerprint,
)
from twinklr.core.sequencer.moving_heads.libraries.color import ColorPreset
from twinklr.core.sequencer.moving_heads.templates import (
    get_template,
    load_builtin_templates,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseError,
    MusicalPhaseMap,
    build_musical_phase_map,
    musical_phase_fraction,
    musical_time_at,
)
from twinklr.core.sequencer.vocabulary.visual import PaletteRole

logger = logging.getLogger(__name__)

# --- Module-level constants and helpers ---

ENERGY_TO_INTENSITY: dict[str, Intensity] = {
    "CHILL": Intensity.SLOW,
    "MODERATE": Intensity.SMOOTH,
    "ENERGETIC": Intensity.DRAMATIC,
    "INTENSE": Intensity.FAST,
}
"""Maps energy-level keywords (from preset IDs) to movement Intensity enums."""

PALETTE_ROLE_TO_COLOR: dict[PaletteRole, ColorPreset | None] = {
    PaletteRole.PRIMARY: ColorPreset.RED,
    PaletteRole.ACCENT: ColorPreset.MAGENTA,
    PaletteRole.WARM: ColorPreset.AMBER,
    PaletteRole.COOL: ColorPreset.CYAN,
    PaletteRole.NEUTRAL: ColorPreset.WHITE,
}
"""Deterministic wheel presets for renderer vocabulary roles.

Legacy omission is tracked separately on ``PlanSection``. Consequently every explicit
palette role, including PRIMARY, remains an actionable renderer request.
"""


def _log_applied_preset_name(name: str) -> None:
    """Emit the selected preset's user-facing name through the shipped renderer logger."""
    logger.debug("Applying preset: %s", name)


def resolve_section_preset(
    section: PlanSection, template_doc: TemplateDoc
) -> TemplatePreset | None:
    """Resolve the preset a section applies to its template.

    A preset the document declares wins. Otherwise a preset id naming an energy
    level becomes a preset patching every step's movement and dimmer intensity.
    Any other id, or none, applies no preset. `RenderingPipeline.render` and the
    control audit both resolve presets here.

    Args:
        section: The (flattened) plan section.
        template_doc: The section's template document.

    Returns:
        The preset to apply, or None.
    """
    template = template_doc.template
    preset = None
    if section.preset_id:
        try:
            preset = next(p for p in template_doc.presets if p.preset_id == section.preset_id)
            _log_applied_preset_name(preset.name)
        except StopIteration:
            # Preset not found - try to infer intensity from preset_id
            from twinklr.core.sequencer.models.template import StepPatch, TemplatePreset

            preset_id_upper = section.preset_id.upper()
            if preset_id_upper in ENERGY_TO_INTENSITY:
                # Auto-create preset with inferred intensity
                intensity = ENERGY_TO_INTENSITY[preset_id_upper]
                step_patches = {
                    step.step_id: StepPatch(
                        movement={"intensity": intensity.value},
                        dimmer={"intensity": intensity.value},
                    )
                    for step in template.steps
                }
                preset = TemplatePreset(
                    preset_id=section.preset_id,
                    name=section.preset_id.title(),
                    defaults={},
                    step_patches=step_patches,
                )
                logger.debug(
                    f"Auto-generated preset '{section.preset_id}' "
                    f"with intensity {intensity.value} for template '{section.template_id}'"
                )
            else:
                logger.warning(
                    f"Preset '{section.preset_id}' not found for template "
                    f"'{section.template_id}' and couldn't infer intensity, using base template"
                )
    return preset


def _compute_section_duration_ms(start_bar: int, end_bar: int, beat_grid: BeatGrid) -> int:
    """Compute the duration of a section in milliseconds.

    Measured between the section's detected downbeats rather than as a bar count
    times a song-wide average, so the duration matches what the renderer emits.

    Args:
        start_bar: First bar of the section (1-indexed).
        end_bar: Last bar of the section (1-indexed, inclusive).
        beat_grid: Beat grid supplying the detected downbeats.

    Returns:
        Duration in milliseconds (rounded to int).
    """
    return int(beat_grid.get_bar_start_ms(end_bar) - beat_grid.get_bar_start_ms(start_bar - 1))


def offered_template_ids(job_config: JobConfig, template_ids: Sequence[str]) -> list[str]:
    """The templates the planner may be offered under the job's render mode.

    `legacy_v1` offers every template. `physical_v2` offers only templates the physical
    renderer can compile as authored (`is_physical_template`), so a plan never names a
    template that fails at render after paid planning.

    Raises:
        UnsupportedRenderModeError: Under `physical_v2`, when no template qualifies.
    """
    if job_config.moving_heads.mode == "legacy_v1":
        return list(template_ids)
    offered = [
        template_id
        for template_id in template_ids
        if is_physical_template(get_template(template_id).template)
    ]
    if not offered:
        raise UnsupportedRenderModeError(
            f"moving_heads.mode 'physical_v2' has no template with physical data to offer the "
            f"planner: none of the {len(template_ids)} loaded templates carries "
            "movement.physical, without legacy data, on every step. Load physical templates "
            "(--template-dir) or set moving_heads.mode to 'legacy_v1'"
        )
    return offered


def physical_cue_limits(phase_map: MusicalPhaseMap, duration_ms: int) -> tuple[int, int]:
    """The frame-grid span a physical cue may occupy: `(start_limit_ms, end_limit_ms)`.

    The start is the covered phase span's start rounded up to the frame grid; the end
    is the earlier of the song's last whole frame and the covered end rounded down.
    Outside it every fixture is held dark.
    """
    start = -(-Fraction(phase_map.covered_start_ms) // EFFECT_GRID_MS) * EFFECT_GRID_MS
    covered_end = Fraction(phase_map.covered_end_ms) // EFFECT_GRID_MS * EFFECT_GRID_MS
    return int(start), int(min(duration_ms // EFFECT_GRID_MS * EFFECT_GRID_MS, covered_end))


_POSE = (ChannelName.PAN, ChannelName.TILT)
_WHEELS = (ChannelName.COLOR, ChannelName.GOBO)


def _enter_section(
    cues: Sequence[FixtureSegment],
    kept: Mapping[str, Sequence[HeadFollow]],
    profiles: Mapping[str, FixtureCapabilities],
    initial_states: Mapping[str, InitialFixtureState],
    *,
    section_start_ms: int,
    phase_map: MusicalPhaseMap,
    failure_mode: FailureMode,
    locks: Sequence[RenderLock] = (),
) -> tuple[list[FixtureSegment], list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep a section's uncut entry where it plays as authored, else open it with a window.

    `kept` holds, per fixture, the cues kept so far as `follow_cues` followed them. A
    fixture whose cues `plan_prepositions` would play as authored after its last kept
    cue, up to and including its first gap (in `error` mode: `_plays_as_authored`),
    keeps its cues uncut (`skipped`); a last kept cue that may be substituted under
    `failure_mode` leaves the head's state unknown, so that fixture always enters
    through a window. For every other fixture `worst_case_entry_ms` bounds the
    reposition into any pose and wheel state its section cues hold, from where its kept
    cues can have left the head (`_predecessor`). Each fixture's window is its own, so a
    head missing from the rig changes no other head's output: from the section start,
    the fewest whole beats on the phase map whose end, rounded up to the frame grid,
    leaves the fixture its bound after its last kept cue; `apply_entry_window` cuts or
    drops its cues there. A fixture with an unknown bound, or whose bound already fits
    before the section, gets no window, but its first revealed cue still begins where
    its shutter state can take effect.

    Returns:
        The kept cues, in input order, one record per cue dropped inside a window, and
        one record per fixture with cues: its bound, its window, its first kept cue and
        `skipped`, `cut` or `none` (no window was needed).
    """
    if not cues:
        return [], [], []
    by_fixture: dict[str, list[FixtureSegment]] = defaultdict(list)
    for cue in sorted(cues, key=lambda cue: cue.t0_ms):
        by_fixture[cue.fixture_id].append(cue)
    bounds: dict[str, int | None] = {}
    windows: dict[str, int | None] = {}
    skipped: set[str] = set()
    for fixture_id, own in by_fixture.items():
        profile = profiles[fixture_id]
        before = kept.get(fixture_id, ())
        initial = initial_states.get(fixture_id)
        last = before[-1] if before else None
        bounds[fixture_id] = windows[fixture_id] = None
        if (last is None or not _substitutable(last.segment, failure_mode)) and _plays_as_authored(
            own, profile, last, initial, locks
        ):
            skipped.add(fixture_id)
            continue
        channels = [ch for ch in _POSE if AXIS_KEYS[ch] in profile.axes]
        predecessor = _predecessor(before, initial, channels, profile, failure_mode)
        bound = bounds[fixture_id] = (
            None
            if predecessor is None
            else worst_case_entry_ms(
                profile,
                entry_pose={ch: _pose_range(own, ch) for ch in channels},
                entry_wheels=_wheel_states(own, profile),
                pose_envelope=predecessor[0],
                held_wheels=predecessor[1],
                residual_ms=predecessor[2],
                frame_ms=EFFECT_GRID_MS,
            )
        )
        if bound is not None:
            needed = (last.segment.t1_ms if last else 0) + bound
            windows[fixture_id] = _window_end(phase_map, section_start_ms, needed)

    # Every entry not played as authored begins where its shutter can take effect, with
    # or without a dark window before it (a bound that fits before the section, or none).
    window_ends = {
        fixture_id: by_fixture[fixture_id][0].t0_ms if end is None else end
        for fixture_id, end in windows.items()
        if fixture_id not in skipped
    }
    entered, dropped = apply_entry_window(cues, window_ends, profiles=profiles)
    first = {}
    for cue in sorted(entered, key=lambda cue: -cue.t0_ms):
        first[cue.fixture_id] = cue.t0_ms
    records = []
    for fixture_id in sorted(by_fixture):
        end = windows[fixture_id]
        action = "skipped" if fixture_id in skipped else "none" if end is None else "cut"
        records.append(
            {
                "section_id": cues[0].section_id,
                "fixture_id": fixture_id,
                "bound_ms": bounds[fixture_id],
                "section_start_ms": section_start_ms,
                "window_end_ms": end,
                "window_ms": None if end is None else end - section_start_ms,
                "first_cue_ms": first.get(fixture_id),
                "action": action,
            }
        )
    return entered, dropped, records


def _plays_as_authored(
    own: Sequence[FixtureSegment],
    profile: FixtureCapabilities,
    last: HeadFollow | None,
    initial: InitialFixtureState | None,
    locks: Sequence[RenderLock],
) -> bool:
    """Whether a fixture's section cues play as authored after `last` up to its first gap.

    An uncut entry may continue the previous cue's motion through the section's
    back-to-back cues; the transaction at the first gap must still fit with that motion
    under way. After it the head is settled, as wherever the gate placed the section.
    """
    if not entry_feasible(
        own[0], profile, after=last, initial=initial, locks=locks, frame_ms=EFFECT_GRID_MS
    ):
        return False
    chain = [own[0]]
    for cue in own[1:]:
        if cue.t0_ms != chain[-1].t1_ms:
            followed = follow_cues(chain, profile, frame_ms=EFFECT_GRID_MS, after=last)[-1]
            return entry_feasible(
                cue, profile, after=followed, initial=initial, locks=locks, frame_ms=EFFECT_GRID_MS
            )
        chain.append(cue)
    return True


def _window_end(phase_map: MusicalPhaseMap, section_start_ms: int, required_ms: int) -> int | None:
    """The first frame boundary at or after a whole beat from the section start that is
    no earlier than `required_ms`; None when the section start already is."""
    origin = min(max(section_start_ms, phase_map.covered_start_ms), phase_map.covered_end_ms)
    if required_ms <= origin:
        return None
    try:
        beats = math.ceil(
            musical_phase_fraction(phase_map, required_ms, origin_ms=origin, period_beats=1.0)
        )
        end = musical_time_at(phase_map, Fraction(beats), origin_ms=origin, period_beats=1.0)
    except MusicalPhaseError:
        end = Fraction(required_ms)  # past the covered span, where every cue is dropped
    return int(-(-end // EFFECT_GRID_MS) * EFFECT_GRID_MS)


def _substitutable(cue: FixtureSegment, failure_mode: FailureMode) -> bool:
    """Whether the transaction pass may play `cue` other than as authored."""
    return failure_mode != "error" and cue.metadata.get(FALLBACK_METADATA_KEY) == failure_mode


def _predecessor(
    before: Sequence[HeadFollow],
    initial: InitialFixtureState | None,
    channels: Sequence[ChannelName],
    profile: FixtureCapabilities,
    failure_mode: FailureMode,
) -> tuple[dict[ChannelName, tuple[float, float]], dict[ChannelName, set[str]], Fraction] | None:
    """Where the kept cues can have left the head: `(pose envelope, wheel states held,
    motion still under way after the last kept cue's end)`.

    The last kept cue's last frame, followed with the planner's head model; under a
    fallback, every kept cue back to the last one that cannot be substituted (or to the
    initial state), since any of them may be where the head stopped. None when that
    reaches an unknown initial state or motion whose timing is unknown.
    """
    end_ms = before[-1].segment.t1_ms if before else 0
    poses: list[dict[ChannelName, tuple[float, float]]] = []
    held: dict[ChannelName, set[str]] = defaultdict(set)
    residual = Fraction(0)
    for follow in reversed(before):
        cue = follow.segment
        fixed = not _substitutable(cue, failure_mode)
        poses.append(
            {
                ch: _last_frame_pose(cue, ch) if fixed and not poses else _pose_range([cue], ch)
                for ch in channels
            }
        )
        for channel in _WHEELS:
            capability = profile.discrete.get(DISCRETE_KEYS[channel])
            if capability is not None:
                last = cue.t1_ms - EFFECT_GRID_MS
                held[channel].add(_wheel_state(cue, channel, last, capability.default_state))
        if follow.settled_ms is None:
            return None
        residual = max(residual, follow.settled_ms - end_ms)
        if fixed:
            break
    else:
        if initial is None:
            return None
        pose = {ChannelName.PAN: initial.pan_deg, ChannelName.TILT: initial.tilt_deg}
        poses.append({ch: (pose[ch], pose[ch]) for ch in channels})
        for channel in _WHEELS:
            key = DISCRETE_KEYS[channel]
            if key in profile.discrete:
                held[channel].add(initial.discrete_states[key])
    envelope = {ch: (min(p[ch][0] for p in poses), max(p[ch][1] for p in poses)) for ch in channels}
    return envelope, dict(held), residual


def _pose_points(cue: FixtureSegment, channel: ChannelName) -> tuple[PhysicalPoint, ...]:
    trajectory = cue.channels[channel].physical
    assert isinstance(trajectory, ContinuousTrajectory)  # a physical cue authors its pose
    return trajectory.points


def _pose_range(cues: Sequence[FixtureSegment], channel: ChannelName) -> tuple[float, float]:
    """Every pose the cues' linear trajectories pass through lies between their points."""
    values = [point.value for cue in cues for point in _pose_points(cue, channel)]
    return min(values), max(values)


def _last_frame_pose(cue: FixtureSegment, channel: ChannelName) -> tuple[float, float]:
    """The pose a cue's last frame commands: its point there, else the points around it."""
    points = _pose_points(cue, channel)
    last = cue.t1_ms - EFFECT_GRID_MS
    exact = [point.value for point in points if point.t_ms == last]
    if exact:
        return exact[0], exact[0]
    left = [point for point in points if point.t_ms < last][-1]
    right = next((point for point in points if point.t_ms > last), left)
    return min(left.value, right.value), max(left.value, right.value)


def _wheel_state(cue: FixtureSegment, channel: ChannelName, time_ms: int, default: str) -> str:
    value = cue.channels.get(channel)
    if value is None or not isinstance(value.physical, DiscreteTrajectory):
        return default
    return [event.state for event in value.physical.events if event.t_ms <= time_ms][-1]


def _wheel_states(
    cues: Sequence[FixtureSegment], profile: FixtureCapabilities
) -> dict[ChannelName, set[str]]:
    """Every color and gobo state the cues select, the default where one is unauthored."""
    states: dict[ChannelName, set[str]] = {}
    for channel in _WHEELS:
        capability = profile.discrete.get(DISCRETE_KEYS[channel])
        if capability is None:
            continue
        selected: set[str] = set()
        for cue in cues:
            value = cue.channels.get(channel)
            if value is None or not isinstance(value.physical, DiscreteTrajectory):
                selected.add(capability.default_state)
            else:
                selected.update(event.state for event in value.physical.events)
        states[channel] = selected
    return states


def check_physical_templates(
    template_ids: Sequence[str],
    *,
    beat_grid: BeatGrid,
    fixture_group: FixtureGroup,
    initial_states: Mapping[str, InitialFixtureState],
    failure_mode: FailureMode,
) -> None:
    """Dry-compile templates on the rig, so a plan can only name ones that will render.

    Each template is compiled with no preset and with each preset it declares (the
    only presets the physical renderer applies), as one section from bar 1 over every
    bar that starts in the song, on every fixture of the rig, through the render's own
    `compile_physical_template` against the song's phase map and within the render's
    cue limits (`physical_cue_limits`). That checks target groups against the rig's
    roles, legacy data a preset adds, every step's states and channels against each
    profile, axis bounds, travel rate, pose motion the head can follow, and pulse and
    shutter timing for that placement, and each step's component references against
    the rig's presets, exactly as the render resolves them. The section then enters as the render enters a
    section (`_enter_section`) and `plan_prepositions` runs over it from the run's
    `initial_states` under the run's `failure_mode`, so a template whose own cues
    cannot be repositioned between is refused unless it declares the fallback the run
    enables.

    Raises:
        UnsupportedRenderModeError: Naming each template, preset, step, fixture and
            item that fails.
    """
    from twinklr.core.sequencer.moving_heads.compile.physical import PhysicalCompileError
    from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
        UnsupportedRigShapeError,
    )

    registries = create_default_registries()
    fixtures = build_fixture_contexts(rig_profile_from_fixture_group(fixture_group), fixture_group)
    profiles = {
        fixture.fixture_id: fixture.config.physical_profile
        for fixture in fixture_group.expand_fixtures()
        if fixture.config.physical_profile is not None
    }
    topology = rig_topology(fixture_group)
    phase_map = build_musical_phase_map(beat_grid)
    duration_ms = int(beat_grid.duration_ms)
    start_limit, end_limit = physical_cue_limits(phase_map, duration_ms)
    sequence_end_ms = len(frame_times(duration_ms)) * EFFECT_GRID_MS
    bars = sum(1 for start in beat_grid.bar_boundaries if start < beat_grid.duration_ms)
    failures: list[str] = []
    for template_id in template_ids:
        document = get_template(template_id)
        repeat = document.template.repeat
        for preset in (None, *document.presets):
            where = f"template {template_id!r}" + (
                f", preset {preset.preset_id!r}" if preset else ""
            )
            # A ONCE cycle plays once wherever a section starts, so it is checked at every
            # start bar a full cycle fits from, not only at bar 1's tempo.
            placements = [(1, max(bars, 1))]
            seen: set[tuple[Any, ...]] = set()
            while placements:
                start_bar, duration_bars = placements.pop(0)
                at = where if start_bar == 1 else f"{where}, placed at bar {start_bar}"
                context = TemplateCompileContext(
                    section_id="render_preflight",
                    template_id=document.template.template_id,
                    preset_id=preset.preset_id if preset else None,
                    fixtures=fixtures,
                    beat_grid=beat_grid,
                    start_bar=start_bar,
                    duration_bars=duration_bars,
                    curve_registry=CurveRegistry(),
                    geometry_registry=registries["geometry"],
                    movement_registry=registries["movement"],
                    dimmer_registry=registries["dimmer"],
                    presets=fixture_group.presets,
                    topology=topology,
                    fixture_group_id=fixture_group.group_id,
                )
                if start_bar > 1:
                    key = _placement_key(context, phase_map, start_limit, end_limit)
                    if key in seen:
                        continue
                    seen.add(key)
                try:
                    compiled = compile_physical_template(
                        document.template,
                        context,
                        preset,
                        phase_map=phase_map,
                        start_limit_ms=start_limit,
                        end_limit_ms=end_limit,
                    )
                except (
                    PhysicalCompileError,
                    PhysicalChannelError,
                    UnsupportedRigShapeError,
                    ValueError,
                ) as error:
                    # A step's error carries a note naming its template, step and fixture.
                    notes = "; ".join(getattr(error, "__notes__", ()))
                    if notes and preset:
                        notes += f", preset {preset.preset_id!r}"
                    if notes and start_bar > 1:
                        notes += f", placed at bar {start_bar}"
                    failures.append(f"{notes or at}: {error}")
                    break
                cues, _, _ = _enter_section(
                    compiled.segments,
                    {},
                    profiles,
                    initial_states,
                    section_start_ms=context.start_ms,
                    phase_map=phase_map,
                    failure_mode=failure_mode,
                )
                # Heads with the same profile, initial state and cues plan identically (the
                # gate has no locks): plan one of each.
                groups: dict[tuple[Any, ...], list[str]] = defaultdict(list)
                for fixture_id, profile in profiles.items():
                    own = [cue for cue in cues if cue.fixture_id == fixture_id]
                    groups[_plan_key(own, profile, initial_states.get(fixture_id))].append(
                        fixture_id
                    )
                members = {group[0]: group for group in groups.values()}
                heads = set(members)
                result = plan_prepositions(
                    [cue for cue in cues if cue.fixture_id in heads],
                    {fixture_id: profiles[fixture_id] for fixture_id in heads},
                    initial_states=initial_states,
                    locks=(),
                    frame_ms=EFFECT_GRID_MS,
                    sequence_end_ms=sequence_end_ms,
                    failure_mode=failure_mode,
                )
                errors = [d for d in result.diagnostics if d.status == "error"]
                if errors:
                    failures.append(
                        f"{at}: dark repositioning between its own cues cannot be planned: "
                        + "; ".join(
                            f"{'/'.join(members[d.fixture_id])} cue at {d.cue_ms} ms: "
                            f"{d.code}: {d.reason}"
                            for d in errors
                        )
                    )
                    break
                if start_bar == 1 and repeat.mode == RepeatMode.ONCE:
                    window = _once_window_bars(
                        compiled.segments,
                        phase_map,
                        section_start_ms=context.start_ms,
                        cycle_bars=repeat.cycle_bars,
                        beats_per_bar=beat_grid.beats_per_bar,
                    )
                    # Bar 1's key is not marked seen: there the head enters from its
                    # initial state at the song start, so an equal key later may still
                    # reposition differently.
                    placements = [
                        (later, min(bars - later + 1, window))
                        for later in range(2, bars + 1)
                        if bars - later + 1 >= repeat.cycle_bars - 1e-9
                    ]
    if failures:
        raise UnsupportedRenderModeError(
            "moving_heads.mode 'physical_v2' would offer the planner templates this rig "
            "cannot render: " + "; ".join(failures)
        )


def _once_window_bars(
    segments: Sequence[FixtureSegment],
    phase_map: MusicalPhaseMap,
    *,
    section_start_ms: int,
    cycle_bars: float,
    beats_per_bar: int,
) -> int:
    """Bars a ONCE section must span for the gate to see all of its motion.

    The cycle, then every head's motion past it (a phase-lagged head finishing its move
    in the hold), measured in beats at bar 1, where the gate compiled the whole song;
    past that each cue holds its terminal pose. Phase is musical, so the span in beats
    is the same at every placement; one bar more covers frame quantization.
    """
    last_ms = section_start_ms
    for segment in segments:
        for channel in _POSE:
            points = _pose_points(segment, channel)
            moving = [point.t_ms for point in points if point.value != points[-1].value]
            if moving:
                last_ms = max(last_ms, max(moving) + EFFECT_GRID_MS)
    beats = musical_phase_fraction(phase_map, last_ms, origin_ms=section_start_ms, period_beats=1.0)
    return math.ceil(max(Fraction(repr(cycle_bars)), beats / beats_per_bar)) + 1


def _placement_key(
    context: TemplateCompileContext,
    phase_map: MusicalPhaseMap,
    start_limit_ms: int,
    end_limit_ms: int,
) -> tuple[Any, ...]:
    """What a section's compile depends on besides the template and rig, relative to its
    start: its frame alignment, the downbeats and phase knots it spans (with the knot on
    each side), and the cue limits inside it. Equal keys compile to the same cues shifted
    by whole frames. The section's end needs no entry of its own: inside the downbeats it
    is the last one listed, and short of the end limit it is the end-limit entry; past
    that limit every cue is cut there."""
    bars = context.beat_grid.bar_boundaries
    origin = bars[context.start_bar - 1]
    end = context.end_ms
    times = phase_map.knot_times_ms
    low = max(bisect.bisect_right(times, origin) - 1, 0)
    high = min(bisect.bisect_left(times, end) + 1, len(times) - 1)
    first_beat = phase_map.knots[low].beat_index
    return (
        origin % EFFECT_GRID_MS,
        tuple(
            bar - origin
            for bar in bars[context.start_bar - 1 : context.start_bar + context.duration_bars]
        ),
        tuple(
            (knot.time_ms - origin, knot.beat_index - first_beat)
            for knot in phase_map.knots[low : high + 1]
        ),
        max(start_limit_ms - context.start_ms, 0),
        min(end_limit_ms, end) - context.start_ms,
    )


def _plan_key(
    cues: Sequence[FixtureSegment],
    profile: FixtureCapabilities,
    initial: InitialFixtureState | None,
) -> tuple[Any, ...]:
    """What `plan_prepositions` reads of one fixture without locks; identifiers aside.

    Every channel's trajectory is hashed, so heads whose phase or pan sign changes a
    trajectory are never planned as one. A cue's `phase_distribution` metadata (its
    head's rank, offsets and sign) is left out: the planner never reads it, and its
    rank alone would keep heads with identical cues from being planned once.
    """
    return (
        profile.model_dump_json(),
        None if initial is None else initial.model_dump_json(),
        tuple(
            (
                cue.t0_ms,
                cue.t1_ms,
                tuple(sorted((ch.value, value.physical) for ch, value in cue.channels.items())),
                tuple(
                    sorted(
                        (key, value)
                        for key, value in cue.metadata.items()
                        if key != "phase_distribution"
                    )
                ),
            )
            for cue in cues
        ),
    )


def _physical_preset(
    section: PlanSection, template_doc: TemplateDoc, diagnostics: list[MHDiagnostic]
) -> TemplatePreset | None:
    """The preset the template declares under the section's id, or none.

    An undeclared id is not turned into an energy preset under `physical_v2`: that is
    planner intent, which Phase 1 does not apply, and it would add legacy data.
    """
    if not section.preset_id:
        return None
    for preset in template_doc.presets:
        if preset.preset_id == section.preset_id:
            return preset
    diagnostics.append(
        MHDiagnostic(
            code="unsupported_attribute",
            severity="warning",
            message=(
                f"section {section.section_name!r}: preset {section.preset_id!r} is not "
                f"declared by template {template_doc.template.template_id!r}; physical_v2 "
                "applies no preset"
            ),
            section_id=section.section_name,
            action="unchanged",
        )
    )
    return None


class PhysicalRenderError(ValueError):
    """The transaction pass refused a physical render; nothing was delivered."""

    def __init__(self, diagnostics: Sequence[TransitionDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        errors = [diagnostic for diagnostic in diagnostics if diagnostic.status == "error"]
        super().__init__(
            "Physical render refused: "
            + "; ".join(
                f"{diagnostic.fixture_id} cue at {diagnostic.cue_ms} ms: "
                f"{diagnostic.code}: {diagnostic.reason}"
                for diagnostic in errors
            )
        )


def _sha256(model: BaseModel) -> str:
    canonical = json.dumps(
        model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _phase_boundaries(phase_map: MusicalPhaseMap) -> list[dict[str, Any]]:
    """The phase map's knots that are not observed beats, with their provenance."""
    return [
        knot.model_dump(mode="json") for knot in phase_map.knots if knot.provenance != "observed"
    ]


def _longest_beat_interval_ms(phase_map: MusicalPhaseMap) -> float | None:
    """The longest interval between consecutive observed beats, if there are two."""
    beats = [knot.time_ms for knot in phase_map.knots if knot.provenance == "observed"]
    return max((later - earlier for earlier, later in pairwise(beats)), default=None)


def _cue_records(cues: Sequence[FixtureSegment]) -> list[dict[str, Any]]:
    """Requested and actual timing of every compiled cue, for the trace.

    A cue's start and end were requested at musical times and quantized (an end also
    cut at the song's last whole frame or the covered end) before compiling. Its hold
    and discrete cues are authored on the frame grid, so only one a quantization moved
    is listed.
    """
    records: list[dict[str, Any]] = []
    for cue in cues:
        identity = {
            "fixture_id": cue.fixture_id,
            "section_id": cue.section_id,
            "segment_id": cue.segment_id,
            "step_id": cue.step_id,
        }
        records.append(
            identity
            | {
                "channel": None,
                "kind": "segment_start",
                "requested_ms": int(cue.metadata["requested_t0_ms"]),
                "actual_ms": cue.t0_ms,
            }
        )
        records.append(
            identity
            | {
                "channel": None,
                "kind": "segment_end",
                "requested_ms": int(cue.metadata["requested_t1_ms"]),
                "actual_ms": cue.t1_ms,
            }
        )
        records.extend(
            identity
            | {
                "channel": timing.channel.value if timing.channel is not None else None,
                "kind": timing.kind,
                "requested_ms": timing.requested_ms,
                "actual_ms": timing.actual_ms,
            }
            for timing in quantized_cues([cue])
            if timing.kind == "cue" and timing.requested_ms != timing.actual_ms
        )
    return records


class RenderingPipeline:
    """Rendering pipeline for moving heads."""

    def __init__(
        self,
        *,
        choreography_plan: ChoreographyPlan,
        beat_grid: BeatGrid,
        fixture_group: FixtureGroup,
        job_config: JobConfig,
        output_path: Path | None = None,
        timeline_tracks: list[TimingTrack] | None = None,
        media_file: str | None = None,
        song: str = "",
        artist: str = "",
        locks: Sequence[RenderLock] = (),
        layout_models: Sequence[Model] | None = None,
        layout_sha256: str | None = None,
    ):
        """Initialize rendering pipeline.

        Args:
            choreography_plan: Choreography plan from agent orchestrator
            beat_grid: Beat grid for musical timing
            fixture_group: Fixture configuration
            job_config: Job configuration
            output_path: Optional output path for the delivered .xsq. When set, the
                run also writes the .xtiming and .xmap sidecars beside it.
            timeline_tracks: Optional pre-built timeline tracks (beats, bars, lyrics, etc.)
            media_file: Audio file the sequence plays against. Falls back to a
                placeholder name, since an empty mediaFile makes the file unopenable.
            song: Song title for the sequence head
            artist: Artist for the sequence head
            locks: Frames a `physical_v2` render must leave as the cues alone make them.
            layout_models: The xLights layout's models, when known. A `physical_v2`
                render then refuses any fixture whose model is not a single-color DMX
                model with enough channels (`check_physical_models`); without them the
                check is recorded as not performed. A `legacy_v1` render ignores them.
            layout_sha256: Content hash of the layout file, recorded in the physical
                trace as evidence. Not render identity: the check passes or refuses
                and never changes a byte.

        Raises:
            UnsupportedRenderModeError: The job's render mode cannot render this rig
                (see `preflight_render_policy`).
            ValueError: If locks are given to a `legacy_v1` render, which cannot honor
                them.
        """
        preflight_render_policy(job_config, fixture_group)
        if locks and job_config.moving_heads.mode == "legacy_v1":
            raise ValueError("render locks apply only to moving_heads.mode 'physical_v2'")

        self.choreography_plan = choreography_plan
        self.fixture_group = fixture_group
        self.job_config = job_config
        self.beat_grid = beat_grid
        self.output_path = output_path
        self.timeline_tracks = timeline_tracks or []
        self.media_file = resolve_media_file(media_file)
        self.song = song
        self.artist = artist
        self.locks = tuple(locks)
        self.layout_models = layout_models
        self.layout_sha256 = layout_sha256
        self.artifacts: DeliveryArtifacts | None = None
        """Set by `render()` when `output_path` is given."""
        self.frames: tuple[EncodedFixtureFrame, ...] = ()
        """Set by a `physical_v2` `render()`: every fixture's encoded frames, rig order."""
        self.render_record: dict[str, Any] | None = None
        """Set by a `physical_v2` `render()`: the identity and evidence the trace carries."""

        # Create shared infrastructure
        self.curve_generator = CurveGenerator()
        self.curve_registry = CurveRegistry()

        # Create rig profile from fixture group
        self.rig_profile = rig_profile_from_fixture_group(fixture_group)

        # Load builtin templates
        load_builtin_templates()

        # Create handler registries
        registries = create_default_registries()
        self.geometry_registry = registries["geometry"]
        self.movement_registry = registries["movement"]
        self.dimmer_registry = registries["dimmer"]
        self.color_registry = registries["color"]
        self.shutter_registry = registries["shutter"]
        self.gobo_registry = registries["gobo"]

        # Create transition components
        self.transition_detector = TransitionDetector()
        self.transition_planner = TransitionPlanner(
            config=job_config.transitions, beat_grid=beat_grid
        )
        blender = ChannelBlender(self.curve_generator)
        self.transition_compiler = TransitionSegmentCompiler(blender)

        logger.debug(
            f"Initialized RenderingPipeline with {len(self.rig_profile.fixtures)} fixtures "
            f"and {len(self.choreography_plan.sections)} sections "
            f"(transitions enabled: {job_config.transitions.enabled})"
        )

    def render(self) -> list[FixtureSegment]:
        """Render the choreography plan to fixture segments.

        Processes each section in the choreography plan:
        1. Detect and plan transitions (if enabled)
        2. For each sequence in section, build template ID from components
        3. Load template and apply energy-based preset
        4. Build compile context aligned to beat grid
        5. Compile template to IR segments
        6. Generate transition segments (if enabled)
        7. Merge and aggregate all segments

        Returns:
            List of all compiled fixture segments across all sections.

        Raises:
            ValueError: If template not found or compilation fails.
        """
        logger.debug("Starting plan rendering...")
        if self.job_config.moving_heads.mode == "physical_v2":
            return self._render_physical()

        # Step 1: Detect and plan transitions (if enabled)
        transition_registry = TransitionRegistry()
        if self.job_config.transitions.enabled:
            transition_registry = self._detect_and_plan_transitions()
            logger.debug(f"Detected and planned {len(transition_registry.transitions)} transitions")

        # Step 2: Compile sections
        section_segments: dict[str, list[FixtureSegment]] = {}
        time_markers: list[TimeMarker] = []

        for section in self.iterate_plan_sections(self.choreography_plan):
            if not section.template_id:
                raise ValueError(f"Section '{section.section_name}' has no template_id")

            logger.debug(
                f"Rendering section '{section.section_name}' "
                f"(bars {section.start_bar}-{section.end_bar}, "
                f"template: {section.template_id}, preset: {section.preset_id})"
            )

            # Load template
            try:
                template_doc = get_template(section.template_id)
                template = template_doc.template
                logger.debug(f"Loaded template: {template.name} (v{template.version})")
            except Exception as e:
                logger.error(f"Failed to load template '{section.template_id}': {e}")
                raise ValueError(f"Template not found: {section.template_id}") from e

            # Apply preset if available
            preset = resolve_section_preset(section, template_doc)

            # Build fixture contexts
            fixture_contexts = self._build_fixture_contexts()

            # Build compile context aligned to beat grid
            context = TemplateCompileContext(
                section_id=section.section_name,
                template_id=template.template_id,
                preset_id=preset.preset_id if preset else None,
                fixtures=fixture_contexts,
                beat_grid=self.beat_grid,
                start_bar=section.start_bar,
                duration_bars=section.end_bar - section.start_bar + 1,
                curve_registry=self.curve_registry,
                geometry_registry=self.geometry_registry,
                movement_registry=self.movement_registry,
                dimmer_registry=self.dimmer_registry,
                color_registry=self.color_registry,
                shutter_registry=self.shutter_registry,
                gobo_registry=self.gobo_registry,
                intent=self._resolve_section_intent(section),
            )

            time_markers.append(
                TimeMarker(
                    name=section.section_name, time_ms=context.start_ms, end_time_ms=context.end_ms
                )
            )

            logger.debug(
                f"Compile context: start={context.start_ms}ms, "
                f"duration={context.duration_ms}ms, "
                f"bpm={context.bpm}"
            )

            # Compile template
            try:
                result = compile_template(template, context, preset)
                logger.debug(
                    f"Compiled {len(result.segments)} segments "
                    f"({result.num_complete_cycles} complete cycles)"
                )
                section_segments[section.section_name] = result.segments
            except Exception as e:
                logger.error(f"Compilation failed for section '{section.section_name}': {e}")
                raise

        # Step 3: Aggregate section segments
        all_segments: list[FixtureSegment] = []
        for segments in section_segments.values():
            all_segments.extend(segments)

        logger.debug(f"Compiled {len(section_segments)} sections into {len(all_segments)} segments")

        # Step 4: Generate transition segments (if enabled)
        if self.job_config.transitions.enabled and len(transition_registry.transitions) > 0:
            transition_segments = self._generate_transition_segments(
                transition_registry, section_segments
            )
            logger.debug(f"Generated {len(transition_segments)} transition segments")
            all_segments.extend(transition_segments)

        logger.debug(f"Render complete: {len(all_segments)} total segments")

        # Step 5: Write the delivery (.xsq + .xtiming + .xmap)
        if self.output_path:
            self._export_delivery(all_segments, time_markers)

        return all_segments

    @property
    def diagnostics(self) -> tuple[MHDiagnostic, ...]:
        """Requested controls this legacy render ignores, for the plan's templates.

        Computed on access; `render()` never runs it. Resolving each section's
        preset logs the same lines `render()` does.
        """
        return audit_legacy_controls(
            self.choreography_plan, self.fixture_group, self._plan_templates()
        )

    def fingerprint(self) -> str:
        """Functional identity of this render; the output path is not part of it.

        A `physical_v2` render also hashes its renderer and encoder revisions, the
        musical phase map built from the detected grid, and any render locks, and leaves
        out the transition settings it does not apply.
        """
        physical = self.job_config.moving_heads.mode == "physical_v2"
        return render_fingerprint(
            plan=self.choreography_plan,
            beat_grid=self.beat_grid,
            fixtures=self.fixture_group,
            templates=self._plan_templates(),
            policy=self.job_config.moving_heads,
            # The physical path plans its own dark repositioning and ignores transitions.
            transitions=None if physical else self.job_config.transitions,
            backend_id=LEGACY_BACKEND_ID,
            renderer_revision=(
                f"physical_v2.{PHYSICAL_RENDERER_REVISION}+encoder.{ENCODER_VERSION}"
                if physical
                else LEGACY_RENDERER_REVISION
            ),
            phase_map=build_musical_phase_map(self.beat_grid) if physical else None,
            locks=self.locks,
        )

    def _render_physical(self) -> list[FixtureSegment]:
        """Render through the opt-in physical path and, with an output path, deliver it.

        Each section's template compiles on the frame grid against the musical phase
        of the detected grid, within its covered span (`physical_cue_limits`); the
        transaction pass authors every fixture of the rig over the whole sequence,
        holding it dark outside every cue and so outside the covered span; each
        fixture's complete frames are encoded in rig order and merged into constant DMX
        runs. Any refusal raises before anything is written,
        and the delivery itself is published only once its size fits the budgets.

        Returns:
            The planned segments: the cues with their transactions and parks.

        Raises:
            PhysicalRenderError: If the transaction pass reports an error.
            PhysicalCompileError, PhysicalChannelError, PhysicalOutputError,
                ValueError: For a step, value, model or output the path refuses.
        """
        policy = self.job_config.moving_heads
        topology = rig_topology(self.fixture_group)
        phase_map = build_musical_phase_map(self.beat_grid)
        duration_ms = int(self.beat_grid.duration_ms)
        start_limit, end_limit = physical_cue_limits(phase_map, duration_ms)
        times = frame_times(duration_ms)
        fixtures = self.fixture_group.expand_fixtures()
        profiles = {}
        for fixture in fixtures:
            profile = fixture.config.physical_profile
            assert profile is not None  # required by preflight_render_policy
            profiles[fixture.fixture_id] = profile
        targets = {fixture.fixture_id: fixture.xlights_model_name for fixture in fixtures}
        if self.layout_models is not None:
            check_physical_models(fixtures, self.layout_models)
        else:
            logger.warning(
                "physical_v2: the xLights model check was not performed (no layout given); "
                "each fixture's model must be a single-color DMX model of at least its "
                "profile's footprint, which nothing has verified"
            )

        cues: list[FixtureSegment] = []
        kept: dict[str, list[HeadFollow]] = defaultdict(list)
        dropped: list[dict[str, Any]] = []
        in_window: list[dict[str, Any]] = []
        entry_windows: list[dict[str, Any]] = []
        time_markers: list[TimeMarker] = []
        diagnostics: list[MHDiagnostic] = []
        fixture_contexts = self._build_fixture_contexts()
        for section in self.iterate_plan_sections(self.choreography_plan):
            if not section.template_id:
                raise ValueError(f"Section '{section.section_name}' has no template_id")
            try:
                template_doc = get_template(section.template_id)
            except Exception as e:
                raise ValueError(f"Template not found: {section.template_id}") from e
            preset = _physical_preset(section, template_doc, diagnostics)
            context = TemplateCompileContext(
                section_id=section.section_name,
                template_id=template_doc.template.template_id,
                preset_id=preset.preset_id if preset else None,
                fixtures=fixture_contexts,
                beat_grid=self.beat_grid,
                start_bar=section.start_bar,
                duration_bars=section.end_bar - section.start_bar + 1,
                curve_registry=self.curve_registry,
                geometry_registry=self.geometry_registry,
                movement_registry=self.movement_registry,
                dimmer_registry=self.dimmer_registry,
                color_registry=self.color_registry,
                shutter_registry=self.shutter_registry,
                gobo_registry=self.gobo_registry,
                presets=self.fixture_group.presets,
                topology=topology,
                fixture_group_id=self.fixture_group.group_id,
            )
            time_markers.append(
                TimeMarker(
                    name=section.section_name, time_ms=context.start_ms, end_time_ms=context.end_ms
                )
            )
            if not section.legacy_intent_omitted:
                diagnostics.append(
                    MHDiagnostic(
                        code="unsupported_attribute",
                        severity="warning",
                        message=(
                            f"section {section.section_name!r}: planner intent (intensity, "
                            "color, shutter and gobo events) is not applied by physical_v2 "
                            "in Phase 1; the template's physical data renders as authored"
                        ),
                        section_id=section.section_name,
                        action="unchanged",
                    )
                )
            compiled = compile_physical_template(
                template_doc.template,
                context,
                preset,
                phase_map=phase_map,
                start_limit_ms=start_limit,
                end_limit_ms=end_limit,
            )
            dropped.extend(compiled.dropped_steps)
            entered, inside, windows = _enter_section(
                compiled.segments,
                kept,
                profiles,
                policy.initial_states,
                section_start_ms=context.start_ms,
                phase_map=phase_map,
                failure_mode=policy.reposition_fallback,
                locks=self.locks,
            )
            for fixture_id in sorted({cue.fixture_id for cue in entered}):
                before = kept[fixture_id]
                kept[fixture_id] += follow_cues(
                    [cue for cue in entered if cue.fixture_id == fixture_id],
                    profiles[fixture_id],
                    frame_ms=EFFECT_GRID_MS,
                    after=before[-1] if before else None,
                )
            cues.extend(entered)
            in_window.extend(inside)
            entry_windows.extend(windows)
            window_end = max(
                (w["window_end_ms"] for w in windows if w["window_end_ms"] is not None),
                default=None,
            )
            if window_end is not None and window_end >= context.end_ms:
                logger.warning(
                    "physical_v2: section %r (%s-%s ms) is shorter than its entry window, "
                    "which ends at %s ms; it renders dark",
                    section.section_name,
                    context.start_ms,
                    context.end_ms,
                    window_end,
                )
        if dropped:
            logger.warning(
                "physical_v2: %d cue(s) start outside the frames %s-%s ms that the covered "
                "phase span and the song allow and are dropped (held dark); the trace's "
                "dropped_cues lists them",
                len(dropped),
                start_limit,
                end_limit,
            )
        if in_window:
            logger.warning(
                "physical_v2: %d cue(s) lie inside their section's entry window and are "
                "dropped (held dark); the trace's dropped_cues and entry_windows list them",
                len(in_window),
            )

        result = plan_prepositions(
            cues,
            profiles,
            initial_states=policy.initial_states,
            locks=self.locks,
            frame_ms=EFFECT_GRID_MS,
            sequence_end_ms=len(times) * EFFECT_GRID_MS,
            failure_mode=policy.reposition_fallback,
        )
        if result.has_errors:
            raise PhysicalRenderError(result.diagnostics)

        frames: list[EncodedFixtureFrame] = []
        for fixture in fixtures:
            frames.extend(
                encode_fixture_frames(
                    [s for s in result.segments if s.fixture_id == fixture.fixture_id],
                    profiles[fixture.fixture_id],
                    frame_times_ms=times,
                )
            )
        runs = coalesce_frames(frames)
        requests = physical_run_requests(runs, result.segments, targets)

        self.frames = tuple(frames)
        self.render_record = {
            "renderer": "physical_v2",
            "render_fingerprint": self.fingerprint(),
            "renderer_revision": PHYSICAL_RENDERER_REVISION,
            "encoder_version": ENCODER_VERSION,
            "backend_id": LEGACY_BACKEND_ID,
            "policy": policy.model_dump(mode="json"),
            "initial_states": {
                fixture_id: state.model_dump(mode="json")
                for fixture_id, state in sorted(policy.initial_states.items())
            },
            "fixtures": [
                {
                    "fixture_id": fixture.fixture_id,
                    "xlights_model_name": fixture.xlights_model_name,
                    "profile_sha256": _sha256(profiles[fixture.fixture_id]),
                }
                for fixture in fixtures
            ],
            "template_sha256": {
                doc.template.template_id: _sha256(doc) for doc in self._plan_templates()
            },
            "beat_grid_sha256": _sha256(self.beat_grid),
            "phase_boundaries": _phase_boundaries(phase_map),
            "covered_span": {
                "start_ms": phase_map.covered_start_ms,
                "end_ms": phase_map.covered_end_ms,
            },
            "longest_beat_interval_ms": _longest_beat_interval_ms(phase_map),
            "frame_grid": {
                "frame_ms": EFFECT_GRID_MS,
                "frame_count": len(times),
                "song_duration_ms": duration_ms,
                "sequence_end_ms": len(times) * EFFECT_GRID_MS,
            },
            "layout_check": "performed" if self.layout_models is not None else "not_performed",
            "layout_sha256": self.layout_sha256,
            "locks": [lock.model_dump(mode="json") for lock in self.locks],
            "quantized_cues": _cue_records(cues),
            "dropped_cues": [
                {**record, "reason": "outside_cue_limits", "entry_window_end_ms": None}
                for record in dropped
            ]
            + [
                {
                    **record,
                    "reason": "entry_window",
                    "start_limit_ms": start_limit,
                    "end_limit_ms": end_limit,
                }
                for record in in_window
            ],
            "entry_windows": entry_windows,
            "topology": (
                None
                if topology is None
                else {
                    "source": "derived" if self.fixture_group.topology is None else "declared",
                    "canonical_order": list(topology.canonical_ids),
                }
            ),
            "phase_distribution": [
                {
                    "section_id": cue.section_id,
                    "step_id": cue.step_id,
                    "fixture_id": cue.fixture_id,
                    "t0_ms": cue.t0_ms,
                    **json.loads(cue.metadata["phase_distribution"]),
                }
                for cue in cues
                if "phase_distribution" in cue.metadata
            ],
            "transactions": [d.model_dump(mode="json") for d in result.diagnostics],
            "diagnostics": [d.model_dump(mode="json") for d in diagnostics],
        }
        if self.output_path:
            xsq = build_physical_sequence(
                requests,
                time_markers,
                media_file=self.media_file,
                duration_ms=duration_ms,
                song=self.song,
                artist=self.artist,
                timeline_tracks=self.timeline_tracks,
            )
            self.artifacts = export_physical_delivery(
                xsq, runs, output_path=self.output_path, policy=policy, render=self.render_record
            )
        return list(result.segments)

    def _plan_templates(self) -> list[TemplateDoc]:
        """The template documents the plan's sections name, once each.

        Sections may spell a template any way the registry resolves (case, separators,
        display name, alias); documents are deduplicated on the canonical id.
        """
        docs: dict[str, TemplateDoc] = {}
        for section in self.iterate_plan_sections(self.choreography_plan):
            if section.template_id:
                doc = get_template(section.template_id)
                docs.setdefault(doc.template.template_id, doc)
        return [docs[template_id] for template_id in sorted(docs)]

    def _resolve_section_intent(self, section: PlanSection) -> SectionRenderIntent:
        """Translate the approved planner schema into renderer-owned categories."""
        if section.legacy_intent_omitted:
            return SectionRenderIntent()

        selection = section.color_intent.selection
        color: ColorPreset | None
        if selection.explicit_color is not None:
            color = selection.explicit_color
        elif selection.palette_role is not None:
            color = PALETTE_ROLE_TO_COLOR[selection.palette_role]
        else:  # pragma: no cover - rejected by ColorIntent's discriminated union
            color = None

        shutter_events = [
            TimedChannelIntent(
                at_ms=self._event_time_ms(event.bar, event.beat),
                pattern_id=event.pattern.value,
            )
            for event in section.shutter_events
        ]
        gobo_events = [
            TimedChannelIntent(
                at_ms=self._event_time_ms(event.bar, event.beat),
                pattern_id=event.pattern.value,
            )
            for event in section.gobo_events
        ]

        return SectionRenderIntent(
            intensity=section.intensity,
            color=color,
            shutter_events=shutter_events,
            gobo_events=gobo_events,
        )

    def _event_time_ms(self, bar: int, beat: int) -> int:
        """Place a 1-based bar/beat event on the existing BeatGrid."""
        if beat > self.beat_grid.beats_per_bar:
            raise ValueError(
                f"Beat {beat} is outside a {self.beat_grid.beats_per_bar}/4 bar at bar {bar}"
            )
        beat_index = (bar - 1) * self.beat_grid.beats_per_bar + (beat - 1)
        try:
            return int(self.beat_grid.get_beat_time_ms(beat_index))
        except IndexError as error:
            raise ValueError(
                f"Event at bar {bar}, beat {beat} is outside the detected beat grid"
            ) from error

    def iterate_plan_sections(self, plan: ChoreographyPlan) -> Iterator[PlanSection]:
        """Iterate over the plan sections and yield each section.

        Args:
            plan: The choreography plan to iterate over.

        Returns:
            An iterator over the plan sections.
        """
        for section in plan.sections:
            if section.segments:
                for seg in section.segments:
                    yield flatten_plan_segment(section, seg)
            else:
                yield section

    def _detect_and_plan_transitions(self) -> TransitionRegistry:
        """Detect boundaries and plan transitions.

        Returns:
            TransitionRegistry containing all planned transitions.
        """
        logger.debug("Detecting transition boundaries...")

        flattened_sections = list(self.iterate_plan_sections(self.choreography_plan))

        # Detect section boundaries
        boundaries = self.transition_detector.detect_section_boundaries(
            ChoreographyPlan(
                sections=flattened_sections,
                overall_strategy=self.choreography_plan.overall_strategy,
            ),
            self.beat_grid,
        )

        logger.debug(f"Detected {len(boundaries)} section boundaries")

        # Build section lookup for duration computation
        section_lookup: dict[str, PlanSection] = {s.section_name: s for s in flattened_sections}

        # Plan transitions for each boundary
        registry = TransitionRegistry()
        fixture_ids = [fx.fixture_id for fx in self.rig_profile.fixtures]

        for boundary in boundaries:
            # Get transition hint and section durations from the plan
            hint = None
            source_section = section_lookup.get(boundary.source_id)
            target_section = section_lookup.get(boundary.target_id)

            if target_section is not None:
                hint = target_section.transition_in

            source_duration_ms = (
                _compute_section_duration_ms(
                    source_section.start_bar, source_section.end_bar, self.beat_grid
                )
                if source_section is not None
                else 0
            )
            target_duration_ms = (
                _compute_section_duration_ms(
                    target_section.start_bar, target_section.end_bar, self.beat_grid
                )
                if target_section is not None
                else 0
            )

            # Plan transition
            transition_id = f"trans_{boundary.source_id}_to_{boundary.target_id}"
            transition_plan = self.transition_planner.plan_transition(
                boundary=boundary,
                hint=hint,
                fixtures=fixture_ids,
                transition_id=transition_id,
            )

            # A zero-width overlap (a snap, or a transition whose duration collapsed to 0)
            # has no blend region. Compiling it would emit a zero-duration FixtureSegment
            # that the emission layer rejects (0 <= start < end), so drop it here rather than
            # produce a degenerate segment downstream.
            if transition_plan.overlap_end_ms <= transition_plan.overlap_start_ms:
                logger.debug(
                    f"Skipping zero-width transition {transition_id}: overlap collapses at "
                    f"{transition_plan.overlap_start_ms}ms (nothing to blend)"
                )
                continue

            # Validate feasibility using actual section durations
            is_feasible, warnings = self.transition_planner.validate_transition_feasibility(
                transition_plan, source_duration_ms, target_duration_ms
            )

            if not is_feasible:
                logger.warning(
                    f"Transition {transition_id} may not be feasible: {', '.join(warnings)}"
                )

            registry.add_transition(transition_plan)

        logger.debug(f"Planned {len(registry.transitions)} transitions")
        return registry

    def _generate_transition_segments(
        self,
        transition_registry: TransitionRegistry,
        section_segments: dict[str, list[FixtureSegment]],
    ) -> list[FixtureSegment]:
        """Generate transition segments for all planned transitions.

        Args:
            transition_registry: Registry of planned transitions.
            section_segments: Compiled segments organized by section name.

        Returns:
            List of transition FixtureSegments.
        """
        logger.debug("Generating transition segments...")
        all_transition_segments: list[FixtureSegment] = []

        for transition_plan in transition_registry.transitions:
            # Get source and target segments near the boundary
            source_segs = self._get_segments_at_boundary(
                section_segments,
                transition_plan.boundary.source_id,
                transition_plan.boundary.time_ms,
                is_source=True,
            )

            target_segs = self._get_segments_at_boundary(
                section_segments,
                transition_plan.boundary.target_id,
                transition_plan.boundary.time_ms,
                is_source=False,
            )

            logger.debug(
                f"Compiling transition {transition_plan.transition_id}: "
                f"{len(source_segs)} source segs, {len(target_segs)} target segs"
            )

            # Compile transition
            try:
                transition_segs = self.transition_compiler.compile_transition(
                    transition_plan, source_segs, target_segs
                )
                all_transition_segments.extend(transition_segs)
            except Exception as e:
                logger.error(f"Failed to compile transition {transition_plan.transition_id}: {e}")
                # Continue with other transitions

        return all_transition_segments

    def _get_segments_at_boundary(
        self,
        section_segments: dict[str, list[FixtureSegment]],
        section_name: str,
        boundary_time_ms: int,
        is_source: bool,
    ) -> list[FixtureSegment]:
        """Get segments at a boundary time.

        Args:
            section_segments: Segments organized by section name.
            section_name: Name of the section.
            boundary_time_ms: Boundary time in milliseconds.
            is_source: True if getting source segments, False for target.

        Returns:
            List of segments at or near the boundary time.
        """
        # Get segments for this section
        segments = section_segments.get(section_name, [])

        if not segments:
            return []

        # For source: get segments that end near or at the boundary
        # For target: get segments that start near or at the boundary
        boundary_segments = []

        for segment in segments:
            if is_source:
                # Source: segment should end at or near boundary
                # Allow some tolerance (e.g., within 100ms)
                if abs(segment.t1_ms - boundary_time_ms) <= 100:
                    boundary_segments.append(segment)
            # Target: segment should start at or near boundary
            elif abs(segment.t0_ms - boundary_time_ms) <= 100:
                boundary_segments.append(segment)

        # If no exact matches, get the closest segments
        if not boundary_segments and segments:
            if is_source:
                # Get segments ending closest to boundary
                boundary_segments = [max(segments, key=lambda s: s.t1_ms)]
            else:
                # Get segments starting closest to boundary
                boundary_segments = [min(segments, key=lambda s: s.t0_ms)]

        return boundary_segments

    def _build_fixture_contexts(self) -> list[FixtureContext]:
        """Build fixture contexts from rig profile.

        Delegates to :func:`build_fixture_contexts` in ``fixture_builder``.

        Returns:
            List of FixtureContext objects for all fixtures in the rig.
        """
        return build_fixture_contexts(self.rig_profile, self.fixture_group)

    def _export_delivery(
        self, segments: list[FixtureSegment], time_markers: list[TimeMarker]
    ) -> None:
        """Write the run's delivery (.xsq + .xtiming + .xmap).

        Delegates to :func:`export_delivery` in ``delivery``.

        Args:
            segments: List of fixture segments to export.
            time_markers: List of time markers to export.
        """
        if not self.output_path:
            logger.warning("No output_path specified, skipping delivery export")
            return

        self.artifacts = export_delivery(
            segments,
            time_markers,
            fixture_group=self.fixture_group,
            output_path=self.output_path,
            media_file=self.media_file,
            duration_ms=int(self.beat_grid.duration_ms),
            song=self.song,
            artist=self.artist,
            timeline_tracks=self.timeline_tracks,
        )
