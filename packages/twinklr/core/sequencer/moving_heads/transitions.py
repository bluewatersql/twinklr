"""The planner's section transitions, played at section boundaries (song-intent W8).

A section's `ENTRY` transition shapes the boundary it starts on, its `EXIT` the one it
ends on; both edges of one boundary name the same change, so where the outgoing
section's `EXIT` and the incoming section's `ENTRY` meet, the `ENTRY` plays and the `EXIT`
is recorded as replaced. The first section's `ENTRY` and the last section's `EXIT` play
against the head at rest (its run's initial pose and darkness), inside the section.

Every value below is a first proposal for the owner's W8 view, not a measured look.

**The window** (`window_for`). `length` counts beats on the detected grid from the bar's
downbeat (`LENGTH_BEATS`, bars of `beats_per_bar` beats). `split` is the share of the
window the outgoing look takes (`SPLIT_SHARE`); its point, the window's start plus that
share, is where the change turns (`split_ms`).

- `crossfade`, `fade_via_black` and `blackout` place the split point on the boundary:
  the window runs from `split` of the length before it to the rest after it;
- `morph` and `sweep` centre the window on the boundary, so the split point falls before
  it (a split under half) or after it;
- `snap` has no blend: its length bounds how early before the boundary the heads may go
  dark to be in place, lit, on the boundary's frame (the wheels turning from the states
  held at that cut); its curve and split shape nothing.

A window stays inside the two parts it joins, ends before the incoming part's first event
that commands darkness or a wheel (`closed`, a strobe, `pulse`, `color`, `gobo`) and
starts after the outgoing part's last such event's span, and after its colour, gobo and hit
events have been seen (`pipeline._seen_until`; the event plays, the transition yields), and
starts after the previous boundary's window; each clamp lands on the frame grid and is
recorded, and where less of the window is left than its mode needs (`MIN_WINDOW_FRAMES`)
it plays on no head. A hit inside it plays on the transition's level; a head whose dark
cut would cover a hit that plays on it without the transition plays no transition.

**What each channel does** (`MODE_STRATEGIES`, overridden per channel by the plan's
`channels`; `zoom` follows `pan`):

- `smooth` (a continuous channel): eases from the outgoing look's value to the incoming
  one's over the window, along the curve, halfway at the split point;
- `crossfade` (the dimmer): the outgoing level eases down to a handover level
  (`CROSSFADE_FLOOR` of the lower of the two looks' levels) at the split point and the
  incoming level eases up from it; on pan or tilt it plays as `smooth` (an aim travels);
- `sweep` (`sweep`'s pan, tilt and dimmer): the outgoing look (aim and level) holds to
  the split point, then the head travels to the incoming look along the curve, lit;
- `snap`: the outgoing value to the split point, the incoming one from it; on pan, tilt
  or a wheel the change happens in a dark cut there;
- `fade_via_black`: as `snap`, with the light fading to dark into the cut and up out of
  it along the curve;
- `sequence`: as `snap`, with the cut made by the shutter (closed before the cut, the
  dimmer held), where the head has a shutter state that extinguishes; else a dimmer cut;
- `dark` (`blackout`): every head is dark over the whole window, whether or not it has a
  cue there (cut to dark at its start, cut in at its end), turning and moving in that
  darkness; the curve shapes nothing.

A colour or gobo wheel never blends: a wheel whose state differs across the boundary
turns in a dark cut at the split point (its strategy shaping the cut's edges; `smooth` or
`crossfade` on a wheel plays as `snap`), as do pan and tilt under a dark strategy, and the
cut replaces the boundary's dark dip (`pipeline._boundary_change`). The cut lasts what the
transaction pass needs for the change (`worst_case_entry_ms`), centred on the split point
by `split` (`fade_via_black` from the boundary, `snap` up to it). A lit move faster than
the head travels (`travel_speed_per_s`), or a cut that does not fit the window, falls back
on that head: a lit move to a dark cut at the split point, a cut that does not fit to no
transition (the boundary's own entry: its dip, its window); each is recorded. A crossfade
whose window events clamp to one side of the boundary has no handover point: its level
eases from the outgoing look to the incoming one.

A transition counts as played on a head only where the head's frames differ from the same
plan rendered without transitions (`pipeline.RenderingPipeline._transitions_played`); where
they do not, its trace says `nothing` and why.

The transition is played on the cues before intensity and hits: it is cut out of the
outgoing and incoming cues and played as its own cues (`TRANSITION_METADATA_KEY`),
which intensity leaves alone (a section's intensity resumes after it with an accent, on
the incoming look's first lit frame) and hits play on. A show's rest darkens it as any cue.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
import functools
import math
from typing import Any, Literal

from easing_functions import (
    BackEaseIn,
    BackEaseInOut,
    BackEaseOut,
    BounceEaseIn,
    BounceEaseOut,
    ElasticEaseIn,
    ElasticEaseOut,
)

from twinklr.core.config.fixtures.capabilities import FixtureCapabilities, InitialFixtureState
from twinklr.core.curves.library import CurveLibrary, build_default_registry
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName, TransitionMode
from twinklr.core.sequencer.models.moving_heads.physical import (
    AXIS_KEYS,
    DISCRETE_KEYS,
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalPoint,
    RenderLock,
)
from twinklr.core.sequencer.models.transition import (
    PlanTransition,
    TransitionChannel,
    TransitionEdge,
    TransitionLength,
    TransitionSplit,
    TransitionStrategy,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    HeadFollow,
    entry_feasible,
    follow_cues,
    follow_lag,
    frame_values,
    state_at,
    worst_case_entry_ms,
)
from twinklr.core.sequencer.moving_heads.compile.step import slice_segment
from twinklr.core.sequencer.moving_heads.export.frame_encoder import quantize_cue
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseError,
    MusicalPhaseMap,
    musical_time_at,
)

FRAME = EFFECT_GRID_MS

TRANSITION_METADATA_KEY = "transition"
"""Metadata on a transition's own cue: the edge that plays it (`entry`, `exit`)."""

LENGTH_BARS: dict[TransitionLength, Fraction | None] = {
    TransitionLength.BEAT: None,
    TransitionLength.HALF_BAR: Fraction(1, 2),
    TransitionLength.BAR: Fraction(1),
    TransitionLength.ONE_AND_HALF_BARS: Fraction(3, 2),
    TransitionLength.TWO_BARS: Fraction(2),
    TransitionLength.THREE_BARS: Fraction(3),
    TransitionLength.FOUR_BARS: Fraction(4),
    TransitionLength.SIX_BARS: Fraction(6),
    TransitionLength.EIGHT_BARS: Fraction(8),
}
"""Each length in bars of the song's meter (`BEAT`: one beat)."""

SPLIT_SHARE: dict[TransitionSplit, Fraction] = {
    TransitionSplit.QUARTER: Fraction(1, 4),
    TransitionSplit.THIRD: Fraction(1, 3),
    TransitionSplit.HALF: Fraction(1, 2),
    TransitionSplit.TWO_THIRDS: Fraction(2, 3),
    TransitionSplit.THREE_QUARTERS: Fraction(3, 4),
}

CROSSFADE_FLOOR = 0.5
"""Proposed (W8). A crossfade hands over at this share of the lower of the two looks'
dimmer levels (a dark look hands over at dark)."""

Behaviour = Literal["smooth", "crossfade", "sweep", "snap", "fade", "sequence", "dark"]
"""What a channel does across the window (the module docstring)."""

_POSE = (ChannelName.PAN, ChannelName.TILT)
_WHEELS = (ChannelName.COLOR, ChannelName.GOBO)
_CHANNELS: dict[TransitionChannel, ChannelName] = {
    TransitionChannel.PAN: ChannelName.PAN,
    TransitionChannel.TILT: ChannelName.TILT,
    TransitionChannel.DIMMER: ChannelName.DIMMER,
    TransitionChannel.SHUTTER: ChannelName.SHUTTER,
    TransitionChannel.COLOR: ChannelName.COLOR,
    TransitionChannel.GOBO: ChannelName.GOBO,
}

MODE_STRATEGIES: dict[TransitionMode, dict[ChannelName, Behaviour]] = {
    TransitionMode.SNAP: dict.fromkeys(
        (*_POSE, ChannelName.DIMMER, ChannelName.SHUTTER, *_WHEELS), "snap"
    ),
    TransitionMode.CROSSFADE: {
        ChannelName.PAN: "smooth",
        ChannelName.TILT: "smooth",
        ChannelName.DIMMER: "crossfade",
        ChannelName.SHUTTER: "snap",
        ChannelName.COLOR: "snap",
        ChannelName.GOBO: "snap",
    },
    TransitionMode.MORPH: {
        ChannelName.PAN: "smooth",
        ChannelName.TILT: "smooth",
        ChannelName.DIMMER: "smooth",
        ChannelName.SHUTTER: "snap",
        ChannelName.COLOR: "snap",
        ChannelName.GOBO: "snap",
    },
    TransitionMode.SWEEP: {
        ChannelName.PAN: "sweep",
        ChannelName.TILT: "sweep",
        ChannelName.DIMMER: "sweep",
        ChannelName.SHUTTER: "snap",
        ChannelName.COLOR: "snap",
        ChannelName.GOBO: "snap",
    },
    TransitionMode.FADE_VIA_BLACK: dict.fromkeys(
        (*_POSE, ChannelName.DIMMER, ChannelName.SHUTTER, *_WHEELS), "fade"
    ),
    TransitionMode.BLACKOUT: dict.fromkeys(
        (*_POSE, ChannelName.DIMMER, ChannelName.SHUTTER, *_WHEELS), "dark"
    ),
}
"""Proposed (W8). What each mode does on each channel group."""

_STRATEGY: dict[TransitionStrategy, Behaviour] = {
    TransitionStrategy.SMOOTH_INTERPOLATION: "smooth",
    TransitionStrategy.CROSSFADE: "crossfade",
    TransitionStrategy.SNAP: "snap",
    TransitionStrategy.FADE_VIA_BLACK: "fade",
    TransitionStrategy.SEQUENCE: "sequence",
}

MIN_WINDOW_FRAMES: dict[TransitionMode, int] = {
    TransitionMode.SNAP: 1,
    TransitionMode.CROSSFADE: 4,
    TransitionMode.MORPH: 4,
    TransitionMode.SWEEP: 4,
    TransitionMode.FADE_VIA_BLACK: 4,
    TransitionMode.BLACKOUT: 1,
}
"""Proposed (W8 fix round). The least of its window, in frames, a transition the events
it yields to have shortened still plays in; less, it plays on no head."""

LIT_MODES = frozenset({TransitionMode.CROSSFADE, TransitionMode.MORPH, TransitionMode.SWEEP})
SPLIT_ON_BOUNDARY = frozenset(
    {TransitionMode.CROSSFADE, TransitionMode.FADE_VIA_BLACK, TransitionMode.BLACKOUT}
)


def length_beats(length: TransitionLength, beats_per_bar: int) -> Fraction:
    """A transition length in beats of the song's meter."""
    bars = LENGTH_BARS[length]
    return Fraction(1) if bars is None else bars * beats_per_bar


def resolved_strategies(
    transition: PlanTransition, profile: FixtureCapabilities | None = None
) -> tuple[dict[ChannelName, Behaviour], list[str]]:
    """What each channel does under `transition` (its mode's, each per-channel strategy
    applied), and why any strategy plays as something else: on a channel the head lacks
    (left out), or one it cannot take (a wheel or the shutter cannot blend; an aim cannot
    cross-fade; `sequence` without a shutter state that extinguishes). `zoom` follows
    `pan`."""
    behaviours = dict(MODE_STRATEGIES[transition.mode])
    notes: list[str] = []
    for entry in transition.channels:
        channel = _CHANNELS[entry.channel]
        wanted = _STRATEGY[entry.strategy]
        if transition.mode is TransitionMode.BLACKOUT:
            notes.append(f"{entry.channel.value} {entry.strategy.value}: it changes in the dark")
            continue
        if profile is not None and not _has(profile, channel):
            notes.append(
                f"{entry.channel.value} {entry.strategy.value}: the head has no such channel"
            )
            continue
        plays = wanted
        if channel in (*_WHEELS, ChannelName.SHUTTER) and wanted in ("smooth", "crossfade"):
            plays = "snap"
            notes.append(
                f"{entry.channel.value} {entry.strategy.value}: a "
                f"{'wheel' if channel in _WHEELS else 'shutter'} cannot blend; it plays as snap"
            )
        elif channel in _POSE and wanted == "crossfade":
            plays = "smooth"
            notes.append(f"{entry.channel.value} crossfade: an aim travels; it plays as smooth")
        elif wanted == "sequence" and profile is not None and _shutter_dark(profile) is None:
            plays = "snap"
            notes.append(
                f"{entry.channel.value} sequence: the head has no shutter state that goes "
                "dark; it plays as snap (a dimmer cut)"
            )
        behaviours[channel] = plays
    return behaviours, notes


def _has(profile: FixtureCapabilities, channel: ChannelName) -> bool:
    if channel in AXIS_KEYS:
        return AXIS_KEYS[channel] in profile.axes
    return DISCRETE_KEYS[channel] in profile.discrete


def _shutter_dark(profile: FixtureCapabilities) -> str | None:
    shutter = profile.discrete.get("shutter")
    if (
        shutter is None
        or shutter.closed_state is None
        or shutter.closed_state not in profile.visibility.extinguishing_shutter_states
    ):
        return None
    return shutter.closed_state


# --- the curve -----------------------------------------------------------------------------

_SAMPLES = 512

_EASING_ONLY: dict[CurveLibrary, Any] = {
    CurveLibrary.EASE_IN_BACK: BackEaseIn,
    CurveLibrary.EASE_OUT_BACK: BackEaseOut,
    CurveLibrary.EASE_IN_OUT_BACK: BackEaseInOut,
    CurveLibrary.BOUNCE_IN: BounceEaseIn,
    CurveLibrary.BOUNCE_OUT: BounceEaseOut,
    CurveLibrary.ELASTIC_IN: ElasticEaseIn,
    CurveLibrary.ELASTIC_OUT: ElasticEaseOut,
}
"""Curves whose overshoot the curve library's point model refuses: evaluated with the
easing functions the library's own generators use."""


@functools.cache
def easing(curve: CurveLibrary) -> tuple[Callable[[float], float], str]:
    """The curve as a transition's progress, 0 at the window's start to 1 at its end, and
    how it plays: its own shape where it rises over its cycle (an easing, overshoot kept),
    turned over where it falls, else `linear` (a wave, a hold or a decay has no single
    rise; the trace says so)."""
    if curve in _EASING_ONLY:
        function = _EASING_ONLY[curve](start=0.0, end=1.0, duration=1.0)
        return (lambda p: float(function.ease(p))), curve.value
    points = build_default_registry().get(curve.value).generator(_SAMPLES + 1)
    values = [float(point.v) for point in points]
    # The library samples [0, 1) at i/n: the last sample stands for p = 1.
    first, last = values[0], values[-1]
    if abs(last - first) < 0.5:
        return (lambda p: p), "linear"

    def shape(p: float) -> float:
        x = min(max(p, 0.0), 1.0) * _SAMPLES
        i = min(int(x), _SAMPLES - 1)
        v = values[i] + (values[i + 1] - values[i]) * (x - i)
        return (v - first) / (last - first)

    return shape, curve.value if last > first else f"{curve.value} (turned over)"


def warped(p: float, split: float) -> float:
    """Progress `p` through the window remapped so the split point is the change's middle."""
    if split <= 0 or split >= 1:
        return p
    return 0.5 * p / split if p < split else 0.5 + 0.5 * (p - split) / (1 - split)


# --- the window ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Window:
    """Where a transition plays: `[start_ms, end_ms)` on the frame grid, its split point,
    and the boundary it shapes; `edge` the edge that plays it; `rest` where the head rests
    (no look on that side: the song's first `ENTRY`, its last `EXIT`)."""

    transition: PlanTransition
    edge: TransitionEdge
    boundary_ms: int
    start_ms: int
    end_ms: int
    split_ms: int
    rest: Literal["before", "after"] | None
    clamps: tuple[str, ...] = ()
    not_played: str | None = None
    """Why it plays on no head: the events it yields to leave less of it than its mode
    needs (`MIN_WINDOW_FRAMES`)."""

    @property
    def mode(self) -> TransitionMode:
        return self.transition.mode

    @property
    def split(self) -> float:
        return float(SPLIT_SHARE[self.transition.split])

    def record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "edge": self.edge.value,
            "mode": self.mode.value,
            "length": self.transition.length.value,
            "curve": self.transition.curve.value,
            "split": self.transition.split.value,
            "boundary_ms": self.boundary_ms,
            "window_ms": [self.start_ms, self.end_ms],
            "split_ms": self.split_ms,
        }
        if self.transition.channels:
            record["channels"] = {
                entry.channel.value: entry.strategy.value for entry in self.transition.channels
            }
        if self.rest is not None:
            record["against"] = "the head at rest (its initial pose, dark)"
        if self.clamps:
            record["clamped"] = list(self.clamps)
        if self.not_played:
            record["not_played"] = self.not_played
        return record


def _at(phase_map: MusicalPhaseMap, origin_ms: float, beats: Fraction) -> int | None:
    try:
        return quantize_cue(
            round(musical_time_at(phase_map, beats, origin_ms=origin_ms, period_beats=1))
        ).actual_ms
    except MusicalPhaseError:
        return None


def window_for(
    transition: PlanTransition,
    edge: TransitionEdge,
    *,
    boundary_ms: float,
    phase_map: MusicalPhaseMap,
    beats_per_bar: int,
    earliest_ms: int,
    latest_ms: int,
    rest: Literal["before", "after"] | None = None,
    not_before: Sequence[tuple[str, int]] = (),
    not_after: Sequence[tuple[str, int]] = (),
) -> Window:
    """The window `transition` plays in at the boundary `boundary_ms` (the bar's downbeat,
    exact): placed by its mode (the module docstring), on the frame grid, inside
    `[earliest_ms, latest_ms)` (the two parts it joins; where the head rests on one side,
    only the other); `not_before` and `not_after` (`why, ms`) narrow it further (events,
    the previous window), each recorded where it does."""
    length = length_beats(transition.length, beats_per_bar)
    split = SPLIT_SHARE[transition.split]
    boundary = quantize_cue(round(boundary_ms)).actual_ms
    if transition.mode is TransitionMode.SNAP:
        before, after = length, Fraction(0)
    elif rest == "before":
        before, after = Fraction(0), length
    elif rest == "after":
        before, after = length, Fraction(0)
    elif transition.mode in SPLIT_ON_BOUNDARY:
        before, after = split * length, (1 - split) * length
    else:
        before, after = length / 2, length / 2
    start = _at(phase_map, boundary_ms, -before) if before else boundary
    end = _at(phase_map, boundary_ms, after) if after else boundary
    notes: list[str] = []
    if start is None or start < earliest_ms:
        if start is not None:
            notes.append("it starts no earlier than the part it leaves")
        start = max(earliest_ms, 0 if start is None else start)
    if end is None or end > latest_ms:
        if end is not None:
            notes.append("it ends no later than the part it enters")
        end = latest_ms
    planned = (start, end)
    for why, ms in not_before:
        ms = math.ceil(ms / FRAME) * FRAME  # on the frame grid, never earlier
        if start < ms:
            start = min(ms, boundary)
            notes.append(why)
    for why, ms in not_after:
        ms = math.floor(ms / FRAME) * FRAME
        if ms < end:
            end = max(ms, boundary)
            notes.append(why)
    start, end = min(start, boundary), max(end, boundary)
    not_played = None
    least = MIN_WINDOW_FRAMES[transition.mode] * FRAME
    if (start, end) != planned and end - start < least:
        not_played = (
            f"the events it yields to leave {end - start} ms of its window, less than the "
            f"{least} ms a {transition.mode.value} needs"
        )
    if transition.mode in SPLIT_ON_BOUNDARY or transition.mode is TransitionMode.SNAP:
        split_ms = boundary if rest is None else start + round(float(split) * (end - start))
    else:
        split_ms = start + round(float(split) * (end - start))
    split_ms = min(max(start, quantize_cue(split_ms).actual_ms), end)
    return Window(
        transition=transition,
        edge=edge,
        boundary_ms=boundary,
        start_ms=start,
        end_ms=end,
        split_ms=split_ms,
        rest=rest,
        clamps=tuple(notes),
        not_played=not_played,
    )


# --- one head's look over the window ---------------------------------------------------------


@dataclass
class _Look:
    """One head's look at each frame of a span, read from its cues (or its rest): the
    pose in degrees, the dimmer level, the shutter, colour and gobo states, and whether
    a cue covers the frame."""

    pose: dict[ChannelName, dict[int, float]] = field(default_factory=dict)
    dimmer: dict[int, float] = field(default_factory=dict)
    states: dict[ChannelName, dict[int, str]] = field(default_factory=dict)
    covered: set[int] = field(default_factory=set)


def _read(cues: Sequence[FixtureSegment], profile: FixtureCapabilities) -> _Look:
    look = _Look()
    axis = profile.axes.get("dimmer")
    for cue in cues:
        times = range(cue.t0_ms, cue.t1_ms, FRAME)
        look.covered.update(times)
        for channel in (*_POSE, ChannelName.ZOOM):
            value = cue.channels.get(channel)
            if value is not None and isinstance(value.physical, ContinuousTrajectory):
                for t, v in frame_values(value.physical, cue.t0_ms, cue.t1_ms, FRAME):
                    look.pose.setdefault(channel, {})[t] = float(v)
        dimmer = cue.channels.get(ChannelName.DIMMER)
        if axis is not None:
            if dimmer is not None and isinstance(dimmer.physical, ContinuousTrajectory):
                for t, v in frame_values(dimmer.physical, cue.t0_ms, cue.t1_ms, FRAME):
                    look.dimmer[t] = float(v)
            else:
                level = axis.word_center(axis.default_word(profile.defaults))
                look.dimmer.update(dict.fromkeys(times, float(level)))
        for channel in (ChannelName.SHUTTER, *_WHEELS):
            key = DISCRETE_KEYS[channel]
            if key not in profile.discrete:
                continue
            value = cue.channels.get(channel)
            for t in times:
                look.states.setdefault(channel, {})[t] = (
                    state_at(value.physical, t)
                    if value is not None and isinstance(value.physical, DiscreteTrajectory)
                    else profile.discrete[key].default_state
                )
    return look


def _rest_look(initial: InitialFixtureState, profile: FixtureCapabilities) -> _Look:
    """The head at rest: its initial pose, dark; its wheels are the other look's."""
    look = _Look()
    pose = initial.pose
    for channel in (*_POSE, ChannelName.ZOOM):
        if AXIS_KEYS[channel] in profile.axes and pose.get(AXIS_KEYS[channel]) is not None:
            look.pose[channel] = {-1: float(pose[AXIS_KEYS[channel]])}
    return look


def _value(series: Mapping[int, float], t: int, *, before: bool) -> float | None:
    """The value at `t`, else the nearest one on the side the look holds to (`before`:
    its last value at or before `t`; else its first at or after)."""
    if t in series:
        return series[t]
    if not series:
        return None
    if -1 in series:  # a rest pose holds everywhere
        return series[-1]
    keys = sorted(series)
    candidates = [k for k in keys if k <= t] if before else [k for k in keys if k >= t]
    if not candidates:
        candidates = keys
        return series[candidates[0] if before else candidates[-1]]
    return series[candidates[-1] if before else candidates[0]]


# --- playing one head ------------------------------------------------------------------------


@dataclass
class HeadTransition:
    """What a transition plays on one head: the outgoing cues as cut (replacing the head's
    outgoing cues), the transition's own cues, the incoming cues as cut, and the trace
    entry. `carries_wheels` where its darkness turns the wheels in place of the
    boundary's dip."""

    outgoing: list[FixtureSegment]
    own: list[FixtureSegment]
    incoming: list[FixtureSegment]
    record: dict[str, Any]
    carries_wheels: bool = False
    lighting: _Light | None = None
    """How its dimmer is made, so it can be played again on the outgoing look as
    intensity shaped it (`relit`)."""

    def relit(self, out_gain: float) -> list[FixtureSegment]:
        """The transition's own cues with the outgoing look's levels scaled by `out_gain`
        (intensity's gain on the outgoing look's last frame before the window)."""
        if self.lighting is None or out_gain == 1.0:
            return list(self.own)
        levels = self.lighting.levels(out_gain)
        out = []
        for cue in self.own:
            dimmer = cue.channels.get(ChannelName.DIMMER)
            if dimmer is None:
                out.append(cue)
                continue
            points: list[PhysicalPoint] = []
            for t in range(cue.t0_ms, cue.t1_ms, FRAME):
                if not points or points[-1].value != levels[t]:
                    points.append(PhysicalPoint(t_ms=t, value=levels[t]))
            channels = dict(cue.channels)
            channels[ChannelName.DIMMER] = ChannelValue(
                channel=ChannelName.DIMMER,
                physical=ContinuousTrajectory(
                    unit="normalized", points=tuple(points), interpolation="hold"
                ),
            )
            out.append(cue.model_copy(update={"channels": channels}))
        return out


@dataclass(frozen=True)
class HeadContext:
    """What the transaction pass needs to judge one head's cues: its profile, its run's
    initial state, the locks, and how the head stands after its cues before the
    outgoing ones; and the frames of events that play on this head without the
    transition, which its darkness may not cover (`protected`: label, frame)."""

    profile: FixtureCapabilities
    initial: InitialFixtureState | None
    locks: Sequence[RenderLock]
    before: HeadFollow | None
    protected: Sequence[tuple[str, int]] = ()


def play_head(
    window: Window,
    outgoing: Sequence[FixtureSegment],
    incoming: Sequence[FixtureSegment],
    context: HeadContext,
    *,
    identity: FixtureSegment,
    edge_label: str,
) -> HeadTransition:
    """`window`'s transition on one head (`outgoing` and `incoming`: its cues on each
    side, in time order; one side empty where the head rests there). Tries the mode as resolved; a lit move too fast for the head
    moves in a dark cut at the split point; where that cut, or any darkness it adds,
    would cover an event that plays on the head without the transition, where a cut
    does not fit the window, or where the transaction pass cannot play a join, the head
    plays no transition (its boundary's own entry; the record says why). A head it
    changes nothing on is recorded `plays: nothing (…)`."""
    behaviours, notes = resolved_strategies(window.transition, context.profile)
    if window.end_ms <= window.start_ms:
        why = (
            "the plain cut: the heads rest dark before the song's first section and are "
            "moved into place in the dark before its first cue"
            if window.rest == "before" and window.mode is TransitionMode.SNAP
            else "its window has no frames here"
        )
        return HeadTransition(
            outgoing=list(outgoing),
            own=[],
            incoming=list(incoming),
            record={"plays": f"nothing: {why}"},
        )
    attempt = _attempt(window, outgoing, incoming, context, behaviours, identity, edge_label)
    fallback = None
    if isinstance(attempt, _Lit):
        moved = {
            channel: "snap" if channel in _POSE and behaviour in ("smooth", "sweep") else behaviour
            for channel, behaviour in behaviours.items()
        }
        fallback = f"{attempt.why}: the aim moves in a dark cut at the split point instead"
        attempt = _attempt(window, outgoing, incoming, context, moved, identity, edge_label)
        if isinstance(attempt, _Lit):
            attempt = attempt.why
    if isinstance(attempt, _Nothing):
        record: dict[str, Any] = {"plays": f"nothing: {attempt.why}"}
    elif isinstance(attempt, str):
        record = {"not_played": attempt}
    else:
        if fallback is not None:
            attempt.record["fallback"] = fallback
        if notes:
            attempt.record["strategies_played_otherwise"] = notes
        return attempt
    if notes:
        record["strategies_played_otherwise"] = notes
    return HeadTransition(outgoing=list(outgoing), own=[], incoming=list(incoming), record=record)


@dataclass(frozen=True)
class _Nothing:
    """A head the transition has nothing to change on, and why."""

    why: str


@dataclass(frozen=True)
class _Lit:
    """A lit move the head cannot travel, and why (it falls back to a dark cut)."""

    why: str


@dataclass
class _Sides:
    """One head's two looks around its own window `[start_ms, end_ms)` and split point,
    and how its channels change between them (`behaviours`, the curve's `shape`)."""

    window: Window
    outgoing: Sequence[FixtureSegment]
    incoming: Sequence[FixtureSegment]
    out_look: _Look
    in_look: _Look
    profile: FixtureCapabilities
    behaviours: Mapping[ChannelName, Behaviour]
    start_ms: int
    end_ms: int
    split_ms: int
    shape: Callable[[float], float]
    state_ms: int = 0
    """Where the outgoing look's wheel states are read: the window's start, or `snap`'s
    dark cut."""

    def __post_init__(self) -> None:
        self.state_ms = self.start_ms

    def p(self, t: int) -> float:
        span = self.end_ms - self.start_ms
        return 0.0 if span <= FRAME else min(1.0, (t - self.start_ms) / (span - FRAME))

    def out_dim(self, t: int) -> float:
        """The outgoing level at `t`: dark where it has no cue (a gap, its rest), its last
        level held past its last cue."""
        end = self.outgoing[-1].t1_ms if self.outgoing else self.start_ms
        if not self.outgoing or (t not in self.out_look.covered and t < end):
            return 0.0
        return _value(self.out_look.dimmer, t, before=True) or 0.0

    def in_dim(self, t: int) -> float:
        """The incoming level at `t`: dark where it has no cue, its first level held
        before its first cue."""
        start = self.incoming[0].t0_ms if self.incoming else self.end_ms
        if not self.incoming or (t not in self.in_look.covered and t >= start):
            return 0.0
        return _value(self.in_look.dimmer, t, before=False) or 0.0

    def out_state(self, channel: ChannelName) -> str | None:
        series = self.out_look.states.get(channel) or self.in_look.states.get(channel)
        if not series:
            return None
        return series.get(self.state_ms - FRAME) or _state_near(series, self.state_ms, before=True)

    def in_state(self, channel: ChannelName) -> str | None:
        series = self.in_look.states.get(channel) or self.out_look.states.get(channel)
        if not series:
            return None
        return series.get(self.end_ms) or _state_near(series, self.end_ms - FRAME, before=False)

    @property
    def pose_channels(self) -> list[ChannelName]:
        return [
            c
            for c in (*_POSE, ChannelName.ZOOM)
            if c in self.out_look.pose and c in self.in_look.pose
        ]

    def pose_at(self, channel: ChannelName, t: int) -> float:
        behaviour = self.behaviours.get(
            ChannelName.PAN if channel is ChannelName.ZOOM else channel, "smooth"
        )
        out_v = _value(self.out_look.pose[channel], t, before=True)
        in_v = _value(self.in_look.pose[channel], t, before=False)
        held = _value(self.out_look.pose[channel], self.start_ms - FRAME, before=True)
        assert out_v is not None and in_v is not None and held is not None
        s = self.split_ms
        if behaviour in ("smooth", "crossfade"):
            value = out_v + (in_v - out_v) * self.shape(warped(self.p(t), self.window.split))
        elif behaviour == "sweep":
            q = 0.0 if t < s else (t - s + FRAME) / max(FRAME, self.end_ms - s)
            value = held + (in_v - held) * self.shape(min(1.0, q))
        else:  # snap, fade, sequence, dark: the outgoing aim to the split point
            value = out_v if t < s else in_v
        return _clamped(self.profile, channel, value)

    def wheels_turn(self) -> list[ChannelName]:
        return [
            c
            for c in _WHEELS
            if (state := self.out_state(c)) is not None and state != self.in_state(c)
        ]

    def dark_pose(self) -> list[ChannelName]:
        s = self.split_ms
        return [
            c
            for c in _POSE
            if c in self.pose_channels
            and self.behaviours.get(c) in ("snap", "fade", "sequence", "dark")
            and _moves(
                self.profile,
                c,
                _value(self.out_look.pose[c], s - FRAME, before=True),
                _value(self.in_look.pose[c], s, before=False),
            )
        ]

    def need_ms(self, last_lit_ms: int, first_lit_ms: int) -> int | None:
        return _need_ms(
            self.profile,
            self.pose_channels,
            self.pose_at,
            self.out_state,
            self.in_state,
            last_lit_ms,
            first_lit_ms,
        )


def _sides(
    window: Window,
    outgoing: Sequence[FixtureSegment],
    incoming: Sequence[FixtureSegment],
    context: HeadContext,
    behaviours: Mapping[ChannelName, Behaviour],
) -> _Sides | _Nothing | str:
    """The head's two looks and its own window: inside the cues that run unbroken into the
    boundary on each side (the transaction pass moves a head only between its cues, in the
    dark, so a lit blend cannot reach across a gap); from rest, no earlier than the head
    can be revealed. `blackout` and `snap` keep the boundary's window: darkness needs no
    cue to blend."""
    profile = context.profile
    rest = None if context.initial is None else _rest_look(context.initial, profile)
    out_look = _read(outgoing, profile) if outgoing else rest
    in_look = _read(incoming, profile) if incoming else rest
    if out_look is None or in_look is None:
        return "the head's initial state is unknown, so it has no rest to transition with"
    mode, boundary = window.mode, window.boundary_ms
    w0, w1, s = window.start_ms, window.end_ms, window.split_ms
    if mode is TransitionMode.SNAP:
        if incoming and incoming[0].t0_ms > boundary:
            return _Nothing(
                "the plain cut: the head enters the section dark, with nothing to be in place for"
            )
    elif mode is not TransitionMode.BLACKOUT:
        if outgoing:
            run = _run_into(outgoing, boundary)
            w0 = boundary if run is None else max(w0, run)
        elif window.rest == "before" and context.initial is not None:
            w0 = max(w0, _from_rest_ms(profile, context.initial, in_look, w0))
        if incoming:
            run = _run_from(incoming, boundary)
            w1 = boundary if run is None else min(w1, run)
        if w1 - w0 < 2 * FRAME:
            return _Nothing("the head is dark on both sides of the boundary (between its cues)")
    if mode in SPLIT_ON_BOUNDARY or mode is TransitionMode.SNAP:
        s = min(max(s, w0), w1)
    else:
        s = min(max(w0, w0 + round(window.split * (w1 - w0) / FRAME) * FRAME), w1)
    shape, _ = easing(window.transition.curve)
    return _Sides(
        window=window,
        outgoing=outgoing,
        incoming=incoming,
        out_look=out_look,
        in_look=in_look,
        profile=profile,
        behaviours=behaviours,
        start_ms=w0,
        end_ms=w1,
        split_ms=s,
        shape=shape,
    )


def _dark_cut(sides: _Sides, light: Behaviour, needs: bool) -> tuple[int, int] | None | str:
    """The dark cut the change needs (None when it needs none), placed by the mode: a
    `blackout`'s whole window (longer where the change needs more), `snap`'s up to the
    boundary (the outgoing wheels read at its start), `fade_via_black`'s from the boundary,
    a lit mode's around its split point by `split`; or why it does not fit."""
    if not needs:
        return None
    window, mode = sides.window, sides.window.mode
    s, w0, w1 = sides.split_ms, sides.start_ms, sides.end_ms
    need = sides.need_ms(s - FRAME, s)
    gap: tuple[int, int] | None = None
    for _ in range(4):
        if need is None:
            return "a term of the change in the dark (a speed, latency or settle) is unknown"
        if mode is TransitionMode.BLACKOUT:
            gap = (w0, max(w1, w0 + need))
        elif mode is TransitionMode.SNAP:
            gap = (window.boundary_ms - need, window.boundary_ms)
            sides.state_ms = gap[0]  # the wheels it turns are the ones held at its cut
        elif light == "fade" and window.rest is None:
            gap = (window.boundary_ms, window.boundary_ms + need)
        else:
            lead = quantize_cue(round(window.split * need)).actual_ms
            start = max(w0, min(s - lead, w1 - need))
            gap = (start, start + need)
        exact = sides.need_ms(gap[0] - FRAME, gap[1])
        if exact is None or exact <= gap[1] - gap[0]:
            break
        need = exact
    assert gap is not None
    if mode is TransitionMode.SNAP and gap[0] < w0:
        return (
            f"the {gap[1] - gap[0]} ms of darkness the heads need to be in place does not fit "
            f"the {w1 - w0} ms before the boundary the length allows"
        )
    if mode in LIT_MODES and (gap[0] < w0 or gap[1] > w1):
        return (
            f"the {gap[1] - gap[0]} ms of darkness the change needs at the split point does "
            f"not fit the {w1 - w0} ms window"
        )
    return gap


def _attempt(
    window: Window,
    outgoing: Sequence[FixtureSegment],
    incoming: Sequence[FixtureSegment],
    context: HeadContext,
    behaviours: Mapping[ChannelName, Behaviour],
    identity: FixtureSegment,
    edge_label: str,
) -> HeadTransition | _Nothing | _Lit | str:
    """One try at the head's transition: the head's new cues; nothing to change; a lit
    move too fast (`_Lit`); or why it cannot play (a string)."""
    sides = _sides(window, outgoing, incoming, context, behaviours)
    if not isinstance(sides, _Sides):
        return sides
    profile, mode = context.profile, window.mode
    light = behaviours.get(ChannelName.DIMMER, "smooth")
    one_sided = (
        light == "crossfade"
        and window.rest is None
        and sides.split_ms in (sides.start_ms, sides.end_ms)
    )
    if one_sided:
        # Clamped to one side of the boundary there is no handover point: the level
        # eases from the outgoing look to the incoming one (no jump at either edge).
        light = "smooth"
    dark_by = [*_POSE, *_WHEELS, ChannelName.SHUTTER, ChannelName.DIMMER]
    edges_fade = any(behaviours.get(c) == "fade" for c in dark_by)
    edges_shutter = (
        any(behaviours.get(c) == "sequence" for c in dark_by) and _shutter_dark(profile) is not None
    )
    wheels_turn, dark_pose = sides.wheels_turn(), sides.dark_pose()
    needs_dark = (
        bool(wheels_turn)
        or bool(dark_pose)
        or light in ("fade", "sequence", "dark")
        or mode is TransitionMode.BLACKOUT
    )
    if mode is TransitionMode.SNAP and not needs_dark:
        return _Nothing("the plain cut: nothing to move or turn before the boundary")
    gap = _dark_cut(sides, light, needs_dark)
    if isinstance(gap, str):
        return gap
    if mode is TransitionMode.SNAP:
        wheels_turn = sides.wheels_turn()  # read again at the cut
    if gap is not None:
        covered = [label for label, at in context.protected if gap[0] <= at < gap[1]]
        if covered:
            return (
                f"its darkness ({gap[0]}-{gap[1]} ms) would cover the {covered[0]}, which "
                "plays on this head without the transition"
            )
        if (
            mode in (TransitionMode.FADE_VIA_BLACK, TransitionMode.BLACKOUT)
            and gap[1] > sides.end_ms
        ):
            sides.end_ms = gap[1]  # the darkness outlasts the window: the light comes up after
    w0, w1, s = sides.start_ms, sides.end_ms, sides.split_ms
    if mode is TransitionMode.SNAP:
        assert gap is not None
        kept_out, kept_in = _cut(outgoing, end_ms=gap[0]), list(incoming)
        spans: list[tuple[int, int]] = []
    else:
        kept_out, kept_in = _cut(outgoing, end_ms=w0), _cut(incoming, start_ms=w1)
        spans = [(w0, gap[0]), (gap[1], w1)] if gap is not None else [(w0, s), (s, w1)]
    lighting = _lighting(sides, light, spans, gap if edges_fade else None)
    own = _own_cues(
        sides, spans, lighting.levels(), gap if edges_shutter else None, identity, edge_label
    )
    too_fast = _too_fast(own, profile)
    if too_fast is not None:
        return _Lit(too_fast)
    joins_ok, why = _joins(kept_out, own, kept_in, context, gap)
    if not joins_ok:
        return why
    levels = lighting.levels()
    record: dict[str, Any] = {
        "plays": _describe(
            mode, gap, wheels_turn, dark_pose, window.rest, one_sided, _ends(levels, spans)
        )
    }
    if mode not in (TransitionMode.SNAP, TransitionMode.BLACKOUT):
        record["curve_played"] = easing(window.transition.curve)[1]
    if (w0, w1, s) != (window.start_ms, window.end_ms, window.split_ms):
        record["window_ms"] = [w0, w1]
        record["split_ms"] = s
    if gap is not None:
        record["dark_ms"] = [gap[0], gap[1]]
        if gap[1] > window.end_ms:
            record["dark_outlasts_window_to_ms"] = gap[1]
    if wheels_turn:
        record["wheels_turn"] = {
            c.value: [sides.out_state(c), sides.in_state(c)] for c in wheels_turn
        }
    return HeadTransition(
        outgoing=kept_out,
        own=own,
        incoming=kept_in,
        record=record,
        carries_wheels=bool(wheels_turn) and gap is not None,
        lighting=lighting if "dimmer" in profile.axes else None,
    )


def _ends(levels: Mapping[int, float], spans: Sequence[tuple[int, int]]) -> tuple[float, float]:
    """The transition's first and last level (0 where it has no lit frames)."""
    times = sorted(t for a, b in spans for t in range(a, b, FRAME))
    return (levels.get(times[0], 0.0), levels.get(times[-1], 0.0)) if times else (0.0, 0.0)


def _lighting(
    sides: _Sides,
    light: Behaviour,
    spans: Sequence[tuple[int, int]],
    fade_gap: tuple[int, int] | None,
) -> _Light:
    """How the transition's dimmer is made on each of its frames: the two looks' levels,
    the progress, and (with `fade_gap`) the fade into and out of the dark cut."""
    w0, w1 = sides.start_ms, sides.end_ms
    frames: list[tuple[int, float, float, float, float]] = []
    for a, b in spans:
        for t in range(a, b, FRAME):
            factor = 1.0
            if fade_gap is not None:
                if t < fade_gap[0]:
                    factor = 1.0 - sides.shape(
                        min(1.0, (t - w0 + FRAME) / max(FRAME, fade_gap[0] - w0))
                    )
                else:
                    factor = sides.shape(
                        min(1.0, (t - fade_gap[1] + FRAME) / max(FRAME, w1 - fade_gap[1]))
                    )
                factor = min(1.0, max(0.0, factor))
            frames.append((t, sides.out_dim(t), sides.in_dim(t), sides.p(t), factor))
    return _Light(
        start_ms=w0,
        end_ms=w1,
        split_ms=sides.split_ms,
        split=sides.window.split,
        curve=sides.window.transition.curve,
        behaviour=light,
        frames=tuple(frames),
    )


def _own_cues(
    sides: _Sides,
    spans: Sequence[tuple[int, int]],
    levels: Mapping[int, float],
    shutter_gap: tuple[int, int] | None,
    identity: FixtureSegment,
    edge_label: str,
) -> list[FixtureSegment]:
    """The transition's own cues, one per span (before the cut, after it): the pose as its
    channels' behaviours make it, the dimmer at `levels`, the wheels and shutter each side's
    (with `shutter_gap`, `sequence`: the shutter closed before the cut)."""
    profile = sides.profile
    closed = _shutter_dark(profile)
    own: list[FixtureSegment] = []
    for side, (a, b) in enumerate(spans):
        if b <= a:
            continue
        channels: dict[ChannelName, ChannelValue] = {}
        for channel in sides.pose_channels:
            channels[channel] = ChannelValue(
                channel=channel,
                physical=ContinuousTrajectory(
                    unit="degree",
                    points=tuple(
                        PhysicalPoint(t_ms=t, value=sides.pose_at(channel, t))
                        for t in range(a, b, FRAME)
                    ),
                    interpolation="hold",
                ),
            )
        if "dimmer" in profile.axes:
            points: list[PhysicalPoint] = []
            for t in range(a, b, FRAME):
                if not points or points[-1].value != levels[t]:
                    points.append(PhysicalPoint(t_ms=t, value=levels[t]))
            channels[ChannelName.DIMMER] = ChannelValue(
                channel=ChannelName.DIMMER,
                physical=ContinuousTrajectory(
                    unit="normalized", points=tuple(points), interpolation="hold"
                ),
            )
        for channel in (ChannelName.SHUTTER, *_WHEELS):
            if DISCRETE_KEYS[channel] not in profile.discrete:
                continue
            state = sides.out_state(channel) if side == 0 else sides.in_state(channel)
            if state is None:
                continue
            events = [DiscretePoint(t_ms=a, state=state)]
            if channel is ChannelName.SHUTTER and side == 0 and shutter_gap and closed:
                shut = max(a, b - _shutter_cut_ms(profile))
                events = [*events[: int(shut > a)], DiscretePoint(t_ms=shut, state=closed)]
            channels[channel] = ChannelValue(
                channel=channel, physical=DiscreteTrajectory(events=tuple(events))
            )
        own.append(
            identity.model_copy(
                update={
                    "step_id": f"transition_{edge_label}",
                    "t0_ms": a,
                    "t1_ms": b,
                    "channels": channels,
                    "metadata": {
                        "requested_t0_ms": str(a),
                        "requested_t1_ms": str(b),
                        TRANSITION_METADATA_KEY: edge_label,
                    },
                }
            )
        )
    return own


@dataclass(frozen=True)
class _Light:
    """How one head's transition makes its dimmer: its own window and split point, the
    curve, the dimmer's behaviour, and per frame the outgoing and incoming levels, the
    progress and the fade factor (into or out of a dark cut)."""

    start_ms: int
    end_ms: int
    split_ms: int
    split: float
    curve: CurveLibrary
    behaviour: Behaviour
    frames: tuple[tuple[int, float, float, float, float], ...]

    def levels(self, out_gain: float = 1.0) -> dict[int, float]:
        """Each frame's level, the outgoing look's levels scaled by `out_gain`."""
        shape, _ = easing(self.curve)
        by_time = {t: (o * out_gain, i) for t, o, i, _, _ in self.frames}
        o_s = by_time.get(self.split_ms - FRAME, (0.0, 0.0))[0]
        i_s = by_time.get(self.split_ms, (0.0, 0.0))[1]
        handover = CROSSFADE_FLOOR * min(o_s, i_s)
        w0, w1, s = self.start_ms, self.end_ms, self.split_ms
        out: dict[int, float] = {}
        for t, o, i, p, factor in self.frames:
            o *= out_gain
            if self.behaviour == "crossfade":
                if t < s:
                    q = (t - w0) / max(FRAME, s - w0)
                    level = o + (handover - o) * shape(q)
                else:
                    q = (t - s + FRAME) / max(FRAME, w1 - s)
                    level = handover + (i - handover) * shape(min(1.0, q))
            elif self.behaviour == "smooth":
                level = o + (i - o) * shape(warped(p, self.split))
            elif self.behaviour == "sweep":
                held = by_time.get(w0, (0.0, 0.0))[0]
                q = 0.0 if t < s else (t - s + FRAME) / max(FRAME, w1 - s)
                level = held + (i - held) * shape(min(1.0, q))
            else:  # snap, fade, sequence: each side's own level
                level = o if t < s else i
            out[t] = min(1.0, max(0.0, level * factor))
        return out


def _run_into(cues: Sequence[FixtureSegment], boundary: int) -> int | None:
    """Where the cues that run unbroken into `boundary` (the last ending on it) start;
    None when the last cue ends before it (the head is dark into the boundary)."""
    if not cues or cues[-1].t1_ms < boundary:
        return None
    start = cues[-1].t0_ms
    for previous in reversed(cues[:-1]):
        if previous.t1_ms != start:
            break
        start = previous.t0_ms
    return start


def _run_from(cues: Sequence[FixtureSegment], boundary: int) -> int | None:
    """Where the cues that run unbroken from `boundary` (the first starting on it) end;
    None when the first cue starts after it (the head is dark from the boundary)."""
    if not cues or cues[0].t0_ms > boundary:
        return None
    end = cues[0].t1_ms
    for following in cues[1:]:
        if following.t0_ms != end:
            break
        end = following.t1_ms
    return end


def _from_rest_ms(
    profile: FixtureCapabilities, initial: InitialFixtureState, look: _Look, earliest: int
) -> int:
    """The first frame from `earliest` a head at rest can be revealed lit at its rest
    pose with the incoming look's wheels (`worst_case_entry_ms` from the song's start)."""
    pose = {
        channel: (float(initial.pose[AXIS_KEYS[channel]]),) * 2
        for channel in (*_POSE, ChannelName.ZOOM)
        if AXIS_KEYS[channel] in profile.axes and initial.pose.get(AXIS_KEYS[channel]) is not None
    }
    wheels = {
        channel: {series[min(series)]}
        for channel in _WHEELS
        if (series := look.states.get(channel))
    }
    held = {
        channel: {initial.discrete_states[DISCRETE_KEYS[channel]]}
        for channel in _WHEELS
        if DISCRETE_KEYS[channel] in initial.discrete_states
    }
    bound = worst_case_entry_ms(
        profile,
        entry_pose=pose,
        entry_wheels=wheels,
        pose_envelope=pose,
        frame_ms=FRAME,
        held_wheels=held,
        residual_ms=0,
    )
    return max(earliest, bound if bound is not None else earliest)


def _state_near(series: Mapping[int, str], t: int, *, before: bool) -> str | None:
    keys = sorted(series)
    if not keys:
        return None
    side = [k for k in keys if k <= t] if before else [k for k in keys if k >= t]
    if side:
        return series[side[-1] if before else side[0]]
    return series[keys[0] if before else keys[-1]]


def _moves(
    profile: FixtureCapabilities, channel: ChannelName, a: float | None, b: float | None
) -> bool:
    if a is None or b is None:
        return False
    axis = profile.axes[AXIS_KEYS[channel]]
    return axis.dmx_word(a) != axis.dmx_word(b)


def _clamped(profile: FixtureCapabilities, channel: ChannelName, value: float) -> float:
    axis = profile.axes[AXIS_KEYS[channel]]
    low, high = axis.operable_range
    return float(min(max(value, low), high))


def _shutter_cut_ms(profile: FixtureCapabilities) -> int:
    """How long before the cut the shutter closes (`sequence`): its close latency and the
    closed state's settle, at least a frame."""
    shutter = profile.discrete.get("shutter")
    closed = _shutter_dark(profile)
    settle = 0 if shutter is None or closed is None else shutter.states[closed].settle_ms or 0
    ms = (profile.visibility.close_latency_ms or 0) + settle
    return max(FRAME, math.ceil(ms / FRAME) * FRAME)


def _need_ms(
    profile: FixtureCapabilities,
    pose_channels: Sequence[ChannelName],
    pose_at: Callable[[ChannelName, int], float],
    out_state: Callable[[ChannelName], str | None],
    in_state: Callable[[ChannelName], str | None],
    last_lit_ms: int,
    first_lit_ms: int,
) -> int | None:
    """The darkness the transaction pass needs between the head's pose at `last_lit_ms`
    and at `first_lit_ms`, turning the wheels that change (`worst_case_entry_ms`, from a
    predecessor still under way)."""
    entry: dict[ChannelName, tuple[float, float]] = {}
    envelope: dict[ChannelName, tuple[float, float]] = {}
    for channel in (*_POSE, ChannelName.ZOOM):
        if AXIS_KEYS[channel] not in profile.axes:
            continue
        if channel not in pose_channels:
            return None
        a, b = pose_at(channel, last_lit_ms), pose_at(channel, first_lit_ms)
        envelope[channel], entry[channel] = (a, a), (b, b)
    held = {c: {state} for c in _WHEELS if (state := out_state(c)) is not None}
    wanted = {c: {state} for c in _WHEELS if (state := in_state(c)) is not None}
    return worst_case_entry_ms(
        profile,
        entry_pose=entry,
        entry_wheels=wanted,
        pose_envelope=envelope,
        frame_ms=FRAME,
        held_wheels=held,
        residual_ms=None,
    )


def _too_fast(cues: Sequence[FixtureSegment], profile: FixtureCapabilities) -> str | None:
    """Why the transition's own cues move an axis faster than the head travels, or None:
    any frame-to-frame step (across back-to-back cues too) beyond a frame's travel, lit or
    dark (the transaction pass moves a head only between its cues), or motion the head
    falls behind (`follow_lag`)."""
    for channel in (*_POSE, ChannelName.ZOOM):
        axis = profile.axes.get(AXIS_KEYS[channel])
        if axis is None or axis.travel_speed_per_s is None:
            continue
        low, high = axis.word_range
        per_word = (axis.physical_max - axis.physical_min) / (high - low)
        allowed = axis.travel_speed_per_s * FRAME / 1000 + per_word
        previous: tuple[int, int] | None = None
        for cue in cues:
            value = cue.channels.get(channel)
            if value is None:
                continue
            assert isinstance(value.physical, ContinuousTrajectory)
            if previous is not None and previous[0] != cue.t0_ms - FRAME:
                previous = None  # a dark cut between them: the transaction pass moves it
            for t, v in frame_values(value.physical, cue.t0_ms, cue.t1_ms, FRAME):
                word = axis.dmx_word(v)
                if previous is not None and abs(word - previous[1]) * per_word > allowed:
                    return (
                        f"its move of {channel.value} at {t} ms is faster than the head travels "
                        f"({axis.travel_speed_per_s:g} {axis.unit}/s)"
                    )
                previous = (t, word)
            if follow_lag(cue, profile, frame_ms=FRAME) is not None:
                return f"the head cannot follow its move of {channel.value}"
    return None


def _joins(
    outgoing: Sequence[FixtureSegment],
    own: Sequence[FixtureSegment],
    incoming: Sequence[FixtureSegment],
    context: HeadContext,
    gap: tuple[int, int] | None,
) -> tuple[bool, str]:
    """Whether the transaction pass plays the head's cues around the transition as
    authored: each of the transition's cues and the first incoming cue after the cue
    before it (a continuation, or the dark cut's transaction), the outgoing cues as they
    already play."""
    previous = context.before
    for index, cue in enumerate([*outgoing, *own, *incoming[:1]]):
        if index >= len(outgoing) and not entry_feasible(
            cue,
            context.profile,
            after=previous,
            initial=context.initial,
            locks=context.locks,
            frame_ms=FRAME,
        ):
            where = "the dark cut" if gap is not None and cue.t0_ms == gap[1] else "a join"
            return False, f"the transaction pass cannot play {where} at {cue.t0_ms} ms in time"
        previous = follow_cues([cue], context.profile, frame_ms=FRAME, after=previous)[-1]
    return True, ""


def _cut(
    cues: Sequence[FixtureSegment], *, start_ms: int | None = None, end_ms: int | None = None
) -> list[FixtureSegment]:
    """The cues with only their frames from `start_ms` (or before `end_ms`)."""
    out = []
    for cue in cues:
        if end_ms is not None:
            if cue.t0_ms >= end_ms:
                continue
            out.append(cue if cue.t1_ms <= end_ms else slice_segment(cue, cue.t0_ms, end_ms))
        elif start_ms is not None:
            if cue.t1_ms <= start_ms:
                continue
            out.append(cue if cue.t0_ms >= start_ms else slice_segment(cue, start_ms, cue.t1_ms))
    return out


def _describe(
    mode: TransitionMode,
    gap: tuple[int, int] | None,
    wheels_turn: Sequence[ChannelName],
    dark_pose: Sequence[ChannelName],
    rest: Literal["before", "after"] | None,
    one_sided: bool,
    ends: tuple[float, float],
) -> str:
    """What the transition plays on a head, in words, as its frames show it."""
    if rest is not None:
        coming = "comes up from" if rest == "before" else "comes to"
        how = {
            TransitionMode.SNAP: "a cut",
            TransitionMode.CROSSFADE: "dark to the split point, then the light up",
            TransitionMode.MORPH: "every continuous channel easing",
            TransitionMode.SWEEP: "holding to the split point, then travelling",
            TransitionMode.FADE_VIA_BLACK: "a fade, dark from the split point"
            if rest == "after"
            else "dark to the split point, then a fade up",
            TransitionMode.BLACKOUT: "dark over the window",
        }[mode]
        return f"{coming} rest (the initial pose, dark): {how}"
    first, last = ends
    said = {
        TransitionMode.SNAP: "dark before the boundary, in place lit on its frame",
        TransitionMode.CROSSFADE: "the light hands over at the split point, the aim eases across",
        TransitionMode.MORPH: "every continuous channel eases across",
        TransitionMode.SWEEP: "the outgoing look holds to the split point, then the head "
        "travels lit to the incoming one",
        TransitionMode.FADE_VIA_BLACK: "fades to dark at the boundary, changes in the dark, "
        "fades up",
        TransitionMode.BLACKOUT: "dark over the whole window",
    }[mode]
    if mode in LIT_MODES:
        if one_sided:
            said = (
                "clamped to one side of the boundary: the level eases from the outgoing look "
                "to the incoming one, the aim eases across"
            )
        if last == 0:
            said += "; it ends dark (the incoming look is dark there)"
        elif first == 0:
            said += "; it starts dark (the outgoing look is dark there)"
    if gap is not None and mode in LIT_MODES:
        why = [f"{c.value} turns" for c in wheels_turn] + [f"{c.value} moves" for c in dark_pose]
        said += f"; a dark cut at the split point ({', '.join(why) or 'a dark strategy'})"
    return said


def describe_transitions(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    """A section's transition trace entries as lines for a reader."""
    lines = []
    for entry in entries:
        said = (
            f"{entry['edge']} {entry['mode']} over {entry['length']} (curve {entry['curve']}, "
            f"split {entry['split']}"
        )
        if entry.get("channels"):
            said += ", " + ", ".join(f"{c} {v}" for c, v in entry["channels"].items())
        said += (
            f") at {entry['boundary_ms']} ms, {entry['window_ms'][0]}-{entry['window_ms'][1]} ms, "
            f"split point {entry['split_ms']} ms"
        )
        if entry.get("against"):
            said += f", against {entry['against']}"
        if entry.get("clamped"):
            said += f" ({'; '.join(entry['clamped'])})"
        by_what: dict[str, list[str]] = {}
        for fixture_id, outcome in sorted(entry.get("heads", {}).items()):
            if "not_played" in outcome:
                what = f"not played ({outcome['not_played']})"
            elif outcome["plays"].startswith("nothing: "):
                what = f"nothing ({outcome['plays'].removeprefix('nothing: ')})"
            else:
                what = outcome["plays"]
                if "window_ms" in outcome:
                    what += f" over {outcome['window_ms'][0]}-{outcome['window_ms'][1]} ms"
                if "dark_ms" in outcome:
                    what += f", dark {outcome['dark_ms'][0]}-{outcome['dark_ms'][1]} ms"
                if "fallback" in outcome:
                    what += f" ({outcome['fallback']})"
                if outcome.get("curve_played") not in (None, entry["curve"]):
                    what += f"; the curve plays as {outcome['curve_played']}"
            if outcome.get("strategies_played_otherwise"):
                what += f"; {'; '.join(outcome['strategies_played_otherwise'])}"
            by_what.setdefault(what, []).append(fixture_id)
        said += ": " + (
            "; ".join(f"{w} on {', '.join(h)}" for w, h in by_what.items()) or "no head"
        )
        if entry.get("replaces"):
            said += f" ({entry['replaces']})"
        lines.append(f"transition {said}")
    return lines
