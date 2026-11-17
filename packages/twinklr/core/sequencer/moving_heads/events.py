"""The planner's timed events, played on a section's frames (song-intent rendering W6/W7).

The planner names an action at a bar and beat (the cue binder has already moved a
lyric-cue-bound one to the cue's snapped beat); this module turns each into deterministic
changes to that section's cues, per head, within the rig's physical limits. Everything
that decides how an event looks is in the tables below (`STROBE_FLASHES_PER_BEAT`,
`PULSE_PERIODS_BEATS`, `HITS`, `HIT_PRE_DIP_BEATS`, `UNBOUND_EMPHASIS`, `HIT_MOVE_BARS`):
a first proposal for the owner's W6/W7 view, not a measured or accepted look.

Every event lands on the frame nearest its beat (as the compiler places a template's own
beat edges), stays inside its section, and is recorded per head: what played, or why
not.

- **closed** darkens the heads from the event's beat until the next shutter event
  (`open`, a strobe, `pulse`) or the section's end; **open** ends it (the template plays
  as authored again). The darkness is commanded on the cue's own path
  (`pipeline._dark_over_spans`: the dimmer at zero where it extinguishes, else the
  closed shutter), so the first dark frame is the beat's.
- **strobe_slow / _medium / _fast**, from the beat to the next shutter event or the end:
  a shutter state tagged with that speed where the head has one (the fixture strobes
  itself, on its lit frames); otherwise an on/off square wave on musical time, dark
  first, `STROBE_FLASHES_PER_BEAT` flashes a beat, through the dimmer where its zero
  extinguishes (what the xLights preview shows) else the shutter. A rate whose half
  period is shorter than the darkness path can follow (one frame, the dimmer's full
  swing at its declared speed, or the shutter's latency plus settle each way) is played
  at the fastest rate that fits, recorded.
- **pulse**: a beat-locked on/off, lit for the first half of each beat and dark for the
  second (`PULSE_PERIODS_BEATS`, slower where the half beat does not fit).
- **hit** (`apply_hits`, after intensity): a short bright accent on the beat. The dimmer
  jumps to its top on the beat's frame and eases back to the level the section plays
  over `decay_beats`; where the level just before the beat leaves less than `contrast`
  of the top to rise, a pre-dip into the beat makes it (`HIT_PRE_DIP_BEATS`), never to
  dark. Contrast and decay come from the bound lyric cue's emphasis (`HITS`; an unbound
  hit uses `UNBOUND_EMPHASIS`). Because it reads the level the section plays after
  intensity, a hit on a beat where an intensity accent lands is one accent, and on a
  section below full (the headroom variant) it rises above the section's level instead.
  A hit on a dark beat lights the head for the hit where the darkness is the dimmer's
  inside a cue (a template's dimmer dark phase, a closed event) with no wheel moving;
  where it is a show's rest, a repositioning or a wheel change it moves to the nearest
  beat the head can show it (within `HIT_MOVE_BARS`), recorded.
- **color / gobo**: the held colour (pattern) changes at the beat to the event's, resolved
  as the section's (`song_intent`: palette role or named colour → nearest offered state;
  pattern → tagged state), and holds until the next such event or the section's end. The
  wheel turns only while the head is dark: the reveal lands on the beat, after a dark
  lead that rides darkness already there or dips at most half a beat
  (`pipeline._dip_span`); else in the first dark window after the beat long enough
  (recorded, late); else it does not play (recorded).
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
import functools
from itertools import pairwise
import math
from typing import TYPE_CHECKING, Any, Protocol

from twinklr.core.config.fixtures.capabilities import AxisCapability, FixtureCapabilities
from twinklr.core.config.fixtures.state_tags import strobe_state
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    DISCRETE_KEYS,
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalPoint,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import frame_values, state_at
from twinklr.core.sequencer.moving_heads.compile.step import shutter_changes
from twinklr.core.sequencer.moving_heads.export.frame_encoder import quantize_cue
from twinklr.core.sequencer.moving_heads.song_intent import (
    PULSE_PERIODS_BEATS,
    STROBE_FLASHES_PER_BEAT,
    HeadWheels,
    SectionPalette,
    color_offer,
    darkness_ms,
    flash_widths,
    frames_ms,
    gobo_offer,
    pulse_period,
    requested_color,
    strobe_flashes,
    wheel_change_ms,
)
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseError,
    MusicalPhaseMap,
    musical_phase_fraction,
    musical_time_at,
)

if TYPE_CHECKING:
    from twinklr.core.sequencer.timing.beat_grid import BeatGrid

FRAME = EFFECT_GRID_MS

SHUTTER_ACTIONS = frozenset(
    {"open", "closed", "strobe_slow", "strobe_medium", "strobe_fast", "pulse"}
)
WHEEL_ACTIONS = {"color": ChannelName.COLOR, "gobo": ChannelName.GOBO}


@dataclass(frozen=True)
class HitShape:
    """One emphasis' hit (`HITS`)."""

    contrast: float
    """The rise into the beat, as a share of the dimmer's top: where the level just
    before the beat is higher than `top * (1 - contrast)`, a pre-dip brings it there."""
    decay_beats: float
    """The hit eases from the top back to the section's level over this many beats, as
    `(1 - p)**2` (the intensity accent's curve)."""


HITS: dict[str, HitShape] = {
    "LOW": HitShape(contrast=0.25, decay_beats=0.25),
    "MED": HitShape(contrast=0.40, decay_beats=0.5),
    "HIGH": HitShape(contrast=0.60, decay_beats=0.75),
}
"""Proposed (W6), by the bound lyric cue's emphasis: a stronger cue cuts deeper into the
beat and rings longer. At full level (every catalog family) the hit is the pre-dip and
the return to full; below full it also rises above the section's level."""

HIT_MIN_LIT_FRAMES = 3
"""A hit plays on a lit head only where at least this many lit frames follow it (60 ms):
a hit on a lit window's last frames would flash and go dark (as an intensity accent)."""

HIT_LATE_FRAMES = 2
"""A hit may play up to this many frames after its beat's nearest frame where the head's
lit window starts there (a template's envelope starts on the first frame at or after its
phase, a frame after the beat's nearest frame)."""

UNBOUND_EMPHASIS = "MED"
"""The emphasis of a hit no lyric cue is bound to."""

HIT_PRE_DIP_BEATS = 0.25
"""Proposed (W6). How long before the beat the pre-dip eases down (at least two frames);
it never reaches dark and never leaves the section or the lit run."""

HIT_MOVE_BARS = 1
"""How far (in bars, either way, inside the section) a hit on a beat the head cannot show
it moves to the nearest beat it can."""


class _Event(Protocol):
    @property
    def bar(self) -> int: ...
    @property
    def beat(self) -> int: ...
    @property
    def moment_cue_id(self) -> str | None: ...
    @property
    def action(self) -> Any: ...
    @property
    def color(self) -> Any: ...
    @property
    def gobo(self) -> Any: ...
    @property
    def cue_emphasis(self) -> str | None: ...


class _Section(Protocol):
    @property
    def section_id(self) -> str: ...
    @property
    def start_bar(self) -> int: ...
    @property
    def end_bar(self) -> int: ...
    @property
    def events(self) -> Sequence[Any]: ...


@dataclass(frozen=True)
class TimedEvent:
    """A planned event on the grid: its beat and the frame it lands on."""

    index: int
    """Its position in the plan section's events."""
    action: str
    bar: int
    beat: int
    beat_ms: float
    frame_ms: int
    cue_id: str | None
    emphasis: str | None
    color: str | None
    gobo: str | None

    def record(self) -> dict[str, Any]:
        """The trace's entry for this event, before what it played is added."""
        record: dict[str, Any] = {
            "action": self.action,
            "bar": self.bar,
            "beat": self.beat,
            "beat_ms": round(self.beat_ms, 1),
            "frame_ms": self.frame_ms,
        }
        if self.color is not None:
            record["color"] = self.color
        if self.gobo is not None:
            record["gobo"] = self.gobo
        if self.cue_id is not None:
            record["moment_cue_id"] = self.cue_id
            record["emphasis"] = self.emphasis or UNBOUND_EMPHASIS
        return record


def _value(value: Any) -> str | None:
    return None if value is None else str(getattr(value, "value", value))


@dataclass(frozen=True)
class SectionEvents:
    """A plan section's events on the grid (`section_events`)."""

    events: tuple[TimedEvent, ...]
    unplaced: tuple[dict[str, Any], ...]
    """Events whose beat lies beyond the beat grid, with why."""
    end_ms: int
    """The frame the section ends on."""

    def shutter_spans(self) -> list[tuple[TimedEvent, int, int]]:
        """Each closed, strobe and pulse event with the frames it plays over: from its
        frame to the next shutter event's or the section's end."""
        shutter = [e for e in self.events if e.action in SHUTTER_ACTIONS]
        if not shutter:
            return []
        ends = [e.frame_ms for e in shutter[1:]] + [self.end_ms]
        return [
            (event, event.frame_ms, end)
            for event, end in zip(shutter, ends, strict=True)
            if event.action != "open" and end > event.frame_ms
        ]

    def wheel_events(self) -> list[TimedEvent]:
        return [e for e in self.events if e.action in WHEEL_ACTIONS]

    def hits(self) -> list[TimedEvent]:
        return [e for e in self.events if e.action == "hit"]


def section_events(section: _Section, beat_grid: BeatGrid) -> SectionEvents:
    """The section's events on the grid, in time order (ties in plan order)."""
    beats = beat_grid.beat_boundaries
    per_bar = beat_grid.beats_per_bar
    placed: list[TimedEvent] = []
    unplaced: list[dict[str, Any]] = []
    for index, event in enumerate(section.events):
        position = (event.bar - 1) * per_bar + event.beat - 1
        action = _value(event.action) or ""
        if not 0 <= position < len(beats):
            unplaced.append(
                {
                    "action": action,
                    "bar": event.bar,
                    "beat": event.beat,
                    "not_played": "its beat lies beyond the detected beat grid",
                }
            )
            continue
        beat_ms = beats[position]
        placed.append(
            TimedEvent(
                index=index,
                action=action,
                bar=event.bar,
                beat=event.beat,
                beat_ms=beat_ms,
                frame_ms=quantize_cue(round(beat_ms)).actual_ms,
                cue_id=event.moment_cue_id,
                emphasis=getattr(event, "cue_emphasis", None),
                color=_value(event.color),
                gobo=_value(event.gobo),
            )
        )
    placed.sort(key=lambda e: (e.frame_ms, e.index))
    bars = beat_grid.bar_boundaries
    end = bars[section.end_bar] if section.end_bar < len(bars) else beat_grid.duration_ms
    return SectionEvents(tuple(placed), tuple(unplaced), quantize_cue(round(end)).actual_ms)


# --- reading and writing one head's cues ------------------------------------------------


def _own(cues: Sequence[FixtureSegment], fixture_id: str) -> list[FixtureSegment]:
    return sorted((c for c in cues if c.fixture_id == fixture_id), key=lambda c: c.t0_ms)


def _levels(cue: FixtureSegment, profile: FixtureCapabilities) -> dict[int, float]:
    """The cue's dimmer level at each frame, as the encoder writes it."""
    axis = profile.axes.get("dimmer")
    times = range(cue.t0_ms, cue.t1_ms, FRAME)
    if axis is None:
        return dict.fromkeys(times, 1.0)
    authored = cue.channels.get(ChannelName.DIMMER)
    if authored is not None and isinstance(authored.physical, ContinuousTrajectory):
        return {
            t: float(v) for t, v in frame_values(authored.physical, cue.t0_ms, cue.t1_ms, FRAME)
        }
    return dict.fromkeys(times, axis.word_center(axis.default_word(profile.defaults)))


def _state(cue: FixtureSegment, channel: ChannelName, profile: FixtureCapabilities, t: int) -> str:
    value = cue.channels.get(channel)
    if value is not None and isinstance(value.physical, DiscreteTrajectory):
        return state_at(value.physical, t)
    return profile.discrete[DISCRETE_KEYS[channel]].default_state


def _shutter_dark(cue: FixtureSegment, profile: FixtureCapabilities, t: int) -> bool:
    return (
        "shutter" in profile.discrete
        and _state(cue, ChannelName.SHUTTER, profile, t)
        in profile.visibility.extinguishing_shutter_states
    )


def _lit(
    cue: FixtureSegment, profile: FixtureCapabilities, levels: Mapping[int, float], t: int
) -> bool:
    axis = profile.axes.get("dimmer")
    dimmer_dark = (
        axis is not None
        and profile.visibility.dimmer_zero_extinguishes
        and axis.dmx_word(levels[t]) == axis.dmx_word(0)
    )
    return not dimmer_dark and not _shutter_dark(cue, profile, t)


def _with_levels(
    cue: FixtureSegment, profile: FixtureCapabilities, changed: Mapping[int, float]
) -> FixtureSegment:
    """`cue` with its dimmer at `changed` levels on those frames."""
    values = _levels(cue, profile) | dict(changed)
    points: list[PhysicalPoint] = []
    for t, v in values.items():
        if not points or points[-1].value != v:
            points.append(PhysicalPoint(t_ms=t, value=v))
    channels = dict(cue.channels)
    channels[ChannelName.DIMMER] = ChannelValue(
        channel=ChannelName.DIMMER,
        physical=ContinuousTrajectory(
            unit="normalized", points=tuple(points), interpolation="hold"
        ),
    )
    return cue.model_copy(update={"channels": channels})


def _with_states(
    cue: FixtureSegment,
    channel: ChannelName,
    states: Mapping[int, str],
    profile: FixtureCapabilities,
) -> FixtureSegment:
    """`cue` with `channel` at `states` on those frames, as authored elsewhere."""
    events: list[DiscretePoint] = []
    for t in range(cue.t0_ms, cue.t1_ms, FRAME):
        state = states.get(t) or _state(cue, channel, profile, t)
        if not events or events[-1].state != state:
            events.append(DiscretePoint(t_ms=t, state=state))
    channels = dict(cue.channels)
    channels[channel] = ChannelValue(
        channel=channel, physical=DiscreteTrajectory(events=tuple(events))
    )
    return cue.model_copy(update={"channels": channels})


def _shutter_holds(own: Sequence[FixtureSegment], profile: FixtureCapabilities) -> bool:
    """Whether every shutter change inside the head's cues holds for the latency it
    crosses plus its settle before the next (the transaction pass's shutter timing; the
    change into the first state is the transaction pass's own)."""
    shutter = profile.discrete.get("shutter")
    if shutter is None or not own:
        return True
    visibility = profile.visibility
    dark = set(visibility.extinguishing_shutter_states)
    changes = [
        c
        for c in shutter_changes(own, {own[0].fixture_id: profile})
        if own[0].t0_ms <= c.t_ms < own[-1].t1_ms
    ]
    for change, following in pairwise(changes):
        latency: int | None = 0
        if change.from_state is not None and (change.to_state in dark) != (
            change.from_state in dark
        ):
            latency = (
                visibility.close_latency_ms
                if change.to_state in dark
                else visibility.open_latency_ms
            )
        if latency is None or change.settle_ms is None:
            return False
        if following.t_ms - change.t_ms < latency + change.settle_ms:
            return False
    return True


# --- shutter events ---------------------------------------------------------------------


def _beat_ms(beat_grid: BeatGrid, time_ms: float) -> float:
    """The length of the beat containing `time_ms` (the nearest at the grid's edges)."""
    beats = beat_grid.beat_boundaries
    index = min(max(bisect.bisect_right(beats, time_ms), 1), len(beats) - 1)
    return beats[index] - beats[index - 1]


def _shortest_beat(beat_grid: BeatGrid, start_ms: int, end_ms: int) -> float:
    beats = beat_grid.beat_boundaries
    inside = [b - a for a, b in pairwise(beats) if b > start_ms and a < end_ms]
    return min(inside) if inside else _beat_ms(beat_grid, start_ms)


def _square_dark(
    phase_map: MusicalPhaseMap,
    origin_ms: float,
    start_ms: int,
    end_ms: int,
    period_beats: Fraction,
    *,
    dark_first: bool,
) -> list[tuple[int, int]]:
    """The dark spans of an on/off square wave of `period_beats` on musical time from the
    beat at `origin_ms`, each phase boundary on the frame nearest it, inside
    `[start_ms, end_ms)`."""
    spans: list[tuple[int, int]] = []
    half = period_beats / 2
    k = 0
    while True:
        try:
            a = musical_time_at(phase_map, k * half, origin_ms=origin_ms, period_beats=1)
        except MusicalPhaseError:
            break
        try:
            b = musical_time_at(phase_map, (k + 1) * half, origin_ms=origin_ms, period_beats=1)
        except MusicalPhaseError:
            b = Fraction(end_ms)
        qa = max(start_ms, quantize_cue(round(a)).actual_ms)
        qb = min(end_ms, quantize_cue(round(b)).actual_ms)
        if qa >= end_ms:
            break
        if (k % 2 == 0) == dark_first and qb > qa:
            spans.append((qa, qb))
        k += 1
    return spans


@dataclass
class _ShutterPlan:
    """How one head plays one shutter event: dark spans, or a strobe state's frames."""

    dark: list[tuple[int, int]] = field(default_factory=list)
    strobe_state: str | None = None
    record: dict[str, Any] = field(default_factory=dict)


def _plan_shutter(
    event: TimedEvent,
    start_ms: int,
    end_ms: int,
    profile: FixtureCapabilities,
    phase_map: MusicalPhaseMap,
    beat_grid: BeatGrid,
    *,
    use_strobe_state: bool = True,
) -> _ShutterPlan:
    """One head's plan for a closed, strobe or pulse event over `[start_ms, end_ms)`."""
    record: dict[str, Any] = {"from_ms": start_ms, "to_ms": end_ms}
    if event.action == "closed":
        record["plays"] = "dark"
        return _ShutterPlan(dark=[(start_ms, end_ms)], record=record)
    if event.action.startswith("strobe_") and use_strobe_state:
        tagged = strobe_state(profile, event.action.removeprefix("strobe_"))  # type: ignore[arg-type]
        if tagged is not None:
            record["plays"] = f"the fixture's own strobe (shutter state {tagged!r})"
            return _ShutterPlan(strobe_state=tagged, record=record)
    widths = flash_widths(profile)
    if widths is None:
        return _ShutterPlan(
            record={
                **record,
                "not_played": "the head's darkness has an unknown latency or settle, so it "
                "cannot flash in time",
            }
        )
    path, dark_ms, lit_ms = widths
    beat = _shortest_beat(beat_grid, start_ms, end_ms)
    widest = max(dark_ms, lit_ms)
    if event.action == "pulse":
        period = pulse_period(beat, widest)
        if period is None:
            return _ShutterPlan(
                record={
                    **record,
                    "not_played": f"the {path} cannot follow even a pulse every "
                    f"{PULSE_PERIODS_BEATS[-1]} beats at this tempo",
                }
            )
        record["plays"] = f"a {path} pulse, lit the first half of every {period} beat(s)"
        record["period_beats"] = period
        if period != PULSE_PERIODS_BEATS[0]:
            record["degraded"] = f"a pulse every beat is faster than the {path} can follow"
        dark = _square_dark(
            phase_map, event.beat_ms, start_ms, end_ms, Fraction(period), dark_first=False
        )
        return _ShutterPlan(dark=dark, record=record)
    asked = STROBE_FLASHES_PER_BEAT[event.action]
    flashes = strobe_flashes(event.action, beat, widest)
    if flashes is None:
        return _ShutterPlan(
            record={
                **record,
                "not_played": f"the {path} cannot follow one flash a beat at this tempo",
            }
        )
    record["plays"] = f"a {path} strobe, {flashes} flash(es) a beat"
    record["flashes_per_beat"] = flashes
    if flashes != asked:
        record["degraded"] = (
            f"{asked} flashes a beat need {beat / (2 * asked):.0f} ms phases; the {path} "
            f"follows {widest} ms"
        )
    dark = _square_dark(
        phase_map, event.beat_ms, start_ms, end_ms, Fraction(1, flashes), dark_first=True
    )
    return _ShutterPlan(dark=dark, record=record)


def _apply_strobe_state(
    own: Sequence[FixtureSegment],
    state: str,
    start_ms: int,
    end_ms: int,
    profile: FixtureCapabilities,
) -> list[FixtureSegment]:
    """The head's cues with the shutter at the strobe `state` on its lit shutter frames
    in `[start_ms, end_ms)` (a frame its shutter holds dark stays dark)."""
    out = []
    for cue in own:
        frames = {
            t: state
            for t in range(max(cue.t0_ms, start_ms), min(cue.t1_ms, end_ms), FRAME)
            if not _shutter_dark(cue, profile, t)
        }
        out.append(_with_states(cue, ChannelName.SHUTTER, frames, profile) if frames else cue)
    return out


# --- wheel events ----------------------------------------------------------------------


def _replace_from(
    own: Sequence[FixtureSegment],
    channel: ChannelName,
    old: str,
    new: str,
    from_ms: int,
    profile: FixtureCapabilities,
    *,
    take_over: bool = True,
) -> list[FixtureSegment]:
    """The head's cues holding `new` on `channel` from `from_ms` where they held `old`
    (the base state), and (with `take_over`), in the first cue from `from_ms`, also where
    it held the state it holds there: the event takes over a template overlay's state it
    lands in (for the rest of that overlay), and later overlays keep theirs."""
    out = []
    first = take_over
    for cue in own:
        if cue.t1_ms <= from_ms:
            out.append(cue)
            continue
        replaced = {old}
        if first:
            replaced.add(_state(cue, channel, profile, max(cue.t0_ms, from_ms)))
            first = False
        frames = {
            t: new
            for t in range(max(cue.t0_ms, from_ms), cue.t1_ms, FRAME)
            if _state(cue, channel, profile, t) in replaced
        }
        out.append(_with_states(cue, channel, frames, profile) if frames else cue)
    return out


@dataclass
class _WheelContext:
    """What turning one head's wheel for one event needs."""

    profile: FixtureCapabilities
    beat_grid: BeatGrid
    darken: Callable[[Sequence[FixtureSegment], Sequence[tuple[int, int]]], list[FixtureSegment]]
    dip_span: Callable[..., tuple[int, int, int] | None]
    dark_runs: Callable[[FixtureSegment, FixtureSegment | Any], list[list[int]]]
    dark_windows: Callable[[Sequence[FixtureSegment], FixtureCapabilities], list[tuple[int, int]]]
    part_start: int
    gap_ok: Callable[[Sequence[FixtureSegment], int], bool]
    """Whether the transaction pass can still enter the cue at this index of the head's
    cues (with the wheel changed) after the gap before it (`entry_feasible`)."""

    def turned_in_gap(
        self,
        own: list[FixtureSegment],
        channel: ChannelName,
        old: str,
        new: str,
        cue: FixtureSegment,
    ) -> list[FixtureSegment] | None:
        """The head's cues holding `new` from `cue`, which follows a gap the transaction pass
        turns the wheel in; None when that turn no longer fits the gap."""
        changed = _replace_from(own, channel, old, new, cue.t0_ms, self.profile)
        index = next(i for i, c in enumerate(changed) if c.t0_ms == cue.t0_ms)
        return changed if index == 0 or self.gap_ok(changed, index) else None


def _turn(
    own: list[FixtureSegment],
    channel: ChannelName,
    old: str,
    new: str,
    event: TimedEvent,
    floor_ms: int,
    until_ms: int,
    ctx: _WheelContext,
) -> tuple[list[FixtureSegment], dict[str, Any], bool]:
    """One head's wheel turned from `old` to `new` for `event`: `(cues, record, played)`.

    The reveal lands on the event's frame `T` after a dark lead (`wheel_change_ms`): the
    darkness rides what the cue before `T` already commands, else dips at most half a beat
    (`pipeline._dip_span`), never before `floor_ms` (the previous wheel event's reveal).
    Else the turn waits for the first dark window after `T` (before `until_ms`, the next
    event of this wheel) long enough. Else it does not play."""
    profile = ctx.profile
    capability = profile.discrete[DISCRETE_KEYS[channel]]
    settle = capability.states[new].settle_ms
    darkness = darkness_ms(profile)
    lead = None if settle is None else wheel_change_ms(profile, settle)
    record: dict[str, Any] = {"state": new}
    if lead is None or darkness is None:
        record["not_played"] = (
            "a term of the wheel change (a settle, or the close latency) is unknown"
        )
        return own, record, False
    t = event.frame_ms
    inside = next((c for c in own if c.t0_ms <= t < c.t1_ms), None)
    after = None if inside is not None else next((c for c in own if c.t0_ms > t), None)
    if inside is None and (after is None or after.t0_ms >= until_ms):
        record["not_played"] = "the head is dark from the beat to the section's end"
        return own, record, False
    gap_cue = after if inside is None else None
    previous = None
    if inside is not None and inside.t0_ms == t:
        previous = next((c for c in own if c.t1_ms == t), None)
        gap_cue = inside if previous is None else None
    if gap_cue is not None:
        # A gap before the cue, or the part's first cue: the transaction pass (or, at a
        # boundary the heads play through, the boundary's dip) turns the wheel there.
        changed = ctx.turned_in_gap(own, channel, old, new, gap_cue)
        if changed is not None:
            record["reveal_ms"] = gap_cue.t0_ms
            if gap_cue.t0_ms <= ctx.part_start:
                record["at_section_start"] = (
                    "turned as the section's colour or gobo is at its boundary (the "
                    "section's boundaries record)"
                )
            else:
                record["turned_in_the_dark_before_ms"] = gap_cue.t0_ms
            return changed, record, True
    holder = None if gap_cue is not None else previous or inside
    half = _beat_ms(ctx.beat_grid, t - 1) / 2
    dip = (
        None
        if holder is None
        else ctx.dip_span(ctx.dark_runs(holder, profile), max(holder.t0_ms, floor_ms), t, lead)
    )
    if holder is not None and dip is not None and dip[1] <= half:
        dark_from, added, dark_start = dip
        index = own.index(holder)
        darkened = holder
        if added:
            (darkened,) = ctx.darken([holder], [(dark_from, t)])
        turn = t - frames_ms(max(settle or 0, FRAME))
        swapped = _replace_from([darkened], channel, old, new, turn, profile)[0]
        # Every frame of the holder from the turn holds the new state, its own too.
        swapped = _with_states(
            swapped,
            channel,
            dict.fromkeys(range(turn, min(swapped.t1_ms, t), FRAME), new),
            profile,
        )
        rest = _replace_from(
            own[index + 1 :], channel, old, new, t, profile, take_over=holder is not inside
        )
        record["reveal_ms"] = t
        record["dark_dip"] = {
            "from_ms": dark_start,
            "lead_ms": lead,
            "added_ms": added,
            "turn_ms": turn,
        }
        return [*own[:index], swapped, *rest], record, True
    why = (
        "the gap before the head's next cue is too short to turn the wheel as well"
        if holder is None
        else f"the previous cue is too short for the {lead} ms dark lead"
        if dip is None
        else f"the {lead} ms of darkness, turn and settle it needs (adding {dip[1]} ms) do not "
        f"fit half the beat before it ({half:g} ms)"
    )
    for start, end in ctx.dark_windows(own, profile):
        if start < t or end - start < lead:
            continue
        if start >= until_ms:
            break
        turn = start + frames_ms(darkness)
        turning = next((c for c in own if c.t0_ms <= turn < c.t1_ms), None)
        if turning is None:
            following = next(c for c in own if c.t0_ms >= end)
            changed = ctx.turned_in_gap(own, channel, old, new, following)
            if changed is None:
                continue
            record["deferred"] = {
                "reveal_ms": following.t0_ms,
                "late_ms": following.t0_ms - t,
                "reason": why,
            }
            record["reveal_ms"] = following.t0_ms
            return changed, record, True
        reveal = end
        record["deferred"] = {
            "turn_ms": turn,
            "reveal_ms": reveal,
            "late_ms": reveal - t,
            "reason": why,
        }
        record["reveal_ms"] = reveal
        return _replace_from(own, channel, old, new, turn, profile), record, True
    record["not_played"] = f"{why}, and the section has no dark window long enough after it"
    return own, record, False


def _note_reveal(
    record: dict[str, Any],
    own: Sequence[FixtureSegment],
    channel: ChannelName,
    state: str,
    frame_ms: int,
    profile: FixtureCapabilities,
) -> None:
    """Record when the head first shows `state` lit at or after the event's frame, and how
    late that is where the head is dark on the beat (a template's dark phase) or a
    template overlay holds its own state there."""
    for cue in own:
        levels = _levels(cue, profile)
        for t in range(max(cue.t0_ms, frame_ms), cue.t1_ms, FRAME):
            if _lit(cue, profile, levels, t) and _state(cue, channel, profile, t) == state:
                record["reveal_ms"] = t
                if t > frame_ms + HIT_LATE_FRAMES * FRAME and "deferred" not in record:
                    record["late"] = {
                        "late_ms": t - frame_ms,
                        "reason": "the head is dark on the beat (its template's dark phase) "
                        "or its template's overlay holds its own state there; it shows the "
                        "change from its next reveal",
                    }
                return
    record["reveal_ms"] = None
    record["late"] = {"reason": "the head never shows it lit before the section's end"}


# --- applying a section's events ---------------------------------------------------------


@dataclass
class EventsPlayed:
    """What a part's events played (`apply_section_events`)."""

    records: dict[int, dict[str, Any]] = field(default_factory=dict)
    """Per event (its index in the plan section), the trace entry."""
    final: dict[str, dict[ChannelName, str]] = field(default_factory=dict)
    """Per head, the wheel states events left it holding at the part's end."""

    def head(self, event: TimedEvent, fixture_id: str, outcome: dict[str, Any]) -> None:
        entry = self.records.setdefault(event.index, event.record())
        entry.setdefault("heads", {})[fixture_id] = outcome


def event_states(
    event: TimedEvent, heads: Sequence[HeadWheels], palette: SectionPalette | None
) -> dict[str, str]:
    """The wheel state each head plays a colour or gobo event with (the section look's
    resolution); a head that cannot show it is left out."""
    if event.action == "color" and event.color is not None:
        asked = requested_color(event.color, palette)
        return {f: h.state for f, h in color_offer(heads, asked.hex).heads.items()}
    if event.action == "gobo" and event.gobo is not None:
        return dict(gobo_offer(heads, event.gobo).states)
    return {}


def carried_states(
    events: SectionEvents,
    before_ms: int,
    heads: Sequence[HeadWheels],
    palette: SectionPalette | None,
) -> dict[str, dict[ChannelName, str]]:
    """Per head, the wheel states the section's events before `before_ms` (an earlier
    part's) leave it holding: a later part holds them from its start."""
    held: dict[str, dict[ChannelName, str]] = {}
    for event in events.wheel_events():
        if event.frame_ms >= before_ms:
            continue
        for fixture_id, state in event_states(event, heads, palette).items():
            held.setdefault(fixture_id, {})[WHEEL_ACTIONS[event.action]] = state
    return held


def apply_section_events(
    cues: Sequence[FixtureSegment],
    events: SectionEvents,
    *,
    window: tuple[int, int],
    profiles: Mapping[str, FixtureCapabilities],
    heads: Sequence[HeadWheels],
    palette: SectionPalette | None,
    phase_map: MusicalPhaseMap,
    beat_grid: BeatGrid,
    darken: Callable[[Sequence[FixtureSegment], Sequence[tuple[int, int]]], list[FixtureSegment]],
    dip_span: Callable[..., tuple[int, int, int] | None],
    dark_runs: Callable[..., list[list[int]]],
    dark_windows: Callable[..., list[tuple[int, int]]],
    gap_ok: Callable[[str, Sequence[FixtureSegment], int], bool],
) -> tuple[list[FixtureSegment], EventsPlayed]:
    """A part's compiled cues (all heads, inside `window`) with its plan section's closed,
    strobe, pulse, colour and gobo events played; hits are `apply_hits`'.

    Shutter events first (their darkness, then the next event's), then the wheel events
    in time order, so a colour or gobo change rides a closed event's darkness. `darken`
    commands frames dark on a cue's own path (`pipeline._dark_over_spans`); `dip_span`,
    `dark_runs` and `dark_windows` are the boundary dip's own helpers; `gap_ok` says
    whether a head's cue at an index of its cues can still be entered after the gap before
    it with a wheel changed there (the transaction pass's `entry_feasible`)."""
    start, end = window
    played = EventsPlayed()
    by_head = {f: _own(cues, f) for f in sorted({c.fixture_id for c in cues})}
    for event, span_start, span_end in events.shutter_spans():
        lo, hi = max(span_start, start), min(span_end, end)
        if lo >= hi:
            continue
        here = start <= event.frame_ms < end
        for fixture_id, own in by_head.items():
            profile = profiles[fixture_id]
            plan = _plan_shutter(event, lo, hi, profile, phase_map, beat_grid)
            if plan.strobe_state is not None:
                trial = _apply_strobe_state(own, plan.strobe_state, lo, hi, profile)
                if not _shutter_holds(trial, profile):
                    plan = _plan_shutter(
                        event, lo, hi, profile, phase_map, beat_grid, use_strobe_state=False
                    )
                    plan.record["fixture_strobe_unusable"] = (
                        "its strobe state does not hold for its settle around the template's "
                        "own shutter changes"
                    )
                else:
                    own = trial
            if plan.dark:
                trial = darken(own, plan.dark)
                if _shutter_holds(trial, profile):
                    own = trial
                else:
                    plan.record = {
                        **{k: v for k, v in plan.record.items() if k in ("from_ms", "to_ms")},
                        "not_played": "the shutter cannot take the darkness in time around the "
                        "template's own shutter changes",
                    }
            by_head[fixture_id] = own
            if here:
                played.head(event, fixture_id, plan.record)
    for event in events.events:
        if event.action == "open" and start <= event.frame_ms < end:
            for fixture_id in by_head:
                played.head(
                    event,
                    fixture_id,
                    {"from_ms": event.frame_ms, "plays": "the template's own shutter and level"},
                )
    wheel_events = [e for e in events.wheel_events() if start <= e.frame_ms < end]
    for fixture_id, own in by_head.items():
        profile = profiles[fixture_id]
        ctx = _WheelContext(
            profile,
            beat_grid,
            darken,
            dip_span,
            dark_runs,
            dark_windows,
            start,
            functools.partial(gap_ok, fixture_id),
        )
        # The base each wheel holds at the part's start (the section's colour, a carried
        # event's, or the template's own): what an event turns from; overlay states stay.
        base: dict[ChannelName, str] = {
            channel: _state(own[0], channel, profile, own[0].t0_ms)
            for channel in WHEEL_ACTIONS.values()
            if own and DISCRETE_KEYS[channel] in profile.discrete
        }
        floor = start
        for index, event in enumerate(wheel_events):
            channel = WHEEL_ACTIONS[event.action]
            if DISCRETE_KEYS[channel] not in profile.discrete:
                played.head(
                    event, fixture_id, {"not_played": f"the head has no {channel.value} wheel"}
                )
                continue
            new = event_states(event, heads, palette).get(fixture_id)
            if new is None:
                played.head(
                    event,
                    fixture_id,
                    {"not_played": f"the head's {channel.value} wheel offers nothing for it"},
                )
                continue
            if channel not in base:
                continue  # the head has no cue in the part
            old = base[channel]
            if old == new:
                played.head(
                    event, fixture_id, {"state": new, "unchanged": "the head already holds it"}
                )
                continue
            until = next(
                (
                    e.frame_ms
                    for e in wheel_events[index + 1 :]
                    if WHEEL_ACTIONS[e.action] == channel
                ),
                end,
            )
            own, record, turned = _turn(own, channel, old, new, event, floor, until, ctx)
            if turned:
                _note_reveal(record, own, channel, new, event.frame_ms, profile)
            played.head(event, fixture_id, record)
            if turned:
                base[channel] = new
                played.final.setdefault(fixture_id, {})[channel] = new
                floor = max(floor, record.get("reveal_ms") or event.frame_ms)
        by_head[fixture_id] = own
    return _in_order(cues, by_head), played


def _in_order(
    cues: Sequence[FixtureSegment], by_head: Mapping[str, Sequence[FixtureSegment]]
) -> list[FixtureSegment]:
    """The changed cues in the order `cues` came in (events never split or move a cue)."""
    changed = {(c.fixture_id, c.t0_ms): c for own in by_head.values() for c in own}
    return [changed[(c.fixture_id, c.t0_ms)] for c in cues]


# --- hits ------------------------------------------------------------------------------


@dataclass
class _HeadFrames:
    """One head's cues and its frame-by-frame dimmer level and darkness."""

    own: list[FixtureSegment]
    profile: FixtureCapabilities
    levels: dict[int, float] = field(default_factory=dict)
    cue_at: dict[int, int] = field(default_factory=dict)
    lit: dict[int, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for index, cue in enumerate(self.own):
            levels = _levels(cue, self.profile)
            for t, v in levels.items():
                self.levels[t] = v
                self.cue_at[t] = index
                self.lit[t] = _lit(cue, self.profile, levels, t)

    def wheels(self, t: int) -> tuple[str, ...]:
        cue = self.own[self.cue_at[t]]
        return tuple(
            _state(cue, channel, self.profile, t)
            for channel in (ChannelName.COLOR, ChannelName.GOBO)
            if DISCRETE_KEYS[channel] in self.profile.discrete
        )


def _forced_frames(
    frames: _HeadFrames, t: int, length: int, dark_spans: Sequence[tuple[int, int]]
) -> int:
    """How many frames from `t` a hit may light where the head is dark: inside its cues,
    dark through the dimmer only (the shutter open), outside every show rest, with the
    wheels still from the dark run's start through the frames after, and the close
    latency (plus a frame) left dark after them. 0 where it may not."""
    profile = frames.profile
    if not profile.visibility.dimmer_zero_extinguishes or "dimmer" not in profile.axes:
        return 0
    if any(a <= t < b for a, b in dark_spans) or t not in frames.cue_at:
        return 0
    run_start = t
    while run_start - FRAME in frames.cue_at and not frames.lit[run_start - FRAME]:
        run_start -= FRAME
    run_end = t
    while run_end in frames.cue_at and not frames.lit[run_end]:
        run_end += FRAME
    tail = frames_ms(profile.visibility.close_latency_ms or 0) + FRAME
    usable = min(length, (run_end - t - tail) // FRAME)
    if usable <= 0:
        return 0
    for u in range(run_start, run_end, FRAME):
        cue = frames.own[frames.cue_at[u]]
        if _shutter_dark(cue, profile, u) or any(a <= u < b for a, b in dark_spans):
            return 0
    if len({frames.wheels(u) for u in range(run_start, run_end, FRAME)}) != 1:
        return 0
    return usable


def apply_hits(
    cues: Sequence[FixtureSegment],
    hits: Sequence[TimedEvent],
    *,
    window: tuple[int, int],
    profiles: Mapping[str, FixtureCapabilities],
    phase_map: MusicalPhaseMap,
    beat_grid: BeatGrid,
    dark_spans: Sequence[tuple[int, int]],
) -> tuple[list[FixtureSegment], dict[int, dict[str, Any]]]:
    """A part's cues as they will play (after every darkness and intensity) with its hits
    played (see the module docstring). A hit is one moment for the rig: it plays on its
    beat's frame on every head that can show it there (lit, or lit for the hit where its
    darkness allows, `_forced_frames`); a head dark there between its template's cues
    does not play it. Only where no head can show it on its beat does the hit move, on
    every head, to the nearest beat inside the part (within `HIT_MOVE_BARS`) where one can;
    else it does not play. Returns the cues and the trace entry per event."""
    start, end = window
    records: dict[int, dict[str, Any]] = {}
    by_head = {f: _own(cues, f) for f in sorted({c.fixture_id for c in cues})}
    beats = beat_grid.beat_boundaries
    reach = HIT_MOVE_BARS * beat_grid.beats_per_bar
    for event in hits:
        entry = records.setdefault(event.index, event.record())
        heads = entry.setdefault("heads", {})
        shape = HITS[event.emphasis or UNBOUND_EMPHASIS]
        frames = {
            f: _HeadFrames(own, profiles[f])
            for f, own in by_head.items()
            if "dimmer" in profiles[f].axes
        }
        home = beats.index(event.beat_ms) if event.beat_ms in beats else None
        able: dict[str, tuple[int, str, int]] = {}
        beat = event.beat_ms
        for offset in [0] + [d for k in range(1, reach + 1) for d in (k, -k)]:
            if home is None or not 0 <= home + offset < len(beats):
                continue
            beat = beats[home + offset]
            for fixture_id, head in frames.items():
                lead = _lead(profiles[fixture_id].axes["dimmer"], beat_grid)
                t = quantize_cue(round(beat - lead)).actual_ms
                if not start <= t < end:
                    continue
                decay = _decay_frames(phase_map, beat, shape, t)
                lit = _lit_start(head, t)
                if lit is not None:
                    able[fixture_id] = (lit, "lit", decay)
                elif forced := _forced_frames(head, t, decay, dark_spans):
                    able[fixture_id] = (t, "lit_from_dark", forced)
            if able:
                break
        index = beats.index(beat) if beat in beats else None
        for fixture_id in by_head:
            if fixture_id not in frames:
                heads[fixture_id] = {"not_played": "the head has no dimmer axis"}
                continue
            if fixture_id not in able:
                heads[fixture_id] = {
                    "not_played": "the head is dark on the hit's beat between its template's "
                    "cues (it repositions or turns a wheel there)"
                    if able
                    else "every head is dark (a show's rest, a repositioning or a wheel "
                    f"change) on the beat and on every beat within {HIT_MOVE_BARS} bar(s) of "
                    "it in the section"
                }
                continue
            t, how, count = able[fixture_id]
            axis = profiles[fixture_id].axes["dimmer"]
            by_head[fixture_id], outcome = _play_hit(
                frames[fixture_id], axis, shape, phase_map, beat, t, how, count, start
            )
            outcome["played_ms"] = t
            if lead := _lead(axis, beat_grid):
                outcome["lead_ms"] = lead
            if beat != event.beat_ms and index is not None:
                outcome["moved"] = {
                    "from_ms": event.frame_ms,
                    "bar": index // beat_grid.beats_per_bar + 1,
                    "beat": index % beat_grid.beats_per_bar + 1,
                    "reason": "every head is dark on the event's beat (a show's rest, a "
                    "repositioning or a wheel change)",
                }
            heads[fixture_id] = outcome
    return _in_order(cues, by_head), records


def _lit_start(frames: _HeadFrames, t: int) -> int | None:
    """Where a hit on frame `t` plays on a lit head: the first frame from `t` (within
    `HIT_LATE_FRAMES`, a template's lit window starting a frame after the beat's nearest
    one) that starts at least `HIT_MIN_LIT_FRAMES` lit frames; None when the head is not
    lit there that long (a hit on a lit window's last frames would flash and go dark)."""
    for start in range(t, t + (HIT_LATE_FRAMES + 1) * FRAME, FRAME):
        run = range(start, start + HIT_MIN_LIT_FRAMES * FRAME, FRAME)
        if all(u in frames.cue_at and frames.lit[u] for u in run):
            return start
    return None


def _lead(axis: AxisCapability, beat_grid: BeatGrid) -> int:
    """The dimmer latency the hit is commanded early by, at most just under half the
    song's shortest beat (as intensity's accents)."""
    if not axis.latency_ms:
        return 0
    shortest = min((b - a for a, b in pairwise(beat_grid.beat_boundaries)), default=0.0)
    return max(0, min(axis.latency_ms, int(shortest / 2) - 1))


def _decay_frames(phase_map: MusicalPhaseMap, beat: float, shape: HitShape, t: int) -> int:
    """How many frames from `t` the hit's decay lasts (at least one)."""
    try:
        end = musical_time_at(
            phase_map, Fraction(shape.decay_beats), origin_ms=beat, period_beats=1
        )
    except MusicalPhaseError:
        return 1
    return max(1, math.ceil((float(end) - t) / FRAME))


def _play_hit(
    frames: _HeadFrames,
    axis: AxisCapability,
    shape: HitShape,
    phase_map: MusicalPhaseMap,
    beat: float,
    t: int,
    how: str,
    count: int,
    part_start: int,
) -> tuple[list[FixtureSegment], dict[str, Any]]:
    """The head's cues with one hit at frame `t`: the top on `t`, easing back to the level
    played over the decay (`count` frames, only lit or lit-from-dark ones), and, where the
    level before `t` leaves less than the shape's contrast, a pre-dip into it."""
    top = float(axis.operable_range[1])
    zero = axis.dmx_word(0)
    changed: dict[int, float] = {t: top}
    outcome: dict[str, Any] = {
        "how": how,
        "contrast": shape.contrast,
        "decay_beats": shape.decay_beats,
    }

    def phase(u: int) -> float:
        try:
            return float(musical_phase_fraction(phase_map, u, origin_ms=beat, period_beats=1))
        except MusicalPhaseError:
            return math.inf

    for k in range(1, count):
        u = t + k * FRAME
        if u not in frames.cue_at or (how == "lit" and not frames.lit[u]):
            break
        p = min(1.0, max(0.0, phase(u) / shape.decay_beats))
        base = frames.levels[u] if how == "lit" else 0.0
        value = base + (top - base) * (1 - p) ** 2
        if axis.dmx_word(value) == zero:
            break
        changed[u] = max(base, value)
    if how == "lit":
        before = t - FRAME
        needed = top * (1 - shape.contrast)
        if (
            before in frames.cue_at
            and before >= part_start
            and frames.lit[before]
            and frames.levels[before] > needed
        ):
            try:
                dip_start = musical_time_at(
                    phase_map, Fraction(-HIT_PRE_DIP_BEATS), origin_ms=beat, period_beats=1
                )
            except MusicalPhaseError:
                dip_start = Fraction(t - 2 * FRAME)
            first = min(t - 2 * FRAME, quantize_cue(round(dip_start)).actual_ms)
            span = [
                u
                for u in range(max(first, part_start), t, FRAME)
                if u in frames.cue_at and frames.lit[u]
            ]
            # Only the frames right before the beat, without a dark frame between.
            while span and any(
                not frames.lit[w] for w in range(span[0], t, FRAME) if w in frames.lit
            ):
                span = span[1:]
            for position, u in enumerate(span, start=1):
                share = (position / len(span)) ** 2
                level = frames.levels[u]
                changed[u] = min(level, level + (needed - level) * share)
            if span:
                outcome["pre_dip"] = {"from_ms": span[0], "to_level": round(needed, 4)}
    if axis.travel_speed_per_s is not None:
        # Each frame-to-frame step within what the dimmer can travel in a frame, walking
        # forward from the frame before the hit to the frame after it.
        allowed = axis.travel_speed_per_s * FRAME / 1000
        lowest, highest = min(changed), max(changed) + FRAME
        previous = frames.levels.get(lowest - FRAME)
        clipped = False
        for u in range(lowest, highest + FRAME, FRAME):
            target = changed.get(u, frames.levels.get(u))
            if target is None or previous is None:
                previous = target
                continue
            if abs(target - previous) > allowed + 1e-12:
                clipped = True
                target = previous + math.copysign(allowed, target - previous)
                if axis.dmx_word(max(0.0, target)) == zero:
                    target = previous
                changed[u] = max(0.0, target)
            previous = target
        if clipped:
            outcome["degraded"] = "the dimmer is too slow to jump to its top in a frame"
    by_cue: dict[int, dict[int, float]] = {}
    for u, value in changed.items():
        if u in frames.cue_at:
            by_cue.setdefault(frames.cue_at[u], {})[u] = value
    own = [
        _with_levels(cue, frames.profile, by_cue[i]) if i in by_cue else cue
        for i, cue in enumerate(frames.own)
    ]
    outcome["frames"] = len([u for u in changed if u >= t])
    return own, outcome


# --- the trace ---------------------------------------------------------------------------


def played_at(outcome: Mapping[str, Any]) -> int | None:
    """When a head played an event (its first frame, reveal or hit), None when it did
    not."""
    if "not_played" in outcome or "unchanged" in outcome:
        return None
    for key in ("played_ms", "reveal_ms", "from_ms"):
        if outcome.get(key) is not None:
            return int(outcome[key])
    return None


def cue_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    """One event's trace entry as its lyric cue's line: when each head played it, where
    it moved, why a head did not."""
    summary: dict[str, Any] = {
        "action": entry["action"],
        "bar": entry["bar"],
        "beat": entry["beat"],
    }
    played: dict[str, int] = {}
    for fixture_id, outcome in sorted(entry.get("heads", {}).items()):
        at = played_at(outcome)
        if at is not None:
            played[fixture_id] = at
        elif "not_played" in outcome:
            summary.setdefault("not_played", {})[fixture_id] = outcome["not_played"]
        if "moved" in outcome:
            summary.setdefault("moved", {})[fixture_id] = outcome["moved"]
        if "deferred" in outcome:
            summary.setdefault("late", {})[fixture_id] = outcome["deferred"]["late_ms"]
        elif "late" in outcome and "late_ms" in outcome["late"]:
            summary.setdefault("late", {})[fixture_id] = outcome["late"]["late_ms"]
    summary["played"] = played
    if "not_played" in entry:
        summary["not_played"] = entry["not_played"]
    return summary


def events_message(section_id: str, entries: Sequence[Mapping[str, Any]]) -> str | None:
    """The warning for a section where an event did not play, played late, moved or
    played slower, on some head."""
    said = []
    for entry in entries:
        heads = entry.get("heads", {})
        label = f"{entry['action']} at bar {entry['bar']} beat {entry['beat']}"
        kinds: dict[str, list[str]] = {}
        for fixture_id, outcome in sorted(heads.items()):
            for kind in ("not_played", "moved", "deferred", "late", "degraded"):
                if kind in outcome:
                    kinds.setdefault(kind, []).append(fixture_id)
        if "not_played" in entry:
            kinds["not_played"] = ["every head"]
        words = {
            "not_played": "not played",
            "moved": "moved to another beat",
            "deferred": "turned late",
            "late": "shown after its beat",
            "degraded": "played slower",
        }
        said += [f"{label} {words[k]} on {', '.join(v)}" for k, v in kinds.items()]
    if not said:
        return None
    return f"section {section_id!r}: " + "; ".join(said) + " (the trace's section_looks events)"


def describe_events(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    """A section's event trace entries as lines for a reader."""
    lines = []
    for entry in entries:
        label = f"{entry['action']}"
        if entry.get("color"):
            label += f" {entry['color']}"
        if entry.get("gobo"):
            label += f" {entry['gobo']}"
        label += f" at bar {entry['bar']} beat {entry['beat']}"
        if entry.get("moment_cue_id"):
            label += f" (lyric cue '{entry['moment_cue_id']}', {entry['emphasis']})"
        if "not_played" in entry:
            lines.append(f"event {label}: not played ({entry['not_played']})")
            continue
        by_what: dict[str, list[str]] = {}
        for fixture_id, outcome in sorted(entry.get("heads", {}).items()):
            by_what.setdefault(_describe_outcome(outcome), []).append(fixture_id)
        parts = [f"{what} on {', '.join(heads)}" for what, heads in by_what.items()]
        lines.append(f"event {label}: {'; '.join(parts) or 'no head plays it'}")
    return lines


def _describe_outcome(outcome: Mapping[str, Any]) -> str:
    if "not_played" in outcome:
        return f"not played ({outcome['not_played']})"
    if "unchanged" in outcome:
        return f"already {outcome['state']}"
    if "plays" in outcome and "to_ms" not in outcome:
        return f"{outcome['plays']} from {outcome['from_ms']} ms"
    if "plays" in outcome:
        said = f"{outcome['plays']} from {outcome['from_ms']} to {outcome['to_ms']} ms"
        return said + (f" ({outcome['degraded']})" if "degraded" in outcome else "")
    if "state" in outcome:
        said = f"{outcome['state']} revealed at {outcome['reveal_ms']} ms"
        if "dark_dip" in outcome:
            said += f" after a {outcome['dark_dip']['added_ms']} ms dark dip"
        if "deferred" in outcome:
            said += f", {outcome['deferred']['late_ms']} ms late ({outcome['deferred']['reason']})"
        elif "late" in outcome:
            said += f", {outcome['late'].get('late_ms', '?')} ms after the beat (dark or in "
            "the template's overlay there)"
        return said
    said = f"a hit at {outcome['played_ms']} ms"
    if outcome.get("how") == "lit_from_dark":
        said += ", lit for it from the dark"
    if "pre_dip" in outcome:
        said += f" after a pre-dip from {outcome['pre_dip']['from_ms']} ms"
    if "moved" in outcome:
        said += f" (moved to bar {outcome['moved']['bar']} beat {outcome['moved']['beat']})"
    if "degraded" in outcome:
        said += f" ({outcome['degraded']})"
    return said


def describe_lyric_cue(entry: Mapping[str, Any]) -> str:
    """A lyric cue's trace entry (`render_record["lyric_cues"]`) as one line: what played
    it, when and on which heads, or why not."""
    said = f"lyric cue '{entry['cue_id']}'"
    if entry.get("emphasis"):
        said += f" ({entry['emphasis']})"
    if "not_played" in entry:
        return f"{said}: not played ({entry['not_played']})"
    parts = []
    for event in entry.get("events", []):
        line = f"{event['action']} at bar {event['bar']} beat {event['beat']}"
        by_time: dict[int, list[str]] = {}
        for fixture_id, at in event.get("played", {}).items():
            by_time.setdefault(at, []).append(fixture_id)
        played = [f"at {at} ms on {', '.join(heads)}" for at, heads in sorted(by_time.items())]
        if event.get("moved"):
            played.append(f"moved on {', '.join(event['moved'])}")
        if isinstance(event.get("not_played"), str):
            played.append(f"not played ({event['not_played']})")
        elif event.get("not_played"):
            played.append(f"not played on {', '.join(event['not_played'])}")
        parts.append(f"{line} {'; '.join(played) or 'played on no head'}")
    return f"{said}: {'; '.join(parts)}"
