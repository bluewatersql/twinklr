"""The planner's section density, played on the heads' light (song-intent rendering W10d).

The planner names `REST`, `SPARSE`, `BALANCED` or `BUSY`; this module turns each into
deterministic changes to a part's cues. Density is light here: REST is dark by the owner's
decision (D3), and SPARSE and BUSY are built on the light too (the owner has been asked
whether density should mean light, as built, or movement, and has not answered). Every
value below is a first proposal for the owner's W10 view, not a measured or accepted look.

- **REST** is dark. A synthetic `closed` on the section's first beat (`with_rest`, event
  index `REST_INDEX`) joins the section's shutter events in `events.apply_section_events`,
  so REST follows the closed rules exactly: commanded dark on each cue's own path, from
  that frame until the planner's next shutter event (`open`, a strobe, `pulse`, `closed`)
  or the section's end. Planner intent wins: a planner shutter event on the same frame
  replaces it (it sorts first, so its span is empty, as for any two shutter events on one
  beat); a hit lights a head from the dark (`lit_from_dark`); a colour or gobo change turns
  in the dark and shows from the head's next reveal. A head that cannot be commanded dark
  (`song_intent.can_darken`) plays its template's look, traced; repair records it.
- **SPARSE**: fewer heads lit at once. The heads split by their folded distribution slot
  (`sparse_halves`: the rig in canonical order folded `min(i, n-1-i)`, so mirror partners
  stay together; even slots one half, odd slots the other), and the halves take turns
  being dark, one unit each, on the cycle of the variant the part plays (as the compiler
  places it, `whole_period_cycle`), never on bars: in unit 0 the even slots are lit and the
  odd dark, in unit 1 the other way. A ONCE template (`finite_snap_hold`) plays its first
  unit (its move) lit on every head and alternates only the hold after it. Fallback order,
  each tried while some head lit as BALANCED would never be lit for `HIT_MIN_LIT_FRAMES`
  running, or nothing would go dark: units of a whole cycle, then of half a cycle, then
  the part plays BALANCED (traced; repair records it). Every head plays as BALANCED over
  each planner event's seen span (`events.yield_spans` with hits, and `seen_until`) widened
  by `EVENT_MARGIN_BEATS` each side, and over each colour or gobo change's whole lit run
  as BALANCED shows it (`shown_spans`), so SPARSE's darkness never touches what an event
  shows. A head that cannot be commanded dark, or whose shutter cannot take the
  alternation in time, stays lit (traced).
- **BALANCED** is the template's own light (identity).
- **BUSY**: an accent each bar on each head's first lit beat of the bar (`play_busy`): the
  first beat of the bar where the head is lit for `HIT_MIN_LIT_FRAMES` running, as
  `events.apply_hits` judges a lit head, played as a hit (`events._play_hit`), `HIGH`
  emphasis where the section's intensity is shaped (`DRAMATIC`, `INTENSE`), else the
  unbound emphasis; never a strobe. Accents are code's, not events: they never enter
  `events.yield_spans`, so they never shorten a transition. An accent whose beat or
  frames fall inside a transition's window on that head, or inside a planner event's seen
  span widened by `EVENT_MARGIN_BEATS` each side, is dropped; one that would not differ visibly from the
  section's level is not played; each is traced with why.

**The song outranks the arrangement.** `DensityGiveWay` is the hook a render accepts per
plan section (`RenderingPipeline.density_give_way`): the section plays BALANCED, or drops
named BUSY accents, each traced with why.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import contextlib
from dataclasses import dataclass, field, replace
from fractions import Fraction
import math
from typing import TYPE_CHECKING, Any

from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.moving_heads.topology import rig_topology
from twinklr.core.sequencer.moving_heads.events import (
    HIT_MIN_LIT_FRAMES,
    HITS,
    SHUTTER_ACTIONS,
    UNBOUND_EMPHASIS,
    SectionEvents,
    TimedEvent,
    _beat_ms,
    _decay_frames,
    _HeadFrames,
    _in_order,
    _lead,
    _lit_start,
    _own,
    _play_hit,
    _shutter_holds,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import quantize_cue
from twinklr.core.sequencer.moving_heads.song_intent import can_darken

if TYPE_CHECKING:
    from twinklr.core.config.fixtures import FixtureGroup
    from twinklr.core.config.fixtures.capabilities import FixtureCapabilities
    from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
    from twinklr.core.sequencer.timing.beat_grid import BeatGrid
    from twinklr.core.sequencer.timing.musical_phase import MusicalPhaseMap

FRAME = EFFECT_GRID_MS

REST, SPARSE, BALANCED, BUSY = "REST", "SPARSE", "BALANCED", "BUSY"

REST_INDEX = -1
"""The synthetic `closed` REST plays as: its index among the section's events (no planned
event has it), so it sorts before a planner event on the same frame and stays out of the
events' trace."""

EVENT_MARGIN_BEATS = 1
"""Proposed (W10d). SPARSE plays every head as BALANCED over each planner event's seen
span widened by this many beats each side (a hit's pre-dip and decay, a colour change's
dark lead and its `SHOWN_FOR_BEATS`); BUSY drops an accent inside a hit's span so widened."""

SPARSE_UNITS: tuple[tuple[str, int], ...] = (("cycle", 1), ("half cycle", 2))
"""SPARSE's units in fallback order: the played variant's cycle divided by each."""

BUSY_SONG_SHARE = 0.25
"""Proposed (W10d). Repair feeds back BUSY sections that together cover more than this
share of the song (lowest energy first): an accent every bar loses its weight. Never a
refusal."""


@dataclass(frozen=True)
class DensityGiveWay:
    """How one plan section's density gives way to the song (the render's
    `density_give_way`, set by the give-way loop that compares the render with the same
    plan at BALANCED)."""

    balanced: str | None = None
    """Why the section plays BALANCED instead (SPARSE gave way to an event); None where
    it plays as planned."""
    accents: Mapping[tuple[str, int], str] = field(default_factory=dict)
    """BUSY accents dropped, by (head, frame), each with why."""


def played_level(asked: str, give_way: DensityGiveWay | None) -> str:
    """The density a section plays: as asked, else BALANCED where it gave way."""
    return BALANCED if give_way is not None and give_way.balanced is not None else asked


# --- REST --------------------------------------------------------------------------------


def with_rest(
    events: SectionEvents, *, start_bar: int, start_ms: int, beat_grid: BeatGrid
) -> SectionEvents:
    """`events` with REST's synthetic `closed` on the section's first beat (its frame as a
    planner event there lands; the section's first frame where the grid has no such beat),
    ordered before a planner event on the same frame."""
    index = beat_grid.beat_index(start_bar, 1)
    beat_ms = float(start_ms) if index is None else beat_grid.beat_boundaries[index]
    rest = TimedEvent(
        index=REST_INDEX,
        action="closed",
        bar=start_bar,
        beat=1,
        beat_index=0 if index is None else index,
        beat_ms=beat_ms,
        frame_ms=start_ms if index is None else quantize_cue(round(beat_ms)).actual_ms,
        cue_id=None,
        emphasis=None,
        cue_ms=None,
        color=None,
        gobo=None,
    )
    ordered = sorted((rest, *events.events), key=lambda e: (e.frame_ms, e.index))
    return replace(events, events=tuple(ordered))


def rest_record(
    events: SectionEvents,
    window: tuple[int, int],
    heads: Sequence[str],
    profiles: Mapping[str, FixtureCapabilities],
    outcomes: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """What REST played in one part (`window`) of a section whose events are `events`
    (`with_rest`): the frames it holds dark, the planner event that ended it, the heads
    that stay lit (no commandable darkness, or a shutter that cannot take it in time,
    from `outcomes`, its first part's per-head trace)."""
    record: dict[str, Any] = {"level": REST}
    shutter = [e for e in events.events if e.action in SHUTTER_ACTIONS]
    at = next(i for i, e in enumerate(shutter) if e.index == REST_INDEX)
    following = shutter[at + 1] if at + 1 < len(shutter) else None
    start = shutter[at].frame_ms
    end = events.end_ms if following is None else following.frame_ms
    if end <= start:
        assert following is not None
        record["plays"] = (
            f"nothing: the planner's {following.action} on the section's first beat replaces "
            "it (planner intent wins on the same frame)"
        )
        return record
    lo, hi = max(start, window[0]), min(end, window[1])
    if hi <= lo:
        assert following is not None
        record["plays"] = (
            f"nothing in this part: the planner's {following.action} at bar {following.bar} "
            f"beat {following.beat} ended it at {end} ms"
        )
        return record
    record["plays"] = "dark"
    record["dark_ms"] = [lo, hi]
    if following is not None and end < window[1]:
        record["ended_by"] = (
            f"the planner's {following.action} at bar {following.bar} beat {following.beat}"
        )
    lit = {
        fixture_id: "it cannot be commanded dark (no dimmer zero or closed shutter state that "
        "extinguishes): it plays its template's look"
        for fixture_id in heads
        if not can_darken(profiles[fixture_id])
    }
    for fixture_id, outcome in (outcomes or {}).items():
        if "not_played" in outcome and fixture_id not in lit:
            lit[fixture_id] = outcome["not_played"]
    if lit:
        record["lit"] = dict(sorted(lit.items()))
    return record


# --- SPARSE ------------------------------------------------------------------------------


def sparse_halves(fixture_group: FixtureGroup) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """The rig's two SPARSE halves: each head's folded slot (`min(i, n-1-i)` of its rank
    in the canonical rig, `topology.rig_topology`; the rig's own order where it has
    none), even slots then odd, so mirror partners share a half. None where every head
    sits on slots of one parity (a rig of one or two heads)."""
    fixtures = [fixture.fixture_id for fixture in fixture_group.expand_fixtures()]
    ranks: Mapping[str, int] = {f: i for i, f in enumerate(fixtures)}
    count = len(fixtures)
    topology = rig_topology(fixture_group)
    if topology is not None:
        # Shared position indices cannot rank the heads: the rig's own order does.
        with contextlib.suppress(ValueError):
            ranks, count = topology.slots()
    folded = {f: min(ranks[f], count - 1 - ranks[f]) for f in fixtures if f in ranks}
    even = tuple(sorted(f for f, slot in folded.items() if slot % 2 == 0))
    odd = tuple(sorted(f for f, slot in folded.items() if slot % 2 == 1))
    return (even, odd) if even and odd else None


def dark_half(unit: int, *, once: bool) -> int | None:
    """Which half (`sparse_halves` index) is dark in SPARSE's unit `unit` of a part: the
    odd slots in even units, the even slots in odd ones; none in a ONCE template's first
    unit (its move)."""
    if once and unit == 0:
        return None
    return 1 if unit % 2 == 0 else 0


def event_spans(
    spans: Sequence[tuple[str, int, int]], beat_grid: BeatGrid
) -> list[tuple[str, int, int]]:
    """Planner events' seen spans (`events.yield_spans`) widened by `EVENT_MARGIN_BEATS`
    each side, on the frame grid."""
    out = []
    for label, start, end in spans:
        before = EVENT_MARGIN_BEATS * _beat_ms(beat_grid, start - 1)
        after = EVENT_MARGIN_BEATS * _beat_ms(beat_grid, end)
        out.append(
            (
                label,
                math.floor((start - before) / FRAME) * FRAME,
                math.ceil((end + after) / FRAME) * FRAME,
            )
        )
    return out


def shown_spans(records: Mapping[int, Mapping[str, Any]] | None) -> list[tuple[str, int, int]]:
    """Each colour or gobo change's lit run showing it on each head, as the part's events
    played it (from its dark lead, or its reveal, to `shown_ms` plus `shown_for_ms`):
    SPARSE keeps every head as BALANCED over it, so no change is shown later or more
    briefly than at BALANCED."""
    out = []
    for entry in (records or {}).values():
        if entry.get("action") not in ("color", "gobo"):
            continue
        label = f"{entry['action']} at bar {entry['bar']} beat {entry['beat']}"
        for outcome in entry.get("heads", {}).values():
            shown, length = outcome.get("shown_ms"), outcome.get("shown_for_ms")
            if shown is None or length is None:
                continue
            start = outcome.get("dark_dip", {}).get("from_ms", outcome.get("reveal_ms", shown))
            out.append((label, min(start, shown), shown + length))
    return out


def _units(
    window: tuple[int, int], at_bars: Callable[[Fraction], float], unit_bars: Fraction
) -> list[tuple[int, int]]:
    """The part's units of `unit_bars` from its first downbeat, on the frame grid, inside
    `window`."""
    lo, hi = window
    units: list[tuple[int, int]] = []
    k = 0
    while True:
        start = max(lo, quantize_cue(round(at_bars(k * unit_bars))).actual_ms)
        if start >= hi:
            return units
        end = min(hi, quantize_cue(round(at_bars((k + 1) * unit_bars))).actual_ms)
        units.append((start, max(start, end)))
        k += 1


def _without(
    spans: Sequence[tuple[int, int]], protected: Sequence[tuple[str, int, int]], shortest: int
) -> list[tuple[int, int]]:
    """`spans` less the `protected` frames, each piece at least `shortest` (a frame)."""
    pieces = list(spans)
    for _, a, b in protected:
        pieces = [
            piece
            for start, end in pieces
            for piece in ((start, min(end, a)), (max(start, b), end))
            if piece[1] > piece[0]
        ]
    return [(a, b) for a, b in pieces if b - a >= max(FRAME, shortest)]


def _lit(own: Sequence[FixtureSegment], profile: FixtureCapabilities) -> list[int]:
    """The head's lit frames, in time order."""
    lit = _HeadFrames(list(own), profile).lit
    return sorted(t for t, on in lit.items() if on)


def _shown(lit: Sequence[int]) -> bool:
    """Whether some `HIT_MIN_LIT_FRAMES` of `lit` run back to back."""
    run = 0
    for previous, t in zip([None, *lit], lit, strict=False):
        run = run + 1 if previous is not None and t - previous == FRAME else 1
        if run >= HIT_MIN_LIT_FRAMES:
            return True
    return False


def play_sparse(
    cues: Sequence[FixtureSegment],
    *,
    window: tuple[int, int],
    cycle_bars: Fraction,
    once: bool,
    at_bars: Callable[[Fraction], float],
    halves: tuple[tuple[str, ...], tuple[str, ...]] | None,
    protected: Sequence[tuple[str, int, int]],
    profiles: Mapping[str, FixtureCapabilities],
    darken: Callable[[Sequence[FixtureSegment], Sequence[tuple[int, int]]], list[FixtureSegment]],
    snap: Callable[[Sequence[tuple[int, int]]], Sequence[tuple[int, int]]],
    shortest_dark_ms: int,
) -> tuple[list[FixtureSegment], dict[str, Any]]:
    """A part's cues (all heads, inside `window`) with SPARSE played (the module
    docstring), and its trace entry. `at_bars` places a bar offset from the part's first
    downbeat as the compiler does (`TemplateCompileContext.bar_offset_to_ms`); `protected`
    the planner events' widened seen spans (`event_spans`); `darken` commands frames dark
    on a cue's own path (`pipeline._dark_over_spans`); `snap` lays a head's dark spans on
    the frame grid at the rig's shortest dark and lit (`pipeline._snap_dark_spans`)."""
    record: dict[str, Any] = {"level": SPARSE, "cycle_bars": float(cycle_bars)}
    if halves is None:
        record["plays"] = "BALANCED"
        record["fallback"] = [
            "every head sits on a folded slot of one parity (mirror partners of a rig of one "
            "or two heads): there is no other half to light while one is dark"
        ]
        return list(cues), record
    by_head = {f: _own(cues, f) for f in sorted({c.fixture_id for c in cues})}
    before = {f: _lit(own, profiles[f]) for f, own in by_head.items()}
    frames = max(1, (window[1] - window[0]) // FRAME)
    cannot = sorted(f for f in by_head if not can_darken(profiles[f]))
    tried: list[str] = []
    for name, divisor in SPARSE_UNITS:
        units = _units(window, at_bars, cycle_bars / divisor)
        dark: dict[str, list[tuple[int, int]]] = {}
        for k, span in enumerate(units):
            half = dark_half(k, once=once)
            if half is not None:
                for fixture_id in halves[half]:
                    dark.setdefault(fixture_id, []).append(span)
        out: dict[str, list[FixtureSegment]] = {}
        held: dict[str, str] = {}
        for fixture_id, own in by_head.items():
            spans = _without(snap(dark.get(fixture_id, [])), protected, shortest_dark_ms)
            if fixture_id in cannot or not spans:
                out[fixture_id] = own
                continue
            darkened = darken(own, spans)
            if not _shutter_holds(darkened, profiles[fixture_id]):
                held[fixture_id] = (
                    "its shutter cannot take the alternation in time around the template's own "
                    "shutter changes"
                )
                out[fixture_id] = own
                continue
            out[fixture_id] = darkened
        after = {f: _lit(own, profiles[f]) for f, own in out.items()}
        never = sorted(f for f in by_head if _shown(before[f]) and not _shown(after[f]))
        if not never and any(len(after[f]) < len(before[f]) for f in by_head):
            record["plays"] = f"half the heads dark, alternating every {name} of the variant"
            record["alternates"] = name
            record["units"] = len(units)
            if tried:
                record["fallback"] = tried
            record["lit_share"] = {
                f: [round(len(before[f]) / frames, 3), round(len(after[f]) / frames, 3)]
                for f in by_head
            }
            if cannot:
                record["lit"] = dict.fromkeys(
                    cannot, "it cannot be commanded dark: it stays lit as BALANCED"
                )
            if held:
                record["lit"] = {**record.get("lit", {}), **held}
            return _in_order(cues, out), record
        tried.append(
            f"every {name}: "
            + (
                f"{', '.join(never)} would never be lit for {HIT_MIN_LIT_FRAMES} frames running"
                if never
                else "nothing would go dark (one unit, a ONCE template's move, or the "
                "planner's events keep every head lit)"
            )
        )
    record["plays"] = "BALANCED"
    record["fallback"] = tried
    return list(cues), record


# --- BUSY --------------------------------------------------------------------------------


def busy_emphasis(shaped: bool) -> str:
    """The emphasis of BUSY's accents: `HIGH` where the section's intensity is shaped (it
    already accents the beats), else the unbound hit's."""
    return "HIGH" if shaped else UNBOUND_EMPHASIS


def play_busy(
    cues: Sequence[FixtureSegment],
    *,
    window: tuple[int, int],
    bars: Sequence[int],
    emphasis: str,
    profiles: Mapping[str, FixtureCapabilities],
    phase_map: MusicalPhaseMap,
    beat_grid: BeatGrid,
    blocked: Mapping[str, Sequence[tuple[str, int, int]]],
    give_way: Mapping[tuple[str, int], str],
) -> tuple[list[FixtureSegment], dict[str, Any]]:
    """A part's cues (all heads, inside `window`, as they play after intensity and hits)
    with BUSY's accents played on `bars` (the module docstring), and its trace entry.
    `blocked`, per head, the spans an accent may not touch, each with what it is (a
    transition's window, a planner event's seen span); `give_way` the accents the
    give-way loop drops (`DensityGiveWay.accents`)."""
    start, end = window
    shape = HITS[emphasis]
    beats = beat_grid.beat_boundaries
    by_head = {f: _own(cues, f) for f in sorted({c.fixture_id for c in cues})}
    placed: dict[str, list[int]] = {}
    dropped: list[dict[str, Any]] = []
    unseen: list[dict[str, Any]] = []
    unlit: dict[str, list[int]] = {}
    no_dimmer: list[str] = []
    for fixture_id, own in by_head.items():
        profile = profiles[fixture_id]
        axis = profile.axes.get("dimmer")
        if axis is None:
            no_dimmer.append(fixture_id)
            continue
        lead = _lead(axis, beat_grid)
        frames = _HeadFrames(own, profile)
        for bar in bars:
            found = None
            for index in beat_grid.bar_beat_indices(bar):
                t = quantize_cue(round(beats[index] - lead)).actual_ms
                if start <= t < end and (lit := _lit_start(frames, t)) is not None:
                    found = (index, t, lit)
                    break
            if found is None:
                unlit.setdefault(fixture_id, []).append(bar)
                continue
            index, t, at = found
            position = beat_grid.bar_and_beat(index)
            label = {
                "fixture_id": fixture_id,
                "bar": bar,
                "beat": None if position is None else position[1],
                "at_ms": at,
            }
            why = give_way.get((fixture_id, at))
            if why is not None:
                dropped.append({**label, "reason": why})
                continue
            decay = _decay_frames(phase_map, beats[index], shape, t)
            played, outcome = _play_hit(
                frames, axis, shape, phase_map, beats[index], at, "lit", decay, start
            )
            if played is None:
                unseen.append({**label, "reason": outcome["not_played"]})
                continue
            after = _HeadFrames(played, profile)
            changed = [u for u, level in after.levels.items() if frames.levels.get(u) != level]
            inside = next(
                (
                    what
                    for what, a, b in blocked.get(fixture_id, ())
                    if any(a <= u < b for u in (at, *changed))
                ),
                None,
            )
            if inside is not None:
                dropped.append({**label, "reason": f"it falls inside {inside}"})
                continue
            own, frames = played, after
            placed.setdefault(fixture_id, []).append(at)
        by_head[fixture_id] = own
    record: dict[str, Any] = {
        "level": BUSY,
        "plays": "an accent each bar on each head's first lit beat",
        "emphasis": emphasis,
        "placed": {f: placed[f] for f in sorted(placed)},
    }
    if dropped:
        record["dropped"] = dropped
    if unseen:
        record["not_visible"] = unseen
    if unlit:
        record["no_lit_beat"] = unlit
    if no_dimmer:
        record["no_dimmer"] = sorted(no_dimmer)
    return _in_order(cues, by_head), record


# --- the trace ---------------------------------------------------------------------------


def describe_density(entry: Mapping[str, Any]) -> list[str]:
    """A part's density trace entry as lines for a reader."""
    level = entry["level"]
    if "gave_way" in entry:
        return [f"density {level}: plays BALANCED ({entry['gave_way']})"]
    if level == REST:
        line = f"density REST: {entry['plays']}"
        if "dark_ms" in entry:
            line += f" from {entry['dark_ms'][0]} to {entry['dark_ms'][1]} ms"
        if "ended_by" in entry:
            line += f", ended by {entry['ended_by']}"
        lines = [line]
        lines += [f"{f} stays lit ({why})" for f, why in entry.get("lit", {}).items()]
        return lines
    if level == SPARSE:
        if entry["plays"] == "BALANCED":
            return [f"density SPARSE: plays BALANCED ({'; '.join(entry.get('fallback', []))})"]
        line = f"density SPARSE: {entry['plays']} ({entry['units']} units)"
        if entry.get("fallback"):
            line += f"; not every cycle: {'; '.join(entry['fallback'])}"
        lines = [line]
        lines += [
            f"{f} lit {before:.0%} of the part as BALANCED, {after:.0%} as SPARSE"
            for f, (before, after) in entry.get("lit_share", {}).items()
        ]
        lines += [f"{f} stays lit ({why})" for f, why in entry.get("lit", {}).items()]
        return lines
    if level == BUSY:
        count = sum(len(at) for at in entry.get("placed", {}).values())
        lines = [f"density BUSY: {count} accent(s) ({entry['emphasis']}), {entry['plays']}"]
        lines += [
            f"accent on {d['fixture_id']} at bar {d['bar']} beat {d['beat']} dropped: {d['reason']}"
            for d in entry.get("dropped", [])
        ]
        lines += [
            f"accent on {d['fixture_id']} at bar {d['bar']} beat {d['beat']} not played: "
            f"{d['reason']}"
            for d in entry.get("not_visible", [])
        ]
        if entry.get("no_dimmer"):
            lines.append(f"{', '.join(entry['no_dimmer'])} have no dimmer: no accent")
        return lines
    return []
