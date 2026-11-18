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
  at the fastest rate that fits, chosen beat by beat (a faster stretch slows only its own
  beats), recorded.
- **pulse**: a beat-locked on/off, lit for the first half of each beat and dark for the
  second (`PULSE_PERIODS_BEATS`, slower where the half beat does not fit).
- **hit** (`apply_hits`, after intensity): a short bright accent on the beat, on the level
  the section plays (`L`, after intensity), so a hit on a beat where an intensity accent
  lands is one accent, and on a section below full (the headroom variant) it rises above
  it. With room before the beat (the head lit there, inside the section) it dips
  `contrast` below `L` over the quarter beat before (`HIT_PRE_DIP_BEATS`), holding the
  last `visible_frames` frames, then snaps to the dimmer's top for that many frames and
  decays back; without room (dark before, a reveal on the beat) it flashes the top and
  ducks `contrast` below `L` for that many frames, recovering over `decay_beats`. Never
  below `HIT_FLOOR`. Contrast, held frames and decay come from the bound lyric cue's
  emphasis (`HITS`; an unbound hit uses `UNBOUND_EMPHASIS`). A head counts it played only
  where `visible_frames` frames differ from `L` by `contrast`, or by the room `L` leaves
  above the floor where that is less (`(L - HIT_FLOOR)`, per frame);
  else "no visible change". A hit on a dark beat lights the head for it where the
  darkness is the dimmer's inside a cue (a template's dimmer dark phase, a closed event)
  with no wheel moving; a head dark between its template's cues does not play it; where
  every head is dark on the beat (a show's rest, a repositioning, a wheel change) it
  moves within `HIT_MOVE_BARS` (in beats on the grid): a hit bound to a lyric cue to the beat
  after its own where a head shows it and that beat is at or after the lyric (a hit
  never lands before its lyric when the next beat serves), else the beat nearest the
  lyric (the later of equals); another to the beat the most heads show,
  a later one first; recorded with the beat, the direction and the offset. A hit that lights a strobe's or pulse's dark frames is traced
  on both.
- **color / gobo**: the held colour (pattern) changes at the beat to the event's, resolved
  as the section's (`song_intent`: palette role or named colour → nearest offered state;
  pattern → tagged state), and holds until the next such event or the section's end. The
  wheel turns only while the head is dark: the reveal lands on the beat, after a dark
  lead that rides darkness already there or adds at most half the beat before it
  (`song_intent.dip_fits`, the test the plan repair uses too); else in the first dark
  window after the beat long enough that reveals it within `WHEEL_LATE_BEATS` (recorded,
  late); else it does not play on that head (recorded). A head dark on the beat (or a
  frame or two after it) turns in that darkness and shows the change from its next
  reveal, its first lit frame however short; only lit for `HIT_MIN_LIT_FRAMES` frames
  running does it count as showing it within a beat. The event plays on its beat where
  some head shows it within `WHEEL_LATE_BEATS`; a head never lit again before the
  section's end does not play it; where no head would, it moves, on every head, to the
  beat within `WHEEL_MOVE_BARS` where the most heads do, a later one first, else does not
  play (`_play_wheel_events`). A change is shown well where a head that shows it in time
  stays lit showing it for `SHOWN_FOR_BEATS` of the beat; where no head does on its own
  beat (the template darkens the heads soon after the reveal), it moves, within the same
  bounds, to the beat where the most heads show it well, among the beats where every
  head that shows it on its own beat still does (a move may only improve on the unmoved
  outcome); where no beat within reach does, it plays as above and each head is traced
  `brief` ("shown for N ms"), which repair feeds back. Inside a template overlay the event takes over the overlay's state from
  the beat.

Every bar and beat is counted from the bar's downbeat (`BeatGrid.beat_index`), as the
planner, the cue binder and the plan repair count it.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
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
    WHEEL_LATE_BEATS,
    WHEEL_MOVE_BARS,
    HeadWheels,
    SectionPalette,
    can_darken,
    color_offer,
    darkness_ms,
    dip_fits,
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
    """How far below the level played, as a share of the dimmer's top, the hit's pre-dip
    (or its duck after the flash) holds, and the least difference from the render
    without the hit that counts as visible."""
    decay_beats: float
    """The hit eases from the top (or the duck) back to the section's level over this
    many beats, as `(1 - p)**2` (the intensity accent's curve)."""
    visible_frames: int
    """The flash's frames at the top, the dip's (or duck's) held frames, and the least
    number of frames that must differ visibly for the hit to count as played."""


HITS: dict[str, HitShape] = {
    "LOW": HitShape(contrast=0.25, decay_beats=0.25, visible_frames=2),
    "MED": HitShape(contrast=0.40, decay_beats=0.5, visible_frames=3),
    "HIGH": HitShape(contrast=0.60, decay_beats=0.75, visible_frames=4),
}
"""Proposed (W6; the visible-change rule from the W6/W7 fix round), by the bound lyric
cue's emphasis: a stronger cue cuts deeper, holds longer and rings longer. With room
before the beat a hit is a pre-dip and a snap to full; without it (a reveal on the beat)
a flash and a duck below the section's level."""

HIT_FLOOR = 0.10
"""A hit's pre-dip or duck never goes below this share of the dimmer's top: never dark."""

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

SHOWN_FOR_BEATS = 0.5
"""Proposed (W10 fit review). A colour or gobo change is shown well where a head that shows
it in time stays lit showing it for this share of the beat; a change shown only briefly
(the template's own darkness following the reveal) moves, within its move bounds, to a beat
where some head shows it well, else plays where it is shown and is traced `brief`."""

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
    beat_index: int
    """Its beat's index in the grid's `beat_boundaries` (`BeatGrid.beat_index`)."""
    beat_ms: float
    frame_ms: int
    cue_id: str | None
    emphasis: str | None
    cue_ms: int | None
    """The bound lyric cue's time (`PlanEvent.cue_ms`)."""
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
            if self.cue_ms is not None:
                record["cue_ms"] = self.cue_ms
        return record


def _value(value: Any) -> str | None:
    return None if value is None else str(getattr(value, "value", value))


@dataclass(frozen=True)
class SectionEvents:
    """A plan section's events on the grid (`section_events`)."""

    events: tuple[TimedEvent, ...]
    unplaced: tuple[tuple[int, dict[str, Any]], ...]
    """Events that cannot be placed in the section's frames (their index in the plan
    section, and the trace entry saying why)."""
    end_ms: int
    """The frame the section ends on."""

    def shutter_spans(self) -> list[tuple[TimedEvent, int, int]]:
        """Each closed, strobe and pulse event with the frames it plays over: from its
        frame to the next shutter event's or the section's end (empty where another
        shutter event shares its frame)."""
        shutter = [e for e in self.events if e.action in SHUTTER_ACTIONS]
        ends = [e.frame_ms for e in shutter[1:]] + [self.end_ms]
        return [
            (event, event.frame_ms, end)
            for event, end in zip(shutter, ends[: len(shutter)], strict=True)
            if event.action != "open"
        ]

    def opens(self) -> list[tuple[TimedEvent, bool]]:
        """Each `open` and whether it ends a closed, strobe or pulse event."""
        shutter = [e for e in self.events if e.action in SHUTTER_ACTIONS]
        return [
            (event, index > 0 and shutter[index - 1].action != "open")
            for index, event in enumerate(shutter)
            if event.action == "open"
        ]

    def wheel_events(self) -> list[TimedEvent]:
        return [e for e in self.events if e.action in WHEEL_ACTIONS]

    def hits(self) -> list[TimedEvent]:
        return [e for e in self.events if e.action == "hit"]


def seen_until(shown_ms: float, cue_ms: int | None, beat_ms: float) -> float:
    """**The seen rule**, one for every event that makes something visible: an event a
    transition must not darken or hand over before it has been seen stays visible until
    half a beat after it is shown and, bound to a lyric cue, a quarter beat after the cue,
    whichever is later (proposed, W8 fix rounds). Each kind is shown from (`yield_spans`):
    a colour or gobo change from its reveal (the latest head's first lit frame showing it);
    a hit from the frame it plays on (the latest head's); an `open` from its frame; a
    strobe or `pulse` from its start, for a full beat of it or to its own end if shorter.
    A `closed`, a strobe and a `pulse` also command darkness over their whole span, which a
    transition never cuts into, so the strobe's or pulse's own rule never reaches past it."""
    return max(shown_ms + beat_ms / 2, -math.inf if cue_ms is None else cue_ms + beat_ms / 4)


def yield_spans(
    events: SectionEvents,
    window: tuple[int, int],
    beat_grid: BeatGrid,
    *,
    hits: bool,
    records: Mapping[int, Mapping[str, Any]] | None = None,
    hit_frames: Mapping[int, Sequence[int]] | None = None,
) -> list[tuple[str, int, int]]:
    """What a transition yields to in a part (`window`): `(label, from, until)` on the frame
    grid (from floored, until ceiled) for each event that commands darkness or a wheel or
    must be seen (`seen_until`): a `closed`, strobe or `pulse` over its span; an `open` from
    its frame until seen; a colour or gobo change from its dark lead (or half the beat
    before its beat) until seen from its reveal (`records`: its trace entry, with each
    head's `dark_dip` and `reveal_ms`; without one, its beat's frame); with `hits`, a hit
    from the earliest frame it plays on until seen from the latest (`hit_frames`: where it
    plays on each head without the transition; without them, its beat's frame). A window
    starts after the `until` of the part it leaves and ends before the `from` of the part
    it enters. The render and the plan repair both read it (the repair without records)."""
    spans: list[tuple[str, int, int]] = []
    lo, hi = window
    beats = beat_grid.beat_boundaries

    def beat_of(event: TimedEvent) -> float:
        i = event.beat_index
        return beats[i + 1] - beats[i] if i + 1 < len(beats) else beats[-1] - beats[-2]

    def on_grid(event: TimedEvent, start: float, end: float) -> None:
        spans.append(
            (
                f"{event.action} at bar {event.bar} beat {event.beat}",
                math.floor(start / FRAME) * FRAME,
                math.ceil(end / FRAME) * FRAME,
            )
        )

    for event, start, end in events.shutter_spans():
        if start < hi and end > lo:
            # Its span reaches at least as far as its seen time (a beat of it, or its end).
            on_grid(event, start, end)
    for event in events.events:
        if not lo <= event.frame_ms < hi:
            continue
        length = beat_of(event)
        if event.action == "open":
            on_grid(event, event.frame_ms, seen_until(event.frame_ms, event.cue_ms, length))
        elif event.action in WHEEL_ACTIONS:
            heads = (records or {}).get(event.index, {}).get("heads", {}).values()
            leads = [h["dark_dip"]["from_ms"] for h in heads if "dark_dip" in h]
            reveals = [h["reveal_ms"] for h in heads if h.get("reveal_ms") is not None]
            on_grid(
                event,
                min([*leads, event.frame_ms - length / 2]),
                seen_until(max(reveals, default=event.frame_ms), event.cue_ms, length),
            )
        elif event.action == "hit" and hits:
            frames = list((hit_frames or {}).get(event.index, ())) or [event.frame_ms]
            on_grid(event, min(frames), seen_until(max(frames), event.cue_ms, length))
    return spans


def section_events(section: _Section, beat_grid: BeatGrid) -> SectionEvents:
    """The section's events on the grid, in time order (ties in plan order): each on its
    bar's beat counted from the bar's downbeat (`BeatGrid.beat_index`: a pickup before
    bar 1 shifts nothing). An event whose bar lies outside the section, beyond the grid,
    or on a beat its bar does not have is unplaced, with why."""
    placed: list[TimedEvent] = []
    unplaced: list[tuple[int, dict[str, Any]]] = []
    bars = beat_grid.bar_boundaries
    end = bars[section.end_bar] if section.end_bar < len(bars) else beat_grid.duration_ms
    end_ms = quantize_cue(round(end)).actual_ms
    for index, event in enumerate(section.events):
        action = _value(event.action) or ""
        beat_index = beat_grid.beat_index(event.bar, event.beat)
        why = None
        if not section.start_bar <= event.bar <= section.end_bar:
            why = f"bar {event.bar} lies outside its section (bars {section.start_bar}-{section.end_bar})"
        elif beat_index is None and not beat_grid.bar_beat_indices(event.bar):
            why = f"bar {event.bar} lies beyond the detected beat grid, where the render is dark"
        elif beat_index is None:
            why = (
                f"bar {event.bar} has {len(beat_grid.bar_beat_indices(event.bar))} detected "
                f"beats, not {event.beat}"
            )
        if why is not None or beat_index is None:
            unplaced.append(
                (
                    index,
                    {"action": action, "bar": event.bar, "beat": event.beat, "not_played": why},
                )
            )
            continue
        beat_ms = beat_grid.beat_boundaries[beat_index]
        frame_ms = quantize_cue(round(beat_ms)).actual_ms
        if frame_ms >= end_ms:
            unplaced.append(
                (
                    index,
                    {
                        "action": action,
                        "bar": event.bar,
                        "beat": event.beat,
                        "not_played": "its beat lies past its section's last frame",
                    },
                )
            )
            continue
        placed.append(
            TimedEvent(
                index=index,
                action=action,
                bar=event.bar,
                beat=event.beat,
                beat_index=beat_index,
                beat_ms=beat_ms,
                frame_ms=frame_ms,
                cue_id=event.moment_cue_id,
                emphasis=getattr(event, "cue_emphasis", None),
                cue_ms=getattr(event, "cue_ms", None),
                color=_value(event.color),
                gobo=_value(event.gobo),
            )
        )
    placed.sort(key=lambda e: (e.frame_ms, e.index))
    return SectionEvents(tuple(placed), tuple(unplaced), end_ms)


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
        if not can_darken(profile):
            # Never a refusal: the head plays its template's look (repair records it).
            record["not_played"] = (
                "the head cannot be commanded dark (no dimmer zero or closed shutter state "
                "that extinguishes)"
            )
            return _ShutterPlan(record=record)
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
    widest = max(dark_ms, lit_ms)
    if event.action == "pulse":
        beat = _shortest_beat(beat_grid, start_ms, end_ms)
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
    dark, rates = _strobe_dark(event, start_ms, end_ms, beat_grid, widest)
    if not rates:
        return _ShutterPlan(
            record={
                **record,
                "not_played": f"the {path} cannot follow one flash a beat at this tempo",
            }
        )
    slowest = min(rates)
    record["plays"] = f"a {path} strobe, {slowest} flash(es) a beat" + (
        f" (up to {max(rates)})" if max(rates) != slowest else ""
    )
    record["flashes_per_beat"] = slowest
    if slowest != asked:
        slowed = sum(1 for n in rates if n != asked)
        record["degraded"] = (
            f"{asked} flashes a beat need phases of 1/{2 * asked} beat; the {path} follows "
            f"{widest} ms: on {slowed} of {len(rates)} beats it plays fewer"
        )
    return _ShutterPlan(dark=dark, record=record)


def strobe_beats(beat_grid: BeatGrid, first_index: int, end_ms: float) -> list[tuple[float, float]]:
    """Each beat `(start, length)` from the beat at `first_index` whose frame (the frame
    nearest it) comes before `end_ms`'s (past the grid's last beat, at its last beat's
    length). The render and the plan repair count a strobe's beats with it."""
    beats = beat_grid.beat_boundaries
    out: list[tuple[float, float]] = []
    index = first_index
    start = beats[index]
    stop = quantize_cue(round(end_ms)).actual_ms
    while quantize_cue(round(start)).actual_ms < stop:
        if index + 1 < len(beats):
            length = beats[index + 1] - start
        else:
            length = beats[-1] - beats[-2] if len(beats) > 1 else 500.0
        out.append((start, length))
        start, index = start + length, index + 1
    return out


def _strobe_dark(
    event: TimedEvent, start_ms: int, end_ms: int, beat_grid: BeatGrid, widest: int
) -> tuple[list[tuple[int, int]], list[int]]:
    """A square-wave strobe's dark spans inside `[start_ms, end_ms)`, dark first, its rate
    chosen per beat (`strobe_flashes` on that beat's length, so a faster stretch of the
    song slows only its own beats), and the rate each beat plays (a beat that cannot
    follow one flash stays lit)."""
    spans: list[tuple[int, int]] = []
    rates: list[int] = []
    for beat_start, length in strobe_beats(beat_grid, event.beat_index, end_ms):
        flashes = strobe_flashes(event.action, length, widest)
        if flashes is None:
            continue
        if beat_start + length > start_ms:
            rates.append(flashes)
        half = length / (2 * flashes)
        for j in range(0, 2 * flashes, 2):
            a = max(start_ms, quantize_cue(round(beat_start + j * half)).actual_ms)
            b = min(end_ms, quantize_cue(round(beat_start + (j + 1) * half)).actual_ms)
            if b > a:
                spans.append((a, b))
    return spans, rates


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
        index = next((i for i, c in enumerate(changed) if c.t0_ms == cue.t0_ms), None)
        if index is None:
            return None
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
    Else the turn waits for the first dark window after `T` long enough that reveals it
    within `WHEEL_LATE_BEATS` (and before `until_ms`, the next event of this wheel). Else it
    does not play."""
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
    if holder is not None:
        for start, end in ctx.dark_windows(own, profile):
            if not t < start <= t + HIT_MIN_LIT_FRAMES * FRAME:
                continue
            if end - start < lead or start >= until_ms:
                break
            # The head goes dark within the frames a reveal must stay lit (a template's dark
            # phase opening a frame after the beat): dark on the beat, it turns in that
            # darkness and shows the change from its next reveal.
            turn = start + frames_ms(darkness)
            if next((c for c in own if c.t0_ms <= turn < c.t1_ms), None) is not None:
                record["reveal_ms"] = record["turned_in_the_dark_before_ms"] = end
                return _replace_from(own, channel, old, new, turn, profile), record, True
            following = next((c for c in own if c.t0_ms >= end), None)
            changed = (
                None
                if following is None or following.t0_ms >= until_ms
                else ctx.turned_in_gap(own, channel, old, new, following)
            )
            if changed is not None and following is not None:
                record["reveal_ms"] = record["turned_in_the_dark_before_ms"] = following.t0_ms
                return changed, record, True
            break
    half = _beat_ms(ctx.beat_grid, t - 1) / 2
    dip = (
        None
        if holder is None
        else ctx.dip_span(ctx.dark_runs(holder, profile), max(holder.t0_ms, floor_ms), t, lead)
    )
    if holder is not None and dip is not None and dip_fits(dip[1], 2 * half):
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
    # A late turn may reveal at most `WHEEL_LATE_BEATS` after the beat (a frame of grid
    # tolerance); later, the head would show the old state too long: not played.
    latest = t + WHEEL_LATE_BEATS * _beat_ms(ctx.beat_grid, t) + FRAME
    for start, end in ctx.dark_windows(own, profile):
        if start < t or end - start < lead:
            continue
        if start >= until_ms or start >= latest:
            break
        turn = start + frames_ms(darkness)
        turning = next((c for c in own if c.t0_ms <= turn < c.t1_ms), None)
        if turning is None:
            following = next((c for c in own if c.t0_ms >= end), None)
            if following is None or following.t0_ms > latest:
                continue
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
        if end > latest:
            continue
        record["deferred"] = {
            "turn_ms": turn,
            "reveal_ms": end,
            "late_ms": end - t,
            "reason": why,
        }
        record["reveal_ms"] = end
        return _replace_from(own, channel, old, new, turn, profile), record, True
    record["not_played"] = (
        f"{why}, and no dark window long enough reveals it within {WHEEL_LATE_BEATS:g} beat "
        "of the beat"
    )
    return own, record, False


def _note_reveal(
    record: dict[str, Any],
    own: Sequence[FixtureSegment],
    channel: ChannelName,
    state: str,
    frame_ms: int,
    profile: FixtureCapabilities,
) -> None:
    """Record when the head first shows `state` lit at or after the event's frame
    (`reveal_ms`, on any lit frame; how late that is where the head is dark on the beat or
    a template overlay holds its own state there), and when it first shows it for
    `HIT_MIN_LIT_FRAMES` frames running (`shown_ms`: a frame or two of the new state
    before the head goes dark does not count toward showing it within a beat, though it
    plays)."""
    shows: dict[int, bool] = {}
    for cue in own:
        levels = _levels(cue, profile)
        for t in range(max(cue.t0_ms, frame_ms), cue.t1_ms, FRAME):
            shows[t] = _lit(cue, profile, levels, t) and _state(cue, channel, profile, t) == state
    lit = [t for t in sorted(shows) if shows[t]]
    record["shown_ms"] = next(
        (t for t in lit if all(shows.get(t + k * FRAME, False) for k in range(HIT_MIN_LIT_FRAMES))),
        None,
    )
    if record["shown_ms"] is not None:
        # How long the head stays lit showing it from there (`SHOWN_FOR_BEATS`).
        t = record["shown_ms"]
        while shows.get(t, False):
            t += FRAME
        record["shown_for_ms"] = t - record["shown_ms"]
    if not lit:
        record["reveal_ms"] = None
        record["late"] = {"reason": "the head never shows it lit before the section's end"}
        return
    record["reveal_ms"] = lit[0]
    if lit[0] > frame_ms + HIT_LATE_FRAMES * FRAME and "deferred" not in record:
        record["late"] = {
            "late_ms": lit[0] - frame_ms,
            "reason": "the head is dark on the beat (its template's dark phase) or its "
            "template's overlay holds its own state there; it shows the change from its next "
            "reveal",
        }


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
        here = start <= event.frame_ms < end
        if span_end <= span_start:
            if here:
                for fixture_id in by_head:
                    played.head(
                        event,
                        fixture_id,
                        {"not_played": "another shutter event on its beat replaces it"},
                    )
            continue
        lo, hi = max(span_start, start), min(span_end, end)
        if lo >= hi:
            continue
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
    for event, ends in events.opens():
        if start <= event.frame_ms < end:
            for fixture_id in by_head:
                played.head(
                    event,
                    fixture_id,
                    {"from_ms": event.frame_ms, "plays": "the template's own shutter and level"}
                    if ends
                    else {
                        "not_played": "nothing to open: no closed, strobe or pulse event plays "
                        "before it in the section"
                    },
                )
    _play_wheel_events(
        by_head,
        [e for e in events.wheel_events() if start <= e.frame_ms < end],
        played,
        window=window,
        section_end=events.end_ms,
        profiles=profiles,
        heads=heads,
        palette=palette,
        beat_grid=beat_grid,
        contexts={
            fixture_id: _WheelContext(
                profiles[fixture_id],
                beat_grid,
                darken,
                dip_span,
                dark_runs,
                dark_windows,
                start,
                functools.partial(gap_ok, fixture_id),
            )
            for fixture_id in by_head
        },
    )
    return _in_order(cues, by_head), played


def _shown_well(record: Mapping[str, Any], event: TimedEvent, beat_grid: BeatGrid) -> bool:
    """Whether a head shown the change in time stays lit showing it for
    `SHOWN_FOR_BEATS` of the event's beat."""
    return _shown_in_time(record, event, beat_grid) and record.get(
        "shown_for_ms", 0
    ) + FRAME >= SHOWN_FOR_BEATS * _beat_ms(beat_grid, event.frame_ms)


def _shown_in_time(record: Mapping[str, Any], event: TimedEvent, beat_grid: BeatGrid) -> bool:
    """Whether a head's outcome for a wheel event shows the change lit for
    `HIT_MIN_LIT_FRAMES` frames running within `WHEEL_LATE_BEATS` of the event's frame (a
    frame of grid tolerance)."""
    shown = record.get("shown_ms")
    latest = event.frame_ms + WHEEL_LATE_BEATS * _beat_ms(beat_grid, event.frame_ms) + FRAME
    return "not_played" not in record and shown is not None and shown <= latest


def _play_wheel_events(
    by_head: dict[str, list[FixtureSegment]],
    wheel_events: Sequence[TimedEvent],
    played: EventsPlayed,
    *,
    window: tuple[int, int],
    section_end: int,
    profiles: Mapping[str, FixtureCapabilities],
    heads: Sequence[HeadWheels],
    palette: SectionPalette | None,
    beat_grid: BeatGrid,
    contexts: Mapping[str, _WheelContext],
) -> None:
    """A part's colour and gobo events, in time order, on every head (`by_head` changed in
    place). Each head turns as `_turn` says and shows the change from its first lit frame
    after (`_note_reveal`): late where it is dark on the beat. The event plays on its beat
    where some head shows it within `WHEEL_LATE_BEATS`; a head that never shows it before
    the section's end does not play it (one the part's later frames do not show plays from
    the section's next part, which holds it). Where no head would, the event moves, on every head,
    to the beat within `WHEEL_MOVE_BARS` (later first, inside the part and between this
    wheel's neighbouring events) on which the most heads show it in time, the nearest of
    equals; else it does not play."""
    start, end = window
    beats = beat_grid.beat_boundaries
    reach = WHEEL_MOVE_BARS * beat_grid.beats_per_bar
    # The base each wheel holds at the part's start (the section's colour, a carried
    # event's, or the template's own): what an event turns from; overlay states stay.
    base: dict[str, dict[ChannelName, str]] = {
        fixture_id: {
            channel: _state(own[0], channel, profiles[fixture_id], own[0].t0_ms)
            for channel in WHEEL_ACTIONS.values()
            if own and DISCRETE_KEYS[channel] in profiles[fixture_id].discrete
        }
        for fixture_id, own in by_head.items()
    }
    floor = dict.fromkeys(by_head, start)
    for event in wheel_events:
        channel = WHEEL_ACTIONS[event.action]
        states = event_states(event, heads, palette)
        turning: dict[str, tuple[str, str]] = {}
        for fixture_id in by_head:
            if DISCRETE_KEYS[channel] not in profiles[fixture_id].discrete:
                played.head(
                    event, fixture_id, {"not_played": f"the head has no {channel.value} wheel"}
                )
            elif (new := states.get(fixture_id)) is None:
                played.head(
                    event,
                    fixture_id,
                    {"not_played": f"the head's {channel.value} wheel offers nothing for it"},
                )
            elif channel not in base[fixture_id]:
                continue  # the head has no cue in the part
            elif base[fixture_id][channel] == new:
                played.head(
                    event, fixture_id, {"state": new, "unchanged": "the head already holds it"}
                )
            else:
                turning[fixture_id] = (base[fixture_id][channel], new)
        if not turning:
            continue
        same = [e.frame_ms for e in wheel_events if WHEEL_ACTIONS[e.action] == channel]
        until = next((t for t in same if t > event.frame_ms), end)
        since = max((t for t in same if t < event.frame_ms), default=start - FRAME)

        def trial(
            at: TimedEvent,
            turning: Mapping[str, tuple[str, str]] = turning,
            channel: ChannelName = channel,
            until: int = until,
        ) -> dict[str, tuple[list[FixtureSegment], dict[str, Any], bool]]:
            out = {}
            for fixture_id, (old, new) in turning.items():
                own, record, turned = _turn(
                    by_head[fixture_id],
                    channel,
                    old,
                    new,
                    at,
                    floor[fixture_id],
                    until,
                    contexts[fixture_id],
                )
                if turned:
                    _note_reveal(record, own, channel, new, at.frame_ms, profiles[fixture_id])
                out[fixture_id] = (own, record, turned)
            return out

        def in_time(
            outcomes: Mapping[str, tuple[list[FixtureSegment], dict[str, Any], bool]],
            at: TimedEvent,
        ) -> int:
            return sum(
                1 for _, record, _ in outcomes.values() if _shown_in_time(record, at, beat_grid)
            )

        def well(
            outcomes: Mapping[str, tuple[list[FixtureSegment], dict[str, Any], bool]],
            at: TimedEvent,
        ) -> int:
            return sum(
                1 for _, record, _ in outcomes.values() if _shown_well(record, at, beat_grid)
            )

        def search(
            score: Callable[..., int],
            event: TimedEvent = event,
            since: int = since,
            until: int = until,
            trial: Callable[[TimedEvent], dict[str, Any]] = trial,
            keep: Collection[str] = (),
        ) -> tuple[int, TimedEvent, dict[str, Any], str] | None:
            """The beat within the move bounds (later first, in beats on the grid)
            the most heads `score`, among those where every head in `keep` still shows the
            change."""
            for side, offsets in (
                ("later", range(1, reach + 1)),
                ("earlier", range(-1, -reach - 1, -1)),
            ):
                candidates = []
                for offset in offsets:
                    i = event.beat_index + offset
                    if not 0 <= i < len(beats):
                        continue
                    frame = quantize_cue(round(beats[i])).actual_ms
                    if not (since < frame < until and start <= frame < end):
                        continue
                    moved = replace(event, beat_index=i, beat_ms=beats[i], frame_ms=frame)
                    found = trial(moved)
                    if any(not found[f][2] or found[f][1].get("reveal_ms") is None for f in keep):
                        continue
                    if count := score(found, moved):
                        candidates.append((count, -abs(offset), moved, found))
                if candidates:
                    count, _, moved, found = max(candidates, key=lambda c: (c[0], c[1]))
                    return count, moved, found, side
            return None

        first = outcomes = trial(event)
        chosen, direction, shown = event, None, in_time(outcomes, event)
        brief = False
        if not well(outcomes, event):
            # The rule as it was (its own beat where some head shows it in time, else the
            # beat within reach the most heads do) is the outcome to improve on: a beat where
            # some head shows it well is preferred only where every head that outcome shows
            # it on still does (a move may only improve on the unmoved outcome); else that
            # outcome plays, traced brief.
            baseline: tuple[int, TimedEvent, dict[str, Any], str | None] | None = (
                (shown, event, outcomes, None) if shown else search(in_time)
            )
            kept = [
                f
                for f, (_, record, turned) in (
                    outcomes if baseline is None else baseline[2]
                ).items()
                if turned and record.get("reveal_ms") is not None
            ]
            better = search(well, keep=kept)
            if better is not None:
                _, chosen, outcomes, direction = better
                shown = in_time(outcomes, chosen)
            elif baseline is not None:
                shown, chosen, outcomes, direction = baseline
                brief = True
        position = beat_grid.bar_and_beat(chosen.beat_index)
        # Moving it changes no frame where every head turns the same as on its own beat
        # (dark on both, shown from the same next reveal): then "moved" only names where
        # it is first seen.
        unchanged = direction is not None and all(
            outcomes[f][0] == first[f][0] and outcomes[f][2] == first[f][2] for f in turning
        )
        for fixture_id, (_, new) in turning.items():
            own, record, turned = outcomes[fixture_id]
            if not shown:
                on_beat = first[fixture_id][1]
                why = on_beat.get("not_played") or (
                    "it shows only from its next reveal, "
                    f"{on_beat['reveal_ms'] - event.frame_ms} ms after its beat"
                    if on_beat.get("reveal_ms") is not None
                    else "the head never shows it lit before the section's end"
                )
                record, turned = (
                    {
                        "state": new,
                        "not_played": f"{why}; no head shows it lit within "
                        f"{WHEEL_LATE_BEATS:g} beat of its beat, nor of any beat within "
                        f"{WHEEL_MOVE_BARS} bar(s) of it in the section",
                    },
                    False,
                )
            elif turned and record.get("reveal_ms") is None and end < section_end:
                record["late"] = {"reason": "the head shows it from the section's next part"}
            elif turned and record.get("reveal_ms") is None:
                record, turned = (
                    {
                        "state": new,
                        "not_played": "the head never shows it lit before the section's end",
                    },
                    False,
                )
            if brief and turned and record.get("shown_for_ms") is not None:
                record["brief"] = (
                    f"shown for {record['shown_for_ms']} ms, under {SHOWN_FOR_BEATS:g} beat: "
                    "its template darkens the head soon after, on every beat within reach"
                )
            if direction is not None and shown:
                record["moved"] = {
                    "from_ms": event.frame_ms,
                    "direction": direction,
                    "bar": None if position is None else position[0],
                    "beat": None if position is None else position[1],
                    "offset_ms": chosen.frame_ms - event.frame_ms,
                    "heads_in_time": shown,
                    "reason": (
                        f"no head shows it within {WHEEL_LATE_BEATS:g} beat of its own "
                        "beat (dark there, or the wheel change does not fit)"
                        if not in_time(first, event)
                        else f"on its own beat no head stays lit showing it for "
                        f"{SHOWN_FOR_BEATS:g} beat"
                    ),
                }
                if unchanged:
                    record["moved"]["changes_nothing"] = (
                        "the heads turn as they would on its own beat and first show it there "
                        "(their next reveal): the move names where it is seen"
                    )
            played.head(event, fixture_id, record)
            if turned:
                by_head[fixture_id] = own
                base[fixture_id][channel] = new
                played.final.setdefault(fixture_id, {})[channel] = new
                floor[fixture_id] = max(
                    floor[fixture_id], record.get("reveal_ms") or chosen.frame_ms
                )


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
    frames: _HeadFrames,
    t: int,
    length: int,
    dark_spans: Sequence[tuple[int, int]],
    *,
    local: bool = False,
) -> int:
    """How many frames from `t` a hit may light where the head is dark: inside its cues,
    dark through the dimmer only (the shutter open), outside every show rest, with the
    wheels still from the dark run's start through the frames after, and the close
    latency (plus a frame) left dark after them. 0 where it may not. With `local` (a
    section's REST, dark from its first beat to its end), the dark run is the stretch
    around `t` where the wheels hold `t`'s states and the shutter is open, lit only after
    the wheels have settled from a turn that starts it."""
    profile = frames.profile
    if not profile.visibility.dimmer_zero_extinguishes or "dimmer" not in profile.axes:
        return 0
    if any(a <= t < b for a, b in dark_spans) or t not in frames.cue_at:
        return 0
    held = frames.wheels(t) if local else None

    def stretch(u: int) -> bool:
        """Whether frame `u` is in the dark run (`local`: holding `t`'s wheels, its
        shutter open)."""
        if u not in frames.cue_at or frames.lit[u]:
            return False
        return held is None or (
            frames.wheels(u) == held and not _shutter_dark(frames.own[frames.cue_at[u]], profile, u)
        )

    if local and not stretch(t):
        return 0
    run_start = t
    while stretch(run_start - FRAME):
        run_start -= FRAME
    run_end = t
    while stretch(run_end):
        run_end += FRAME
    if (
        held is not None
        and run_start - FRAME in frames.cue_at
        and not frames.lit[run_start - FRAME]
        and frames.wheels(run_start - FRAME) != held
    ):
        # The stretch starts on a wheel turn in the dark: lit only once it has settled.
        cue = frames.own[frames.cue_at[t]]
        settles = [
            profile.discrete[DISCRETE_KEYS[channel]]
            .states[_state(cue, channel, profile, t)]
            .settle_ms
            for channel in (ChannelName.COLOR, ChannelName.GOBO)
            if DISCRETE_KEYS[channel] in profile.discrete
        ]
        if None in settles or t - run_start < frames_ms(max((s or 0 for s in settles), default=0)):
            return 0
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
    flashing: Sequence[tuple[TimedEvent, int, int]] = (),
    required: Mapping[int, Collection[str]] | None = None,
    rest: bool = False,
) -> tuple[list[FixtureSegment], dict[int, dict[str, Any]], dict[int, dict[str, list[str]]]]:
    """A part's cues as they will play (after every darkness and intensity) with its hits
    played (see the module docstring). A hit is one moment for the rig: it plays on its
    beat's frame on every head that can show it there (lit, or lit for the hit where its
    darkness allows, `_forced_frames`); a head dark there between its template's cues
    does not play it. Only where no head can show it on its beat does the hit move, on
    every head, to a beat within `HIT_MOVE_BARS` inside the part where some head can: for
    a hit bound to a lyric cue, the one nearest the lyric (the later of equals); for
    another, the one the most heads show, a later beat first, an earlier one only where no
    later one serves; else it does not play. A head counts it played only where its frames
    differ visibly from the render without it (`_play_hit`). A hit that lights frames a
    strobe or pulse (`flashing`, each with the frames it plays over) holds dark is traced
    on both. `required` (per hit, the heads that play it in the same plan rendered
    without transitions) makes a beat serve only where every one of those heads can show
    it, so a transition never loses a hit on a head: where its beat does not serve them,
    the hit moves, by the same rules, to the beat that does (else it plays as without
    them). With `rest` (the part is in a section's REST), a head is lit for the hit from
    REST's darkness wherever its wheels hold still around it (`_forced_frames`, local).
    Every head of `profiles` has an outcome per hit. Returns the cues, the trace entry per
    hit, and per flashing event and head the hits that light its dark frames."""
    start, end = window
    records: dict[int, dict[str, Any]] = {}
    notes: dict[int, dict[str, list[str]]] = {}
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

        def able_on(
            index: int,
            frames: dict[str, _HeadFrames] = frames,
            shape: HitShape = shape,
        ) -> dict[str, tuple[int, str, int]]:
            """The heads that can show the hit on the beat at `index`: where, how and for
            how many frames."""
            able: dict[str, tuple[int, str, int]] = {}
            beat = beats[index]
            for fixture_id, head in frames.items():
                lead = _lead(profiles[fixture_id].axes["dimmer"], beat_grid)
                t = quantize_cue(round(beat - lead)).actual_ms
                if not start <= t < end:
                    continue
                decay = _decay_frames(phase_map, beat, shape, t)
                lit = _lit_start(head, t)
                if lit is not None:
                    able[fixture_id] = (lit, "lit", decay)
                elif forced := _forced_frames(head, t, decay, dark_spans, local=rest):
                    able[fixture_id] = (t, "lit_from_dark", forced)
                elif rest:
                    # In REST a cue may start up to `HIT_LATE_FRAMES` after the beat's
                    # frame, as a lit one may (`_lit_start`).
                    for late in range(t + FRAME, t + (HIT_LATE_FRAMES + 1) * FRAME, FRAME):
                        if forced := _forced_frames(head, late, decay, dark_spans, local=True):
                            able[fixture_id] = (late, "lit_from_dark", forced)
                            break
            return able

        home = event.beat_index
        need = frozenset((required or {}).get(event.index, ()))

        def serves(found: Mapping[str, Any], need: frozenset[str] = need) -> bool:
            return bool(found) and need <= found.keys()

        def moved(
            serves: Callable[[Mapping[str, Any]], bool],
            event: TimedEvent = event,
            home: int = home,
            able_on: Callable[[int], dict[str, tuple[int, str, int]]] = able_on,
        ) -> tuple[int, dict[str, tuple[int, str, int]], str] | None:
            """The beat the hit moves to among those that `serves` (within `HIT_MOVE_BARS`
            in beats on the grid): a cue-bound hit's beat after its own where that is at or
            after its lyric, else its nearest the lyric (the later of equals); another's the
            most heads show, a later one first."""
            if event.cue_ms is not None:
                cue_ms = event.cue_ms
                nearby = [
                    offset
                    for offset in (*range(1, reach + 1), *range(-1, -reach - 1, -1))
                    if 0 <= home + offset < len(beats)
                ]
                # At or after the lyric, no later than the beat after its own.
                after = [
                    (beats[home + offset] - cue_ms, home + offset, found)
                    for offset in nearby
                    if offset <= 1
                    and beats[home + offset] >= cue_ms - FRAME
                    and serves(found := able_on(home + offset))
                ]
                if after:
                    _, at, found = min(after, key=lambda c: c[0])
                    return at, found, "later" if at > home else "earlier"
                near = [
                    (abs(beats[home + offset] - cue_ms), -offset, home + offset, found)
                    for offset in nearby
                    if serves(found := able_on(home + offset))
                ]
                if near:
                    _, _, at, found = min(near, key=lambda c: (c[0], c[1]))
                    return at, found, "later" if at > home else "earlier"
                return None
            for side, offsets in (
                ("later", range(1, reach + 1)),
                ("earlier", range(-1, -reach - 1, -1)),
            ):
                candidates = [
                    (len(found), -abs(offset), home + offset, found)
                    for offset in offsets
                    if 0 <= home + offset < len(beats) and serves(found := able_on(home + offset))
                ]
                if candidates:
                    _, _, at, found = max(candidates, key=lambda c: (c[0], c[1]))
                    return at, found, side
            return None

        chosen, able, direction = home, able_on(home), None
        reason = (
            "every head is dark on the event's beat (a show's rest, a repositioning or a "
            "wheel change)"
        )
        if not serves(able):
            found = moved(serves)
            if found is None and not able:
                found = moved(bool)
            elif found is not None and able:
                reason = (
                    "a head that plays it without the transitions is dark on its beat with "
                    "them; it moves where every such head shows it"
                )
            # A move may only improve on the unmoved outcome: never lose a head that
            # shows it on its own beat, unless it moves for the heads a transition would
            # otherwise lose it on (`required`), which the rule protects first.
            if found is not None and (need or able.keys() <= found[1].keys()):
                chosen, able, direction = found
        beat = beats[chosen]
        position = beat_grid.bar_and_beat(chosen)
        for fixture_id in sorted({*by_head, *profiles}):
            if fixture_id not in by_head:
                heads[fixture_id] = {
                    "not_played": "the head has no cue in this part (its template leaves it "
                    "out, or it is held dark through the section's entry)"
                }
                continue
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
            played, outcome = _play_hit(
                frames[fixture_id], axis, shape, phase_map, beat, t, how, count, start
            )
            if played is None:
                heads[fixture_id] = outcome
                continue
            after = _HeadFrames(played, frames[fixture_id].profile)
            relit = [
                u
                for u, lit in frames[fixture_id].lit.items()
                if not lit and after.lit.get(u, False)
            ]
            for flash, lo, hi in flashing:
                inside = [u for u in relit if lo <= u < hi]
                if not inside:
                    continue
                label = f"{flash.action} at bar {flash.bar} beat {flash.beat}"
                outcome.setdefault("lights_flash_dark", []).append(
                    f"{len(inside)} frame(s) the {label} holds dark"
                )
                notes.setdefault(flash.index, {}).setdefault(fixture_id, []).append(
                    f"a hit at {t} ms"
                    + ("" if position is None else f" (bar {position[0]} beat {position[1]})")
                    + f" lights {len(inside)} of its dark frames"
                )
            by_head[fixture_id] = played
            outcome["played_ms"] = t
            if lead := _lead(axis, beat_grid):
                outcome["lead_ms"] = lead
            if direction is not None:
                outcome["moved"] = {
                    "from_ms": event.frame_ms,
                    "direction": direction,
                    "bar": None if position is None else position[0],
                    "beat": None if position is None else position[1],
                    "offset_ms": t - event.frame_ms,
                    "heads_lit": len(able),
                    "rule": "the beat nearest its lyric cue"
                    if event.cue_ms is not None
                    else "the beat the most heads show, a later one first",
                    "reason": reason,
                }
            heads[fixture_id] = outcome
    return _in_order(cues, by_head), records, notes


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
) -> tuple[list[FixtureSegment] | None, dict[str, Any]]:
    """The head's cues with one hit at frame `t`, and its trace entry; the cues are None
    where the hit would not differ visibly from the render without it.

    `shape.visible_frames` frames at the top on the beat (the flash). Where the head is lit
    for at least that many frames plus one right before the beat, inside the section, a
    pre-dip eases down over the quarter beat before it and holds `contrast` of the top
    below the level played for its last `visible_frames` frames, then the flash and a
    decay back to that level (`pre_dip`). Where it is not (dark before the beat, a reveal
    on it), the flash is followed by a duck: `visible_frames` frames `contrast` below the
    level played, recovering over the decay (`flash_and_duck`). Lit from the dark, the
    flash eases back to dark over the decay. Neither dip goes below `HIT_FLOOR` of the top.
    Visible: at least `visible_frames` frames differ from the level played without the hit
    (`L`, per frame) by at least `contrast` of the top, or by `L - HIT_FLOOR` where that is
    less (the deepest the hit may go there), and by at least one word."""
    top = float(axis.operable_range[1])
    zero = axis.dmx_word(0)
    floor = HIT_FLOOR * top
    depth = shape.contrast * top
    hold = shape.visible_frames
    changed: dict[int, float] = {}
    outcome: dict[str, Any] = {
        "how": how,
        "contrast": shape.contrast,
        "decay_beats": shape.decay_beats,
    }

    def base(u: int) -> float:
        return frames.levels[u] if how == "lit" else 0.0

    def usable(u: int) -> bool:
        return u in frames.cue_at and (how != "lit" or frames.lit[u])

    after = []
    for k in range(max(count, 2 * hold + 1)):
        u = t + k * FRAME
        if not usable(u) or (how != "lit" and k >= count):
            break
        after.append(u)
    flash = after[:hold]
    for u in flash:
        changed[u] = top
    before: list[int] = []
    if how == "lit":
        try:
            dip_start = quantize_cue(
                round(
                    musical_time_at(
                        phase_map, Fraction(-HIT_PRE_DIP_BEATS), origin_ms=beat, period_beats=1
                    )
                )
            ).actual_ms
        except MusicalPhaseError:
            dip_start = t - (hold + 1) * FRAME
        u = t - FRAME
        while u >= max(part_start, min(dip_start, t - (hold + 1) * FRAME)) and usable(u):
            before.insert(0, u)
            u -= FRAME
    rest = after[hold:]
    if how == "lit" and len(before) >= hold + 1:
        outcome["shape"] = "pre_dip"
        easing = before[:-hold]
        for position, u in enumerate(easing, start=1):
            dipped = max(floor, base(u) - depth)
            share = (position / (len(easing) + 1)) ** 2
            changed[u] = min(base(u), base(u) + (dipped - base(u)) * share)
        for u in before[-hold:]:
            changed[u] = min(base(u), max(floor, base(u) - depth))
        for k, u in enumerate(rest, start=1):
            p = k / (len(rest) + 1)
            changed[u] = max(base(u), base(u) + (top - base(u)) * (1 - p) ** 2)
        outcome["pre_dip"] = {"from_ms": before[0]}
    elif how == "lit":
        outcome["shape"] = "flash_and_duck"
        ducked = rest[:hold]
        for u in ducked:
            changed[u] = min(base(u), max(floor, base(u) - depth))
        recover = rest[hold:]
        for k, u in enumerate(recover, start=1):
            duck = min(base(u), max(floor, base(u) - depth))
            p = k / (len(recover) + 1)
            changed[u] = base(u) - (base(u) - duck) * (1 - p) ** 2
    else:
        outcome["shape"] = "lit_from_dark"
        for k, u in enumerate(rest, start=1):
            p = k / (len(rest) + 1)
            value = top * (1 - p) ** 2
            if axis.dmx_word(value) == zero:
                break
            changed[u] = value
    if axis.travel_speed_per_s is not None and changed:
        # Each frame-to-frame step within what the dimmer can travel in a frame, walking
        # forward from the frame before the hit to the frame after it.
        allowed = axis.travel_speed_per_s * FRAME / 1000
        lowest, highest = min(changed), max(changed) + FRAME
        previous: float | None = frames.levels.get(lowest - FRAME)
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

    def needed(u: int) -> int:
        """The words frame `u` must differ by: the contrast, or the room above the floor
        where that is less, and at least one."""
        share = min(shape.contrast, max(0.0, (base(u) - floor) / top))
        return max(1, abs(axis.dmx_word(share * top) - zero) - 1)

    visible = sum(
        1
        for u, value in changed.items()
        if abs(axis.dmx_word(value) - axis.dmx_word(base(u))) >= needed(u)
    )
    outcome["visible_frames"] = visible
    if visible < hold:
        return None, {
            "not_played": f"no visible change: the hit would differ from the section's level "
            f"by {shape.contrast:.0%} of full (or all the room above the floor) on {visible} "
            f"frame(s), fewer than {hold}",
            "visible_frames": visible,
        }
    by_cue: dict[int, dict[int, float]] = {}
    for u, value in changed.items():
        by_cue.setdefault(frames.cue_at[u], {})[u] = value
    own = [
        _with_levels(cue, frames.profile, by_cue[i]) if i in by_cue else cue
        for i, cue in enumerate(frames.own)
    ]
    outcome["frames"] = len(changed)
    return own, outcome


def recount_shown(
    entries: Sequence[Mapping[str, Any]],
    segments: Sequence[FixtureSegment],
    profiles: Mapping[str, FixtureCapabilities],
    beat_grid: BeatGrid,
) -> None:
    """Each colour and gobo event's `shown_for_ms` recounted on the planned segments (after
    every transition, transaction and park), so darkness laid after the events (an EXIT,
    a repositioning) shortens it; a head now shown under `SHOWN_FOR_BEATS` is traced
    `brief` (entries changed in place)."""
    heads: dict[str, _HeadFrames] = {}

    def frames_of(fixture_id: str) -> _HeadFrames:
        if fixture_id not in heads:
            heads[fixture_id] = _HeadFrames(_own(segments, fixture_id), profiles[fixture_id])
        return heads[fixture_id]

    for entry in entries:
        if entry.get("action") not in WHEEL_ACTIONS:
            continue
        for fixture_id, outcome in entry.get("heads", {}).items():
            shown = outcome.get("shown_ms")
            if shown is None or fixture_id not in profiles:
                continue
            lit = frames_of(fixture_id).lit
            t = shown
            while lit.get(t, False):
                t += FRAME
            outcome["shown_for_ms"] = t - shown
            half = SHOWN_FOR_BEATS * _beat_ms(beat_grid, shown)
            if t - shown + FRAME < half and "brief" not in outcome:
                outcome["brief"] = (
                    f"shown for {t - shown} ms, under {SHOWN_FOR_BEATS:g} beat: darkness laid "
                    "after the reveal (a transition, a repositioning) follows it"
                )


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
            # Where it played on the bar grid: the beat it moved to.
            summary["played_bar"] = outcome["moved"]["bar"]
            summary["played_beat"] = outcome["moved"]["beat"]
            if "changes_nothing" in outcome["moved"]:
                summary["seen_only"] = True
        if "deferred" in outcome:
            summary.setdefault("late", {})[fixture_id] = outcome["deferred"]["late_ms"]
        elif "late" in outcome and "late_ms" in outcome["late"]:
            summary.setdefault("late", {})[fixture_id] = outcome["late"]["late_ms"]
    summary["played"] = played
    if entry.get("cue_ms") is not None and played:
        # Signed: where each head plays it, less the lyric's own time (negative: before).
        summary["cue_ms"] = entry["cue_ms"]
        summary["offset_ms"] = {f: at - int(entry["cue_ms"]) for f, at in played.items()}
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
        rest = f"; {outcome['rest']}" if "rest" in outcome else ""
        return f"not played ({outcome['not_played']}){rest}"
    if "unchanged" in outcome:
        return f"already {outcome['state']}"
    if "plays" in outcome and "to_ms" not in outcome:
        return f"{outcome['plays']} from {outcome['from_ms']} ms"
    if "plays" in outcome:
        said = f"{outcome['plays']} from {outcome['from_ms']} to {outcome['to_ms']} ms"
        said += f" ({outcome['degraded']})" if "degraded" in outcome else ""
        if outcome.get("lit_by_hits"):
            said += f"; {'; '.join(outcome['lit_by_hits'])}"
        return said
    if "state" in outcome:
        said = f"{outcome['state']} revealed at {outcome['reveal_ms']} ms"
        if "dark_dip" in outcome:
            said += f" after a {outcome['dark_dip']['added_ms']} ms dark dip"
        if "deferred" in outcome:
            said += f", {outcome['deferred']['late_ms']} ms late ({outcome['deferred']['reason']})"
        elif "late" in outcome and "late_ms" in outcome["late"]:
            said += f", {outcome['late']['late_ms']} ms after the beat (dark or in the "
            "template's overlay there)"
        elif "late" in outcome:
            said += f" ({outcome['late']['reason']})"
        if "moved" in outcome and "changes_nothing" in outcome["moved"]:
            moved = outcome["moved"]
            said += (
                f" (first seen at bar {moved['bar']} beat {moved['beat']}, "
                f"{moved['offset_ms']:+d} ms: the heads are dark from its own beat until then)"
            )
        elif "moved" in outcome:
            moved = outcome["moved"]
            said += (
                f" (moved {moved['direction']} to bar {moved['bar']} beat {moved['beat']}, "
                f"{moved['offset_ms']:+d} ms, where {moved['heads_in_time']} head(s) show it "
                "within a beat)"
            )
        return said
    said = f"a hit at {outcome['played_ms']} ms"
    if outcome.get("how") == "lit_from_dark":
        said += ", lit for it from the dark"
    if "pre_dip" in outcome:
        said += f" after a pre-dip from {outcome['pre_dip']['from_ms']} ms"
    if outcome.get("shape") == "flash_and_duck":
        said += ", a flash and a duck below the section's level"
    if "moved" in outcome:
        moved = outcome["moved"]
        said += (
            f" (moved {moved['direction']} to bar {moved['bar']} beat {moved['beat']}, "
            f"{moved['offset_ms']:+d} ms, {moved['rule']}, where {moved['heads_lit']} head(s) "
            "show it)"
        )
    if "degraded" in outcome:
        said += f" ({outcome['degraded']})"
    if outcome.get("lights_flash_dark"):
        said += f" (lighting {'; '.join(outcome['lights_flash_dark'])})"
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
        if event.get("played_bar") is not None:
            verb = "first seen" if event.get("seen_only") else "played"
            line = (
                f"{event['action']} planned at bar {event['bar']} beat {event['beat']}, {verb} "
                f"at bar {event['played_bar']} beat {event['played_beat']}"
            )
        by_time: dict[int, list[str]] = {}
        for fixture_id, at in event.get("played", {}).items():
            by_time.setdefault(at, []).append(fixture_id)
        offsets = event.get("offset_ms", {})
        played = [
            f"at {at} ms"
            + (
                f" ({offsets[heads[0]]:+d} ms from the lyric at {event['cue_ms']} ms)"
                if heads[0] in offsets
                else ""
            )
            + f" on {', '.join(heads)}"
            for at, heads in sorted(by_time.items())
        ]
        if event.get("moved"):
            played.append(f"moved on {', '.join(event['moved'])}")
        if isinstance(event.get("not_played"), str):
            played.append(f"not played ({event['not_played']})")
        elif event.get("not_played"):
            played.append(f"not played on {', '.join(event['not_played'])}")
        parts.append(f"{line} {'; '.join(played) or 'played on no head'}")
    return f"{said}: {'; '.join(parts)}"
