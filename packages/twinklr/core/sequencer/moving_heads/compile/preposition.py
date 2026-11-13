"""Feasible dark reposition transactions between physical moving-head cues.

`plan_prepositions` authors every fixture explicitly over the whole sequence: in the
span before each cue a transaction commands darkness, waits until the fixture is
optically dark, turns changed wheels and lets them settle, moves pan/tilt no faster
than the configured speed, waits for the head to arrive and settle, then reveals on the
cue's own aligned frame; after the last cue the fixture parks dark at its last aim.
An unauthored channel would return to its default byte, so nothing is left unauthored.

Darkness comes only from the profile's visibility declaration (dimmer at normalized
zero when `dimmer_zero_extinguishes`, or a shutter state listed in
`extinguishing_shutter_states`), after `close_latency_ms` (plus the shutter state's
`settle_ms` when the shutter is the mechanism), or from the run's initial-state
evidence. Default bytes never establish it and an unknown latency never does.

Motion is judged on the encoded DMX words, as the fixture receives them. The head
follows its commands: a word change at frame time `c` is reached at
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
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict

from twinklr.core.config.fixtures.capabilities import (
    AxisCapability,
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
from twinklr.core.sequencer.moving_heads.compile.physical import shutter_changes

FailureMode = Literal["error", "preserve_aim", "drop_accent"]

FALLBACK_METADATA_KEY = "preposition_fallback"
"""Cue metadata naming the failure mode its effect opts into; the pass mode must match."""

TRANSACTION_METADATA_KEY = "preposition_target"
"""Metadata on an authored segment: the id of the cue it prepares, empty for a park."""

_POSE = (ChannelName.PAN, ChannelName.TILT)
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
        segments: Every fixture's physical cues, on the frame grid, each authoring the
            pan and tilt its profile declares, all ending by `sequence_end_ms`.
        capabilities: Each physical fixture's profile. A fixture without cues parks
            dark at its initial state over the whole sequence.
        initial_states: Run-supplied time-zero states; a missing fixture is unknown,
            which fails every fixture that has a profile.
        locks: Frames no authored segment may cover; spans snap outward to the grid.
        frame_ms: The effect frame grid; must be `EFFECT_GRID_MS`.
        sequence_end_ms: The end of the last frame, on the frame grid.
        failure_mode: The most this pass may substitute when a reposition needs more
            time than it has or an unknown speed, latency or settle. A cue gets it only
            when its own `metadata[FALLBACK_METADATA_KEY]` names the same mode.
            `preserve_aim` plays the cue at the aim the head holds (pan/tilt held
            there, everything else as authored); `drop_accent` keeps the cue dark at
            that aim and plans later cues from there. Neither applies to unknown initial
            state, unknown visibility latency, a missing darkness guarantee, an
            unencodable value or a lock.

    Returns:
        The cues with their transactions and parks, ordered by fixture and time, or no
        segments when any diagnostic is an error.

    Raises:
        ValueError: If `frame_ms` is not the effect grid, `sequence_end_ms` is off the
            grid, a fixture has no profile, or a cue is off the grid, empty, overlaps
            another of its fixture, ends after the sequence or omits its pan or tilt.
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
        )
        out, fixture_diagnostics, fixture_dependencies = planner.plan(by_fixture[fixture_id])
        if not any(diagnostic.status == "error" for diagnostic in fixture_diagnostics):
            fixture_diagnostics += planner.shutter_timing(out)
        planned.extend(out)
        diagnostics.extend(sorted(fixture_diagnostics, key=lambda diagnostic: diagnostic.cue_ms))
        dependencies.extend(fixture_dependencies)

    if any(diagnostic.status == "error" for diagnostic in diagnostics):
        planned = []
    return PrepositionResult(
        segments=tuple(planned), diagnostics=tuple(diagnostics), dependencies=tuple(dependencies)
    )


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
    ) -> None:
        self.fixture_id = fixture_id
        self.profile = profile
        self.initial = initial
        self.frame_ms = frame_ms
        self.end_ms = end_ms
        self.failure_mode = failure_mode
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

    # --- Planning ---------------------------------------------------------------------

    def plan(
        self, segments: Sequence[FixtureSegment]
    ) -> tuple[list[FixtureSegment], list[TransitionDiagnostic], list[TransitionDependency]]:
        ordered = self._checked(segments)
        out: list[FixtureSegment] = []
        diagnostics: list[TransitionDiagnostic] = []
        dependencies: list[TransitionDependency] = []
        if not ordered and self.end_ms == 0:
            return out, diagnostics, dependencies

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
            return out, diagnostics, dependencies

        state = _State(0, self._head(self.initial), None, None, self._evidence(), None)
        last: FixtureSegment | None = None
        for target in ordered:
            available = target.t0_ms - state.start_ms
            status: TransitionStatus = "feasible"
            code: TransitionCode | None = None
            try:
                plan = self._transaction(state, target)
            except _InfeasibleError as failure:
                mode = self._fallback(target, failure)
                if mode is None:
                    fail(state, target, failure)
                    return out, diagnostics, dependencies
                status, code = mode, failure.code
                aim = self._aim(state)
                if mode == "drop_accent":
                    diagnostics.append(
                        self._diagnostic(
                            target.t0_ms,
                            status,
                            code,
                            failure.required_ms,
                            available,
                            f"{failure.reason}; drop_accent keeps the cue dark at the aim "
                            f"{aim} and plans the next cue from there",
                        )
                    )
                    dependencies.append(self._dependency(state, target, target.t1_ms))
                    last = target
                    continue
                try:
                    target = self._hold_aim(target, state.head.values.words)
                    self._check_locks(target.t0_ms, target.t1_ms, _POSE, failure.required_ms)
                    plan = self._transaction(state, target)
                except _InfeasibleError as second:
                    second.reason = f"{failure.reason}; preserve_aim cannot apply: {second.reason}"
                    fail(state, target, second)
                    return out, diagnostics, dependencies
                plan = replace(
                    plan,
                    required_ms=failure.required_ms,
                    reason=f"{failure.reason}; preserve_aim holds pan/tilt at the settled aim "
                    f"{aim} through the cue; {plan.reason}",
                )
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
                return out, diagnostics, dependencies
            out.append(park)
        return out, diagnostics, dependencies

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
        """Follow word commands from `word`; return the motion and the last word."""
        axis = self._axis(channel)
        speed, latency, settle = axis.travel_speed_per_s, axis.latency_ms, axis.settle_ms
        for time_ms, commanded in commands:
            if commanded == word:
                continue
            if motion is None or speed is None or latency is None or settle is None:
                motion = None
            else:
                travel = self._travel_ms(channel, word, commanded)
                arrival = max(motion[0], Fraction(time_ms + latency)) + travel
                motion = (arrival, arrival + settle)
            word = commanded
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

    def _center(self, key: Literal["pan", "tilt", "dimmer"], word: int) -> float:
        """A value that encodes to `word` with margin: the word's center, kept in the window.

        Planner-authored values are always word centers, so no float rounding can land
        on a DMX rounding tie and move the head between two frames that should hold.
        """
        axis = self.profile.axes[key]
        uninverted = axis.full_word - word if axis.inverted else word
        low, high = (Fraction(bound) for bound in axis.operable_range)
        minimum = Fraction(axis.physical_min)
        exact = minimum + (Fraction(axis.physical_max) - minimum) * uninverted / axis.full_word
        value = float(min(max(exact, low), high))
        if not axis.admits(value) or axis.dmx_word(value) != word:
            raise _InfeasibleError(
                "infeasible_transition", f"{key} word {word} cannot be commanded exactly"
            )
        return value

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
                if value.physical is None:
                    raise ValueError(f"{name} {channel.value} is not a physical value")
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
        pose = {ChannelName.PAN: initial.pan_deg, ChannelName.TILT: initial.tilt_deg}
        dimmer = self.profile.axes.get("dimmer")
        level = None if initial.dimmer is None else Fraction(initial.dimmer)
        values = _Values(
            words={ch: self._axis(ch).dmx_word(pose[ch]) for ch in self.pose_channels},
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
        def level(channel: ChannelName) -> Fraction | None:
            value = segment.channels.get(channel)
            if value is None or not isinstance(value.physical, ContinuousTrajectory):
                return None
            return _level_at(value.physical, time_ms)

        def state(channel: ChannelName) -> str | None:
            value = segment.channels.get(channel)
            if value is None or not isinstance(value.physical, DiscreteTrajectory):
                return None
            return _state_at(value.physical, time_ms)

        words = {}
        for channel in self.pose_channels:
            pose = level(channel)
            assert pose is not None  # checked: cues author their pose
            words[channel] = self._axis(channel).dmx_word(pose)
        dimmer = self.profile.axes.get("dimmer")
        authored = level(ChannelName.DIMMER)
        shutter = state(ChannelName.SHUTTER)
        capability = self.profile.discrete.get("shutter")
        return _Values(
            words=words,
            dimmer=authored,
            dimmer_word=(
                None
                if dimmer is None
                else self._default_word(dimmer)
                if authored is None
                else dimmer.dmx_word(authored)
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
            axis = self._axis(channel)
            commands = (
                (t, axis.dmx_word(value))
                for t, value in _frame_levels(physical, segment.t0_ms, segment.t1_ms, self.frame_ms)
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

    def _travel_ms(self, channel: ChannelName, start: int, end: int) -> Fraction:
        """Time to travel between two encoded words at the configured speed."""
        axis = self._axis(channel)
        assert axis.travel_speed_per_s is not None
        span = Fraction(axis.physical_max) - Fraction(axis.physical_min)
        return abs(end - start) * span / axis.full_word * 1000 / Fraction(axis.travel_speed_per_s)

    def _wheel_settle(self, channel: ChannelName, state: str) -> int | None:
        return self.profile.discrete[DISCRETE_KEYS[channel]].states[state].settle_ms

    def _default_word(self, axis: AxisCapability) -> int:
        word = self.profile.defaults[axis.coarse_offset]
        if axis.fine_offset is not None:
            word = word << 8 | self.profile.defaults[axis.fine_offset]
        return word

    def _ceil(self, value: Fraction | int) -> int:
        return math.ceil(Fraction(value) / self.frame_ms) * self.frame_ms

    def _aim(self, state: _State) -> str:
        parts = []
        for channel, word in state.head.values.words.items():
            axis = self._axis(channel)
            uninverted = axis.full_word - word if axis.inverted else word
            span = axis.physical_max - axis.physical_min
            parts.append(
                f"{channel.value} {axis.physical_min + span * uninverted / axis.full_word:g}"
            )
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


def _level_at(trajectory: ContinuousTrajectory, time_ms: int) -> Fraction:
    """The value the encoder samples at a frame start, in exact arithmetic."""
    return next(_frame_levels(trajectory, time_ms, time_ms + 1, 1))[1]


def _frame_levels(
    trajectory: ContinuousTrajectory, start_ms: int, end_ms: int, step_ms: int
) -> Iterator[tuple[int, Fraction]]:
    """The encoder's sample at each frame start in `[start_ms, end_ms)`, in one pass."""
    points = trajectory.points
    index = 0
    for time_ms in range(start_ms, end_ms, step_ms):
        while index + 1 < len(points) and points[index + 1].t_ms <= time_ms:
            index += 1
        left = points[index]
        if left.t_ms > time_ms:
            raise ValueError(f"no value is defined at {time_ms} ms")
        if trajectory.interpolation == "hold" or index + 1 == len(points) or left.t_ms == time_ms:
            yield time_ms, Fraction(left.value)
            continue
        right = points[index + 1]
        share = Fraction(time_ms - left.t_ms, right.t_ms - left.t_ms)
        yield time_ms, Fraction(left.value) + (Fraction(right.value) - Fraction(left.value)) * share


def _state_at(trajectory: DiscreteTrajectory, time_ms: int) -> str:
    current = [event.state for event in trajectory.events if event.t_ms <= time_ms]
    if not current:
        raise ValueError(f"no discrete state is defined at {time_ms} ms")
    return current[-1]
