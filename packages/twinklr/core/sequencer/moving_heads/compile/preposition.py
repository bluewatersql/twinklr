"""Feasible dark reposition transactions between moving-head cues.

`plan_prepositions` authors every fixture explicitly over the whole sequence: in the
span before each cue a transaction commands darkness, waits until the fixture is
optically dark, turns changed wheels and lets them settle, moves pan/tilt (and the zoom,
on a profile with a zoom axis) no faster than the configured speed, waits for the head
to arrive and settle, then reveals on the cue's own aligned frame; after the last cue
the fixture parks dark at its last aim. An unauthored channel would return to its
default byte, so nothing is left unauthored: the zoom is held through every gap.

Darkness comes only from the profile's visibility declaration (dimmer at normalized
zero when `dimmer_zero_extinguishes`, or a shutter state listed in
`extinguishing_shutter_states`), after `close_latency_ms` (plus the shutter state's
`settle_ms` when the shutter is the mechanism), or from the run's initial-state
evidence. Default bytes never establish it and an unknown latency never does.

Motion is judged on the encoded DMX words, as the fixture receives them. The head (its
pan, tilt and zoom, the pose axes) follows its commands: a word change at frame time `c`
is reached at
`max(previous arrival, c + latency_ms) + word distance / travel_speed_per_s` and is
settled `settle_ms` later; a wheel settles its new state's `settle_ms` after the change.
That covers motion from every source (a cue's own trajectory, a transaction, the
initial state), so a reveal waits for whatever motion is still under way.

Cues are left as compiled: motion inside a cue is visible by design and was
rate-checked by the compile, and back-to-back cues may continue it one frame step within
the configured speed. Unknown initial state, unknown speed, latency or settle for a
needed change or a reveal, no darkness guarantee, a lock in the way or too little time
is an error diagnostic, and a result with an error carries no segments. A cue may opt
into `preserve_aim` or `drop_accent` (see `plan_prepositions`).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from itertools import pairwise
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from twinklr.core.config.fixtures.capabilities import (
    AxisCapability,
    AxisName,
    FixtureCapabilities,
    InitialFixtureState,
)
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    AXIS_KEYS,
    DISCRETE_KEYS,
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalPoint,
    PhysicalValue,
    RenderLock,
    TransitionCode,
    TransitionDependency,
    TransitionDiagnostic,
    TransitionStatus,
    check_physical_value,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.step import shutter_changes

FailureMode = Literal["error", "preserve_aim", "drop_accent"]
UnplayableMode = Literal["dark", "error"]

FALLBACK_METADATA_KEY = "preposition_fallback"
"""Cue metadata naming the failure mode its effect opts into; the pass mode must match."""

TRANSACTION_METADATA_KEY = "preposition_target"
"""Metadata on an authored segment: the id of the cue it prepares, empty for a park."""

_POSE = (ChannelName.PAN, ChannelName.TILT, ChannelName.ZOOM)
"""The pose axes: each moves only in the dark and settles before a reveal."""
_WHEELS = (ChannelName.COLOR, ChannelName.GOBO)

type _Motion = tuple[Fraction, Fraction] | None
"""A pose axis' (arrival, settled) times for its last command; None when unknown."""


class PrepositionResult(BaseModel):
    """Replacement segments with one diagnostic and one dependency per planned cue.

    Diagnostics also report shutter changes that cannot take effect in time and a
    fixture that cannot be parked. Any error diagnostic aborts emission, and the
    result then carries no segments.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    segments: tuple[FixtureSegment, ...]
    diagnostics: tuple[TransitionDiagnostic, ...]
    dependencies: tuple[TransitionDependency, ...]
    unplayable: tuple[dict[str, str | int], ...] = ()
    """Under `on_unplayable="dark"`, one record per cue kept dark because it could not
    be played: its fixture, section, template, step and frames, and the diagnostic's
    code and reason."""

    @property
    def has_errors(self) -> bool:
        return any(diagnostic.status == "error" for diagnostic in self.diagnostics)


def plan_prepositions(
    segments: Sequence[FixtureSegment],
    capabilities: Mapping[str, FixtureCapabilities],
    *,
    initial_states: Mapping[str, InitialFixtureState],
    locks: Sequence[RenderLock],
    frame_ms: int,
    sequence_end_ms: int,
    failure_mode: FailureMode = "error",
    on_unplayable: UnplayableMode = "error",
    memo: PrepositionMemo | None = None,
) -> PrepositionResult:
    """Author every fixture over `[0, sequence_end_ms)`, transactions before each cue.

    Timing, in whole frames: movement may start once the fixture is optically dark,
    rounded up (no wait when the predecessor was already dark long enough or the
    initial state is dark). Changed wheels are commanded then and settle before pan/tilt
    move, because no profile declares them independent. Both axes then step together
    toward their target words over `max(word distance / travel_speed_per_s)`, rounded
    up, never leaving more distance than the remaining frames can cover. The cue's
    reveal waits until the head, as it follows every command so far, has arrived and
    settled, and every wheel has settled. The cue is the reveal command; its optical
    reveal is reported `open_latency_ms` later.

    Args:
        segments: Every fixture's cues, on the frame grid, each authoring the
            pan, tilt and zoom its profile declares, all ending by `sequence_end_ms`.
        capabilities: Each fixture's profile. A fixture without cues parks
            dark at its initial state over the whole sequence.
        initial_states: Run-supplied time-zero states; a missing fixture is unknown,
            which fails every fixture that has a profile.
        locks: Frames no authored segment may cover; spans snap outward to the grid.
        frame_ms: The effect frame grid; must be `EFFECT_GRID_MS`.
        sequence_end_ms: The end of the last frame, on the frame grid.
        failure_mode: The most this pass may substitute when a reposition needs more
            time than it has or an unknown speed, latency or settle. A cue gets it only
            when its own `metadata[FALLBACK_METADATA_KEY]` names the same mode.
            `preserve_aim` plays the cue at the aim the head holds (pan, tilt and
            zoom held there, everything else as authored); `drop_accent` keeps the cue
            dark at that aim and plans later cues from there. Neither applies to unknown initial
            state, unknown visibility latency, a missing darkness guarantee, an
            unencodable value or a lock.
        on_unplayable: `dark` keeps a cue that still cannot be played after its
            fallback dark, as `drop_accent` does (status `drop_accent`, listed in
            `unplayable`): a cue whose transaction fails for any reason but an unknown
            initial state or a lock, and a cue that a shutter state too short to take
            effect, or a park that cannot follow, lies in. Each fixture is replanned
            with the cues found so far kept dark until nothing more is found; every
            replan keeps at least one more cue dark, so it ends, at worst with every
            cue dark and the fixture parked. `error` reports them as errors.
        memo: For a caller planning the same cue objects several times over (the
            pre-planning gate, once per section entry): where a fixture's planning
            reaches a cue in a state an earlier call in the memo reached it in, with the
            same cue objects after it and the same profile and arguments, the rest of
            that call's plan is reused, since planning from there reads nothing else.
            It holds the cues and profiles it was filled from; the caller keeps it for
            one set of cues and profiles, and drops it after.

    Returns:
        The cues with their transactions and parks, ordered by fixture and time, or no
        segments when any diagnostic is an error.

    Raises:
        ValueError: If `frame_ms` is not the effect grid, `sequence_end_ms` is off the
            grid, a fixture has no profile, or a cue is off the grid, empty, overlaps
            another of its fixture, ends after the sequence or omits a pose axis.
        PhysicalChannelError: If a cue holds a value its profile cannot honor.
    """
    if frame_ms != EFFECT_GRID_MS:
        raise ValueError(f"frame_ms must be the {EFFECT_GRID_MS} ms effect frame grid")
    if sequence_end_ms < 0 or sequence_end_ms % frame_ms:
        raise ValueError(f"sequence_end_ms {sequence_end_ms} is not on the frame grid")
    by_fixture: dict[str, list[FixtureSegment]] = defaultdict(list)
    for segment in segments:
        by_fixture[segment.fixture_id].append(segment)

    planned: list[FixtureSegment] = []
    diagnostics: list[TransitionDiagnostic] = []
    dependencies: list[TransitionDependency] = []
    unplayable: list[dict[str, str | int]] = []
    for fixture_id in sorted(by_fixture.keys() | capabilities.keys()):
        profile = capabilities.get(fixture_id)
        if profile is None:
            raise ValueError(f"fixture {fixture_id!r} has no physical profile")
        planner = _FixturePlanner(
            fixture_id,
            profile,
            initial_states.get(fixture_id),
            locks,
            frame_ms,
            sequence_end_ms,
            failure_mode,
            on_unplayable,
        )
        dark: dict[int, _InfeasibleError] = {}
        recalled = None
        if memo is not None:
            key = (
                fixture_id,
                id(profile),
                tuple(locks),
                frame_ms,
                sequence_end_ms,
                failure_mode,
                on_unplayable,
            )
            # Kept with its plans, the profile keeps its id while the memo lives.
            recalled = memo.setdefault(key, (profile, {}))[1]
        while True:
            out, fixture_diagnostics, fixture_dependencies, kept_dark = planner.plan(
                by_fixture[fixture_id], dark, None if dark else recalled
            )
            errors = [d for d in fixture_diagnostics if d.status == "error"]
            if not errors:
                errors = planner.shutter_timing(out)
                fixture_diagnostics += errors
            found = {} if on_unplayable == "error" else planner.culprits(out, errors)
            if not found.keys() - dark.keys():
                break
            dark |= found
        planned.extend(out)
        diagnostics.extend(sorted(fixture_diagnostics, key=lambda diagnostic: diagnostic.cue_ms))
        dependencies.extend(fixture_dependencies)
        unplayable.extend(kept_dark)

    if any(diagnostic.status == "error" for diagnostic in diagnostics):
        planned = []
    return PrepositionResult(
        segments=tuple(planned),
        diagnostics=tuple(diagnostics),
        dependencies=tuple(dependencies),
        unplayable=tuple(unplayable),
    )


def worst_case_entry_ms(
    profile: FixtureCapabilities,
    *,
    entry_pose: Mapping[ChannelName, tuple[float, float]],
    entry_wheels: Mapping[ChannelName, Collection[str]],
    pose_envelope: Mapping[ChannelName, tuple[float, float]],
    frame_ms: int,
    held_wheels: Mapping[ChannelName, Collection[str]] | None = None,
    residual_ms: Fraction | int | None = None,
) -> int | None:
    """The most time a transaction into a cue may need, from any predecessor in an envelope.

    The cue starts anywhere in `entry_pose` (per pose axis, an inclusive min/max range; a
    single pose is a range with equal ends) with each wheel in one of `entry_wheels`
    (a wheel left out may hold only its default state). The predecessor's commanded
    pose lies anywhere in `pose_envelope`, its shutter in any state and each wheel in
    one of `held_wheels` (any state where that is not given). The sum of the terms
    `plan_prepositions` times, each rounded up to whole frames:

    - darkness: `close_latency_ms`, plus the slowest extinguishing shutter settle when
      only the shutter extinguishes;
    - wheels: the slowest settle of an entry wheel state the predecessor may not already
      hold, and at least one frame;
    - travel between the farthest envelope and entry words at `travel_speed_per_s`;
    - the slowest axis' `latency_ms` plus `settle_ms`;
    - predecessor motion still under way after its last frame: `residual_ms` when the
      caller followed the actual predecessor (`follow_cues`), else once more latency
      plus settle and one word's travel. That suffices for a predecessor cue the
      template compile admits (`follow_lag` finds nothing) entered settled; a wheel
      change inside a cue is covered only by `residual_ms`.

    Returns:
        The bound in ms on the frame grid, or None when a needed term is unknown or the
        profile cannot guarantee darkness from every predecessor state; None is never
        feasible.
    """
    visibility = profile.visibility
    close = visibility.close_latency_ms
    if close is None:
        return None
    dark: int = close
    if not visibility.dimmer_zero_extinguishes:
        # The transaction holds an extinguishing shutter state, or switches to the closed
        # state when the predecessor holds another; it may hold any of them.
        shutter = profile.discrete.get("shutter")
        if shutter is None or shutter.closed_state not in visibility.extinguishing_shutter_states:
            return None
        settles = [shutter.states[s].settle_ms for s in visibility.extinguishing_shutter_states]
        if None in settles:
            return None
        dark += max(s for s in settles if s is not None)

    wheel = frame_ms
    for channel in _WHEELS:
        capability = profile.discrete.get(DISCRETE_KEYS[channel])
        if capability is None:
            continue
        held = None if held_wheels is None else set(held_wheels.get(channel, ()))
        for state in entry_wheels.get(channel, (capability.default_state,)):
            if held == {state}:
                continue  # already selected: no change to settle
            settle = capability.states[state].settle_ms
            if settle is None:
                return None
            wheel = max(wheel, settle)

    travel = follow = predecessor = Fraction(0)
    for channel in _POSE:
        axis = profile.axes.get(AXIS_KEYS[channel])
        if axis is None:
            continue
        speed, latency, settle = axis.travel_speed_per_s, axis.latency_ms, axis.settle_ms
        if speed is None or latency is None or settle is None:
            return None
        word_ms = _word_ms(axis)
        # `dmx_word` is monotonic, so the farthest words are at the range ends.
        entry = [axis.dmx_word(value) for value in entry_pose[channel]]
        envelope = [axis.dmx_word(value) for value in pose_envelope[channel]]
        distance = max(abs(a - b) for a in entry for b in envelope)
        travel = max(travel, distance * word_ms)
        follow = max(follow, Fraction(latency + settle))
        predecessor = max(predecessor, latency + settle + word_ms)
    if residual_ms is not None:
        predecessor = Fraction(residual_ms)

    def ceil(value: Fraction | int) -> int:
        return math.ceil(Fraction(value) / frame_ms) * frame_ms

    return ceil(dark) + ceil(wheel) + ceil(travel) + ceil(follow) + ceil(predecessor)


@dataclass(frozen=True)
class HeadFollow:
    """A fixture's head over a cue's last frame, as this pass's head model follows it."""

    segment: FixtureSegment
    settled_ms: Fraction | None
    """When every pose axis and wheel has settled after the cue's commands; None when
    unknown."""
    state: _State = field(repr=False)


def follow_cues(
    segments: Sequence[FixtureSegment],
    profile: FixtureCapabilities,
    *,
    frame_ms: int,
    after: HeadFollow | None = None,
) -> list[HeadFollow]:
    """Follow one fixture's cues, in time order, as `plan_prepositions` would play them.

    A cue right after the previous one (or `after`) continues its motion; any other cue
    starts settled at its own first values, as a transaction leaves it. Each cue is
    followed with the planner's own head model (`_end_state`), so its result is the
    state a transaction or continuation after the cue starts from.
    """
    out: list[HeadFollow] = []
    previous = after
    for segment in sorted(segments, key=lambda segment: segment.t0_ms):
        planner = _FixturePlanner(
            segment.fixture_id, profile, None, (), frame_ms, segment.t1_ms, "error"
        )
        if previous is not None and previous.segment.t1_ms == segment.t0_ms:
            head = previous.state.head
        else:
            start = Fraction(segment.t0_ms)
            rest: dict[ChannelName, _Motion] = dict.fromkeys(planner.pose_channels, (start, start))
            head = _Head(planner._values_at(segment, segment.t0_ms), rest, start)
        state = planner._end_state(segment, head)
        times = [state.head.wheels_settled]
        times += [None if motion is None else motion[1] for motion in state.head.motion.values()]
        settled = None if None in times else max(t for t in times if t is not None)
        previous = HeadFollow(segment, settled, state)
        out.append(previous)
    return out


def entry_feasible(
    segment: FixtureSegment,
    profile: FixtureCapabilities,
    *,
    after: HeadFollow | None,
    initial: InitialFixtureState | None,
    locks: Sequence[RenderLock],
    frame_ms: int,
) -> bool:
    """Whether `plan_prepositions` in `error` mode plays `segment` as authored right after
    `after` (or, without it, from the run's initial state): its transaction or
    continuation fits, and every shutter change from the predecessor's last frame to the
    segment's own first change takes effect in time (`shutter_timing`)."""
    planner = _FixturePlanner(
        segment.fixture_id, profile, initial, locks, frame_ms, segment.t1_ms, "error"
    )
    if after is not None:
        state = after.state
    elif initial is None or not initial.settled or profile.check_initial_state(initial):
        return False
    else:
        state = _State(0, planner._head(initial), None, None, planner._evidence(), None)
    try:
        plan = planner._transaction(state, segment)
    except _InfeasibleError:
        return False
    previous = None if after is None else after.segment
    authored = [s for s in (previous, plan.segment, segment) if s is not None]
    return all(problem.cue_ms < state.start_ms for problem in planner.shutter_timing(authored))


def follow_lag(
    segment: FixtureSegment, profile: FixtureCapabilities, *, frame_ms: int
) -> tuple[ChannelName, int, str] | None:
    """Where the head falls more than one encoded word behind a cue's pose commands.

    Followed from rest at the cue's start with this pass's head model, a command at frame
    `c` should be reached by the next frame's command, `c + latency_ms + frame_ms`; a
    head still more than one word's travel short of it then is chasing motion finer
    than the axis can follow. Axes with unknown speed, latency or settle are skipped.

    Returns:
        The axis, the frame and a reason naming the word-space rates, or None.
    """
    planner = _FixturePlanner(
        segment.fixture_id, profile, None, (), frame_ms, segment.t1_ms, "error"
    )
    for channel in planner.pose_channels:
        axis = planner._axis(channel)
        speed, latency = axis.travel_speed_per_s, axis.latency_ms
        if speed is None or latency is None or axis.settle_ms is None:
            continue
        physical = segment.channels[channel].physical
        assert isinstance(physical, ContinuousTrajectory)
        word_ms = _word_ms(axis)
        # One frame's commands travel at most its degrees plus one word of rounding; while
        # that fits in a frame the head never trails by more than the frame itself. The
        # float screen keeps a margin far wider than its rounding error.
        steepest = max(
            (abs(b.value - a.value) / (b.t_ms - a.t_ms) for a, b in pairwise(physical.points)),
            default=0.0,
        )
        if steepest * frame_ms * 1000 / speed + float(word_ms) <= frame_ms * (1 - 1e-6):
            continue
        start = Fraction(segment.t0_ms)
        motion: _Motion = (start, start)
        word: int | None = None
        changes = 0
        for time_ms, level in _frame_levels(physical, segment.t0_ms, segment.t1_ms, frame_ms):
            commanded = axis.dmx_word(level)
            if word is None:
                word = commanded
                continue
            changes += abs(commanded - word)
            motion, word = planner._follow(channel, motion, word, ((time_ms, commanded),))
            assert motion is not None
            behind = motion[0] - (time_ms + latency + frame_ms)
            if behind > word_ms:
                seconds = Fraction(time_ms + frame_ms - segment.t0_ms, 1000)
                return (
                    channel,
                    time_ms,
                    f"trails its commands by {float(behind / word_ms):.3g} words at "
                    f"{time_ms} ms: it commands {float(changes / seconds):.4g} word "
                    f"changes/s where {speed:g} {axis.unit}/s follows "
                    f"{float(1000 / word_ms):.4g} words/s; motion finer than the axis "
                    "can follow is not rendered",
                )
    return None


def dark_throughout(segment: FixtureSegment, profile: FixtureCapabilities, start_ms: int) -> bool:
    """Whether every frame of `segment` from `start_ms` commands darkness: an authored
    dimmer at zero the profile declares extinguishing, or an extinguishing shutter state."""
    visibility = profile.visibility
    dimmer = segment.channels.get(ChannelName.DIMMER)
    levels: dict[int, Fraction] = {}
    if (
        visibility.dimmer_zero_extinguishes
        and dimmer is not None
        and isinstance(dimmer.physical, ContinuousTrajectory)
    ):
        levels = dict(_frame_levels(dimmer.physical, start_ms, segment.t1_ms, EFFECT_GRID_MS))
    shutter = segment.channels.get(ChannelName.SHUTTER)
    for time_ms in range(start_ms, segment.t1_ms, EFFECT_GRID_MS):
        if levels.get(time_ms) == 0:
            continue
        if (
            shutter is not None
            and isinstance(shutter.physical, DiscreteTrajectory)
            and state_at(shutter.physical, time_ms) in visibility.extinguishing_shutter_states
        ):
            continue
        return False
    return True


def _word_ms(axis: AxisCapability) -> Fraction:
    """Time to travel one encoded word at the configured speed."""
    assert axis.travel_speed_per_s is not None
    span = Fraction(axis.physical_max) - Fraction(axis.physical_min)
    word_min, word_max = axis.word_range
    return span / (word_max - word_min) * 1000 / Fraction(axis.travel_speed_per_s)


class _InfeasibleError(Exception):
    """Why a cue cannot be planned. Only `substitutable` causes admit a fallback."""

    def __init__(
        self,
        code: TransitionCode,
        reason: str,
        required_ms: int | None = None,
        *,
        substitutable: bool = False,
    ) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.required_ms = required_ms
        self.substitutable = substitutable


@dataclass(frozen=True)
class _Values:
    """A fixture's commanded values at one frame.

    `dimmer` and `shutter` are only what a segment authors, the evidence for darkness;
    `dimmer_word`, `held_shutter` and `wheels` also take the default where nothing is
    authored, which is what the encoder emits there.
    """

    words: dict[ChannelName, int]
    dimmer: Fraction | None
    dimmer_word: int | None
    shutter: str | None
    held_shutter: str | None
    wheels: dict[ChannelName, str]


@dataclass(frozen=True)
class _Head:
    """The commanded words and wheels before a frame, and the motion still under way."""

    values: _Values
    motion: dict[ChannelName, _Motion]
    wheels_settled: Fraction | None
    """When every wheel has settled; None when unknown."""


@dataclass(frozen=True)
class _State:
    """Where the next transaction starts: the fixture over the frame before."""

    start_ms: int
    head: _Head
    dimmer_dark_since: int | None
    """Start of the authored dimmer-zero run reaching `start_ms`, as far back as matters."""
    shutter_dark_since: int | None
    """Start of the run of the held extinguishing shutter state reaching `start_ms`."""
    known_dark: frozenset[Literal["dimmer", "shutter"]]
    """Mechanisms the run's dark initial state evidences as already optically dark.

    Each counts only while the frames in question keep it: the dimmer at zero, or the
    same extinguishing shutter state."""
    source: FixtureSegment | None
    substituted: TransitionStatus | None = None
    """How the source cue was played when not as authored (`preserve_aim`): what the
    head actually did then is not the cue's content, so nothing may continue it."""


@dataclass(frozen=True)
class _Plan:
    segment: FixtureSegment | None
    required_ms: int | None
    """For a substitution, what the cue as authored needed; None when unknown."""
    optical_reveal_ms: int | None
    reason: str
    head: _Head
    """The head as the cue's first frame finds it."""


@dataclass(frozen=True)
class _Reached:
    """A cue an earlier plan of a fixture reached in a state (`_plan_view`), and that
    plan's whole output; from the cue on, it is the output `lengths` (out,
    diagnostics, dependencies, kept dark) into each."""

    cues: tuple[FixtureSegment, ...]
    index: int
    view: tuple[Any, ...]
    out: tuple[FixtureSegment, ...]
    diagnostics: tuple[TransitionDiagnostic, ...]
    dependencies: tuple[TransitionDependency, ...]
    kept_dark: tuple[dict[str, str | int], ...]
    lengths: tuple[int, int, int, int]

    def continues(self, cues: Sequence[FixtureSegment], index: int, view: tuple[Any, ...]) -> bool:
        """Whether planning `cues` from `index` in a state with `view` is this plan from
        its cue on: the same view and the very same cue objects to the end."""
        return (
            len(cues) - index == len(self.cues) - self.index
            and self.view == view
            and all(a is b for a, b in zip(cues[index:], self.cues[self.index :], strict=True))
        )


PrepositionMemo = dict[
    tuple[str, int, tuple[RenderLock, ...], int, int, FailureMode, UnplayableMode],
    tuple[FixtureCapabilities, dict[int, list[_Reached]]],
]
"""`plan_prepositions`' memo: by fixture, profile identity, locks, frame, sequence end,
failure mode and `on_unplayable`, the profile itself and, by cue identity, the states
earlier plans reached that cue in."""


def _plan_view(state: _State) -> tuple[Any, ...]:
    """Everything planning on from `state` reads of it.

    A pose axis' arrival or settle time, or the wheels' settle time, at or before
    `start_ms` is only ever compared with a time at or after it: a command's
    `time_ms + latency_ms` (`_follow`), a transaction's `motion_at` among the times it
    waits for, or a wheel change's settle (`_transaction`, `_end_state`). Every such
    time therefore plans the same, and the view leaves its value out; it stays at or
    before every later state's `start_ms`. Everything else is kept as it is.
    """
    start = state.start_ms

    def recent(time_ms: Fraction | None) -> Fraction | str | None:
        return "past" if time_ms is not None and time_ms <= start else time_ms

    head = state.head
    motion = tuple(
        (channel, None if times is None else (recent(times[0]), recent(times[1])))
        for channel, times in head.motion.items()
    )
    return (
        start,
        head.values,
        motion,
        recent(head.wheels_settled),
        state.dimmer_dark_since,
        state.shutter_dark_since,
        state.known_dark,
        state.source,
        state.substituted,
    )


def _remember(
    memo: dict[int, list[_Reached]],
    ordered: Sequence[FixtureSegment],
    reached: Sequence[tuple[int, tuple[Any, ...], int, int, int, int]],
    out: Sequence[FixtureSegment],
    diagnostics: Sequence[TransitionDiagnostic],
    dependencies: Sequence[TransitionDependency],
    kept_dark: Sequence[dict[str, str | int]],
) -> None:
    """Record a completed plan's cues in `memo`, each with the state it was reached in.
    Copies, since the caller extends its lists after."""
    cues, done = tuple(ordered), (tuple(out), tuple(diagnostics), tuple(dependencies))
    kept = tuple(kept_dark)
    for index, view, *lengths in reached:
        memo.setdefault(id(cues[index]), []).append(
            _Reached(
                cues, index, view, *done, kept, (lengths[0], lengths[1], lengths[2], lengths[3])
            )
        )


class _FixturePlanner:
    """Plans one fixture in time order."""

    def __init__(
        self,
        fixture_id: str,
        profile: FixtureCapabilities,
        initial: InitialFixtureState | None,
        locks: Sequence[RenderLock],
        frame_ms: int,
        end_ms: int,
        failure_mode: FailureMode,
        on_unplayable: UnplayableMode = "error",
    ) -> None:
        self.fixture_id = fixture_id
        self.profile = profile
        self.initial = initial
        self.frame_ms = frame_ms
        self.end_ms = end_ms
        self.failure_mode = failure_mode
        self.on_unplayable = on_unplayable
        self.pose_channels = tuple(ch for ch in _POSE if AXIS_KEYS[ch] in profile.axes)
        self.wheel_channels = tuple(ch for ch in _WHEELS if DISCRETE_KEYS[ch] in profile.discrete)
        self.channels = tuple(
            channel
            for channel in ChannelName
            if (channel in AXIS_KEYS and AXIS_KEYS[channel] in profile.axes)
            or (channel in DISCRETE_KEYS and DISCRETE_KEYS[channel] in profile.discrete)
        )
        self.locks = tuple(
            (
                lock.start_ms // frame_ms * frame_ms,
                -(-lock.end_ms // frame_ms) * frame_ms,
                frozenset(lock.channels),
            )
            for lock in locks
            if fixture_id in lock.fixture_ids
        )
        # Encoded pose words by commanded value (`_word`) and travel times by word
        # distance (`_travel_ms`), reused wherever a value recurs, as on every cycle of
        # a periodic cue; both are exact and pure.
        self._words: dict[ChannelName, dict[Fraction | float, int]] = {
            channel: {} for channel in self.pose_channels
        }
        self._travel: dict[ChannelName, dict[int, Fraction]] = {
            channel: {} for channel in self.pose_channels
        }
        # Word centers by axis and word (`_center`), as pure as the two above.
        self._centers: dict[AxisName, dict[int, float]] = {}

    # --- Planning ---------------------------------------------------------------------

    def plan(
        self,
        segments: Sequence[FixtureSegment],
        dark: Mapping[int, _InfeasibleError] | None = None,
        memo: dict[int, list[_Reached]] | None = None,
    ) -> tuple[
        list[FixtureSegment],
        list[TransitionDiagnostic],
        list[TransitionDependency],
        list[dict[str, str | int]],
    ]:
        """Plan the fixture's cues in time order; `dark` maps the start of each cue to
        keep dark (`on_unplayable="dark"`) to the failure found for it. `memo` (only
        without `dark`) holds, by cue, the states earlier plans of this fixture reached it
        in (`plan_prepositions`)."""
        ordered = self._checked(segments)
        dark = dark or {}
        out: list[FixtureSegment] = []
        diagnostics: list[TransitionDiagnostic] = []
        dependencies: list[TransitionDependency] = []
        kept_dark: list[dict[str, str | int]] = []
        if not ordered and self.end_ms == 0:
            return out, diagnostics, dependencies, kept_dark

        def fail(state: _State, target: FixtureSegment | None, failure: _InfeasibleError) -> None:
            cue_ms = state.start_ms if target is None else target.t0_ms
            diagnostics.append(
                self._diagnostic(
                    cue_ms,
                    "error",
                    failure.code,
                    failure.required_ms,
                    None if target is None else target.t0_ms - state.start_ms,
                    failure.reason,
                )
            )
            if target is not None:
                dependencies.append(self._dependency(state, target, target.t0_ms + self.frame_ms))

        problems = self.profile.check_initial_state(self.initial)
        if self.initial is not None and not self.initial.settled:
            problems += ("initial state is not settled",)
        if problems or self.initial is None:
            unknown = _State(0, self._head(None), None, None, frozenset(), None)
            reason = "; ".join(problems)
            fail(
                unknown,
                ordered[0] if ordered else None,
                _InfeasibleError("unknown_initial_state", reason),
            )
            return out, diagnostics, dependencies, kept_dark

        state = _State(0, self._head(self.initial), None, None, self._evidence(), None)
        last: FixtureSegment | None = None
        # Where each cue was reached (`memo`): its index, the state, the output so far.
        reached: list[tuple[int, tuple[Any, ...], int, int, int, int]] = []
        for index, target in enumerate(ordered):
            if memo is not None:
                view = _plan_view(state)
                for earlier in memo.get(id(target), ()):
                    if earlier.continues(ordered, index, view):
                        out += earlier.out[earlier.lengths[0] :]
                        diagnostics += earlier.diagnostics[earlier.lengths[1] :]
                        dependencies += earlier.dependencies[earlier.lengths[2] :]
                        kept_dark += earlier.kept_dark[earlier.lengths[3] :]
                        _remember(memo, ordered, reached, out, diagnostics, dependencies, kept_dark)
                        return out, diagnostics, dependencies, kept_dark
                lengths = (len(out), len(diagnostics), len(dependencies), len(kept_dark))
                reached.append((index, view, *lengths))
            available = target.t0_ms - state.start_ms
            status: TransitionStatus = "feasible"
            code: TransitionCode | None = None
            failure = dark.get(target.t0_ms)
            if failure is None:
                try:
                    plan = self._transaction(state, target)
                except _InfeasibleError as error:
                    failure = error
            if failure is not None:
                mode = None if target.t0_ms in dark else self._fallback(target, failure)
                aim = self._aim(state)
                if mode == "preserve_aim":
                    try:
                        held = self._hold_aim(target, state.head.values.words)
                        self._check_locks(held.t0_ms, held.t1_ms, _POSE, failure.required_ms)
                        plan = self._transaction(state, held)
                    except _InfeasibleError as second:
                        second.reason = (
                            f"{failure.reason}; preserve_aim cannot apply: {second.reason}"
                        )
                        failure, mode = second, None
                    else:
                        target, status, code = held, mode, failure.code
                        plan = replace(
                            plan,
                            required_ms=failure.required_ms,
                            reason=f"{failure.reason}; preserve_aim holds pan/tilt at the "
                            f"settled aim {aim} through the cue; {plan.reason}",
                        )
                if mode != "preserve_aim":
                    degrade = mode is None
                    if degrade and not self._degrades(failure):
                        fail(state, target, failure)
                        return out, diagnostics, dependencies, kept_dark
                    why = "on_unplayable 'dark'" if degrade else "drop_accent"
                    diagnostics.append(
                        self._diagnostic(
                            target.t0_ms,
                            "drop_accent",
                            failure.code,
                            failure.required_ms,
                            available,
                            f"{failure.reason}; {why} keeps the cue dark at the aim "
                            f"{aim} and plans the next cue from there",
                        )
                    )
                    dependencies.append(self._dependency(state, target, target.t1_ms))
                    if degrade:
                        kept_dark.append(self._kept_dark(target, failure))
                    last = target
                    continue
            diagnostics.append(
                self._diagnostic(
                    target.t0_ms,
                    status,
                    code,
                    plan.required_ms,
                    available,
                    plan.reason,
                    plan.optical_reveal_ms,
                )
            )
            end_ms = target.t0_ms + self.frame_ms
            if plan.optical_reveal_ms is not None:
                end_ms = max(end_ms, self._ceil(plan.optical_reveal_ms))
            if status == "preserve_aim":
                end_ms = max(end_ms, target.t1_ms)
            dependencies.append(self._dependency(state, target, end_ms))
            if plan.segment is not None:
                out.append(plan.segment)
            out.append(target)
            state = self._end_state(target, plan.head)
            if status != "feasible":
                state = replace(state, substituted=status)
            last = target

        if state.start_ms < self.end_ms:
            # After the last cue (or with none): extinguish and park at the held aim.
            try:
                dimmer_word, shutter = self._dark_commands(state)
                park = self._author(
                    state, None, self.end_ms, state.head.values, dimmer_word, shutter
                )
                self._check_locks(state.start_ms, self.end_ms, tuple(park.channels), None)
            except _InfeasibleError as failure:
                failure.reason = f"cannot park {'after ' + last.segment_id if last else 'the fixture'}: {failure.reason}"
                fail(state, None, failure)
                return out, diagnostics, dependencies, kept_dark
            out.append(park)
        if memo is not None:
            _remember(memo, ordered, reached, out, diagnostics, dependencies, kept_dark)
        return out, diagnostics, dependencies, kept_dark

    def culprits(
        self, out: Sequence[FixtureSegment], errors: Sequence[TransitionDiagnostic]
    ) -> dict[int, _InfeasibleError]:
        """The cue to keep dark for each error a dark cue could clear, by its start.

        A shutter state too short to take effect lies in a cue, a transaction (its cue
        then) or the park (the last cue played then); a park that cannot follow is
        the last cue's. An unknown initial state or a lock is never cleared so."""
        found: dict[int, _InfeasibleError] = {}
        cues = [segment for segment in out if TRANSACTION_METADATA_KEY not in segment.metadata]
        for error in errors:
            if error.code is None or error.code in ("unknown_initial_state", "lock_conflict"):
                continue
            where = next((s for s in out if s.t0_ms <= error.cue_ms < s.t1_ms), None)
            if where is None:  # a park that could not be authored, after its cue
                where = next((s for s in cues if s.t1_ms == error.cue_ms), None)
            if where is not None and TRANSACTION_METADATA_KEY in where.metadata:
                if where.metadata[TRANSACTION_METADATA_KEY]:
                    where = next((s for s in cues if s.t0_ms == where.t1_ms), None)
                else:
                    where = next((s for s in cues if s.t1_ms == where.t0_ms), None)
            if where is not None:
                found[where.t0_ms] = _InfeasibleError(
                    error.code, error.reason, error.required_ms, substitutable=True
                )
        return found

    def _degrades(self, failure: _InfeasibleError) -> bool:
        """Whether `on_unplayable` keeps a cue dark that cannot be played for `failure`:
        never for an unknown initial state or a lock."""
        return self.on_unplayable == "dark" and failure.code not in (
            "unknown_initial_state",
            "lock_conflict",
        )

    def _kept_dark(self, cue: FixtureSegment, failure: _InfeasibleError) -> dict[str, str | int]:
        return {
            "fixture_id": cue.fixture_id,
            "section_id": cue.section_id,
            "template_id": cue.template_id,
            "step_id": cue.step_id,
            "start_ms": cue.t0_ms,
            "end_ms": cue.t1_ms,
            "frames": (cue.t1_ms - cue.t0_ms) // self.frame_ms,
            "reason": "unplayable",
            "code": failure.code,
            "detail": failure.reason,
        }

    def _transaction(self, state: _State, target: FixtureSegment) -> _Plan:
        g0, g1 = state.start_ms, target.t0_ms
        available = g1 - g0
        now, goal = state.head.values, self._values_at(target, g1)
        moving = [ch for ch in self.pose_channels if goal.words[ch] != now.words[ch]]
        changed = [ch for ch in self.wheel_channels if goal.wheels[ch] != now.wheels[ch]]
        if available == 0 and state.source is not None:
            return self._continuation(state, goal, moving, changed)

        unknown = [
            f"{channel.value} {name}"
            for channel in moving
            for name, value in self._axis_timing(channel)
            if value is None
        ]
        unknown += [
            f"{channel.value} state {goal.wheels[channel]!r} settle_ms"
            for channel in changed
            if self._wheel_settle(channel, goal.wheels[channel]) is None
        ]
        if unknown:
            raise _InfeasibleError(
                "unknown_motion_rate",
                f"needed change has unknown {', '.join(unknown)}",
                substitutable=True,
            )

        dark_commands = self._dark_commands(state) if available else None
        dark_start = g0
        if moving or changed:
            dimmer_dark = self.profile.visibility.dimmer_zero_extinguishes
            if dark_commands is None:
                # Time zero: no transaction; the cue's own first frame must hold darkness.
                held = (dimmer_dark and goal.dimmer == 0, goal.shutter)
            else:
                held = (dimmer_dark, dark_commands[1])
            dark_from = self._dark_from(state, *held)
            lit = not self._commanded_dark(goal.dimmer, goal.shutter)
            if dark_from is None and dark_commands is None and lit and self._can_darken(state):
                # A lit cue at time zero that must change first: dropping it is safe, so a
                # fallback may apply.
                names = "/".join(ch.value for ch in (*moving, *changed))
                raise _InfeasibleError(
                    "infeasible_transition",
                    f"a lit cue at time zero changes {names} from the initial state, and "
                    "nothing is pre-rolled before time zero to darken and change it",
                    substitutable=True,
                )
            if dark_from is None:
                raise _InfeasibleError(
                    "infeasible_transition",
                    "darkness is never established before the change: nothing in force "
                    "extinguishes the fixture, or close_latency_ms or the extinguishing "
                    "shutter state's settle_ms is unknown",
                )
            dark_start = g0 + self._ceil(max(0, dark_from - g0))
        wheel_settle = max(
            (self._wheel_settle(ch, goal.wheels[ch]) or 0 for ch in changed), default=0
        )
        wheel_ms = self._ceil(wheel_settle)
        if changed and available:
            # The transaction turns the wheel on a dark frame of its own, never on the
            # cue's reveal frame, so the masking holds even for an instant wheel.
            wheel_ms = max(wheel_ms, self.frame_ms)
        motion_at = dark_start + wheel_ms
        ramp_ms = self._ceil(
            max((self._travel_ms(ch, now.words[ch], goal.words[ch]) for ch in moving), default=0)
        )
        schedules = {
            ch: self._schedule(now.words[ch], goal.words[ch], motion_at, ramp_ms) for ch in moving
        }

        motion = {
            ch: self._follow(ch, state.head.motion[ch], now.words[ch], schedules.get(ch, ()))[0]
            for ch in self.pose_channels
        }
        wheels_settled = state.head.wheels_settled
        if changed and wheels_settled is not None:
            wheels_settled = max(wheels_settled, Fraction(dark_start + wheel_settle))
        settled = [
            wheels_settled,
            Fraction(motion_at),
            *(None if m is None else m[1] for m in motion.values()),
        ]
        known = [time for time in settled if time is not None]
        if len(known) < len(settled):
            raise _InfeasibleError(
                "unknown_motion_rate",
                "earlier motion has an unknown travel_speed_per_s, latency_ms or settle_ms, so "
                "the head is never known to have settled",
                substitutable=True,
            )
        done = g0 + self._ceil(max(Fraction(0), max(known) - g0))
        required = done - g0
        if required > available:
            raise _InfeasibleError(
                "infeasible_transition",
                f"needs {required} ms to darken, change, arrive and settle but has {available} ms",
                required,
                substitutable=True,
            )

        head = _Head(goal, motion, wheels_settled)
        visible = not self._commanded_dark(goal.dimmer, goal.shutter)
        if available == 0:
            # Time zero: nothing is pre-rolled before it.
            if visible and not self._initial_matches(goal):
                raise _InfeasibleError(
                    "infeasible_transition",
                    "a visible cue at time zero needs the initial state already lit with "
                    "its dimmer and shutter; nothing is pre-rolled before time zero",
                    required,
                    substitutable=True,
                )
            head = replace(head, values=now)
            return _Plan(None, 0, None, "the initial state already holds the cue's state", head)

        assert dark_commands is not None
        segment = self._author(
            state, target, g1, goal, *dark_commands, schedules, motion_at, wheel_at=dark_start
        )
        self._check_locks(g0, g1, tuple(segment.channels), required)

        parts = [f"commands dark at {g0} ms"]
        if changed:
            names = "/".join(ch.value for ch in changed)
            parts.append(f"{names} change from {dark_start} ms and settle by {motion_at} ms")
        if moving:
            names = "/".join(ch.value for ch in moving)
            parts.append(f"{names} move from {motion_at} ms for {ramp_ms} ms")
        parts.append(f"settled by {done} ms")
        optical: int | None = None
        if visible:
            open_ms = self.profile.visibility.open_latency_ms
            if open_ms is None:
                raise _InfeasibleError(
                    "infeasible_transition",
                    "open_latency_ms is unknown, so the cue's optical reveal time is unknown",
                    required,
                )
            optical = g1 + open_ms
            parts.append(
                f"reveal command on the cue at {g1} ms; expected optical reveal at {optical} ms, "
                f"{open_ms} ms after the command"
            )
        else:
            parts.append("the cue starts dark")
        return _Plan(segment, required, optical, "; ".join(parts), head)

    def _continuation(
        self, state: _State, goal: _Values, moving: list[ChannelName], changed: list[ChannelName]
    ) -> _Plan:
        """A cue right after another: only visible motion within one frame's travel.

        Only a predecessor played as authored can be continued. After a substituted one
        the head's state is the substitution's, so any pose or wheel change at the cue
        is a reposition with no time for it.
        """
        if state.substituted is not None and (moving or changed):
            names = "/".join(ch.value for ch in (*moving, *changed))
            raise _InfeasibleError(
                "infeasible_transition",
                f"the previous cue was played as {state.substituted}, so {names} would "
                "change at this cue with no time between cues to darken and move",
                substitutable=True,
            )
        if changed:
            raise _InfeasibleError(
                "infeasible_transition",
                f"{'/'.join(ch.value for ch in changed)} changes at the cue with no time "
                "between cues to mask and settle it",
                substitutable=True,
            )
        now = state.head.values
        for channel in moving:
            if self._axis(channel).travel_speed_per_s is None:
                raise _InfeasibleError(
                    "unknown_motion_rate",
                    f"{channel.value} moves across the cue with unknown travel_speed_per_s",
                    substitutable=True,
                )
            needed = self._ceil(self._travel_ms(channel, now.words[channel], goal.words[channel]))
            if needed > self.frame_ms:
                raise _InfeasibleError(
                    "infeasible_transition",
                    f"{channel.value} jumps across the cue with no time between cues; the "
                    f"travel needs {needed} ms",
                    needed,
                    substitutable=True,
                )
        return _Plan(None, 0, None, "continues the previous cue without a gap", state.head)

    def _fallback(self, target: FixtureSegment, failure: _InfeasibleError) -> FailureMode | None:
        if self.failure_mode == "error" or not failure.substitutable:
            return None
        if target.metadata.get(FALLBACK_METADATA_KEY) != self.failure_mode:
            return None
        return self.failure_mode

    # --- Head motion ------------------------------------------------------------------

    def _follow(
        self,
        channel: ChannelName,
        motion: _Motion,
        word: int,
        commands: Iterable[tuple[int, int]],
    ) -> tuple[_Motion, int]:
        """Follow word commands from `word`; return the motion and the last word.

        Each change is reached at `max(arrival, time_ms + latency_ms)` plus its word
        distance's travel (`_travel_ms`, linear in the distance) and settles `settle_ms`
        later. The arrival is kept as an integer count of `1/scale` ms, over the
        denominators of the previous arrival and of one word's travel: exact, without
        a fraction per command.
        """
        axis = self._axis(channel)
        speed, latency, settle = axis.travel_speed_per_s, axis.latency_ms, axis.settle_ms
        if motion is None or speed is None or latency is None or settle is None:
            for _, commanded in commands:
                if commanded != word:
                    motion, word = None, commanded
            return motion, word
        per_word = self._travel_ms(channel, 0, 1)
        start = Fraction(motion[0])
        scale = math.lcm(start.denominator, per_word.denominator)
        arrival = start.numerator * (scale // start.denominator)
        step = per_word.numerator * (scale // per_word.denominator)
        moved = False
        for time_ms, commanded in commands:
            if commanded == word:
                continue
            arrival = max(arrival, (time_ms + latency) * scale) + abs(commanded - word) * step
            word, moved = commanded, True
        if moved:
            reached = Fraction(arrival, scale)
            motion = (reached, reached + settle)
        return motion, word

    def _schedule(
        self, start: int, end: int, motion_at: int, ramp_ms: int
    ) -> list[tuple[int, int]]:
        """Word commands from `motion_at`, one per frame over `ramp_ms`, ending at `end`.

        Each frame's word leaves at most the linear share of the distance for the
        frames after it, rounded toward the target, so the head (moving no faster than
        `ramp_ms` allows for the whole distance) is never left more than it can cover.
        """
        direction = 1 if end > start else -1
        distance = abs(end - start)
        steps = ramp_ms // self.frame_ms
        return [
            (
                motion_at + step * self.frame_ms,
                end - direction * (distance * (ramp_ms - (step + 1) * self.frame_ms) // ramp_ms),
            )
            for step in range(steps)
        ]

    # --- Authoring --------------------------------------------------------------------

    def _author(
        self,
        state: _State,
        identity: FixtureSegment | None,
        end_ms: int,
        goal: _Values,
        dimmer_word: int | None,
        shutter: str | None,
        schedules: Mapping[ChannelName, list[tuple[int, int]]] | None = None,
        motion_at: int = 0,
        *,
        wheel_at: int | None = None,
    ) -> FixtureSegment:
        """The explicit transaction (or, without `identity`, park) over `[start, end_ms)`."""
        g0 = state.start_ms
        channels: dict[ChannelName, PhysicalValue] = {}
        for channel in self.pose_channels:
            held = state.head.values.words[channel]
            schedule = (schedules or {}).get(channel)
            points: list[tuple[int, int]] = [(g0, held)]
            if schedule:
                # Hold until the frame before `motion_at`, then one command per frame.
                if motion_at == g0:
                    points = []
                elif motion_at - self.frame_ms > g0:
                    points.append((motion_at - self.frame_ms, held))
                points += schedule
            key = AXIS_KEYS[channel]
            channels[channel] = ContinuousTrajectory(
                unit="degree",
                points=tuple(PhysicalPoint(t_ms=t, value=self._center(key, w)) for t, w in points),
                interpolation="linear",
            )
        if dimmer_word is not None:
            channels[ChannelName.DIMMER] = ContinuousTrajectory(
                unit="normalized",
                points=(PhysicalPoint(t_ms=g0, value=self._center("dimmer", dimmer_word)),),
                interpolation="hold",
            )
        if shutter is not None:
            channels[ChannelName.SHUTTER] = _held(g0, shutter)
        for channel in self.wheel_channels:
            held_state, selected = state.head.values.wheels[channel], goal.wheels[channel]
            if selected == held_state or wheel_at is None or wheel_at >= end_ms:
                channels[channel] = _held(g0, held_state)
            elif wheel_at == g0:
                channels[channel] = _held(g0, selected)
            else:
                channels[channel] = DiscreteTrajectory(
                    events=(
                        DiscretePoint(t_ms=g0, state=held_state),
                        DiscretePoint(t_ms=wheel_at, state=selected),
                    )
                )
        name = f"{self.fixture_id}/park" if identity is None else identity.segment_id
        return FixtureSegment(
            section_id="" if identity is None else identity.section_id,
            segment_id=f"{name}/preposition",
            step_id="preposition",
            template_id="" if identity is None else identity.template_id,
            preset_id=None if identity is None else identity.preset_id,
            fixture_id=self.fixture_id,
            t0_ms=g0,
            t1_ms=end_ms,
            channels={ch: ChannelValue(channel=ch, physical=v) for ch, v in channels.items()},
            metadata={TRANSACTION_METADATA_KEY: "" if identity is None else identity.segment_id},
        )

    def _hold_aim(self, target: FixtureSegment, words: Mapping[ChannelName, int]) -> FixtureSegment:
        channels = dict(target.channels)
        for channel in self.pose_channels:
            value = self._center(AXIS_KEYS[channel], words[channel])
            points = (
                PhysicalPoint(t_ms=target.t0_ms, value=value),
                PhysicalPoint(t_ms=target.t1_ms, value=value),
            )
            channels[channel] = ChannelValue(
                channel=channel,
                physical=ContinuousTrajectory(unit="degree", points=points, interpolation="linear"),
            )
        return FixtureSegment(
            **{**dict(target), "channels": channels, "metadata": dict(target.metadata)}
        )

    def _center(self, key: AxisName, word: int) -> float:
        """A value that encodes to `word` with margin (`AxisCapability.word_center`).

        Planner-authored values are always word centers, so no float rounding can land
        on a DMX rounding tie and move the head between two frames that should hold.
        """
        centers = self._centers.setdefault(key, {})
        if word not in centers:
            try:
                centers[word] = self.profile.axes[key].word_center(word)
            except ValueError as error:
                raise _InfeasibleError("infeasible_transition", f"{key} {error}") from error
        return centers[word]

    def _dark_commands(self, state: _State) -> tuple[int | None, str | None]:
        """The dimmer word and shutter state a transaction holds: every declared darkness.

        Dimmer zero when it extinguishes, else the held word; the held shutter state
        when it extinguishes, else `closed_state` when that does, else the held state.
        """
        visibility = self.profile.visibility
        values = state.head.values
        dimmer = self.profile.axes.get("dimmer")
        dimmer_word = values.dimmer_word
        if visibility.dimmer_zero_extinguishes and dimmer is not None:
            dimmer_word = dimmer.dmx_word(0)
        shutter = values.held_shutter
        capability = self.profile.discrete.get("shutter")
        closed = None if capability is None else capability.closed_state
        if shutter not in visibility.extinguishing_shutter_states and (
            closed is not None and closed in visibility.extinguishing_shutter_states
        ):
            shutter = closed
        level = Fraction(0) if visibility.dimmer_zero_extinguishes else None
        if not self._commanded_dark(level, shutter):
            raise _InfeasibleError(
                "infeasible_transition",
                "the profile declares no way to extinguish the fixture "
                "(dimmer_zero_extinguishes, or a closed_state listed in "
                "extinguishing_shutter_states)",
            )
        return dimmer_word, shutter

    def _check_locks(
        self, start_ms: int, end_ms: int, channels: Sequence[ChannelName], required: int | None
    ) -> None:
        for lock_start, lock_end, locked in self.locks:
            hit = [channel for channel in ChannelName if channel in locked and channel in channels]
            if hit and lock_start < end_ms and start_ms < lock_end:
                raise _InfeasibleError(
                    "lock_conflict",
                    f"lock on {'/'.join(ch.value for ch in hit)} over [{lock_start}, "
                    f"{lock_end}) ms covers frames that must change in [{start_ms}, {end_ms}) ms",
                    required,
                )

    # --- State ------------------------------------------------------------------------

    def _checked(self, segments: Sequence[FixtureSegment]) -> list[FixtureSegment]:
        ordered = sorted(segments, key=lambda segment: (segment.t0_ms, segment.t1_ms))
        end_ms = 0
        for segment in ordered:
            name = f"segment {segment.segment_id!r} of {self.fixture_id}"
            cue_times = [segment.t0_ms, segment.t1_ms]
            for channel, value in segment.channels.items():
                check_physical_value(self.fixture_id, channel, value.physical, self.profile)
                if isinstance(value.physical, DiscreteTrajectory):
                    cue_times += [event.t_ms for event in value.physical.events]
                elif value.physical.interpolation == "hold":
                    cue_times += [point.t_ms for point in value.physical.points]
            if off := [t for t in cue_times if t % self.frame_ms]:
                raise ValueError(f"{name} has times {off} off the {self.frame_ms} ms frame grid")
            if segment.t1_ms <= segment.t0_ms:
                raise ValueError(f"{name} is empty")
            if segment.t0_ms < end_ms:
                raise ValueError(f"{name} overlaps the segment before it")
            if segment.t1_ms > self.end_ms:
                raise ValueError(f"{name} ends after sequence_end_ms {self.end_ms}")
            if missing := [ch.value for ch in self.pose_channels if ch not in segment.channels]:
                raise ValueError(f"{name} must author its {'/'.join(missing)}: its pose is the cue")
            end_ms = segment.t1_ms
        return ordered

    def _head(self, initial: InitialFixtureState | None) -> _Head:
        """The head before time zero: the initial state, settled."""
        if initial is None:
            return _Head(_Values({}, None, None, None, None, {}), {}, None)
        states = initial.discrete_states
        pose = initial.pose
        dimmer = self.profile.axes.get("dimmer")
        level = None if initial.dimmer is None else Fraction(initial.dimmer)
        values = _Values(
            words={ch: self._axis(ch).dmx_word(pose[AXIS_KEYS[ch]]) for ch in self.pose_channels},
            dimmer=level,
            dimmer_word=(
                dimmer.dmx_word(level)
                if dimmer is not None and level is not None and dimmer.admits(level)
                else None
            ),
            shutter=states.get("shutter"),
            held_shutter=states.get("shutter"),
            wheels={channel: states[DISCRETE_KEYS[channel]] for channel in self.wheel_channels},
        )
        rest = (Fraction(0), Fraction(0))
        return _Head(values, dict.fromkeys(self.pose_channels, rest), Fraction(0))

    def _values_at(self, segment: FixtureSegment, time_ms: int) -> _Values:
        def level(channel: ChannelName) -> Fraction | float | None:
            """The sample (`frame_values`) of a continuous channel, else None."""
            value = segment.channels.get(channel)
            if value is None or not isinstance(value.physical, ContinuousTrajectory):
                return None
            return next(frame_values(value.physical, time_ms, time_ms + 1, 1))[1]

        def state(channel: ChannelName) -> str | None:
            value = segment.channels.get(channel)
            if value is None or not isinstance(value.physical, DiscreteTrajectory):
                return None
            return state_at(value.physical, time_ms)

        words = {}
        for channel in self.pose_channels:
            pose = level(channel)
            assert pose is not None  # checked: cues author their pose
            words[channel] = self._word(channel, pose)
        dimmer = self.profile.axes.get("dimmer")
        authored = level(ChannelName.DIMMER)
        shutter = state(ChannelName.SHUTTER)
        capability = self.profile.discrete.get("shutter")
        return _Values(
            words=words,
            dimmer=None if authored is None else Fraction(authored),
            dimmer_word=(
                None
                if dimmer is None
                else self._default_word(dimmer)
                if authored is None
                else _encoded(dimmer, authored)
            ),
            shutter=shutter,
            held_shutter=shutter or (None if capability is None else capability.default_state),
            wheels={
                channel: state(channel)
                or self.profile.discrete[DISCRETE_KEYS[channel]].default_state
                for channel in self.wheel_channels
            },
        )

    def _end_state(self, segment: FixtureSegment, head: _Head) -> _State:
        """The state over a cue's last frame: its own motion followed, its dark runs."""
        motion = dict(head.motion)
        for channel in self.pose_channels:
            physical = segment.channels[channel].physical
            assert isinstance(physical, ContinuousTrajectory)
            first = physical.points[0]
            if (
                first.t_ms <= segment.t0_ms
                and all(point.value == first.value for point in physical.points)
                and self._word(channel, first.value) == head.values.words[channel]
            ):
                continue  # held at the word the head already has: no command moves it
            commands = (
                (t, self._word(channel, value))
                for t, value in frame_values(physical, segment.t0_ms, segment.t1_ms, self.frame_ms)
            )
            motion[channel], _ = self._follow(
                channel, motion[channel], head.values.words[channel], commands
            )
        wheels_settled = head.wheels_settled
        for channel in self.wheel_channels:
            held = head.values.wheels[channel]
            value = segment.channels.get(channel)
            default = self.profile.discrete[DISCRETE_KEYS[channel]].default_state
            events = (
                [(event.t_ms, event.state) for event in value.physical.events]
                if value is not None and isinstance(value.physical, DiscreteTrajectory)
                else [(segment.t0_ms, default)]
            )
            for time_ms, selected in events:
                if selected == held:
                    continue
                settle = self._wheel_settle(channel, selected)
                if wheels_settled is not None:
                    wheels_settled = (
                        None if settle is None else max(wheels_settled, Fraction(time_ms + settle))
                    )
                held = selected

        last = segment.t1_ms - self.frame_ms
        values = self._values_at(segment, last)
        visibility = self.profile.visibility
        dimmer_since = shutter_since = None
        close = visibility.close_latency_ms
        if close is not None:
            # Darkness commanded long enough before the last frame is in effect by then.
            capability = self.profile.discrete.get("shutter")
            settles = [
                capability.states[name].settle_ms or 0
                for name in visibility.extinguishing_shutter_states
                if capability is not None
            ]
            stop = max(segment.t0_ms, last - close - max(settles, default=0))
            frames = range(last, stop - 1, -self.frame_ms)
            for time_ms in frames:
                if not self._commanded_dark(self._values_at(segment, time_ms).dimmer, None):
                    break
                dimmer_since = time_ms
            end_shutter = values.shutter
            if end_shutter in visibility.extinguishing_shutter_states:
                for time_ms in frames:
                    if self._values_at(segment, time_ms).shutter != end_shutter:
                        break
                    shutter_since = time_ms
        head = _Head(values, motion, wheels_settled)
        return _State(segment.t1_ms, head, dimmer_since, shutter_since, frozenset(), segment)

    def _dark_from(
        self, state: _State, dimmer_zero: bool, shutter: str | None
    ) -> Fraction | int | None:
        """When the fixture is optically dark while `dimmer_zero` and `shutter` hold.

        A held dimmer zero counts from its zero run (or the start) plus
        `close_latency_ms`; a held extinguishing shutter from its run plus the latency
        and that state's `settle_ms`. Initial-state evidence makes a mechanism dark at
        once, but only that mechanism and only while it is kept. The earliest known wins.
        """
        visibility = self.profile.visibility
        close = visibility.close_latency_ms
        candidates: list[int] = []
        if dimmer_zero:
            if "dimmer" in state.known_dark:
                candidates.append(state.start_ms)
            elif close is not None:
                since = state.dimmer_dark_since
                candidates.append((state.start_ms if since is None else since) + close)
        capability = self.profile.discrete.get("shutter")
        if capability is not None and shutter in visibility.extinguishing_shutter_states:
            held = state.head.values.shutter == shutter
            settle = capability.states[shutter].settle_ms
            if held and "shutter" in state.known_dark:
                candidates.append(state.start_ms)
            elif close is not None and settle is not None:
                since = state.shutter_dark_since if held else None
                candidates.append((state.start_ms if since is None else since) + close + settle)
        return min(candidates, default=None)

    def _evidence(self) -> frozenset[Literal["dimmer", "shutter"]]:
        """The mechanisms by which the dark initial state is already dark."""
        initial, visibility = self.initial, self.profile.visibility
        if initial is None or not initial.dark:
            return frozenset()
        evidence: set[Literal["dimmer", "shutter"]] = set()
        if visibility.dimmer_zero_extinguishes and initial.dimmer == 0:
            evidence.add("dimmer")
        if initial.discrete_states.get("shutter") in visibility.extinguishing_shutter_states:
            evidence.add("shutter")
        return frozenset(evidence)

    def _can_darken(self, state: _State) -> bool:
        """Whether a transaction from `state` could establish darkness at all: a declared
        mechanism with a known close latency (and shutter settle)."""
        try:
            _, shutter = self._dark_commands(state)
        except _InfeasibleError:
            return False
        dimmer_dark = self.profile.visibility.dimmer_zero_extinguishes
        return self._dark_from(state, dimmer_dark, shutter) is not None

    def _commanded_dark(self, dimmer: Fraction | None, shutter: str | None) -> bool:
        visibility = self.profile.visibility
        return (visibility.dimmer_zero_extinguishes and dimmer == 0) or (
            shutter is not None and shutter in visibility.extinguishing_shutter_states
        )

    def _initial_matches(self, goal: _Values) -> bool:
        assert self.initial is not None
        values = self._head(self.initial).values
        return (
            not self.initial.dark
            and ("dimmer" not in self.profile.axes or goal.dimmer == values.dimmer)
            and goal.held_shutter == values.held_shutter
        )

    # --- Profile arithmetic -----------------------------------------------------------

    def _axis(self, channel: ChannelName) -> AxisCapability:
        return self.profile.axes[AXIS_KEYS[channel]]

    def _axis_timing(self, channel: ChannelName) -> list[tuple[str, float | None]]:
        axis = self._axis(channel)
        return [
            ("travel_speed_per_s", axis.travel_speed_per_s),
            ("latency_ms", axis.latency_ms),
            ("settle_ms", axis.settle_ms),
        ]

    def _word(self, channel: ChannelName, value: Fraction | float) -> int:
        """The axis' `dmx_word` for a commanded value, exact (a float is the value it
        holds, and keys the same entry as the equal fraction)."""
        words = self._words[channel]
        word = words.get(value)
        if word is None:
            word = words[value] = _encoded(self._axis(channel), value)
        return word

    def _travel_ms(self, channel: ChannelName, start: int, end: int) -> Fraction:
        """Time to travel between two encoded words at the configured speed."""
        travel = self._travel[channel]
        words = abs(end - start)
        if words not in travel:
            axis = self._axis(channel)
            assert axis.travel_speed_per_s is not None
            span = Fraction(axis.physical_max) - Fraction(axis.physical_min)
            word_min, word_max = axis.word_range
            travel[words] = (
                words * span / (word_max - word_min) * 1000 / Fraction(axis.travel_speed_per_s)
            )
        return travel[words]

    def _wheel_settle(self, channel: ChannelName, state: str) -> int | None:
        return self.profile.discrete[DISCRETE_KEYS[channel]].states[state].settle_ms

    def _default_word(self, axis: AxisCapability) -> int:
        return axis.default_word(self.profile.defaults)

    def _ceil(self, value: Fraction | int) -> int:
        return math.ceil(Fraction(value) / self.frame_ms) * self.frame_ms

    def _aim(self, state: _State) -> str:
        parts = []
        for channel, word in state.head.values.words.items():
            axis = self._axis(channel)
            word_min, word_max = axis.word_range
            uninverted = word_min + word_max - word if axis.inverted else word
            span = axis.physical_max - axis.physical_min
            value = axis.physical_min + span * (uninverted - word_min) / (word_max - word_min)
            parts.append(f"{channel.value} {value:g}")
        return ", ".join(parts)

    # --- Reports ----------------------------------------------------------------------

    def _diagnostic(
        self,
        cue_ms: int,
        status: TransitionStatus,
        code: TransitionCode | None,
        required_ms: int | None,
        available_ms: int | None,
        reason: str,
        optical_reveal_ms: int | None = None,
    ) -> TransitionDiagnostic:
        return TransitionDiagnostic(
            fixture_id=self.fixture_id,
            cue_ms=cue_ms,
            status=status,
            code=code,
            required_ms=required_ms,
            available_ms=available_ms,
            optical_reveal_ms=optical_reveal_ms,
            reason=reason,
            provenance=self.profile.provenance,
        )

    def _dependency(
        self, state: _State, target: FixtureSegment, end_ms: int
    ) -> TransitionDependency:
        source = state.source
        return TransitionDependency(
            source_section_id=None if source is None else source.section_id,
            target_section_id=target.section_id,
            fixture_id=self.fixture_id,
            channels=self.channels,
            start_ms=0 if source is None else source.t0_ms,
            end_ms=end_ms,
        )

    def shutter_timing(self, segments: Sequence[FixtureSegment]) -> list[TransitionDiagnostic]:
        """Reject a shutter change that cannot take effect before the next one.

        Covers every change the encoded frames make, including a step's first state and
        changes across step and transaction boundaries, from the run's initial state:
        each must hold for the visibility latency it crosses plus its settle time.
        """
        capability = self.profile.discrete.get("shutter")
        if capability is None or not segments or self.initial is None:
            return []
        visibility = self.profile.visibility
        dark = set(visibility.extinguishing_shutter_states)
        changes = shutter_changes(segments, {self.fixture_id: self.profile})
        previous = self.initial.discrete_states["shutter"]
        problems: list[TransitionDiagnostic] = []
        for change, following in zip(changes, (*changes[1:], None), strict=True):
            if change.to_state == previous:
                continue
            latency: int | None = 0
            if (change.to_state in dark) != (previous in dark):
                closing = change.to_state in dark
                latency = visibility.close_latency_ms if closing else visibility.open_latency_ms
            settle = capability.states[change.to_state].settle_ms
            needed = None if latency is None or settle is None else latency + settle
            hold = None if following is None else following.t_ms - change.t_ms
            if needed is None or (hold is not None and hold < needed):
                takes = "an unknown latency or settle" if needed is None else f"{needed} ms"
                holds = "indefinitely" if hold is None else f"{hold} ms"
                problems.append(
                    self._diagnostic(
                        change.t_ms,
                        "error",
                        "infeasible_transition",
                        needed,
                        hold,
                        f"shutter state {change.to_state!r} after {previous!r} needs {takes} "
                        f"to take effect but holds {holds}",
                    )
                )
            previous = change.to_state
        return problems


def _held(time_ms: int, state: str) -> DiscreteTrajectory:
    return DiscreteTrajectory(events=(DiscretePoint(t_ms=time_ms, state=state),))


def _encoded(axis: AxisCapability, value: Fraction | float) -> int:
    """`axis.dmx_word` of the exact value: an admitted float as is (`dmx_word` takes it
    as the same fraction) without a fraction-to-float range check, anything else as a
    fraction, so a refusal reads as it always has."""
    if isinstance(value, float) and axis.admits(value):
        return axis.dmx_word(value)
    return axis.dmx_word(Fraction(value))


def _frame_levels(
    trajectory: ContinuousTrajectory, start_ms: int, end_ms: int, step_ms: int
) -> Iterator[tuple[int, Fraction]]:
    """The encoder's sample at each frame start in `[start_ms, end_ms)`, in one pass."""
    for time_ms, value in frame_values(trajectory, start_ms, end_ms, step_ms):
        yield time_ms, Fraction(value)


def frame_values(
    trajectory: ContinuousTrajectory, start_ms: int, end_ms: int, step_ms: int
) -> Iterator[tuple[int, Fraction | float]]:
    """`_frame_levels`, with a sample that is a point's own value left as its float."""
    points = trajectory.points
    index = 0
    for time_ms in range(start_ms, end_ms, step_ms):
        while index + 1 < len(points) and points[index + 1].t_ms <= time_ms:
            index += 1
        left = points[index]
        if left.t_ms > time_ms:
            raise ValueError(f"no value is defined at {time_ms} ms")
        if trajectory.interpolation == "hold" or index + 1 == len(points) or left.t_ms == time_ms:
            yield time_ms, left.value
            continue
        right = points[index + 1]
        share = Fraction(time_ms - left.t_ms, right.t_ms - left.t_ms)
        yield time_ms, Fraction(left.value) + (Fraction(right.value) - Fraction(left.value)) * share


def state_at(trajectory: DiscreteTrajectory, time_ms: int) -> str:
    current = [event.state for event in trajectory.events if event.t_ms <= time_ms]
    if not current:
        raise ValueError(f"no discrete state is defined at {time_ms} ms")
    return current[-1]
