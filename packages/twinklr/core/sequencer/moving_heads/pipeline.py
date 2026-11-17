from __future__ import annotations

import bisect
from collections import defaultdict
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from fractions import Fraction
import functools
import gc
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
    from twinklr.core.formats.xlights.sequence.emission import EmissionRequest
    from twinklr.core.sequencer.models.context import FixtureContext
    from twinklr.core.sequencer.models.template import TemplateDoc, TemplatePreset

from twinklr.core.agents.sequencer.moving_heads import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.models import PlanSection, flatten_section
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup, InitialFixtureState
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import (
    UnsupportedRenderModeError,
    preflight_render_policy,
)
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS, resolve_media_file
from twinklr.core.formats.xlights.sequence.models.xsq import (
    TimeMarker,
    TimingTrack,
    XSequence,
)
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    AXIS_KEYS,
    DISCRETE_KEYS,
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalChannelError,
    PhysicalPoint,
    RenderLock,
    TransitionDiagnostic,
)
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.moving_heads.topology import rig_topology
from twinklr.core.sequencer.models.template import RepeatMode
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    FALLBACK_METADATA_KEY,
    FailureMode,
    HeadFollow,
    PrepositionMemo,
    UnplayableMode,
    entry_feasible,
    follow_cues,
    frame_values,
    plan_prepositions,
    state_at,
    worst_case_entry_ms,
)
from twinklr.core.sequencer.moving_heads.compile.preset import apply_preset
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    apply_entry_window,
    compile_template,
    whole_period_cycle,
)
from twinklr.core.sequencer.moving_heads.delivery import (
    DeliveryArtifacts,
    build_sequence,
    export_delivery,
)
from twinklr.core.sequencer.moving_heads.diagnostics import MHDiagnostic
from twinklr.core.sequencer.moving_heads.events import (
    WHEEL_ACTIONS,
    EventsPlayed,
    SectionEvents,
    apply_hits,
    apply_section_events,
    carried_states,
    cue_summary,
    events_message,
    section_events,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    ENCODER_VERSION,
    EncodedFixtureFrame,
    FrameRun,
    coalesce_frames,
    encode_fixture_frames,
    frame_times,
    quantize_cue,
    quantized_cues,
)
from twinklr.core.sequencer.moving_heads.export.xsq_adapter import (
    check_models,
    run_requests,
)
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.identity import (
    BACKEND_ID,
    RENDERER_REVISION,
    render_fingerprint,
)
from twinklr.core.sequencer.moving_heads.intensity import (
    effective_intensity,
    shape_for,
    shape_section,
)
from twinklr.core.sequencer.moving_heads.song_intent import (
    DarkPhases,
    HeadWheels,
    RigOffer,
    SectionPalette,
    TemplateOffer,
    darkness_ms,
    frames_ms,
    is_late,
    resolve_section_look,
    rig_offer,
    section_palette_for,
    wheel_change_ms,
)
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseError,
    MusicalPhaseMap,
    build_musical_phase_map,
    musical_phase_fraction,
    musical_time_at,
)

logger = logging.getLogger(__name__)


def cue_limits(phase_map: MusicalPhaseMap, duration_ms: int) -> tuple[int, int]:
    """The frame-grid span a cue may occupy: `(start_limit_ms, end_limit_ms)`.

    The start is the covered phase span's start rounded up to the frame grid; the end
    is the earlier of the song's last whole frame and the covered end rounded down.
    Outside it every fixture is held dark.
    """
    start = -(-Fraction(phase_map.covered_start_ms) // EFFECT_GRID_MS) * EFFECT_GRID_MS
    covered_end = Fraction(phase_map.covered_end_ms) // EFFECT_GRID_MS * EFFECT_GRID_MS
    return int(start), int(min(duration_ms // EFFECT_GRID_MS * EFFECT_GRID_MS, covered_end))


def _snap_dark_spans(
    spans: Sequence[tuple[int, int]], *, shortest_dark_ms: int, shortest_lit_ms: int
) -> tuple[tuple[int, int], ...]:
    """Spans snapped outward to the frame grid, so every frame touching one is dark,
    each lengthened to at least `shortest_dark_ms`, then merged, in time order, where
    they overlap or leave less than `shortest_lit_ms` lit between them."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(
        (start, max(end, start + shortest_dark_ms))
        for start, end in (
            (start // EFFECT_GRID_MS * EFFECT_GRID_MS, -(-end // EFFECT_GRID_MS) * EFFECT_GRID_MS)
            for start, end in spans
            if end > start
        )
    ):
        if merged and start - merged[-1][1] < shortest_lit_ms:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return tuple(merged)


def _dark_through_dimmer(profile: FixtureCapabilities) -> bool:
    """Whether a span darkens this profile's cues through the dimmer (its zero
    extinguishes) rather than through the closed shutter (`_dark_over_spans`)."""
    return profile.visibility.dimmer_zero_extinguishes and "dimmer" in profile.axes


def _span_limits(fixture_group: FixtureGroup) -> tuple[int, int]:
    """`(shortest dark, shortest lit)` for the rig's dark spans, on the frame grid.

    What the transaction pass's shutter timing requires of a head darkened through its
    shutter: the closed state holds its close latency plus its settle, and the state a
    cue relights into its open latency plus its settle (the slowest of the profile's
    lit states). A head darkened through its dimmer has no such timing. Spans are
    rig-wide, so the slowest profile sets both; a lit stretch is at least two frames.
    """
    dark = lit = 0
    for fixture in fixture_group.expand_fixtures():
        profile = fixture.config.physical_profile
        shutter = None if profile is None else profile.discrete.get("shutter")
        if profile is None or _dark_through_dimmer(profile) or shutter is None:
            continue
        visibility = profile.visibility
        if shutter.closed_state is not None:
            closing = shutter.states[shutter.closed_state].settle_ms or 0
            dark = max(dark, (visibility.close_latency_ms or 0) + closing)
        opening = max(
            (
                state.settle_ms or 0
                for name, state in shutter.states.items()
                if name not in visibility.extinguishing_shutter_states
            ),
            default=0,
        )
        lit = max(lit, (visibility.open_latency_ms or 0) + opening)

    def frames(ms: int) -> int:
        return -(-ms // EFFECT_GRID_MS) * EFFECT_GRID_MS

    return frames(dark), max(2 * EFFECT_GRID_MS, frames(lit))


def _dark_over_spans(
    cues: Sequence[FixtureSegment],
    spans: Sequence[tuple[int, int]],
    profiles: Mapping[str, FixtureCapabilities],
    *,
    shortest_lit_ms: int,
) -> list[FixtureSegment]:
    """Command each cue dark over the render's dark spans, on its own authored path.

    A cue a span touches keeps every channel as compiled except the one its profile is
    darkened through: the dimmer, at zero over the span's frames, when the profile
    declares that zero extinguishes; else the shutter, in the profile's closed state.
    Through the shutter, a lit remainder between a span and the cue's own start or end
    shorter than `shortest_lit_ms` (what the shutter needs to open, `_span_limits`) is
    kept dark too, so the relit state can take effect. Pose, zoom and wheels play on
    as authored, so the head never leaves the cue's path and needs no re-entry after
    the span. Every other frame encodes as before. The transaction pass, which runs
    after, sees the darkness as it sees a visibility envelope's.

    Raises:
        ValueError: If a profile declares no darkness a cue can command.
    """
    out: list[FixtureSegment] = []
    for cue in cues:
        times = range(cue.t0_ms, cue.t1_ms, EFFECT_GRID_MS)
        dark = {t for t in times if any(start <= t < end for start, end in spans)}
        if not dark:
            out.append(cue)
            continue
        profile = profiles[cue.fixture_id]
        if not _dark_through_dimmer(profile):
            if 0 < min(dark) - cue.t0_ms < shortest_lit_ms:
                dark.update(range(cue.t0_ms, min(dark), EFFECT_GRID_MS))
            if 0 < cue.t1_ms - (max(dark) + EFFECT_GRID_MS) < shortest_lit_ms:
                dark.update(range(max(dark) + EFFECT_GRID_MS, cue.t1_ms, EFFECT_GRID_MS))
        channels = dict(cue.channels)
        dimmer = profile.axes.get("dimmer")
        shutter = profile.discrete.get("shutter")
        authored = channels.get(ChannelName.DIMMER)
        if profile.visibility.dimmer_zero_extinguishes and dimmer is not None:
            if authored is not None and isinstance(authored.physical, ContinuousTrajectory):
                samples = dict(
                    frame_values(authored.physical, cue.t0_ms, cue.t1_ms, EFFECT_GRID_MS)
                )
            else:  # unauthored: the profile's default word, as the encoder writes it
                word = profile.defaults[dimmer.coarse_offset]
                if dimmer.fine_offset is not None:
                    word = word << 8 | profile.defaults[dimmer.fine_offset]
                samples = dict.fromkeys(times, dimmer.word_center(word))
            levels: list[PhysicalPoint] = []
            for t in times:
                value = 0.0 if t in dark else float(samples[t])
                if not levels or levels[-1].value != value:
                    levels.append(PhysicalPoint(t_ms=t, value=value))
            channels[ChannelName.DIMMER] = ChannelValue(
                channel=ChannelName.DIMMER,
                physical=ContinuousTrajectory(
                    unit="normalized", points=tuple(levels), interpolation="hold"
                ),
            )
        elif (
            shutter is not None
            and shutter.closed_state is not None
            and shutter.closed_state in profile.visibility.extinguishing_shutter_states
        ):
            held = channels.get(ChannelName.SHUTTER)
            events: list[DiscretePoint] = []
            for t in times:
                state = (
                    shutter.closed_state
                    if t in dark
                    else state_at(held.physical, t)
                    if held is not None and isinstance(held.physical, DiscreteTrajectory)
                    else shutter.default_state
                )
                if not events or events[-1].state != state:
                    events.append(DiscretePoint(t_ms=t, state=state))
            channels[ChannelName.SHUTTER] = ChannelValue(
                channel=ChannelName.SHUTTER, physical=DiscreteTrajectory(events=tuple(events))
            )
        else:
            raise ValueError(
                f"{cue.fixture_id}: a dark span needs the profile to declare a darkness a "
                "cue can command (dimmer_zero_extinguishes, or a closed_state listed in "
                "extinguishing_shutter_states)"
            )
        out.append(cue.model_copy(update={"channels": channels}))
    return out


_POSE = (ChannelName.PAN, ChannelName.TILT, ChannelName.ZOOM)
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
        if profile.check_initial_state(initial):
            return None  # unknown: no state, or one the profile cannot take (no zoom)
        assert initial is not None  # checked above
        pose = initial.pose
        poses.append({ch: (pose[AXIS_KEYS[ch]], pose[AXIS_KEYS[ch]]) for ch in channels})
        for channel in _WHEELS:
            key = DISCRETE_KEYS[channel]
            if key in profile.discrete:
                held[channel].add(initial.discrete_states[key])
    envelope = {ch: (min(p[ch][0] for p in poses), max(p[ch][1] for p in poses)) for ch in channels}
    return envelope, dict(held), residual


def _pose_points(cue: FixtureSegment, channel: ChannelName) -> tuple[PhysicalPoint, ...]:
    trajectory = cue.channels[channel].physical
    assert isinstance(trajectory, ContinuousTrajectory)  # a cue authors its pose
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


@dataclass(frozen=True)
class _Deferral:
    """A wheel change turned in a dark window inside the section instead of before it:
    the cues before `split` hold the old states, the cue `turn_cue` (when the turn falls
    inside one) changes at `turn_ms`, the rest hold the new states (`_swap_wheels` each
    way, so it applies to a section compiled with either; a template overlay's own state
    is left as it is)."""

    changes: dict[ChannelName, tuple[str, str]]
    turn_ms: int
    split: int
    turn_cue: int | None

    def apply(
        self, own: Sequence[FixtureSegment], profile: FixtureCapabilities
    ) -> list[FixtureSegment]:
        """`own` (one head's section cues, in time order) with the change deferred."""
        back = {channel: (new, old) for channel, (old, new) in self.changes.items()}
        out = []
        for index, cue in enumerate(own):
            if index == self.turn_cue:
                old = _swap_wheels(cue, self.changes, profile)
                channels = dict(cue.channels)
                for channel, (held, new) in self.changes.items():
                    channels[channel] = ChannelValue(
                        channel=channel,
                        physical=DiscreteTrajectory(
                            events=(
                                *_wheel_events(old, channel, held, self.turn_ms),
                                DiscretePoint(t_ms=self.turn_ms, state=new),
                            )
                        ),
                    )
                out.append(cue.model_copy(update={"channels": channels}))
            elif index < self.split:
                out.append(_swap_wheels(cue, self.changes, profile))
            else:
                out.append(_swap_wheels(cue, back, profile))
        return out


@dataclass(frozen=True)
class _BoundaryChange:
    """What a head does at a boundary it plays lit through when song intent changes a
    wheel there (`_boundary_change`): one of a dip, a deferral, or the states kept."""

    record: dict[str, Any]
    dip: tuple[FixtureSegment, HeadFollow] | None = None
    """The previous cue with its tail dark and the wheel turned there, and the head as it
    leaves it."""
    deferred: _Deferral | None = None
    kept: dict[ChannelName, str] = field(default_factory=dict)
    """Without a dip or a deferral: the wheel states the head keeps from the previous
    section for the whole section."""
    retry: tuple[dict[ChannelName, tuple[str, str]], int, int] | None = None
    """With `kept`: the changes, lead and darkness to retry a deferral with once the
    section is compiled holding the kept states (a template overlay masks a change only
    from a base state other than its own, so holding the old state can open a mask)."""


def _half_beat_before(beat_grid: BeatGrid, time_ms: float) -> float:
    """Half the beat that ends at `time_ms` (a section start); the first beat's at the
    song's first beat."""
    beats = beat_grid.beat_boundaries
    if len(beats) < 2:
        return 0.0
    index = min(max(bisect.bisect_left(beats, time_ms), 1), len(beats) - 1)
    return (beats[index] - beats[index - 1]) / 2


def _commanded_dark_runs(cue: FixtureSegment, profile: FixtureCapabilities) -> list[list[int]]:
    """`[start, end)` runs of the cue's frames that command darkness: an authored dimmer
    at zero the profile declares extinguishing, or an extinguishing shutter state."""
    visibility = profile.visibility
    dimmer = cue.channels.get(ChannelName.DIMMER)
    levels: dict[int, Any] = {}
    if (
        visibility.dimmer_zero_extinguishes
        and dimmer is not None
        and isinstance(dimmer.physical, ContinuousTrajectory)
    ):
        levels = dict(frame_values(dimmer.physical, cue.t0_ms, cue.t1_ms, EFFECT_GRID_MS))
    shutter = cue.channels.get(ChannelName.SHUTTER)
    runs: list[list[int]] = []
    for time_ms in range(cue.t0_ms, cue.t1_ms, EFFECT_GRID_MS):
        dark = levels.get(time_ms) == 0 or (
            shutter is not None
            and isinstance(shutter.physical, DiscreteTrajectory)
            and state_at(shutter.physical, time_ms) in visibility.extinguishing_shutter_states
        )
        if not dark:
            continue
        if runs and runs[-1][1] == time_ms:
            runs[-1][1] = time_ms + EFFECT_GRID_MS
        else:
            runs.append([time_ms, time_ms + EFFECT_GRID_MS])
    return runs


def _dark_windows(
    cues: Sequence[FixtureSegment], profile: FixtureCapabilities
) -> list[tuple[int, int]]:
    """One head's dark windows between its first cue's start and its last cue's end, in
    time order: the gaps between its cues (the transaction pass holds the head dark
    there) and the frames its cues command dark, merged where they touch."""
    ordered = sorted(cues, key=lambda cue: cue.t0_ms)
    runs = [[a.t1_ms, b.t0_ms] for a, b in pairwise(ordered) if a.t1_ms < b.t0_ms]
    for cue in ordered:
        runs += _commanded_dark_runs(cue, profile)
    merged: list[list[int]] = []
    for start, end in sorted(runs):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _dip_span(
    runs: Sequence[Sequence[int]], cue_start_ms: int, boundary_ms: int, lead_ms: int
) -> tuple[int, int, int] | None:
    """How a dip before `boundary_ms` darkens the cue, `(added_from_ms, added_ms,
    dark_from_ms)`: the cue must be dark for `lead_ms` up to the boundary, and its own
    commanded darkness (`runs`, as `_commanded_dark_runs`) counts. Of the places the
    added darkness can start (the full lead before the boundary, or where one of the runs
    ends, so the dip rides that run), the one that adds the fewest lit frames, the latest
    of equals; `dark_from_ms` is where the darkness the turn rides begins. None when the
    cue is shorter than the lead."""
    if boundary_ms - lead_ms < cue_start_ms:
        return None
    before = sorted(
        (start, min(end, boundary_ms)) for start, end, *_ in runs if start < boundary_ms
    )

    def merged_start(dark_from: int) -> int:
        start = dark_from
        for run_start, run_end in reversed(before):
            if run_start < start <= run_end:
                start = run_start
        return start

    def lit(dark_from: int) -> int:
        covered = sum(max(0, end - max(start, dark_from)) for start, end in before)
        return boundary_ms - dark_from - covered

    best: tuple[int, int, int] | None = None
    for dark_from in {boundary_ms - lead_ms, *(end for _, end in before)}:
        start = merged_start(dark_from)
        if dark_from < cue_start_ms or boundary_ms - start < lead_ms:
            continue
        added = lit(dark_from)
        if best is None or (added, -dark_from) < (best[1], -best[0]):
            best = (dark_from, added, start)
    return best


def _boundary_change(
    own: Sequence[FixtureSegment],
    before: Sequence[HeadFollow],
    profile: FixtureCapabilities,
    initial: InitialFixtureState | None,
    locks: Sequence[RenderLock],
    failure_mode: FailureMode,
    *,
    intent_channels: Collection[ChannelName],
    half_beat_ms: float,
    shortest_lit_ms: int,
    section_end_ms: int,
) -> _BoundaryChange | None:
    """Where a head enters a section straight from its previous cue, lit, and song intent
    (this section's colour or gobo, or the previous section's) changes a wheel there, in
    order:

    1. A dark dip before the boundary: the tail of the previous cue is commanded dark on
       its own path (`_dark_over_spans`; the head keeps moving as authored), the wheel
       turns once the head is dark and settles, and the head reveals on the section's
       first frame as before. The dark lead is what the darkness, turn and settle need
       (`wheel_change_ms`), at most half the beat before the boundary and inside the
       previous cue, and the entry must then play as authored (`_plays_as_authored`,
       which also times the shutter). Darkness the previous cue already commands counts
       (`_dip_span`): the dip rides it, the half-beat bound applies to the darkness it
       adds (`added_ms`), and it adds nothing where the cue is dark for the whole lead.
    2. Else the change is deferred to the first dark window inside the section long
       enough for it (`_dark_windows`: a template's dark phase or overlay mask, a dark
       span), the head playing the previous states until then.
    3. Else the head keeps the previous states for the whole section.

    None where nothing changes, the change is not the song intent's, the head does not
    enter from its previous cue (a gap, or the section's start), or the entry repositions
    anyway, so the change rides its entry window (`_enter_section`).
    """
    if not own or not before:
        return None
    last = before[-1]
    first = own[0]
    if last.segment.t1_ms != first.t0_ms or _substitutable(last.segment, failure_mode):
        return None
    changes: dict[ChannelName, tuple[str, str]] = {}
    for channel in _WHEELS:
        capability = profile.discrete.get(DISCRETE_KEYS[channel])
        if capability is None or channel not in intent_channels:
            continue
        old = _wheel_state(
            last.segment, channel, last.segment.t1_ms - EFFECT_GRID_MS, capability.default_state
        )
        new = _wheel_state(first, channel, first.t0_ms, capability.default_state)
        if old != new:
            changes[channel] = (old, new)
    if not changes:
        return None
    unchanged = [_swap_wheels(cue, changes, profile) for cue in own]
    if not _plays_as_authored(unchanged, profile, last, initial, locks):
        return None
    kept = {channel: old for channel, (old, _) in changes.items()}
    states = {channel.value: {"from": old, "to": new} for channel, (old, new) in changes.items()}
    settles = [
        profile.discrete[DISCRETE_KEYS[channel]].states[new].settle_ms
        for channel, (_, new) in changes.items()
    ]
    known = [settle for settle in settles if settle is not None]
    lead = None if len(known) < len(settles) else wheel_change_ms(profile, max(known))
    darkness = darkness_ms(profile)
    boundary = first.t0_ms
    record: dict[str, Any] = {"boundary_ms": boundary, "wheels": states}
    if lead is None or darkness is None:
        record["kept_previous"] = {
            "reason": "a term of the wheel change (a settle, or the close latency) is unknown"
        }
        return _BoundaryChange(record, kept=kept)
    settle = frames_ms(max(max(known), EFFECT_GRID_MS))
    dip = _dip_span(_commanded_dark_runs(last.segment, profile), last.segment.t0_ms, boundary, lead)
    if dip is not None and dip[1] <= half_beat_ms:
        dark_from, added, dark_start = dip
        turn = boundary - settle
        darkened = last.segment
        if added:
            (darkened,) = _dark_over_spans(
                [last.segment],
                [(dark_from, boundary)],
                {last.segment.fixture_id: profile},
                shortest_lit_ms=shortest_lit_ms,
            )
        channels = dict(darkened.channels)
        for channel, (old, new) in changes.items():
            channels[channel] = ChannelValue(
                channel=channel,
                physical=DiscreteTrajectory(
                    events=(
                        *_wheel_events(darkened, channel, old, turn),
                        DiscretePoint(t_ms=turn, state=new),
                    )
                ),
            )
        dipped = darkened.model_copy(update={"channels": channels})
        follow = follow_cues(
            [dipped],
            profile,
            frame_ms=EFFECT_GRID_MS,
            after=before[-2] if len(before) > 1 else None,
        )[-1]
        if _plays_as_authored(own, profile, follow, initial, locks):
            record["dark_dip"] = {
                "from_ms": dark_start,
                "lead_ms": lead,
                "added_ms": added,
                "turn_ms": turn,
            }
            return _BoundaryChange(record, dip=(dipped, follow))
        reason = "the section's entry does not play as authored after a dark dip"
    elif dip is None:
        reason = f"the previous cue is shorter than the {lead} ms dark dip"
    else:
        extra = "" if dip[1] == lead else f" (it would add {dip[1]} ms to the darkness there)"
        reason = (
            f"the {lead} ms of darkness, turn and settle it needs{extra} do not fit half "
            f"the beat before the boundary ({half_beat_ms:g} ms)"
        )
    deferral = _defer(own, changes, profile, last, initial, locks, lead=lead, darkness=darkness)
    if deferral is not None:
        record["deferred"] = {
            "turn_ms": deferral.turn_ms,
            "waited_ms": deferral.turn_ms - boundary,
            # The window it turns in opens past half the section (`is_late`).
            "late": is_late(deferral.turn_ms - frames_ms(darkness), boundary, section_end_ms),
            "reason": reason,
        }
        return _BoundaryChange(record, deferred=deferral)
    record["kept_previous"] = {
        "reason": f"{reason}, and the section has no dark window long enough to turn in"
    }
    return _BoundaryChange(record, kept=kept, retry=(changes, lead, darkness))


def _defer(
    own: Sequence[FixtureSegment],
    changes: dict[ChannelName, tuple[str, str]],
    profile: FixtureCapabilities,
    last: HeadFollow,
    initial: InitialFixtureState | None,
    locks: Sequence[RenderLock],
    *,
    lead: int,
    darkness: int,
) -> _Deferral | None:
    """The first dark window of the head's section cues (`_dark_windows`) at least `lead`
    long in which its wheels can turn from the old to the new states: inside a cue, the
    turn falls `darkness` (frame-rounded) after the window opens and settles before it
    closes; in a gap between two cues, the transaction pass turns it, so the cue after
    the gap must still be entered as authored (`entry_feasible`). None when no window
    serves."""
    for start, end in _dark_windows(own, profile):
        if end - start < lead:
            continue
        turn = start + frames_ms(darkness)
        inside = next((i for i, cue in enumerate(own) if cue.t0_ms <= turn < cue.t1_ms), None)
        if inside is not None:
            return _Deferral(changes, turn, inside + 1, inside)
        after = next((i for i, cue in enumerate(own) if cue.t0_ms > turn), None)
        if after is None or after == 0:
            continue
        deferral = _Deferral(changes, turn, after, None)
        held = deferral.apply(own, profile)
        follows = follow_cues(held[:after], profile, frame_ms=EFFECT_GRID_MS, after=last)
        if entry_feasible(
            held[after],
            profile,
            after=follows[-1],
            initial=initial,
            locks=locks,
            frame_ms=EFFECT_GRID_MS,
        ):
            return deferral
    return None


def _unplayable_holds(
    held_cues: Sequence[FixtureSegment],
    authored_cues: Sequence[FixtureSegment],
    held: Mapping[str, Mapping[ChannelName, str]],
    overlay_wheels: Collection[str],
    profiles: Mapping[str, FixtureCapabilities],
    initial_states: Mapping[str, InitialFixtureState],
    failure_mode: FailureMode,
) -> dict[str, set[ChannelName]]:
    """Per head, the overlay wheels whose held state its section cues cannot be planned
    with (an overlay mask too short to turn to it and back) where the authored cues can:
    each head's cues are planned on their own (`plan_prepositions`), entered dark at
    their first pose and wheel states."""

    def plans(fixture_id: str, cues: Sequence[FixtureSegment]) -> bool:
        own = sorted((c for c in cues if c.fixture_id == fixture_id), key=lambda c: c.t0_ms)
        initial = initial_states.get(fixture_id)
        if not own or initial is None:
            return True
        profile = profiles[fixture_id]
        result = plan_prepositions(
            own,
            {fixture_id: profile},
            initial_states={fixture_id: _revealing_state(own[0], profile, initial)},
            locks=(),
            frame_ms=EFFECT_GRID_MS,
            sequence_end_ms=own[-1].t1_ms,
            failure_mode=failure_mode,
        )
        return not result.has_errors

    out: dict[str, set[ChannelName]] = {}
    for fixture_id, channels in held.items():
        wheels = {channel for channel in channels if channel.value in overlay_wheels}
        if wheels and not plans(fixture_id, held_cues) and plans(fixture_id, authored_cues):
            out[fixture_id] = wheels
    return out


def _played_record(
    record: dict[str, Any], outcomes: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> dict[str, Any]:
    """A section's look record (`SectionLook.record`) as rendered: each head that does not
    play the asked state from the section's start moves out of `heads` into `deferred`
    (the state and when it turns), `kept_previous` or `kept_authored_unplayable`."""
    for wheel, by_head in outcomes.items():
        entry = record.get(wheel)
        if entry is None:
            continue
        for fixture_id, outcome in sorted(by_head.items()):
            entry["heads"].pop(fixture_id, None)
            for kind, value in outcome.items():
                entry.setdefault(kind, {})[fixture_id] = value
    return record


def _unplayed_message(
    section_id: str, outcomes: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> str | None:
    """The warning for a section whose colour or gobo some heads play late or not at all."""
    said = []
    for wheel, noun in (("color", "colour"), ("gobo", "gobo")):
        kinds: dict[str, list[str]] = defaultdict(list)
        for fixture_id, outcome in sorted(outcomes[wheel].items()):
            for kind in outcome:
                kinds[kind].append(fixture_id)
        if kinds.get("deferred"):
            said.append(
                f"its {noun} change turns late on {len(kinds['deferred'])} head(s) "
                f"({', '.join(kinds['deferred'])}), in a dark window inside the section"
            )
        if kinds.get("kept_previous"):
            said.append(
                f"{len(kinds['kept_previous'])} head(s) ({', '.join(kinds['kept_previous'])}) "
                f"keep the previous section's {noun}: no time to turn the wheel in the dark"
            )
        if kinds.get("kept_authored_unplayable"):
            heads = kinds["kept_authored_unplayable"]
            said.append(
                f"{len(heads)} head(s) ({', '.join(heads)}) keep the template's {noun}: its "
                "overlay mask is too short for the asked state"
            )
    if not said:
        return None
    return f"section {section_id!r}: " + "; ".join(said) + " (the trace's section_looks)"


def _wheel_events(
    cue: FixtureSegment, channel: ChannelName, held: str, before_ms: int
) -> tuple[DiscretePoint, ...]:
    """The cue's own selections of `channel` before `before_ms` (`held` from its start
    where it authors none)."""
    value = cue.channels.get(channel)
    if value is None or not isinstance(value.physical, DiscreteTrajectory):
        return (DiscretePoint(t_ms=cue.t0_ms, state=held),)
    return tuple(event for event in value.physical.events if event.t_ms < before_ms)


def _swap_wheels(
    cue: FixtureSegment,
    changes: Mapping[ChannelName, tuple[str, str]],
    profile: FixtureCapabilities,
) -> FixtureSegment:
    """`cue` with each wheel of `changes` that holds the new state throughout holding the
    old one instead."""
    channels = dict(cue.channels)
    for channel, (old, new) in changes.items():
        default = profile.discrete[DISCRETE_KEYS[channel]].default_state
        value = cue.channels.get(channel)
        events = (
            value.physical.events
            if value is not None and isinstance(value.physical, DiscreteTrajectory)
            else None
        )
        holds = (events is None and default == new) or (
            events is not None and {event.state for event in events} == {new}
        )
        if holds:
            channels[channel] = ChannelValue(
                channel=channel,
                physical=DiscreteTrajectory(events=(DiscretePoint(t_ms=cue.t0_ms, state=old),)),
            )
    return cue.model_copy(update={"channels": channels})


@dataclass(frozen=True)
class TemplateAdmission:
    """What the pre-planning gate offers the planner (`admit_templates`).

    A template's rungs are its base (no preset), then each preset it declares, in that
    order; a template is admitted when any rung passes. `admitted` keeps the order the
    templates were given in. `effective_preset` holds each admitted template's first
    passing rung, its effective variant on this rig and song (None for the base): what a
    section naming no preset, or a preset that is not admitted, renders.
    `admitted_presets` holds each admitted template's admitted presets in the order it
    declares them. `exclusions` holds one `{"template_id", "reason"}` per catalog
    template no rung of which passes, and `preset_exclusions` one
    `{"template_id", "preset_id", "reason"}` per failing rung of an admitted template,
    `preset_id` None for the base. `entry_dips` holds, per admitted template, its
    worst-case section-entry dip: the largest `worst_case_entry_ms` over its admitted
    rungs and fixtures, from any pose in the union of every admitted rung's poses and
    the initial pose, with any of their wheel states or any wheel state the rig offers
    the planner held, into any of their wheel states or any offered one (a section's
    colour or gobo turns the wheel at its entry), as `{"fixture_id", "bound_ms",
    "beats"}`, `beats` at the song's shortest beat. `offer` is what the rig can show of
    the planner's song intent (`song_intent.rig_offer`).
    """

    admitted: tuple[str, ...]
    admitted_presets: dict[str, tuple[str, ...]]
    effective_preset: dict[str, str | None]
    exclusions: tuple[dict[str, str], ...]
    preset_exclusions: tuple[dict[str, str | None], ...]
    entry_dips: dict[str, dict[str, Any]]
    offer: RigOffer

    def record(self) -> dict[str, Any]:
        """The admission as JSON values, for the plan checkpoint."""
        return {
            **{key: value for key, value in asdict(self).items() if key != "offer"},
            "offer": self.offer.model_dump(mode="json"),
        }


_Reach = tuple[dict[ChannelName, tuple[float, float]], dict[ChannelName, set[str]]]
"""Per fixture, the pose range and the wheel states a template's cues hold."""


def _gc_paused[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Run `function` with the cyclic garbage collector paused. The gate allocates
    millions of short-lived, acyclic trajectory points, and collection passes over them
    cost about a quarter of its time without freeing anything; reference counting still
    frees them. The collector's previous state is restored."""

    @functools.wraps(function)
    def paused(*args: P.args, **kwargs: P.kwargs) -> R:
        enabled = gc.isenabled()
        gc.disable()
        try:
            return function(*args, **kwargs)
        finally:
            if enabled:
                gc.enable()

    return paused


@_gc_paused
def admit_templates(
    template_ids: Sequence[str],
    *,
    beat_grid: BeatGrid,
    fixture_group: FixtureGroup,
    initial_states: Mapping[str, InitialFixtureState],
    failure_mode: FailureMode,
    on_unplayable: UnplayableMode = "error",
    excludable: Collection[str] = (),
) -> TemplateAdmission:
    """Dry-compile templates on the rig, so a plan can only name ones that will render.

    Each template is compiled with no preset and with each preset it declares (the
    only presets the renderer applies), as one section from bar 1 over every
    bar that starts in the song, on every fixture of the rig, through the render's own
    `compile_template` against the song's phase map and within the render's
    cue limits (`cue_limits`). That checks target groups against the rig's
    roles, a preset patch the step models refuse, every step's states and channels against each
    profile, axis bounds, travel rate, pose motion the head can follow, and pulse and
    shutter timing for that placement, and each step's component references against
    the rig's presets, exactly as the render resolves them. The section then enters as the render enters a
    section (`_enter_section`) and `plan_prepositions` runs over it from the run's
    `initial_states` under the run's `failure_mode`, so a template whose own cues
    cannot be repositioned between is refused unless it declares the fallback the run
    enables.

    Beyond bar 1 it checks the placements a section can give the template: a repeating
    cycle from each bar that starts another alignment to the bars, to the song's end; a
    ONCE cycle from every start bar; each entered with every cue of its first cycle
    revealed first. So an admitted template plays at every alignment of its cycles to
    the song's bars and tempo, from whichever first-cycle cue a section reveals. What a
    section's end adds (a cycle cut short, a remainder after the last whole cycle, the
    state a fallback cascade reaches there) and what an earlier section leaves is
    checked only under `on_unplayable="error"`, as best effort, from every start bar;
    under `dark` the render keeps any such cue dark instead (`plan_prepositions`).

    Section entry is sized at render (`_enter_section`), so a template fails for its
    entry only where `worst_case_entry_ms` has no bound on some fixture, naming the
    fixture and the unknown profile terms. Each admitted template's worst-case dip is
    reported (`TemplateAdmission.entry_dips`, and logged).

    A template is admitted through the first of its rungs that passes, the base (no
    preset) and then each preset in the order it declares them: that rung is its
    effective variant, and each failing rung is recorded with its reason. That applies
    to a template in `excludable` (the shipped family catalog), which is left out of
    the offer with the reasons when no rung passes, instead of refusing the run. Any
    other template that fails on any rung refuses the run, so its effective variant is
    always its base.

    Returns:
        The admitted templates, presets and effective variants, the exclusions, the
        worst-case entry dips and the rig's offer (`song_intent.rig_offer`).

    Raises:
        UnsupportedRenderModeError: Naming each rung, step, fixture and item that fails,
            for any template not in `excludable`, or for every exclusion when none
            remains to admit, or none was offered.
    """
    from twinklr.core.sequencer.moving_heads.compile.step import CompileError
    from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
        UnsupportedRigShapeError,
    )

    fixtures = build_fixture_contexts(rig_profile_from_fixture_group(fixture_group), fixture_group)
    profiles = {
        fixture.fixture_id: fixture.config.physical_profile
        for fixture in fixture_group.expand_fixtures()
        if fixture.config.physical_profile is not None
    }
    topology = rig_topology(fixture_group)
    phase_map = build_musical_phase_map(beat_grid)
    duration_ms = int(beat_grid.duration_ms)
    start_limit, end_limit = cue_limits(phase_map, duration_ms)
    sequence_end_ms = len(frame_times(duration_ms)) * EFFECT_GRID_MS
    bars = sum(1 for start in beat_grid.bar_boundaries if start < beat_grid.duration_ms)
    # Keyed by (template id, preset id), None for the base.
    failures: dict[tuple[str, str | None], list[str]] = {}
    reach: dict[tuple[str, str | None], dict[str, _Reach]] = {}
    presets_of: dict[str, tuple[str, ...]] = {}
    # Each rung's bar-1 compile over the whole song: its cues, context, preset and cycle.
    whole_compiles: dict[
        tuple[str, str | None],
        tuple[list[FixtureSegment], TemplateCompileContext, TemplatePreset | None, float],
    ] = {}
    for template_id in template_ids:
        document = get_template(template_id)
        repeat = document.template.repeat
        presets_of[template_id] = tuple(preset.preset_id for preset in document.presets)
        for preset in (None, *document.presets):
            combination = (template_id, preset.preset_id if preset else None)
            where = f"template {template_id!r}" + (
                f", preset {preset.preset_id!r}" if preset else ""
            )
            # Bar 1 over the whole song first, from the initial state. Then every
            # placement class a section can give the template: a repeating cycle at each
            # alignment to the bars, cut short at every bar, and ending in every
            # remainder at every bar (`_repeating_placements`), for the cycle the compile
            # plays (`whole_period_cycle`, added once bar 1 compiles); a ONCE cycle at
            # every start bar (added once bar 1 shows how far its motion runs).
            placements = [(1, max(bars, 1), True)]
            cycle_bars = repeat.cycle_bars
            seen: set[tuple[Any, ...]] = set()
            # A step instance over the same frames compiles the same at every placement.
            # Only placements cut at section ends share instances, so without them the
            # cache is kept for one placement: what it holds is no longer kept alive.
            step_cache: dict[tuple[Any, ...], FixtureSegment] = {}
            index = 0
            while index < len(placements):
                start_bar, duration_bars, plan = placements[index]
                if on_unplayable != "error":
                    step_cache = {}
                whole = index == 0
                index += 1
                at = where
                if not whole:
                    at += f", placed at bar {start_bar}"
                    if repeat.mode != RepeatMode.ONCE:
                        at += f" for {duration_bars} bar(s)"
                context = TemplateCompileContext(
                    section_id="render_preflight",
                    template_id=document.template.template_id,
                    preset_id=preset.preset_id if preset else None,
                    fixtures=fixtures,
                    beat_grid=beat_grid,
                    start_bar=start_bar,
                    duration_bars=duration_bars,
                    presets=fixture_group.presets,
                    topology=topology,
                    fixture_group_id=fixture_group.group_id,
                )
                if start_bar > 1:
                    # Bar 1 is never deduplicated: there the head enters from its initial
                    # state at the song start, so an equal key later may reposition
                    # differently.
                    key = _placement_key(context, phase_map, start_limit, end_limit)
                    if key in seen:
                        continue
                    seen.add(key)
                # The previous placement's cues are released before this one is compiled.
                compiled = None
                try:
                    compiled = compile_template(
                        document.template,
                        context,
                        preset,
                        phase_map=phase_map,
                        start_limit_ms=start_limit,
                        end_limit_ms=end_limit,
                        step_cache=step_cache,
                    )
                except (
                    CompileError,
                    PhysicalChannelError,
                    UnsupportedRigShapeError,
                    ValueError,
                ) as error:
                    # A step's error carries a note naming its template, step and fixture.
                    notes = "; ".join(getattr(error, "__notes__", ()))
                    if notes:
                        notes += at.removeprefix(f"template {template_id!r}")
                    failures.setdefault(combination, []).append(f"{notes or at}: {error}")
                    break
                if whole:
                    reach[combination] = _reach(compiled.segments, profiles)
                    if repeat.mode != RepeatMode.ONCE:
                        # It compiled, so `whole_period_cycle` gives the cycle it played.
                        cycle_bars = whole_period_cycle(
                            apply_preset(document.template, preset)
                            if preset
                            else document.template,
                            beat_grid.beats_per_bar,
                        ).repeat.cycle_bars
                        placements += _repeating_placements(
                            cycle_bars, bars, section_ends=on_unplayable == "error"
                        )
                    whole_compiles[combination] = (compiled.segments, context, preset, cycle_bars)
                if not plan:
                    continue
                refusal = _plan_placement(
                    compiled.segments,
                    profiles,
                    initial_states,
                    section_start_ms=context.start_ms,
                    first_cycle_end_ms=context.bar_offset_to_ms(cycle_bars),
                    phase_map=phase_map,
                    failure_mode=failure_mode,
                    sequence_end_ms=sequence_end_ms,
                    song_start=start_bar == 1,
                )
                if refusal:
                    failures.setdefault(combination, []).append(
                        f"{at}: dark repositioning between its own cues cannot be planned: "
                        + refusal
                    )
                    break
                if whole and repeat.mode == RepeatMode.ONCE:
                    window = _once_window_bars(
                        compiled.segments,
                        phase_map,
                        section_start_ms=context.start_ms,
                        cycle_bars=repeat.cycle_bars,
                        beats_per_bar=beat_grid.beats_per_bar,
                    )
                    placements += [
                        (later, min(bars - later + 1, window), True)
                        for later in range(2, bars + 1)
                        if bars - later + 1 >= repeat.cycle_bars - 1e-9
                    ]
    # A rung without an entry bound fails, and leaves the envelope the other rungs' dips
    # and bounds are measured from. Rungs that lose their bound together may do so only
    # through each other: each pass removes those that have none even with every rung
    # failing in it removed (when none has, all of them), until every rung has one.
    shortest_beat_ms = min(
        (later - earlier for earlier, later in pairwise(beat_grid.beat_boundaries)),
        default=None,
    )
    heads = rig_offer(fixture_group, beat_grid).heads
    excluded = {
        template_id: _overlay_exclusions(
            get_template(template_id),
            {c: compiles for c, compiles in whole_compiles.items() if c[0] == template_id},
            heads,
            profiles=profiles,
            initial_states=initial_states,
            phase_map=phase_map,
            failure_mode=failure_mode,
            sequence_end_ms=sequence_end_ms,
            start_limit_ms=start_limit,
            end_limit_ms=end_limit,
        )
        for template_id in template_ids
        if any(c[0] == template_id and c not in failures for c in whole_compiles)
    }
    offered = {
        template_id: {
            head.fixture_id: {
                ChannelName.COLOR: set(head.colors)
                - set(excluded.get(template_id, {}).get(head.fixture_id, {}).get("color", ())),
                ChannelName.GOBO: set(head.gobos)
                - set(excluded.get(template_id, {}).get(head.fixture_id, {}).get("gobo", ())),
            }
            for head in heads
        }
        for template_id in template_ids
    }
    rungs = {c: per_fixture for c, per_fixture in reach.items() if c not in failures}
    while True:
        dips, unbounded = _entry_dips(rungs, profiles, initial_states, shortest_beat_ms, offered)
        if not unbounded:
            break
        rest = {c: per_fixture for c, per_fixture in rungs.items() if c not in unbounded}
        certain = {
            combination: reason
            for combination, reason in unbounded.items()
            if combination
            in _entry_dips(
                {**rest, combination: rungs[combination]},
                profiles,
                initial_states,
                shortest_beat_ms,
                offered,
            )[1]
        }
        for combination, reason in (certain or unbounded).items():
            failures.setdefault(combination, []).append(reason)
            del rungs[combination]
    # Each template's rungs, base first, then its presets in declared order.
    passing = {
        t: [p for p in (None, *presets_of[t]) if (t, p) not in failures] for t in template_ids
    }

    def reasons(template_id: str) -> list[str]:
        """Every failure of the template's rungs, base first."""
        return [
            reason
            for preset_id in (None, *presets_of[template_id])
            for reason in failures.get((template_id, preset_id), ())
        ]

    refused = [reason for t in template_ids if t not in excludable for reason in reasons(t)]
    if refused:
        raise UnsupportedRenderModeError(
            "the moving-head renderer would offer the planner templates this rig "
            "cannot render: " + "; ".join(refused)
        )
    exclusions = tuple(
        {"template_id": t, "reason": "; ".join(reasons(t))} for t in template_ids if not passing[t]
    )
    admitted = tuple(t for t in template_ids if passing[t])
    if not admitted:
        raise UnsupportedRenderModeError(
            "the moving-head renderer has no template this rig can render, so no "
            "template remains to offer the planner: "
            + ("; ".join(exclusion["reason"] for exclusion in exclusions) or "none is loaded")
        )
    effective_preset = {t: passing[t][0] for t in admitted}
    offer = rig_offer(
        fixture_group,
        beat_grid,
        {
            t: TemplateOffer(
                variants={
                    "base" if p is None else p: _dark_phases(
                        whole_compiles[t, p], profiles, phase_map
                    )
                    for p in passing[t]
                },
                excluded=excluded.get(t, {}),
            )
            for t in admitted
        },
        # Only song intent changes a wheel at a boundary, so only a rig that offers a
        # wheel state needs to know where it always enters dark.
        {}
        if not any(head.colors or head.gobos for head in heads)
        else _dark_entries(
            {t: passing[t] for t in admitted},
            template_cycles={c: whole_compiles[c][3] for c in whole_compiles},
            beat_grid=beat_grid,
            bars=bars,
            fixtures=fixtures,
            fixture_group=fixture_group,
            topology=topology,
            profiles=profiles,
            initial_states=initial_states,
            phase_map=phase_map,
            failure_mode=failure_mode,
            start_limit_ms=start_limit,
            end_limit_ms=end_limit,
        ),
    )
    admitted_presets = {t: tuple(p for p in passing[t] if p is not None) for t in admitted}
    preset_exclusions = tuple(
        {"template_id": t, "preset_id": p, "reason": "; ".join(failures[t, p])}
        for t in admitted
        for p in (None, *presets_of[t])
        if (t, p) in failures
    )
    for exclusion in exclusions:
        logger.warning(
            "moving heads: template %r is left out of the planner's offer: %s",
            exclusion["template_id"],
            exclusion["reason"],
        )
    for rung in preset_exclusions:
        template_id, preset_id = str(rung["template_id"]), rung["preset_id"]
        effective = effective_preset[template_id]
        logger.warning(
            "moving heads: %s of template %r is not admitted, so a section naming %s renders %s: %s",
            "the base" if preset_id is None else f"preset {preset_id!r}",
            template_id,
            "no preset" if preset_id is None else "it",
            "its base" if effective is None else f"its effective variant, preset {effective!r}",
            rung["reason"],
        )
    for template_id, dip in dips.items():
        logger.info(
            "moving heads: template %r enters a section dark for up to %s beat(s) at the "
            "song's shortest beat (%s ms on fixture %r, from any admitted template)",
            template_id,
            dip["beats"],
            dip["bound_ms"],
            dip["fixture_id"],
        )
    return TemplateAdmission(
        admitted=admitted,
        admitted_presets=admitted_presets,
        effective_preset=effective_preset,
        exclusions=exclusions,
        preset_exclusions=preset_exclusions,
        entry_dips=dips,
        offer=offer,
    )


def _overlay_exclusions(
    document: TemplateDoc,
    compiles: Mapping[
        tuple[str, str | None],
        tuple[list[FixtureSegment], TemplateCompileContext, TemplatePreset | None, float],
    ],
    heads: Sequence[HeadWheels],
    *,
    profiles: Mapping[str, FixtureCapabilities],
    initial_states: Mapping[str, InitialFixtureState],
    phase_map: MusicalPhaseMap,
    failure_mode: FailureMode,
    sequence_end_ms: int,
    start_limit_ms: int,
    end_limit_ms: int,
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Per fixture and wheel, the offered states a template with overlays cannot hold:
    a section's colour or gobo replaces the base state its overlay masks turn from and
    back to, so a slower-settling state can need more than a mask gives. Each rung's
    bar-1 compile over the song is repeated with every fixture holding its slowest
    offered state on the overlay's wheel, then the next slower settle down, until the
    dark repositioning between its cues plans (`_plan_placement`); the states slower than
    that are left out of the template's offer (all of them when none plans). A template
    without overlays excludes nothing."""
    from twinklr.core.sequencer.moving_heads.compile.step import CompileError
    from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
        UnsupportedRigShapeError,
    )

    wheels = {overlay.channel for overlay in document.template.overlays}
    excluded: dict[str, dict[str, set[str]]] = {}
    for wheel in sorted(wheels):
        channel = ChannelName(wheel)
        offered = {
            head.fixture_id: dict(head.colors if wheel == "color" else head.gobos) for head in heads
        }

        def settle(fixture_id: str, state: str, wheel: str = wheel) -> int:
            value = profiles[fixture_id].discrete[wheel].states[state].settle_ms  # type: ignore[index]
            assert value is not None  # offered states have one
            return value

        thresholds = sorted(
            {settle(f, state) for f, states in offered.items() for state in states}, reverse=True
        )
        for segments, context, preset, cycle_bars in compiles.values():
            del segments
            allowed: int | None = None
            for threshold in thresholds:
                held = {}
                for fixture_id, states in offered.items():
                    fitting = [s for s in states if settle(fixture_id, s) <= threshold]
                    if fitting:
                        slowest = max(fitting, key=lambda s: (settle(fixture_id, s), s))
                        held[fixture_id] = {channel: slowest}
                try:
                    compiled = compile_template(
                        document.template,
                        context,
                        preset,
                        phase_map=phase_map,
                        start_limit_ms=start_limit_ms,
                        end_limit_ms=end_limit_ms,
                        held_states=held,
                    )
                except (CompileError, PhysicalChannelError, UnsupportedRigShapeError, ValueError):
                    continue
                if not _plan_placement(
                    compiled.segments,
                    profiles,
                    initial_states,
                    section_start_ms=context.start_ms,
                    first_cycle_end_ms=context.bar_offset_to_ms(cycle_bars),
                    phase_map=phase_map,
                    failure_mode=failure_mode,
                    sequence_end_ms=sequence_end_ms,
                    song_start=True,
                ):
                    allowed = threshold
                    break
            for fixture_id, states in offered.items():
                slow = {s for s in states if allowed is None or settle(fixture_id, s) > allowed}
                if slow:
                    excluded.setdefault(fixture_id, {}).setdefault(wheel, set()).update(slow)
    return {
        fixture_id: {wheel: tuple(sorted(states)) for wheel, states in by_wheel.items()}
        for fixture_id, by_wheel in excluded.items()
    }


def _enters_lit(
    own: Sequence[FixtureSegment],
    before: Sequence[HeadFollow],
    profile: FixtureCapabilities,
    initial: InitialFixtureState | None,
    failure_mode: FailureMode,
) -> bool:
    """Whether a head plays straight from its previous cue into a section's cues, lit, so
    a wheel change there needs a dip or a deferral (`_boundary_change`); else it enters
    through a dark window, where the turn rides the entry. The wheels are held at the
    previous cue's states, as `_boundary_change` checks the entry without the change."""
    if not own or not before:
        return False
    last = before[-1]
    first = own[0]
    if last.segment.t1_ms != first.t0_ms or _substitutable(last.segment, failure_mode):
        return False
    changes = {}
    for channel in _WHEELS:
        capability = profile.discrete.get(DISCRETE_KEYS[channel])
        if capability is None:
            continue
        old = _wheel_state(
            last.segment, channel, last.segment.t1_ms - EFFECT_GRID_MS, capability.default_state
        )
        new = _wheel_state(first, channel, first.t0_ms, capability.default_state)
        if old != new:
            changes[channel] = (old, new)
    unchanged = [_swap_wheels(cue, changes, profile) for cue in own]
    return _plays_as_authored(unchanged, profile, last, initial, ())


def _dark_entries(
    variants: Mapping[str, Sequence[str | None]],
    *,
    template_cycles: Mapping[tuple[str, str | None], float],
    beat_grid: BeatGrid,
    bars: int,
    fixtures: Any,
    fixture_group: FixtureGroup,
    topology: Any,
    profiles: Mapping[str, FixtureCapabilities],
    initial_states: Mapping[str, InitialFixtureState],
    phase_map: MusicalPhaseMap,
    failure_mode: FailureMode,
    start_limit_ms: int,
    end_limit_ms: int,
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Per admitted template and admitted predecessor template, the heads that always
    enter it through a dark window after that one (`_enters_lit` false): for every pair
    of their admitted variants, the predecessor placed from bar 1 and the successor from each bar after
    it, up to the predecessor's longest cycle (each phase of its cycle the boundary can
    fall on, at this song's opening tempo). A wheel change there rides the entry."""
    from twinklr.core.sequencer.moving_heads.compile.step import CompileError
    from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
        UnsupportedRigShapeError,
    )

    def compile_at(
        template_id: str, preset_id: str | None, start_bar: int, duration_bars: int
    ) -> dict[str, list[FixtureSegment]] | None:
        document = get_template(template_id)
        preset = next((p for p in document.presets if p.preset_id == preset_id), None)
        context = TemplateCompileContext(
            section_id="render_preflight",
            template_id=document.template.template_id,
            preset_id=preset_id,
            fixtures=fixtures,
            beat_grid=beat_grid,
            start_bar=start_bar,
            duration_bars=duration_bars,
            presets=fixture_group.presets,
            topology=topology,
            fixture_group_id=fixture_group.group_id,
        )
        try:
            segments = compile_template(
                document.template,
                context,
                preset,
                phase_map=phase_map,
                start_limit_ms=start_limit_ms,
                end_limit_ms=end_limit_ms,
            ).segments
        except (CompileError, PhysicalChannelError, UnsupportedRigShapeError, ValueError):
            return None
        by_fixture: dict[str, list[FixtureSegment]] = defaultdict(list)
        for cue in sorted(segments, key=lambda cue: cue.t0_ms):
            by_fixture[cue.fixture_id].append(cue)
        return by_fixture

    longest = max((math.ceil(cycle) for cycle in template_cycles.values()), default=1)
    starts = range(2, min(bars, 1 + max(longest, 1)) + 1)
    pairs = {(t, p) for t, presets in variants.items() for p in presets}
    entries: dict[tuple[str, str | None], dict[int, dict[str, list[FixtureSegment]] | None]] = {}
    follows: dict[tuple[str, str | None], dict[int, dict[str, list[HeadFollow]]] | None] = {}
    for t, p in sorted(pairs, key=lambda pair: (pair[0], pair[1] or "")):
        cycle = max(1, math.ceil(template_cycles.get((t, p), 1)))
        entries[t, p] = {b: compile_at(t, p, b, min(cycle, bars - b + 1)) for b in starts}
        befores = {b: compile_at(t, p, 1, b - 1) for b in starts}
        follows[t, p] = (
            None
            if any(cues is None for cues in befores.values())
            else {
                b: {
                    f: follow_cues(own, profiles[f], frame_ms=EFFECT_GRID_MS)
                    for f, own in (cues or {}).items()
                    if f in profiles
                }
                for b, cues in befores.items()
            }
        )

    def dark_heads(predecessor: str, successor: str) -> set[str]:
        heads = set(profiles)
        for pp in variants[predecessor]:
            before_by_bar = follows[predecessor, pp]
            if before_by_bar is None:
                return set()
            for sp in variants[successor]:
                for b in starts:
                    own_by_fixture = entries[successor, sp][b]
                    if own_by_fixture is None:
                        return set()
                    heads -= {
                        f
                        for f, own in own_by_fixture.items()
                        if f in profiles
                        and _enters_lit(
                            own,
                            before_by_bar[b].get(f, []),
                            profiles[f],
                            initial_states.get(f),
                            failure_mode,
                        )
                    }
        return heads if starts else set()

    dark: dict[str, dict[str, tuple[str, ...]]] = {}
    for successor in variants:
        for predecessor in variants:
            heads = dark_heads(predecessor, successor)
            if heads:
                dark.setdefault(successor, {})[predecessor] = tuple(sorted(heads))
    return dark


def _dark_phases(
    compile: tuple[list[FixtureSegment], TemplateCompileContext, TemplatePreset | None, float],
    profiles: Mapping[str, FixtureCapabilities],
    phase_map: MusicalPhaseMap,
) -> DarkPhases:
    """A rung's dark phases in its first cycle (`DarkPhases`), from its bar-1 compile: per
    fixture, each dark window (`_dark_windows`) that opens inside the cycle, in beats from
    the cycle's start."""
    segments, context, _, cycle_bars = compile
    start = context.start_ms
    cycle_end = context.bar_offset_to_ms(cycle_bars)

    def beats(time_ms: float) -> float:
        return round(
            float(musical_phase_fraction(phase_map, time_ms, origin_ms=start, period_beats=1.0)),
            3,
        )

    by_fixture: dict[str, list[FixtureSegment]] = defaultdict(list)
    for segment in segments:
        by_fixture[segment.fixture_id].append(segment)
    return DarkPhases(
        cycle_beats=beats(cycle_end),
        heads={
            fixture_id: tuple(
                (beats(a), beats(b))
                for a, b in _dark_windows(own, profiles[fixture_id])
                if start <= a < cycle_end
            )
            for fixture_id, own in sorted(by_fixture.items())
        },
    )


def _reach(
    segments: Sequence[FixtureSegment], profiles: Mapping[str, FixtureCapabilities]
) -> dict[str, _Reach]:
    """Per fixture, every pose and wheel state a compiled section's cues hold."""
    by_fixture: dict[str, list[FixtureSegment]] = defaultdict(list)
    for segment in segments:
        by_fixture[segment.fixture_id].append(segment)
    reach: dict[str, _Reach] = {}
    for fixture_id, own in by_fixture.items():
        profile = profiles[fixture_id]
        channels = [ch for ch in _POSE if AXIS_KEYS[ch] in profile.axes]
        reach[fixture_id] = (
            {ch: _pose_range(own, ch) for ch in channels},
            _wheel_states(own, profile),
        )
    return reach


def _entry_dips(
    reach: Mapping[tuple[str, str | None], Mapping[str, _Reach]],
    profiles: Mapping[str, FixtureCapabilities],
    initial_states: Mapping[str, InitialFixtureState],
    shortest_beat_ms: float | None,
    offered: Mapping[str, Mapping[str, Mapping[ChannelName, Collection[str]]]],
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str | None], str]]:
    """Each template's worst-case section-entry dip, over its rungs in `reach` (keyed by
    template and preset id, None for the base), and each rung without a bound on some
    fixture, with the reason naming the fixture and the unknown terms: no section entry
    into it can be sized. A rung without a bound adds nothing to its template's dip.

    The predecessor may be any rung in `reach` or the initial state: per
    fixture, the envelope is the union of their pose ranges and the initial pose, and the
    wheels held are the union of their wheel states and the initial ones. A section's
    colour or gobo can hold any wheel state the rig offers for its template (`offered`,
    per template and fixture), so the states offered for any template join the states
    held, and those offered for a rung's template its entry states. A wheel is offered
    only when every one of its states has a known settle, so they never leave a rung
    without a bound.
    """
    envelope: dict[str, dict[ChannelName, tuple[float, float]]] = {}
    held: dict[str, dict[ChannelName, set[str]]] = defaultdict(lambda: defaultdict(set))
    for fixture_id, initial in initial_states.items():
        # An unknown initial state already fails every template at its bar-1 placement.
        if fixture_id not in profiles or profiles[fixture_id].check_initial_state(initial):
            continue
        pose = initial.pose
        envelope[fixture_id] = {
            ch: (pose[AXIS_KEYS[ch]], pose[AXIS_KEYS[ch]])
            for ch in _POSE
            if AXIS_KEYS[ch] in profiles[fixture_id].axes
        }
        for channel in _WHEELS:
            state = initial.discrete_states.get(DISCRETE_KEYS[channel])
            if state is not None:
                held[fixture_id][channel].add(state)
    for per_fixture in reach.values():
        for fixture_id, (poses, wheels) in per_fixture.items():
            merged = envelope.setdefault(fixture_id, dict(poses))
            for ch, (low, high) in poses.items():
                merged[ch] = (min(merged[ch][0], low), max(merged[ch][1], high))
            for channel, states in wheels.items():
                held[fixture_id][channel] |= states
    for by_fixture in offered.values():
        for fixture_id, by_channel in by_fixture.items():
            for channel, offered_states in by_channel.items():
                held[fixture_id][channel] |= set(offered_states)

    worst: dict[str, tuple[int, str]] = {}
    unbounded: dict[tuple[str, str | None], str] = {}
    for (template_id, preset_id), per_fixture in reach.items():
        found: tuple[int, str] | None = None
        for fixture_id, (poses, wheels) in sorted(per_fixture.items()):
            profile = profiles[fixture_id]
            ours = offered.get(template_id, {}).get(fixture_id, {})
            entry = {
                channel: set(states) | set(ours.get(channel, ()))
                for channel, states in wheels.items()
            }
            bound = worst_case_entry_ms(
                profile,
                entry_pose=poses,
                entry_wheels=entry,
                pose_envelope=envelope[fixture_id],
                held_wheels=held[fixture_id],
                frame_ms=EFFECT_GRID_MS,
            )
            if bound is None:
                where = f"template {template_id!r}" + (
                    f", preset {preset_id!r}" if preset_id else ""
                )
                unbounded[template_id, preset_id] = (
                    f"{where}: fixture {fixture_id!r} has no worst-case section-entry bound, "
                    "since its profile leaves "
                    + ", ".join(_unknown_bound_terms(profile, entry, held[fixture_id]))
                    + " unknown"
                )
                break
            if found is None or bound > found[0]:
                found = (bound, fixture_id)
        else:
            if found is not None and (template_id not in worst or found[0] > worst[template_id][0]):
                worst[template_id] = found
    dips = {
        template_id: {
            "fixture_id": fixture_id,
            "bound_ms": bound,
            "beats": None if shortest_beat_ms is None else math.ceil(bound / shortest_beat_ms),
        }
        for template_id, (bound, fixture_id) in worst.items()
    }
    return dips, unbounded


def _unknown_bound_terms(
    profile: FixtureCapabilities,
    entry_wheels: Mapping[ChannelName, Collection[str]],
    held_wheels: Mapping[ChannelName, Collection[str]],
) -> list[str]:
    """The profile terms `worst_case_entry_ms` needs for this entry and finds unknown."""
    visibility = profile.visibility
    terms = [] if visibility.close_latency_ms is not None else ["visibility.close_latency_ms"]
    if not visibility.dimmer_zero_extinguishes:
        shutter = profile.discrete.get("shutter")
        if shutter is None or shutter.closed_state not in visibility.extinguishing_shutter_states:
            terms.append("an extinguishing discrete.shutter.closed_state")
        else:
            terms += [
                f"discrete.shutter.states.{state}.settle_ms"
                for state in visibility.extinguishing_shutter_states
                if shutter.states[state].settle_ms is None
            ]
    for channel in _WHEELS:
        key = DISCRETE_KEYS[channel]
        capability = profile.discrete.get(key)
        if capability is None:
            continue
        terms += [
            f"discrete.{key}.states.{state}.settle_ms"
            for state in sorted(entry_wheels.get(channel, (capability.default_state,)))
            if set(held_wheels.get(channel, ())) != {state}
            and capability.states[state].settle_ms is None
        ]
    for channel in _POSE:
        name = AXIS_KEYS[channel]
        axis = profile.axes.get(name)
        if axis is not None:
            terms += [
                f"axes.{name}.{term}"
                for term in ("travel_speed_per_s", "latency_ms", "settle_ms")
                if getattr(axis, term) is None
            ]
    return terms


def _repeating_placements(
    cycle_bars: float, bars: int, *, section_ends: bool = True
) -> list[tuple[int, int, bool]]:
    """The `(start_bar, duration_bars, plan)` sections the gate checks a repeating
    template at, beyond bar 1 over the whole song; `plan` is False where compiling alone
    adds anything.

    A cycle of `p/q` bars, started on any bar, puts its cycles at `p` alignments to the
    bars: a section from each of the bars 2 to `p` to the song's end holds every cycle
    at its alignment, every boundary between consecutive cycles and the longest chains.
    A section's end adds two things a longer one never shows: cutting a cycle's head
    short (sections shorter than a cycle: compiled, since nothing follows the cut in
    them) and a remainder after its last complete cycle under the remainder policy
    (sections of up to `q` cycles plus a remainder, from every start bar: compiled and
    planned, since the remainder follows a cycle); only with `section_ends`.
    """
    cycle = Fraction(repr(cycle_bars)).limit_denominator(64)
    placements = [
        (start, bars - start + 1, True) for start in range(2, min(cycle.numerator, bars) + 1)
    ]
    for start in range(1, bars + 1 if section_ends else 1):
        for length in range(
            1, min(math.ceil((cycle.denominator + 1) * cycle), bars - start + 1) + 1
        ):
            if length < cycle:
                placements.append((start, length, False))
            elif (length / cycle).denominator != 1:
                placements.append((start, length, True))
    return placements


def _plan_placement(
    segments: Sequence[FixtureSegment],
    profiles: Mapping[str, FixtureCapabilities],
    initial_states: Mapping[str, InitialFixtureState],
    *,
    section_start_ms: int,
    first_cycle_end_ms: int,
    phase_map: MusicalPhaseMap,
    failure_mode: FailureMode,
    sequence_end_ms: int,
    song_start: bool,
) -> str:
    """Plan a gate placement entered at each cue of its first cycle; "" when every entry
    plans, else the diagnostics of the first that does not.

    After a section's entry window any cue of its first cycle can be the first a head
    reveals, entered from darkness and played as authored (cut or whole, it ends the
    same); a `drop_accent` cascade runs differently from each. Each entry is planned
    from a dark head already at that cue's first pose and wheel states, so it plays
    however wide a window the previous section leaves. At the song start the section
    also enters from the run's initial state, as it renders there. Heads with the same
    profile, initial state and cues plan identically (the gate has no locks): one of
    each is planned. Entries share their later cues, and a head reaching one of them in
    the state an earlier entry reached it in plans the rest as that entry did
    (`plan_prepositions`' memo, kept for this placement only).
    """
    by_fixture: dict[str, list[FixtureSegment]] = defaultdict(list)
    for segment in sorted(segments, key=lambda segment: segment.t0_ms):
        by_fixture[segment.fixture_id].append(segment)
    first_cycle = {
        fixture_id: sum(
            1 for cue in own if int(cue.metadata["requested_t0_ms"]) < first_cycle_end_ms
        )
        for fixture_id, own in by_fixture.items()
    }
    entries: list[int | None] = [None] if song_start else []
    entries += range(max(first_cycle.values(), default=1) or 1)
    memo: PrepositionMemo = {}
    for entry in entries:
        states = dict(initial_states)
        entered = list(segments)
        if entry is not None:
            entered = []
            for fixture_id, own in by_fixture.items():
                own = own[min(entry, max(first_cycle[fixture_id] - 1, 0)) :]
                entered += own
                if fixture_id in states:
                    states[fixture_id] = _revealing_state(
                        own[0], profiles[fixture_id], states[fixture_id]
                    )
        cues, _, _ = _enter_section(
            entered,
            {},
            profiles,
            states,
            section_start_ms=section_start_ms,
            phase_map=phase_map,
            failure_mode=failure_mode,
        )
        members = _plan_groups(cues, profiles, states)
        result = plan_prepositions(
            [cue for cue in cues if cue.fixture_id in members],
            {fixture_id: profiles[fixture_id] for fixture_id in members},
            initial_states=states,
            locks=(),
            frame_ms=EFFECT_GRID_MS,
            sequence_end_ms=sequence_end_ms,
            failure_mode=failure_mode,
            memo=memo,
        )
        errors = [d for d in result.diagnostics if d.status == "error"]
        if errors:
            prefix = "" if entry is None else f"(entered at cue {entry + 1} of its first cycle) "
            return prefix + "; ".join(
                f"{'/'.join(members[d.fixture_id])} cue at {d.cue_ms} ms: {d.code}: {d.reason}"
                for d in errors
            )
    return ""


def _revealing_state(
    cue: FixtureSegment, profile: FixtureCapabilities, initial: InitialFixtureState
) -> InitialFixtureState:
    """The run's dark initial state moved to `cue`'s first pose and wheel states."""
    pose = {}
    for channel in _POSE:
        if AXIS_KEYS[channel] in profile.axes:
            pose[f"{AXIS_KEYS[channel]}_deg"] = _pose_points(cue, channel)[0].value
    wheels = dict(initial.discrete_states)
    for channel in _WHEELS:
        key = DISCRETE_KEYS[channel]
        capability = profile.discrete.get(key)
        if capability is not None:
            wheels[key] = _wheel_state(cue, channel, cue.t0_ms, capability.default_state)
    return initial.model_copy(update={**pose, "discrete_states": wheels})


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
        for channel in (ch for ch in _POSE if ch in segment.channels):
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


def _plan_groups(
    cues: Sequence[FixtureSegment],
    profiles: Mapping[str, FixtureCapabilities],
    states: Mapping[str, InitialFixtureState],
) -> dict[str, list[str]]:
    """The fixtures with equal `_plan_key`s, each group under its first, in `profiles`
    order. Keys are compared, never hashed (hashing hashes every point), and computed
    only for heads alike in everything cheaper to compare (their cues' times and first
    and last pose values), since heads differing there have different keys."""
    own: dict[str, list[FixtureSegment]] = defaultdict(list)
    for cue in cues:
        own[cue.fixture_id].append(cue)
    alike: dict[tuple[Any, ...], list[tuple[str, list[Any]]]] = defaultdict(list)
    groups: dict[str, list[str]] = {}
    for fixture_id, profile in profiles.items():
        mine = own.get(fixture_id, [])
        initial = states.get(fixture_id)
        candidates = alike[_rough_plan_key(mine)]
        key: list[Any] = []  # computed once, if any other head is alike
        for first, first_key in candidates:
            if not first_key:
                first_key.append(_plan_key(own.get(first, []), profiles[first], states.get(first)))
            if not key:
                key.append(_plan_key(mine, profile, initial))
            if first_key[0] == key[0]:
                groups[first].append(fixture_id)
                break
        else:
            candidates.append((fixture_id, key))
            groups[fixture_id] = [fixture_id]
    return groups


def _rough_plan_key(cues: Sequence[FixtureSegment]) -> tuple[Any, ...]:
    """Cue times and each pose channel's first and last values: equal for equal
    `_plan_key`s."""
    rough: list[tuple[Any, ...]] = []
    for cue in cues:
        rough.append((cue.t0_ms, cue.t1_ms))
        for channel in _POSE:
            value = cue.channels.get(channel)
            physical = None if value is None else value.physical
            if isinstance(physical, ContinuousTrajectory):
                rough.append((physical.points[0].value, physical.points[-1].value))
    return tuple(rough)


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


def _section_preset(
    section: PlanSection,
    template_doc: TemplateDoc,
    diagnostics: list[MHDiagnostic],
    admission: TemplateAdmission | None,
) -> TemplatePreset | None:
    """The preset a flattened section (one part, `flatten_section`) renders: the one its
    part names, when the template declares it and the pre-planning gate (`admission`,
    when it ran) did not leave it out; otherwise the template's effective variant (the
    base without a gate result), with a warning when the part named a preset.

    An undeclared id is not turned into an energy preset: intensity plays on the dimmer
    (`intensity.shape_section`), never through a preset.
    """
    template_id = template_doc.template.template_id
    declared = {preset.preset_id: preset for preset in template_doc.presets}
    fallback = None if admission is None else admission.effective_preset.get(template_id)
    (part,) = section.parts
    if not part.preset_id:
        return None if fallback is None else declared[fallback]
    reason = next(
        (
            exclusion["reason"]
            for exclusion in (admission.preset_exclusions if admission else ())
            if (exclusion["template_id"], exclusion["preset_id"]) == (template_id, part.preset_id)
        ),
        None,
    )
    if part.preset_id in declared and reason is None:
        return declared[part.preset_id]
    diagnostics.append(
        MHDiagnostic(
            code="unsupported_attribute",
            severity="warning",
            message=(
                f"section {section.section_id!r}: preset {part.preset_id!r} is not "
                + (
                    f"declared by template {template_id!r}"
                    if reason is None
                    else f"admitted for template {template_id!r} on this rig and song ({reason})"
                )
                + (
                    "; the renderer applies no preset"
                    if fallback is None
                    else f"; the renderer applies its effective variant {fallback!r}"
                )
            ),
            section_id=section.section_id,
            action="unchanged",
        )
    )
    return None if fallback is None else declared[fallback]


def _unrendered_intent_message(section: PlanSection) -> str | None:
    """What of the section's song intent the renderer does not render yet, split into
    what the renderer before the cutover rendered (a regression) and what no renderer
    has rendered yet; None for a section that sets none of it. Its colour and gobo
    (`song_intent.resolve_section_look`), its intensity (`intensity.shape_section`), its
    events and their lyric cues (`events`) render, so they are never listed."""
    regressed: list[str] = []
    new: list[str] = []
    if section.entry is not None:
        regressed.append("entry transition")
    for name, is_set in (
        ("exit transition", section.exit is not None),
        ("motif", section.motif_id is not None),
        ("variation", section.variation.value != "NONE"),
        ("density", section.density.value != "BALANCED"),
        ("modifiers", any(part.modifiers for part in section.parts)),
    ):
        if is_set:
            new.append(name)
    if not regressed and not new:
        return None
    said = []
    if regressed:
        said.append(
            f"{', '.join(regressed)}: a known regression (the renderer before the "
            "single-renderer cutover rendered them)"
        )
    if new:
        said.append(f"{', '.join(new)}: not rendered by any renderer yet")
    return (
        f"section {section.section_id!r}: the planner's song intent is not rendered yet; "
        + "; ".join(said)
        + ". Both are being fixed under "
        "changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md; for these the "
        "template renders as authored"
    )


class RenderRefusedError(ValueError):
    """The transaction pass refused a render; nothing was delivered."""

    def __init__(self, diagnostics: Sequence[TransitionDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        errors = [diagnostic for diagnostic in diagnostics if diagnostic.status == "error"]
        super().__init__(
            "Moving-head render refused: "
            + "; ".join(
                f"{diagnostic.fixture_id} cue at {diagnostic.cue_ms} ms: "
                f"{diagnostic.code}: {diagnostic.reason}"
                for diagnostic in errors
            )
        )


def _sha256(model: BaseModel) -> str:
    return _json_sha256(model.model_dump(mode="json"))


def _json_sha256(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
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
        admission: TemplateAdmission | None = None,
        dark_spans: Sequence[tuple[int, int]] = (),
        palettes: Mapping[str, SectionPalette] | None = None,
        focal_roles: Mapping[str, str] | None = None,
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
            locks: Frames the render must leave as the cues alone make them.
            layout_models: The xLights layout's models, when known. The render then
                refuses any fixture whose model is not a single-color DMX model with
                enough channels (`check_models`); without them the check is
                recorded as not performed.
            layout_sha256: Content hash of the layout file, recorded in the render
                trace as evidence. Not render identity: the check passes or refuses
                and never changes a byte.
            admission: The pre-planning gate's result, when it ran. The render plays each template's effective variant in a section naming no
                preset, or a preset the gate did not admit or the template does not
                declare (without a result, the base), and its trace records the gate's
                exclusions as `admission_exclusions` and `admission_preset_exclusions`
                and each effective variant other than the base as
                `admission_effective_presets`, when there are any. Not render identity.
            dark_spans: `[start_ms, end_ms)` spans the render holds every
                fixture dark over (the combined show's coordination windows that rest
                the moving heads), each snapped outward to the frame grid, lengthened
                to the time a closed shutter needs to take effect and merged where
                they would leave a head lit for less than two frames or less than its
                shutter needs to open, the rig's slowest profile deciding
                (`_span_limits`). The cues they cover play on along their authored
                paths, commanded dark there (`_dark_over_spans`), before section entry
                and repositioning are planned. Render identity when given, as
                lengthened and merged; the trace records them so as `dark_spans`.
            palettes: Each song section's macro palette (`song_intent.section_palettes`),
                by section id. A section whose colour is a palette role takes the stop the
                role names (`song_intent.requested_color`); without one, the fixed role
                table's colour. Render identity for the sections that resolve one
                (`rendered_palettes`); the trace records them as `palettes`.
            focal_roles: The moving heads' macro focal role (LEAD, SUPPORT, REST) in each
                song section, by section id (`twinklr show` only): it adjusts the
                section's effective intensity (`intensity.effective_intensity`). Render
                identity for the sections it adjusts (`rendered_focal_roles`); the trace
                records those as `focal_roles`.

        Raises:
            UnsupportedRenderModeError: The renderer cannot render this rig (see
                `preflight_render_policy`).
        """
        preflight_render_policy(job_config, fixture_group)

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
        self.admission = admission
        shortest_dark_ms, shortest_lit_ms = _span_limits(fixture_group)
        self.dark_spans = (
            _snap_dark_spans(
                dark_spans, shortest_dark_ms=shortest_dark_ms, shortest_lit_ms=shortest_lit_ms
            )
            if dark_spans
            else ()
        )
        self._shortest_lit_ms = shortest_lit_ms
        self.palettes = dict(palettes or {})
        self.focal_roles = dict(focal_roles or {})
        self.artifacts: DeliveryArtifacts | None = None
        """Set by `render()` when `output_path` is given."""
        self.sequence: XSequence | None = None
        """Set by `render()` when `output_path` is given: the sequence its
        `.xsq` is written from, which live injection reads (`live_effects_from_sequence`)."""
        self.frames: tuple[EncodedFixtureFrame, ...] = ()
        """Set by `render()`: every fixture's encoded frames, rig order."""
        self.runs: tuple[FrameRun, ...] = ()
        """Set by `render()`: the frames merged into constant DMX runs."""
        self.requests: tuple[EmissionRequest, ...] = ()
        """Set by `render()`: one DMX effect request per run."""
        self.render_record: dict[str, Any] | None = None
        """Set by `render()`: the identity and evidence the trace carries."""
        self.unplayable_warning: str | None = None
        """Set by a `render()` that kept cues dark under `on_unplayable`:
        the one warning it logged, with the counts."""

        # Create rig profile from fixture group
        self.rig_profile = rig_profile_from_fixture_group(fixture_group)

    def fingerprint(self) -> str:
        """Functional identity of this render; the output path is not part of it.

        Hashes the renderer and encoder revisions, the musical phase map built from the
        detected grid, any render locks and, for each section that renders a preset
        other than the one it names (`_section_preset`: the effective variant, or
        none), the preset it renders, and its dark spans as snapped, when there are any.
        """
        substitutions: list[tuple[str, str | None]] = []
        for section in self.iterate_plan_sections(self.choreography_plan):
            (part,) = section.parts
            preset = _section_preset(section, get_template(part.template_id), [], self.admission)
            rendered = None if preset is None else preset.preset_id
            if rendered != (part.preset_id or None):
                substitutions.append((section.section_id, rendered))
        return render_fingerprint(
            palettes=self.rendered_palettes(),
            plan=self.choreography_plan,
            beat_grid=self.beat_grid,
            fixtures=self.fixture_group,
            templates=self._plan_templates(),
            policy=self.job_config.moving_heads,
            backend_id=BACKEND_ID,
            renderer_revision=f"renderer.{RENDERER_REVISION}+encoder.{ENCODER_VERSION}",
            phase_map=build_musical_phase_map(self.beat_grid),
            locks=self.locks,
            preset_substitutions=substitutions,
            dark_spans=self.dark_spans,
            focal_roles=self.rendered_focal_roles(),
        )

    def rendered_palettes(self) -> dict[str, SectionPalette]:
        """The macro palette each plan section whose colour, or a colour event's, is a
        palette role resolves it through (of `palettes`), by section id: render identity,
        since the stop it takes decides the wheel state."""
        return {
            section.section_id: self.palettes[section.section_id]
            for section in self.choreography_plan.sections
            if section.section_id in self.palettes
            and any(
                color is not None and color.value.startswith("PALETTE_")
                for color in (section.color, *(event.color for event in section.events))
            )
        }

    def rendered_focal_roles(self) -> dict[str, str]:
        """The focal role of each plan section whose intensity it changes (of
        `focal_roles`), by section id: render identity. A role that leaves the planner's
        intensity as it is (SUPPORT; REST on an identity level) changes no byte."""
        return {
            section.section_id: self.focal_roles[section.section_id]
            for section in self.choreography_plan.sections
            if section.section_id in self.focal_roles
            and effective_intensity(
                None if section.intensity is None else section.intensity.value,
                self.focal_roles[section.section_id],
            )
            != (None if section.intensity is None else section.intensity.value)
        }

    def checkpoint_record(self, *, live_layout: bool = False) -> dict[str, Any]:
        """What `twinklr eval-report` re-renders this render from, and what names
        the input that differs when its re-render is another render; written under the
        plan checkpoint's `render` key (`record_render`), for every command's render.

        Its keys: `render_fingerprint`; the moving-head `policy`; the `beat_grid` it
        rendered against; the gate's `admission` (null when none ran); `dark_spans`, as
        snapped and merged, only when there are any; and `inputs`, the trace's input
        hashes (each fixture's profile and model name, each template, the beat grid, the
        renderer and encoder revisions, the dark spans when there are any) with the
        rendered rig's identity (`rig`): the hash of the fixture group as the fingerprint
        hashes it, the hash of each of its top-level fields, and whether it is the rig
        as reconciled with the live xLights layout (`live_layout`).

        Args:
            live_layout: The render's rig is the fixture config reconciled with the live
                xLights layout (`inject`, `regenerate`).

        Raises:
            ValueError: If this pipeline has not rendered.
        """
        record = self.render_record
        if record is None:
            raise ValueError("only a rendered render has a checkpoint record")
        rig = self.fixture_group.model_dump(mode="json")
        inputs: dict[str, Any] = {
            key: record[key]
            for key in (
                "fixtures",
                "template_sha256",
                "beat_grid_sha256",
                "renderer_revision",
                "encoder_version",
            )
        }
        inputs["rig"] = {
            "sha256": _json_sha256(rig),
            "fields": {name: _json_sha256(value) for name, value in rig.items()},
            "live_layout": live_layout,
        }
        checkpoint: dict[str, Any] = {
            "render_fingerprint": record["render_fingerprint"],
            "policy": self.job_config.moving_heads.model_dump(mode="json"),
            "beat_grid": self.beat_grid.model_dump(mode="json"),
            "admission": None if self.admission is None else self.admission.record(),
            "inputs": inputs,
        }
        if "dark_spans" in record:
            # Left out when there are none, as in the trace. The re-render takes the
            # spans from `dark_spans`; `inputs` keeps the run's, to name them on a
            # mismatch.
            checkpoint["dark_spans"] = record["dark_spans"]
            inputs["dark_spans"] = record["dark_spans"]
        if "palettes" in record:
            # As the dark spans: the re-render resolves palette roles through them.
            checkpoint["palettes"] = record["palettes"]
            inputs["palettes"] = record["palettes"]
        if "focal_roles" in record:
            # As the palettes: the re-render adjusts each section's intensity by them.
            checkpoint["focal_roles"] = record["focal_roles"]
            inputs["focal_roles"] = record["focal_roles"]
        return checkpoint

    def render(self) -> list[FixtureSegment]:
        """Render the choreography plan on the frame grid and, with an output path,
        deliver it.

        Each section's template compiles on the frame grid against the musical phase
        of the detected grid, within its covered span (`cue_limits`); the
        transaction pass authors every fixture of the rig over the whole sequence,
        holding it dark outside every cue and so outside the covered span; each
        fixture's complete frames are encoded in rig order and merged into constant DMX
        runs. Each section's cues are first commanded dark over the dark spans, on
        their authored paths (`_dark_over_spans`). Any refusal raises before
        anything is written,
        and the delivery itself is published only once its size fits the budgets.

        Returns:
            The planned segments: the cues with their transactions and parks.

        Raises:
            RenderRefusedError: If the transaction pass reports an error.
            CompileError, PhysicalChannelError, OutputError,
                ValueError: For a step, value, model or output the renderer refuses.
        """
        logger.debug("Starting plan rendering...")
        policy = self.job_config.moving_heads
        topology = rig_topology(self.fixture_group)
        phase_map = build_musical_phase_map(self.beat_grid)
        duration_ms = int(self.beat_grid.duration_ms)
        start_limit, end_limit = cue_limits(phase_map, duration_ms)
        times = frame_times(duration_ms)
        fixtures = self.fixture_group.expand_fixtures()
        profiles = {}
        for fixture in fixtures:
            profile = fixture.config.physical_profile
            assert profile is not None  # required by preflight_render_policy
            profiles[fixture.fixture_id] = profile
        targets = {fixture.fixture_id: fixture.xlights_model_name for fixture in fixtures}
        if self.layout_models is not None:
            check_models(fixtures, self.layout_models)
        else:
            logger.warning(
                "moving heads: the xLights model check was not performed (no layout given); "
                "each fixture's model must be a single-color DMX model of at least its "
                "profile's footprint, which nothing has verified"
            )

        cues: list[FixtureSegment] = []
        kept: dict[str, list[HeadFollow]] = defaultdict(list)
        dropped: list[dict[str, Any]] = []
        unplayable: list[dict[str, str | int]] | None = (
            [] if policy.on_unplayable == "dark" else None
        )
        basic_checked: set[tuple[str, str | None]] = set()
        in_window: list[dict[str, Any]] = []
        entry_windows: list[dict[str, Any]] = []
        time_markers: list[TimeMarker] = []
        diagnostics: list[MHDiagnostic] = []
        fixture_contexts = self._build_fixture_contexts()
        heads = [HeadWheels.from_profile(f, p) for f, p in profiles.items()]
        held_by_fixture: dict[str, dict[ChannelName, str]] = {}
        """Per fixture, the wheel states song intent held in the section of its last cue."""
        section_looks: list[dict[str, Any]] = []
        shaping: list[tuple[str, str | None, float, int, dict[str, Any]]] = []
        """Per section a shaped intensity plays in: its id, level, bounds, trace entry."""
        plan_sections = {s.section_id: s for s in self.choreography_plan.sections}
        timed: dict[str, SectionEvents] = {}
        """Per plan section, its events on the grid (`events.section_events`)."""
        hitting: list[tuple[str, tuple[int, int], SectionEvents, dict[str, Any]]] = []
        """Per part with hits: its id, frame window, its plan section's events, trace entry."""
        event_records: dict[tuple[str, int], dict[str, Any]] = {}
        """Per plan section and event index, the event's trace entry."""
        for section in self.iterate_plan_sections(self.choreography_plan):
            (part,) = section.parts
            try:
                template_doc = get_template(part.template_id)
            except Exception as e:
                raise ValueError(f"Template not found: {part.template_id}") from e
            preset = _section_preset(section, template_doc, diagnostics, self.admission)
            context = TemplateCompileContext(
                section_id=section.section_id,
                template_id=template_doc.template.template_id,
                preset_id=preset.preset_id if preset else None,
                fixtures=fixture_contexts,
                beat_grid=self.beat_grid,
                start_bar=section.start_bar,
                duration_bars=section.end_bar - section.start_bar + 1,
                presets=self.fixture_group.presets,
                topology=topology,
                fixture_group_id=self.fixture_group.group_id,
            )
            time_markers.append(
                TimeMarker(
                    name=section.section_id, time_ms=context.start_ms, end_time_ms=context.end_ms
                )
            )
            message = _unrendered_intent_message(section)
            if message is not None:
                diagnostics.append(
                    MHDiagnostic(
                        code="unsupported_attribute",
                        severity="warning",
                        message=message,
                        section_id=section.section_id,
                        action="unchanged",
                    )
                )
            template_heads = (
                heads
                if self.admission is None
                else list(
                    self.admission.offer.for_templates({template_doc.template.template_id}).heads
                )
            )
            palette = section_palette_for(self.palettes, section.section_id)
            look = resolve_section_look(section, template_heads, palette)
            held = look.states
            base_id = section.section_id.split("|")[0]
            events = timed.setdefault(
                base_id, section_events(plan_sections[base_id], self.beat_grid)
            )
            window = (
                quantize_cue(context.start_ms).actual_ms,
                quantize_cue(context.end_ms).actual_ms,
            )
            # A colour or gobo an earlier part's event left the heads holding: this part
            # holds it from its start, as a section colour.
            for fixture_id, states in carried_states(
                events, window[0], template_heads, palette
            ).items():
                held = {**held, fixture_id: {**held.get(fixture_id, {}), **states}}
            part_events = [e for e in events.events if window[0] <= e.frame_ms < window[1]]
            plays_events = bool(
                [
                    span
                    for span in events.shutter_spans()
                    if span[1] < window[1] and span[2] > window[0]
                ]
                or [e for e in part_events if e.action in WHEEL_ACTIONS]
            )
            played_box: list[EventsPlayed] = [EventsPlayed()]
            authored_states: dict[str, dict[ChannelName, str]] = {}
            """The held states of the authored compile `_unplayable_holds` compares with."""
            refused = 0 if unplayable is None else len(unplayable)
            compiled_steps: list[dict[str, str | int]] = []
            asked = None if section.intensity is None else section.intensity.value
            focal_role = self.focal_roles.get(section.section_id.split("|")[0])
            level = effective_intensity(asked, focal_role)
            if level == asked:
                focal_role = None  # it changes nothing here

            def compile_section(
                held_states: Mapping[str, Mapping[ChannelName, str]],
                template_doc: TemplateDoc = template_doc,
                context: TemplateCompileContext = context,
                preset: TemplatePreset | None = preset,
                refused: int = refused,
                compiled_steps: list[dict[str, str | int]] = compiled_steps,
                events: SectionEvents = events,
                window: tuple[int, int] = window,
                plays_events: bool = plays_events,
                played_box: list[EventsPlayed] = played_box,
                template_heads: list[HeadWheels] = template_heads,
                palette: SectionPalette | None = palette,
                authored_states: dict[str, dict[ChannelName, str]] = authored_states,
            ) -> list[FixtureSegment]:
                if unplayable is not None:
                    del unplayable[refused:]  # a recompile records its refusals again
                result = compile_template(
                    template_doc.template,
                    context,
                    preset,
                    phase_map=phase_map,
                    start_limit_ms=start_limit,
                    end_limit_ms=end_limit,
                    unplayable=unplayable,
                    held_states=held_states,
                )
                compiled_steps[:] = result.dropped_steps
                spanned = _dark_over_spans(
                    result.segments,
                    self.dark_spans,
                    profiles,
                    shortest_lit_ms=self._shortest_lit_ms,
                )
                if not plays_events:
                    return spanned
                # The plan's closed, strobe, pulse, colour and gobo events, after the
                # template, the section's held states and the show's rests.
                played, events_played = apply_section_events(
                    spanned,
                    events,
                    window=window,
                    profiles=profiles,
                    heads=template_heads,
                    palette=palette,
                    phase_map=phase_map,
                    beat_grid=self.beat_grid,
                    darken=lambda cues, spans: _dark_over_spans(
                        cues, spans, profiles, shortest_lit_ms=self._shortest_lit_ms
                    ),
                    dip_span=_dip_span,
                    dark_runs=_commanded_dark_runs,
                    dark_windows=_dark_windows,
                    gap_ok=lambda head_id, head_cues, gap_index: entry_feasible(
                        head_cues[gap_index],
                        profiles[head_id],
                        after=follow_cues(
                            head_cues[:gap_index], profiles[head_id], frame_ms=EFFECT_GRID_MS
                        )[-1],
                        initial=policy.initial_states.get(head_id),
                        locks=self.locks,
                        frame_ms=EFFECT_GRID_MS,
                    ),
                )
                if held_states is not authored_states:
                    played_box[0] = events_played  # what the section plays, not the probe
                return played

            section_cues = compile_section(held)
            key = (template_doc.template.template_id, context.preset_id)
            if unplayable is not None and len(unplayable) > refused and key not in basic_checked:
                # Only a refusal this placement adds is left dark: one the template shows
                # from bar 1 over the song, where the gate places it, still raises.
                basic_checked.add(key)
                compile_template(
                    template_doc.template,
                    context.model_copy(
                        update={
                            "section_id": "render_preflight",
                            "start_bar": 1,
                            "duration_bars": max(
                                1,
                                sum(
                                    1
                                    for start in self.beat_grid.bar_boundaries
                                    if start < self.beat_grid.duration_ms
                                ),
                            ),
                        }
                    ),
                    preset,
                    phase_map=phase_map,
                    start_limit_ms=start_limit,
                    end_limit_ms=end_limit,
                )
            outcomes: dict[str, dict[str, dict[str, Any]]] = {"color": {}, "gobo": {}}
            """Per wheel and head, how it departs from playing the section's state from its
            start: `deferred`, `kept_previous` or `kept_authored_unplayable`."""
            # A held state an overlay mask cannot turn to and back in time: that head
            # plays the authored state in this section instead (never a refusal).
            if template_doc.template.overlays and held:
                fallback = _unplayable_holds(
                    section_cues,
                    compile_section(authored_states),
                    held,
                    {overlay.channel for overlay in template_doc.template.overlays},
                    profiles,
                    policy.initial_states,
                    policy.reposition_fallback,
                )
                for fixture_id, channels in fallback.items():
                    for channel in channels:
                        outcomes[channel.value][fixture_id] = {
                            "kept_authored_unplayable": "its overlay mask is too short to turn "
                            f"to {held[fixture_id][channel]} and back"
                        }
                if fallback:
                    held = {
                        f: {c: st for c, st in by.items() if c not in fallback.get(f, ())}
                        for f, by in held.items()
                    }
                    section_cues = compile_section(held)
            # A wheel change the song intent makes at a boundary the heads play lit
            # through: a dark dip before it, else a turn in the section's first dark window
            # long enough, else the previous state kept (`_boundary_change`).
            boundaries: list[dict[str, Any]] = []
            dips: dict[str, tuple[FixtureSegment, HeadFollow]] = {}
            deferrals: dict[str, _Deferral] = {}
            keep: dict[str, dict[ChannelName, str]] = {}
            retries: dict[str, tuple[_BoundaryChange, int]] = {}
            half_beat = _half_beat_before(self.beat_grid, context.start_ms)
            for fixture_id in sorted({cue.fixture_id for cue in section_cues}):
                change = _boundary_change(
                    sorted(
                        (cue for cue in section_cues if cue.fixture_id == fixture_id),
                        key=lambda cue: cue.t0_ms,
                    ),
                    kept[fixture_id],
                    profiles[fixture_id],
                    policy.initial_states.get(fixture_id),
                    self.locks,
                    policy.reposition_fallback,
                    intent_channels={
                        *held.get(fixture_id, {}),
                        *held_by_fixture.get(fixture_id, {}),
                        *(
                            WHEEL_ACTIONS[e.action]
                            for e in part_events
                            if e.action in WHEEL_ACTIONS
                        ),
                    },
                    half_beat_ms=half_beat,
                    shortest_lit_ms=self._shortest_lit_ms,
                    section_end_ms=context.end_ms,
                )
                if change is None:
                    continue
                boundaries.append({"fixture_id": fixture_id, **change.record})
                if change.dip is not None:
                    dips[fixture_id] = change.dip
                elif change.deferred is not None:
                    deferrals[fixture_id] = change.deferred
                    for channel, (_, new) in change.deferred.changes.items():
                        outcomes[channel.value][fixture_id] = {
                            "deferred": {"state": new, "from_ms": change.deferred.turn_ms}
                        }
                else:
                    keep[fixture_id] = change.kept
                    retries[fixture_id] = (change, len(boundaries) - 1)
                    for channel, state in change.kept.items():
                        outcomes[channel.value][fixture_id] = {"kept_previous": state}
            if keep:
                held = {
                    fixture_id: {**held.get(fixture_id, {}), **keep.get(fixture_id, {})}
                    for fixture_id in {*held, *keep}
                }
                section_cues = compile_section(held)
                # Held at the old states, an overlay may now mask a turn to the new ones.
                for fixture_id, (change, at) in retries.items():
                    if change.retry is None:
                        continue
                    changes, lead, darkness = change.retry
                    deferral = _defer(
                        sorted(
                            (c for c in section_cues if c.fixture_id == fixture_id),
                            key=lambda c: c.t0_ms,
                        ),
                        changes,
                        profiles[fixture_id],
                        kept[fixture_id][-1],
                        policy.initial_states.get(fixture_id),
                        self.locks,
                        lead=lead,
                        darkness=darkness,
                    )
                    if deferral is None:
                        continue
                    deferrals[fixture_id] = deferral
                    boundary = boundaries[at]
                    reason = boundary.pop("kept_previous")["reason"].split(", and the")[0]
                    boundary["deferred"] = {
                        "turn_ms": deferral.turn_ms,
                        "waited_ms": deferral.turn_ms - boundary["boundary_ms"],
                        "late": is_late(
                            deferral.turn_ms - frames_ms(darkness),
                            boundary["boundary_ms"],
                            context.end_ms,
                        ),
                        "reason": reason,
                    }
                    for channel, (_, new) in changes.items():
                        outcomes[channel.value][fixture_id] = {
                            "deferred": {"state": new, "from_ms": deferral.turn_ms}
                        }
            if deferrals:
                deferred_cues = []
                for fixture_id in sorted({cue.fixture_id for cue in section_cues}):
                    own = sorted(
                        (cue for cue in section_cues if cue.fixture_id == fixture_id),
                        key=lambda cue: cue.t0_ms,
                    )
                    deferral = deferrals.get(fixture_id)
                    deferred_cues += (
                        own if deferral is None else deferral.apply(own, profiles[fixture_id])
                    )
                section_cues = deferred_cues
            for fixture_id, (dipped, follow) in dips.items():
                replaced = kept[fixture_id][-1].segment
                cues[next(i for i, cue in enumerate(cues) if cue is replaced)] = dipped
                kept[fixture_id][-1] = follow
            for fixture_id in {cue.fixture_id for cue in section_cues}:
                held_by_fixture[fixture_id] = {
                    **held.get(fixture_id, {}),
                    **played_box[0].final.get(fixture_id, {}),
                }
            record = _played_record(look.record(), outcomes)
            if boundaries:
                record["boundaries"] = boundaries
            first_part = section.start_bar == plan_sections[base_id].start_bar
            if part_events or (events.unplaced and first_part):
                entries = [played_box[0].records.get(e.index, e.record()) for e in part_events]
                for event, event_entry in zip(part_events, entries, strict=True):
                    event_records[(base_id, event.index)] = event_entry
                # An event beyond the beat grid is recorded on the section's first part.
                record["events"] = entries + (list(events.unplaced) if first_part else [])
                if any(e.action == "hit" for e in part_events):
                    hitting.append((section.section_id, window, events, record))
            if asked is not None or focal_role is not None or shape_for(level) is not None:
                record["intensity"] = {
                    "asked": asked,
                    **({} if focal_role is None else {"focal_role": focal_role}),
                    "effective": level,
                    "shape": None,
                }
                if shape_for(level) is not None:
                    # Shaped once every darkness of the section is placed (below).
                    shaping.append(
                        (
                            section.section_id,
                            level,
                            self.beat_grid.get_bar_start_ms(context.start_bar - 1),
                            context.end_ms,
                            record,
                        )
                    )
            if len(record) > 1:
                section_looks.append(record)
            message = _unplayed_message(section.section_id, outcomes)
            if message is not None:
                diagnostics.append(
                    MHDiagnostic(
                        code="unsupported_attribute",
                        severity="warning",
                        message=message,
                        section_id=section.section_id,
                        action="unchanged",
                    )
                )
            dropped.extend(compiled_steps)
            entered, inside, windows = _enter_section(
                section_cues,
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
                    "moving heads: section %r (%s-%s ms) is shorter than its entry window, "
                    "which ends at %s ms; it renders dark",
                    section.section_id,
                    context.start_ms,
                    context.end_ms,
                    window_end,
                )
        if dropped:
            logger.warning(
                "moving heads: %d cue(s) start outside the frames %s-%s ms that the covered "
                "phase span and the song allow and are dropped (held dark); the trace's "
                "dropped_cues lists them",
                len(dropped),
                start_limit,
                end_limit,
            )
        if in_window:
            logger.warning(
                "moving heads: %d cue(s) lie inside their section's entry window and are "
                "dropped (held dark); the trace's dropped_cues and entry_windows list them",
                len(in_window),
            )
        if self.dark_spans:
            logger.info(
                "moving heads: every fixture is held dark over %d span(s), its cues playing "
                "on there along their authored paths; the trace's dark_spans lists them",
                len(self.dark_spans),
            )

        for section_id, level, start_ms, end_ms, record in shaping:
            # Intensity plays on the cues as they will play: after the dark spans, the
            # boundary dips, deferred turns and entry windows of every section, so a head
            # revealed after any of them comes in on an accent.
            base, _, segment = section_id.partition("|")
            index = [
                i
                for i, cue in enumerate(cues)
                if cue.section_id == base and cue.segment_id == (segment or "A")
            ]
            shaped, record["intensity"]["shape"] = shape_section(
                [cues[i] for i in index],
                level,
                profiles=profiles,
                phase_map=phase_map,
                origin_ms=start_ms,
                end_ms=end_ms,
                beats_per_bar=self.beat_grid.beats_per_bar,
            )
            for i, cue in zip(index, shaped, strict=True):
                cues[i] = cue
            if record["intensity"]["shape"].get("unavailable"):
                diagnostics.append(
                    MHDiagnostic(
                        code="unsupported_attribute",
                        severity="warning",
                        message=(
                            f"section {section_id!r}: intensity {level} is not shaped on "
                            f"{', '.join(record['intensity']['shape']['unavailable'])}, which "
                            "have no dimmer axis; they play the template's own level"
                        ),
                        section_id=section_id,
                        action="unchanged",
                    )
                )

        for section_id, window, events, record in hitting:
            # Hits play on the level the section plays, after intensity: one accent where
            # an intensity accent lands on the hit's beat, a rise above a level below full.
            base, _, segment = section_id.partition("|")
            index = [
                i
                for i, cue in enumerate(cues)
                if cue.section_id == base and cue.segment_id == (segment or "A")
            ]
            hits = [e for e in events.hits() if window[0] <= e.frame_ms < window[1]]
            struck, hit_outcomes = apply_hits(
                [cues[i] for i in index],
                hits,
                window=window,
                profiles=profiles,
                phase_map=phase_map,
                beat_grid=self.beat_grid,
                dark_spans=self.dark_spans,
            )
            for i, cue in zip(index, struck, strict=True):
                cues[i] = cue
            for event_entry in record["events"]:
                for event in hits:
                    if event_entry is event_records.get((base, event.index)):
                        event_entry.update(hit_outcomes.get(event.index, {}))

        lyric_cues: list[dict[str, Any]] = []
        """Per lyric moment cue a plan section references, what played it, or why not."""
        for plan_section in self.choreography_plan.sections:
            for cue_id in plan_section.moment_cues:
                bound = [
                    (i, e) for i, e in enumerate(plan_section.events) if e.moment_cue_id == cue_id
                ]
                cue_entry: dict[str, Any] = {
                    "cue_id": cue_id,
                    "section_id": plan_section.section_id,
                }
                if not bound:
                    cue_entry["not_played"] = "no event lands on it (the planner was told)"
                else:
                    cue_entry["emphasis"] = bound[0][1].cue_emphasis
                    cue_entry["events"] = [
                        cue_summary(event_records[(plan_section.section_id, i)])
                        if (plan_section.section_id, i) in event_records
                        else {
                            "action": e.action.value,
                            "bar": e.bar,
                            "beat": e.beat,
                            "played": {},
                            "not_played": "its beat lies beyond the detected beat grid",
                        }
                        for i, e in bound
                    ]
                lyric_cues.append(cue_entry)
        for section_look in section_looks:
            message = events_message(section_look["section_id"], section_look.get("events", []))
            if message is not None:
                diagnostics.append(
                    MHDiagnostic(
                        code="unsupported_attribute",
                        severity="warning",
                        message=message,
                        section_id=section_look["section_id"],
                        action="unchanged",
                    )
                )

        result = plan_prepositions(
            cues,
            profiles,
            initial_states=policy.initial_states,
            locks=self.locks,
            frame_ms=EFFECT_GRID_MS,
            sequence_end_ms=len(times) * EFFECT_GRID_MS,
            failure_mode=policy.reposition_fallback,
            on_unplayable=policy.on_unplayable,
        )
        if result.has_errors:
            raise RenderRefusedError(result.diagnostics)
        unplayable = [*(unplayable or ()), *result.unplayable]
        unplayable_totals: dict[str, dict[str, int]] = {}
        for record in unplayable:
            total = unplayable_totals.setdefault(str(record["code"]), {"cues": 0, "frames": 0})
            total["cues"] += 1
            total["frames"] += int(record["frames"])
        if unplayable:
            self.unplayable_warning = (
                f"moving heads: {len(unplayable)} cue(s) placed where they cannot play honestly "
                f"are kept dark ({sum(t['frames'] for t in unplayable_totals.values())} "
                "frame(s); "
                + ", ".join(
                    f"{code}: {total['cues']}" for code, total in sorted(unplayable_totals.items())
                )
                + "); the trace's dropped_cues lists them"
            )
            logger.warning(self.unplayable_warning)

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
        requests = run_requests(runs, result.segments, targets)

        self.frames = tuple(frames)
        self.runs = runs
        self.requests = requests
        self.render_record = {
            "render_fingerprint": self.fingerprint(),
            "renderer_revision": RENDERER_REVISION,
            "encoder_version": ENCODER_VERSION,
            "backend_id": BACKEND_ID,
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
                    # What the profile left out and its loading filled; left out when
                    # nothing was, so a fully stated rig's trace keeps its keys.
                    **(
                        {"defaulted": list(profiles[fixture.fixture_id].defaulted)}
                        if profiles[fixture.fixture_id].defaulted
                        else {}
                    ),
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
            ]
            + unplayable,
            "unplayable_totals": unplayable_totals,
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
        if self.dark_spans:
            # Left out when there are none, so earlier traces keep their keys.
            self.render_record["dark_spans"] = [list(span) for span in self.dark_spans]
        palettes = self.rendered_palettes()
        if palettes:
            # Left out when no section resolves a palette role through one.
            self.render_record["palettes"] = {
                section_id: palette.model_dump(mode="json")
                for section_id, palette in palettes.items()
            }
        focal_roles = self.rendered_focal_roles()
        if focal_roles:
            # Left out when no focal role changes a section's intensity (`twinklr run`).
            self.render_record["focal_roles"] = dict(sorted(focal_roles.items()))
        if section_looks:
            # What each section's colour, gobo, intensity and events play on each head,
            # and the wheel changes they make at boundaries; left out when no section
            # sets any.
            self.render_record["section_looks"] = section_looks
        if lyric_cues:
            # What each lyric moment cue the plan references played, or why not; left out
            # when the plan references none.
            self.render_record["lyric_cues"] = lyric_cues
        if self.choreography_plan.repairs:
            # What repair changed in the planner's response; left out when nothing was.
            self.render_record["plan_repairs"] = [
                repair.model_dump(mode="json") for repair in self.choreography_plan.repairs
            ]
        if self.admission is not None:
            # Each key is left out when empty (nothing excluded, every admitted template
            # playing its base), so earlier traces keep their keys.
            if self.admission.exclusions:
                self.render_record["admission_exclusions"] = [
                    dict(exclusion) for exclusion in self.admission.exclusions
                ]
            if self.admission.preset_exclusions:
                self.render_record["admission_preset_exclusions"] = [
                    dict(exclusion) for exclusion in self.admission.preset_exclusions
                ]
            varied = {
                template_id: preset_id
                for template_id, preset_id in self.admission.effective_preset.items()
                if preset_id is not None
            }
            if varied:
                self.render_record["admission_effective_presets"] = varied
        omitted = [
            {
                "section_id": cue.section_id,
                "step_id": cue.step_id,
                "fixture_id": cue.fixture_id,
                "t0_ms": cue.t0_ms,
                "attribute": cue.metadata["omitted_optional"],
                "alternative": f"omit_optional_{cue.metadata['omitted_optional']}",
            }
            for cue in cues
            if "omitted_optional" in cue.metadata
        ]
        if omitted:
            # Each cue played without an optional attribute its fixture lacks, by the
            # step's declared alternative; left out when none was, like the exclusions.
            self.render_record["omitted_optional"] = omitted
        if self.output_path:
            xsq = build_sequence(
                requests,
                time_markers,
                media_file=self.media_file,
                duration_ms=duration_ms,
                song=self.song,
                artist=self.artist,
                timeline_tracks=self.timeline_tracks,
            )
            self.artifacts = export_delivery(
                xsq, runs, output_path=self.output_path, policy=policy, render=self.render_record
            )
            self.sequence = xsq
        return list(result.segments)

    def _plan_templates(self) -> list[TemplateDoc]:
        """The template documents the plan's sections name, once each.

        Sections may spell a template any way the registry resolves (case, separators,
        display name, alias); documents are deduplicated on the canonical id.
        """
        docs: dict[str, TemplateDoc] = {}
        for section in self.iterate_plan_sections(self.choreography_plan):
            doc = get_template(section.parts[0].template_id)
            docs.setdefault(doc.template.template_id, doc)
        return [docs[template_id] for template_id in sorted(docs)]

    def iterate_plan_sections(self, plan: ChoreographyPlan) -> Iterator[PlanSection]:
        """Yield the plan's sections as the renderer places them: one per part
        (`flatten_section`).

        Args:
            plan: The choreography plan to iterate over.

        Returns:
            An iterator over the flattened sections, each with exactly one part.
        """
        for section in plan.sections:
            yield from flatten_section(section)

    def _build_fixture_contexts(self) -> list[FixtureContext]:
        """Build fixture contexts from rig profile.

        Delegates to :func:`build_fixture_contexts` in ``fixture_builder``.

        Returns:
            List of FixtureContext objects for all fixtures in the rig.
        """
        return build_fixture_contexts(self.rig_profile, self.fixture_group)
