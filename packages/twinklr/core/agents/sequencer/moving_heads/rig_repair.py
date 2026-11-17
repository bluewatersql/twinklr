"""Repair of the planner's colours, gobos and intensity against what the rig can show.

Deterministic repair, as `moment_cues.bind_lyric_moment_cues` repairs what the song
cannot hold: one planned item at a time, recorded in `ChoreographyPlan.repairs`, shown to
the planner on its next revision, never a refusal. The resolution is the renderer's
(`sequencer/moving_heads/song_intent.py`), so what repair keeps is what plays.
"""

from __future__ import annotations

import bisect
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import pairwise
import math
from typing import TYPE_CHECKING, Any

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    EventAction,
    PlanColor,
    PlanEvent,
    PlanRepair,
    PlanSection,
    RepairAction,
)
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import TransitionMode
from twinklr.core.sequencer.models.transition import (
    PlanTransition,
    TransitionChannel,
    TransitionEdge,
    TransitionLength,
)
from twinklr.core.sequencer.moving_heads.events import (
    HIT_LATE_FRAMES,
    HIT_MIN_LIT_FRAMES,
    HIT_MOVE_BARS,
    strobe_beats,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import quantize_cue
from twinklr.core.sequencer.moving_heads.intensity import SHAPED_LEVELS
from twinklr.core.sequencer.moving_heads.song_intent import (
    STROBE_FLASHES_PER_BEAT,
    WHEEL_LATE_BEATS,
    WHEEL_MOVE_BARS,
    DarkPhases,
    RigOffer,
    SectionPalette,
    dip_fits,
    excluded_reason,
    is_late,
    partial_reason,
    pulse_period,
    requested_color,
    round_beats,
    strobe_flashes,
    unshown_color_reason,
    unshown_gobo_reason,
)
from twinklr.core.sequencer.moving_heads.transitions import (
    LIT_MODES,
    SPLIT_ON_BOUNDARY,
    SPLIT_SHARE,
    length_beats,
    resolved_strategies,
)

if TYPE_CHECKING:
    from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _canonical(template_id: str) -> str:
    from twinklr.core.sequencer.moving_heads.templates import get_template

    try:
        return get_template(template_id).template.template_id
    except Exception:  # an unknown template is the validator's to report
        return template_id


def section_offer(offer: RigOffer, section: PlanSection) -> RigOffer:
    """The offer for a section's first part: without the states its template cannot hold
    (`RigOffer.for_templates`). A boundary is entered through the first part."""
    return offer.for_templates({_canonical(section.parts[0].template_id)})


def _parts(offer: RigOffer, section: PlanSection) -> list[tuple[str, int, int, RigOffer]]:
    """Each part of the section: its canonical template, its bars and its offer."""
    out = []
    for part, start, end in section.part_bars():
        template_id = _canonical(part.template_id)
        out.append((template_id, start, end, offer.for_templates({template_id})))
    return out


def _judge(
    offer: RigOffer,
    parts: Sequence[tuple[str, int, int, RigOffer]],
    asked: str,
    unavailable: Sequence[bool],
    missing: Sequence[Sequence[str]],
    played: Sequence[Sequence[str]],
    wheel: str,
    unshown: str,
) -> tuple[str, str] | None:
    """How a colour or gobo plays over a section's parts: `("clear", reason)` when no
    part shows it, `("record", reason)` when some part or head does not, else None."""
    templates = [template for template, *_ in parts]
    if all(unavailable):
        excluded = excluded_reason(offer, templates, wheel)
        rig_wide = (
            offer.color(asked).status != "unavailable"
            if wheel == "color"
            else offer.gobo(asked).available != "none"
        )
        return "clear", (excluded if excluded and rig_wide else unshown)
    if any(unavailable):
        kept = sorted({t for t, gone in zip(templates, unavailable, strict=True) if not gone})
        lost = sorted({t for t, gone in zip(templates, unavailable, strict=True) if gone})
        reason = excluded_reason(offer, lost, wheel) or unshown
        return "record", (
            f"plays in the parts on {', '.join(kept)}; not in those on {', '.join(lost)} ({reason})"
        )
    heads = sorted({head for gone in missing for head in gone})
    if heads:
        shown_by = sorted({head for heads_ in played for head in heads_} - set(heads))
        return "record", partial_reason(shown_by, heads)
    return None


def repair_rig_intent(
    plan: ChoreographyPlan,
    offer: RigOffer,
    palettes: Mapping[str, SectionPalette],
    beat_grid: BeatGrid | None = None,
) -> ChoreographyPlan:
    """Repair the colours and gobos the rig cannot show, one item at a time.

    - A palette role the section's macro palette has no stop for (`RequestedColor.
      role_missing`) becomes `PALETTE_PRIMARY` (adjusted), which then stands or is
      repaired as any colour.
    - A section colour no part of the section shows (`unavailable` with each part's
      template, which leaves out the states its overlay masks cannot reach) is cleared to
      as authored, and a colour event's colour that the part it falls in does not show
      drops the event; a section gobo, or a gobo event's pattern, likewise. The reason
      names the template where its masks, not the rig, are why.
    - One some parts or heads show is kept and recorded, naming what keeps its look.
    - A DRAMATIC or INTENSE intensity on a rig where some or no head has a dimmer axis is
      kept and recorded as not shaped there (`RigOffer.hit`): those heads play the
      template's own level, so emphasis has to come from events or colour.
    - An event the render will play other than asked is kept and recorded
      (`_event_records`): a strobe or pulse slowed at this tempo, a hit on a beat its
      template is dark on (it plays on the lit heads, or moves), a wheel change too soon
      after the previous one.
    - With `beat_grid`, transitions (`_transition_repairs`): one longer than its two
      parts hold is shortened (adjusted); a per-channel strategy for a channel no head
      has is dropped (adjusted); the rest is recorded as it plays (an EXIT the next
      ENTRY replaces, a strategy a channel cannot take, a lit transition's dark cut for a
      colour or gobo change).
    - With `beat_grid`: a colour change between two sections that set colours, where a
      head's wheel change does not fit half the beat before the boundary, is recorded
      for the heads that do not always enter the new section's template dark after the
      previous one (`RigOffer.dark_entries`) when it has no dark window long enough for the turn, or
      only one that opens past half the section (`is_late`).

    A colour a head shows only approximately is not a repair: the offer says so up front
    and the render trace records what plays. Each repair is appended to `plan.repairs`.
    """
    repairs = list(plan.repairs)
    sections: list[PlanSection] = []
    for section in plan.sections:
        palette = palettes.get(section.section_id)
        parts = _parts(offer, section)
        update: dict[str, Any] = {}

        def note(
            item: str, action: RepairAction, reason: str, section_id: str = section.section_id
        ) -> None:
            repairs.append(
                PlanRepair(section_id=section_id, item=item, action=action, reason=reason)
            )

        def colour_verdict(
            hex_: str, among: Sequence[tuple[str, int, int, RigOffer]] = parts
        ) -> tuple[str, str] | None:
            shown = [rig.color(hex_) for *_, rig in among]
            return _judge(
                offer,
                among,
                hex_,
                [s.status == "unavailable" for s in shown],
                [s.missing for s in shown],
                [list(s.heads) for s in shown],
                "color",
                unshown_color_reason(among[0][3]),
            )

        def gobo_verdict(
            pattern: str, among: Sequence[tuple[str, int, int, RigOffer]] = parts
        ) -> tuple[str, str] | None:
            shown = [rig.gobo(pattern) for *_, rig in among]
            return _judge(
                offer,
                among,
                pattern,
                [s.available == "none" for s in shown],
                [s.missing for s in shown],
                [list(s.states) for s in shown],
                "gobo",
                unshown_gobo_reason(among[0][3]),
            )

        color = section.color
        if color is not None:
            asked = requested_color(color.value, palette)
            if asked.role_missing:
                color = update["color"] = PlanColor.PALETTE_PRIMARY
                note(
                    f"colour {section.color.value if section.color else ''}",
                    RepairAction.ADJUSTED,
                    f"the section's palette {palette.palette_id if palette else ''!r} has no "
                    "stop for this role; it is changed to PALETTE_PRIMARY, the palette's "
                    "first colour",
                )
                asked = requested_color(color.value, palette)
            item = f"colour {color.value} ({asked.hex}, {asked.source})"
            verdict = colour_verdict(asked.hex)
            if verdict is not None and verdict[0] == "clear":
                update["color"] = None
                note(
                    item,
                    RepairAction.ADJUSTED,
                    verdict[1] + "; the section keeps its authored colour (as_authored)",
                )
            elif verdict is not None:
                note(item, RepairAction.RECORDED, verdict[1])
        if (
            section.intensity is not None
            and section.intensity.value in SHAPED_LEVELS
            and offer.hit != "all"
        ):
            note(
                f"intensity {section.intensity.value}",
                RepairAction.RECORDED,
                (
                    "no head of this rig has a dimmer axis"
                    if offer.hit == "none"
                    else "only some heads of this rig have a dimmer axis"
                )
                + ", and intensity is played on the dimmer: "
                + ("the heads play" if offer.hit == "none" else "the others play")
                + " the template's own level; emphasis there needs events or colour",
            )
        if section.gobo is not None:
            item = f"gobo {section.gobo.value}"
            verdict = gobo_verdict(section.gobo.value)
            if verdict is not None and verdict[0] == "clear":
                update["gobo"] = None
                note(
                    item,
                    RepairAction.ADJUSTED,
                    verdict[1] + "; the section keeps its authored gobo (as_authored)",
                )
            elif verdict is not None:
                note(item, RepairAction.RECORDED, verdict[1])
        events = []
        changed_events = False
        for event in section.events:
            here = [p for p in parts if p[1] <= event.bar <= p[2]] or parts[:1]
            if event.action is EventAction.COLOR and event.color is not None:
                asked = requested_color(event.color.value, palette)
                if asked.role_missing:
                    note(
                        f"event at {event.describe()}",
                        RepairAction.ADJUSTED,
                        "the section's palette has no stop for this role; it is changed to "
                        "PALETTE_PRIMARY, the palette's first colour",
                    )
                    event = event.model_copy(update={"color": PlanColor.PALETTE_PRIMARY})
                    changed_events = True
                    asked = requested_color(PlanColor.PALETTE_PRIMARY.value, palette)
                item = f"event at {event.describe()} ({asked.hex}, {asked.source})"
                verdict = colour_verdict(asked.hex, here)
                if verdict is not None and verdict[0] == "clear":
                    note(item, RepairAction.DROPPED, verdict[1])
                    changed_events = True
                    continue
                if verdict is not None:
                    note(item, RepairAction.RECORDED, verdict[1])
            if event.action is EventAction.GOBO and event.gobo is not None:
                item = f"event at {event.describe()}"
                verdict = gobo_verdict(event.gobo.value, here)
                if verdict is not None and verdict[0] == "clear":
                    note(item, RepairAction.DROPPED, verdict[1])
                    changed_events = True
                    continue
                if verdict is not None:
                    note(item, RepairAction.RECORDED, verdict[1])
            events.append(event)
        if changed_events:
            update["events"] = events
        for item, reason in _event_records(section, events, parts, offer, beat_grid, palette):
            note(item, RepairAction.RECORDED, reason)
        sections.append(section.model_copy(update=update) if update else section)
    if beat_grid is not None:
        repairs += _boundary_repairs(sections, offer, palettes, beat_grid)
        sections, transition_repairs = _transition_repairs(sections, offer, palettes, beat_grid)
        repairs += transition_repairs
    if len(repairs) == len(plan.repairs):
        return plan
    return plan.model_copy(update={"sections": sections, "repairs": repairs})


def _event_records(
    section: PlanSection,
    events: Sequence[PlanEvent],
    parts: Sequence[tuple[str, int, int, RigOffer]],
    offer: RigOffer,
    beat_grid: BeatGrid | None,
    palette: SectionPalette | None = None,
) -> list[tuple[str, str]]:
    """What the render will play differently from what an event asks, for the planner
    (`(item, reason)`; the plan keeps the event, the render decides and traces), each on
    the bar grid (`BeatGrid.beat_index`) and with the render's own tests:

    - a shutter event on a rig whose heads cannot go dark;
    - a strobe or pulse slower than asked on some beat of its span at this tempo, or not
      at all (`strobe_flashes` per beat, `pulse_period`);
    - a hit on heads without a dimmer; on a beat the part's template is dark on some or
      every head (published dark phases: it plays on the others, or moves, and where to);
      on a beat a colour or gobo change's dark lead covers (it moves);
    - a colour or gobo change (`_wheel_plays`): where heads show it after its beat (dark
      there, or its wheel change does not fit half the beat before it and it turns in a
      later dark moment), where it moves because no head shows it within
      `WHEEL_LATE_BEATS`, where a head never shows it; one closer to the previous change
      than the wheel change time."""
    records: list[tuple[str, str]] = []
    if beat_grid is None:
        return records
    beats = beat_grid.beat_boundaries
    bars = beat_grid.bar_boundaries
    end_ms = bars[section.end_bar] if section.end_bar < len(bars) else beat_grid.duration_ms
    placed = [
        (event, index)
        for event in events
        if (index := beat_grid.beat_index(event.bar, event.beat)) is not None
    ]
    shutter = [(e, i) for e, i in placed if e.action.value in SHUTTER_KINDS]
    wheel_leads: list[tuple[float, float]] = []  # each colour/gobo change's dark lead, in ms
    previous: dict[str, float] = {}
    closed_from: list[tuple[float, float]] = []
    for position, (event, index) in enumerate(shutter):
        following = next((beats[i] for _, i in shutter[position + 1 :]), end_ms)
        if event.action.value == "closed":
            closed_from.append((beats[index], following))
    held: dict[str, dict[str, str]] = {
        "color": _head_colors(section, offer, palette),
        "gobo": _head_gobos(section, offer),
    }
    wheel_placed = [(e, i) for e, i in placed if e.action.value in ("color", "gobo")]
    for event, index in placed:
        action = event.action.value
        item = f"event at {event.describe()}"
        at = beats[index]
        length = beats[index + 1] - at if index + 1 < len(beats) else offer.beat_ms
        if action in SHUTTER_KINDS and offer.dark == "none":
            records.append((item, "no head of this rig can go dark, so it does not play"))
            continue
        tagged = offer.strobes.get(action.removeprefix("strobe_"))
        if action.startswith("strobe_") and (tagged is None or tagged.available != "all"):
            if offer.flash_ms is None:
                records.append(
                    (item, "the heads' darkness has an unknown latency or settle: it cannot flash")
                )
            else:
                following = next((beats[i] for e, i in shutter if i > index), end_ms)
                rates = [
                    strobe_flashes(action, beat_length, offer.flash_ms)
                    for _, beat_length in strobe_beats(beat_grid, index, following)
                ]
                asked = STROBE_FLASHES_PER_BEAT[action]
                played = [rate for rate in rates if rate is not None]
                if not played:
                    records.append(
                        (
                            item,
                            f"at this tempo the darkness ({offer.flash_ms} ms each way) "
                            "cannot follow even one flash a beat: it does not play",
                        )
                    )
                elif min(played) != asked or len(played) < len(rates):
                    slowed = sum(1 for rate in rates if rate != asked)
                    records.append(
                        (
                            item,
                            f"at this tempo it plays as few as {min(played)} flash(es) a beat, "
                            f"not {asked}, on {slowed} of its {len(rates)} beats: the darkness "
                            f"follows {offer.flash_ms} ms phases",
                        )
                    )
        if action == "pulse" and offer.flash_ms is not None and length is not None:
            period = pulse_period(length, offer.flash_ms)
            if period != 1:
                records.append(
                    (
                        item,
                        "at this tempo the pulse cannot follow every beat: "
                        + (
                            "it does not play"
                            if period is None
                            else f"it pulses every {period} beats"
                        ),
                    )
                )
        if action in ("color", "gobo"):
            same = [i for e, i in wheel_placed if e.action is event.action]
            plays = _wheel_plays(
                event,
                index,
                parts,
                offer,
                palette,
                beat_grid,
                closed_from,
                end_ms,
                held[action],
                since=max((i for i in same if i < index), default=-1),
                until=min((i for i in same if i > index), default=len(beats)),
            )
            if plays is not None:
                reasons, leads, shown = plays
                records += [(item, reason) for reason in reasons]
                wheel_leads += leads
                held[action].update(shown)
            slowest = max((h.change_ms or 0 for h in offer.heads), default=0)
            earlier = previous.get(action)
            if earlier is not None and 0 < at - earlier < slowest:
                records.append(
                    (
                        item,
                        f"it comes {at - earlier:.0f} ms after the previous {action} change, "
                        f"and a wheel change needs {slowest} ms of darkness: it turns late or "
                        "does not play; space wheel changes further apart",
                    )
                )
            previous[action] = at
    for event, index in placed:
        if event.action.value != "hit":
            continue
        item = f"event at {event.describe()}"
        at = beats[index]
        length = beats[index + 1] - at if index + 1 < len(beats) else offer.beat_ms
        if offer.hit != "all":
            records.append(
                (
                    item,
                    "no head has a dimmer axis, so it does not play"
                    if offer.hit == "none"
                    else "only the heads with a dimmer axis play it",
                )
            )
        if any(start <= at < end for start, end in wheel_leads):
            records.append(
                (
                    item,
                    "the heads are dark there for a colour or gobo change's wheel turn: "
                    + _hit_move(event, index, parts, offer, beat_grid, wheel_leads),
                )
            )
            continue
        dark = _dark_heads_on(index, parts, offer, beat_grid, length)
        if dark is not None:
            template, heads, every = dark
            records.append(
                (
                    item,
                    f"template {template!r} is dark on this beat on every head (between "
                    "its cues): " + _hit_move(event, index, parts, offer, beat_grid, wheel_leads)
                    if every
                    else f"template {template!r} is dark on this beat on {', '.join(heads)} "
                    "(between its cues): only the other heads play it",
                )
            )
    return records


SHUTTER_KINDS = frozenset(
    {"open", "closed", "strobe_slow", "strobe_medium", "strobe_fast", "pulse"}
)


def _part_at(
    parts: Sequence[tuple[str, int, int, RigOffer]], bar: int
) -> tuple[str, int, int, RigOffer] | None:
    return next((p for p in parts if p[1] <= bar <= p[2]), None)


def _phases(offer: RigOffer, template_id: str) -> DarkPhases | None:
    template = offer.templates.get(template_id)
    if template is None or not template.variants:
        return None
    phases = template.variants.get("base") or next(iter(template.variants.values()))
    return phases if phases.cycle_beats > 0 else None


def _beat_time(beats: Sequence[float], index: int, offset: float) -> float:
    """The time `offset` beats (fractional) after the beat at `index`, on the grid's beats
    (past its ends at the nearest beat's length)."""
    x = index + offset
    k = min(max(math.floor(x), 0), len(beats) - 2)
    return beats[k] + (x - k) * (beats[k + 1] - beats[k])


def _cycle_windows(phases: DarkPhases, fixture_id: str) -> list[tuple[float, float]]:
    """A head's dark windows over three cycles (the previous, this and the next), in beats
    from this cycle's start."""
    return [
        (start + shift, end + shift)
        for start, end in phases.heads.get(fixture_id, ())
        for shift in (-phases.cycle_beats, 0.0, phases.cycle_beats)
    ]


def _head_wheel_turn(
    fixture_id: str,
    change: int | None,
    index: int,
    part: tuple[str, int, int, RigOffer],
    offer: RigOffer,
    beat_grid: BeatGrid,
    closed_from: Sequence[tuple[float, float]],
    end_ms: float,
) -> tuple[float | None, str | None, tuple[float, float] | None]:
    """When a head shows a colour or gobo change on the beat at `index`, as the render
    turns it (`events._turn`): `(late_ms, why_not, dark_lead)`. `late_ms` 0 on the beat
    (after a dip `dip_fits` allows, with the darkness already there counted, `dark_lead` its
    span), the time to its next reveal where it is dark on the beat (a `closed`, the
    template's dark phase), the time to the end of a later dark window that turns it within
    `WHEEL_LATE_BEATS`; None, with why, where it does not show it before the section's end
    or cannot turn it."""
    beats = beat_grid.beat_boundaries
    at = beats[index]
    for start, end in closed_from:
        if start <= at < end:
            # The wheel turns in the `closed`'s darkness, which a hit there then cannot light
            # (its wheels change in that dark run); the head shows it from the `open`.
            if end >= end_ms:
                return None, "the head is dark from a `closed` to the section's end", None
            return _frames_late(at, end), None, (start, end)
    if change is None:
        return None, "a term of its wheel change (a settle, or the close latency) is unknown", None
    start_index = beat_grid.beat_index(part[1], 1)
    if index == start_index:
        # On the part's first beat it turns as the part's colour or gobo does, at its
        # boundary (the section's boundaries record says how).
        return 0.0, None, None
    before = at - beats[index - 1] if index > 0 else (offer.beat_ms or 0.0)
    phases = _phases(offer, part[0])
    windows: list[tuple[float, float]] = []
    position = 0.0
    if phases is not None and start_index is not None:
        windows = _cycle_windows(phases, fixture_id)
        position = (index - start_index) % phases.cycle_beats
    frame = EFFECT_GRID_MS / max(before, 1.0)
    for start, end in windows:
        # Dark where a window opens within the frames a reveal must stay lit (the render
        # does not count a frame or two of the new state as shown).
        if start - HIT_MIN_LIT_FRAMES * frame <= position < end - frame:
            reveal = _beat_time(beats, index, end - position)
            if reveal >= end_ms:
                return None, "the head is not lit again before the section's end", None
            return _frames_late(at, reveal), None, None
    lead = change / before
    covered = sum(
        max(0.0, min(end, position) - max(start, position - lead)) for start, end in windows
    )
    added = change - covered * before
    if dip_fits(added, before):
        return 0.0, None, (at - change, at)
    for start, end in sorted(windows):
        if (
            position < start <= position + WHEEL_LATE_BEATS
            and end - start >= lead
            and end - position <= WHEEL_LATE_BEATS + frame
        ):
            return _frames_late(at, _beat_time(beats, index, end - position)), None, None
    return (
        None,
        f"its {change} ms wheel change (adding {added:.0f} ms of darkness) does not fit half "
        f"the beat before it ({before / 2:.0f} ms), and no dark moment of its template turns "
        f"it within {WHEEL_LATE_BEATS:g} beat",
        None,
    )


def _wheel_plays(
    event: PlanEvent,
    index: int,
    parts: Sequence[tuple[str, int, int, RigOffer]],
    offer: RigOffer,
    palette: SectionPalette | None,
    beat_grid: BeatGrid,
    closed_from: Sequence[tuple[float, float]],
    end_ms: float,
    held: Mapping[str, str],
    *,
    since: int,
    until: int,
) -> tuple[list[str], list[tuple[float, float]], dict[str, str]] | None:
    """How the render plays a colour or gobo event (`events._play_wheel_events`), from the
    published dark phases and each head's wheel change into its own target state: the
    reasons to record, the dark leads of its on-beat turns, and the state each head shows
    after it. On its beat where some head shows it within `WHEEL_LATE_BEATS`; else moved to
    the beat within `WHEEL_MOVE_BARS` (later first, inside the part, between this wheel's
    neighbouring events) where the most heads do; else not played. None where no head
    changes."""
    beats = beat_grid.beat_boundaries
    wheel = event.action.value
    part = _part_at(parts, event.bar)
    if part is None:
        return None
    if wheel == "color":
        if event.color is None:
            return None
        targets = {
            f: h.state
            for f, h in part[3].color(requested_color(event.color.value, palette).hex).heads.items()
        }
    else:
        if event.gobo is None:
            return None
        targets = dict(part[3].gobo(event.gobo.value).states)
    turning = {f: state for f, state in targets.items() if held.get(f) != state}
    if not turning:
        return None
    changes = {h.fixture_id: h.changes.get(wheel, {}) for h in offer.heads}

    def outcomes(i: int) -> dict[str, tuple[float | None, str | None, tuple[float, float] | None]]:
        position = beat_grid.bar_and_beat(i)
        here = None if position is None else _part_at(parts, position[0])
        return {
            f: _head_wheel_turn(
                f,
                changes.get(f, {}).get(state),
                i,
                here or part,
                offer,
                beat_grid,
                closed_from,
                end_ms,
            )
            for f, state in turning.items()
        }

    def in_time(i: int, found: Mapping[str, tuple[float | None, str | None, Any]]) -> int:
        bound = WHEEL_LATE_BEATS * _beat_length(beats, i) + EFFECT_GRID_MS
        return sum(1 for late, _, _ in found.values() if late is not None and late <= bound)

    first = found = outcomes(index)
    chosen, direction = index, None
    shown = in_time(index, found)
    reasons: list[str] = []
    if not shown:
        first_bar, last_bar = part[1], part[2]
        reach = WHEEL_MOVE_BARS * beat_grid.beats_per_bar
        for side, offsets in (
            ("later", range(1, reach + 1)),
            ("earlier", range(-1, -reach - 1, -1)),
        ):
            candidates = []
            for offset in offsets:
                i = index + offset
                position = beat_grid.bar_and_beat(i) if 0 <= i < len(beats) else None
                if position is None or not first_bar <= position[0] <= last_bar:
                    continue
                if not since < i < until or beats[i] >= end_ms:
                    continue
                trial = outcomes(i)
                if count := in_time(i, trial):
                    candidates.append((count, -abs(offset), i, trial))
            if candidates:
                shown, _, chosen, found = max(candidates, key=lambda c: (c[0], c[1]))
                direction = side
                break
        if direction is None:
            whys = sorted({why for _, why, _ in first.values() if why is not None})
            return (
                [
                    f"no head shows it lit within {WHEEL_LATE_BEATS:g} beat of its beat, nor of "
                    f"any beat within {WHEEL_MOVE_BARS} bar(s) of it in the section (the heads "
                    "are dark there, or the wheel change does not fit): it does not play; put "
                    "it where the heads are lit, or after a `closed`"
                    + "".join(
                        f"; on its beat on {', '.join(sorted(f for f, (_, w, _) in first.items() if w == why))}: {why}"
                        for why in whys
                    )
                ],
                [],
                {},
            )
        bar, beat = beat_grid.bar_and_beat(chosen) or (0, 0)
        reasons.append(
            f"no head shows it lit within {WHEEL_LATE_BEATS:g} beat of its beat (the heads are "
            f"dark there, or the wheel change does not fit): it moves {direction} to bar {bar} "
            f"beat {beat} ({beats[chosen] - beats[index]:+.0f} ms), where {shown} head(s) show "
            "it in time"
        )
    late = {
        f: round(ms)
        for f, (ms, _, _) in found.items()
        if ms is not None and ms > 2 * EFFECT_GRID_MS
    }
    if late:
        reasons.append(
            "it shows after its beat on "
            + ", ".join(f"{f} ({ms} ms)" for f, ms in sorted(late.items()))
            + ": dark on the beat (from the head's next reveal), or turned in a later dark "
            "moment"
        )
    for why in sorted({why for _, why, _ in found.values() if why is not None}):
        heads = sorted(f for f, (_, w, _) in found.items() if w == why)
        reasons.append(f"on {', '.join(heads)} it does not play: {why}")
    leads = [lead for _, _, lead in found.values() if lead is not None]
    if chosen != index:
        leads = [
            (a + beats[chosen] - beats[index], b + beats[chosen] - beats[index]) for a, b in leads
        ]
    return reasons, leads, {f: turning[f] for f, (ms, _, _) in found.items() if ms is not None}


def _frames_late(at: float, reveal: float) -> float:
    """How late a reveal at `reveal` is after the beat at `at`, each on the frame nearest
    it (as the render places both)."""
    return quantize_cue(round(reveal)).actual_ms - quantize_cue(round(at)).actual_ms


def _beat_length(beats: Sequence[float], index: int) -> float:
    if index + 1 < len(beats):
        return beats[index + 1] - beats[index]
    return beats[-1] - beats[-2] if len(beats) > 1 else 500.0


def _dark_heads_on(
    index: int,
    parts: Sequence[tuple[str, int, int, RigOffer]],
    offer: RigOffer,
    beat_grid: BeatGrid,
    beat_ms: float | None,
) -> tuple[str, list[str], bool] | None:
    """The part's template, the heads it is dark on at the beat at `index` (its published
    steady-state dark phases, `RigOffer.templates`, counted in detected beats from the
    part's downbeat, at the render's frame tolerances: a beat within the frames a hit
    needs lit before a dark window counts as dark, one within the frames a hit may play
    late before a lit window as lit), and whether that is every head; None when it is lit
    there on every head or nothing is published. The render decides and traces what
    played."""
    position_ = beat_grid.bar_and_beat(index)
    part = None if position_ is None else _part_at(parts, position_[0])
    phases = None if part is None else _phases(offer, part[0])
    start_index = None if part is None else beat_grid.beat_index(part[1], 1)
    if part is None or phases is None or start_index is None:
        return None
    position = (index - start_index) % phases.cycle_beats
    frame = 0.0 if not beat_ms else EFFECT_GRID_MS / beat_ms
    heads = sorted(
        fixture_id
        for fixture_id in phases.heads
        if any(
            start - HIT_MIN_LIT_FRAMES * frame <= position < end - HIT_LATE_FRAMES * frame
            for start, end in _cycle_windows(phases, fixture_id)
        )
    )
    if not heads:
        return None
    return part[0], heads, set(heads) >= {h.fixture_id for h in offer.heads}


def _hit_move(
    event: PlanEvent,
    index: int,
    parts: Sequence[tuple[str, int, int, RigOffer]],
    offer: RigOffer,
    beat_grid: BeatGrid,
    wheel_leads: Sequence[tuple[float, float]],
) -> str:
    """Where a hit no head can show on its beat moves (`events.apply_hits`): to a beat
    within `HIT_MOVE_BARS` inside the section the published dark phases leave some head
    lit on, outside every wheel turn's lead: one bound to a lyric cue to the one nearest
    the lyric (the later of equals), another to the one the most heads show, later first;
    with its direction and offset, or that it does not play."""
    beats = beat_grid.beat_boundaries
    everyone = {h.fixture_id for h in offer.heads}
    reach = HIT_MOVE_BARS * beat_grid.beats_per_bar
    first_bar, last_bar = parts[0][1], parts[-1][2]

    def lit(i: int) -> int:
        position = beat_grid.bar_and_beat(i) if 0 <= i < len(beats) else None
        if position is None or not first_bar <= position[0] <= last_bar:
            return 0
        if any(start <= beats[i] < end for start, end in wheel_leads):
            return 0
        dark = _dark_heads_on(i, parts, offer, beat_grid, _beat_length(beats, i))
        return len(everyone) if dark is None else len(everyone - set(dark[1]))

    offsets = [*range(1, reach + 1), *range(-1, -reach - 1, -1)]
    found = [(index + o, n) for o in offsets if (n := lit(index + o))]
    if not found:
        return (
            f"no head shows it on any beat within {HIT_MOVE_BARS} bar(s) of it in the section, "
            "so it does not play"
        )
    if event.cue_ms is not None:
        chosen, count = min(found, key=lambda c: (abs(beats[c[0]] - event.cue_ms), -c[0]))
        rule, offset = "the beat nearest its lyric cue", beats[chosen] - event.cue_ms
        anchor = "from the lyric"
    else:
        later = [c for c in found if c[0] > index]
        pool = later or found
        chosen, count = max(pool, key=lambda c: (c[1], -abs(c[0] - index)))
        rule, offset = (
            "the beat the most heads show, a later one first",
            beats[chosen] - beats[index],
        )
        anchor = "from its beat"
    bar, beat = beat_grid.bar_and_beat(chosen) or (0, 0)
    direction = "later" if chosen > index else "earlier"
    return (
        f"the hit moves {direction} to bar {bar} beat {beat} ({offset:+.0f} ms {anchor}; "
        f"{rule}), where {count} head(s) show it"
    )


def _head_gobos(section: PlanSection, offer: RigOffer) -> dict[str, str]:
    """The gobo state each head plays for the section's gobo (none when it is as authored
    or the head cannot show it)."""
    if section.gobo is None:
        return {}
    return dict(section_offer(offer, section).gobo(section.gobo.value).states)


def _head_colors(
    section: PlanSection, offer: RigOffer, palette: SectionPalette | None
) -> dict[str, str]:
    """The colour state each head plays for the section's colour (none when it is as
    authored or the head cannot show it)."""
    if section.color is None:
        return {}
    asked = requested_color(section.color.value, palette)
    shown = section_offer(offer, section).color(asked.hex)
    return {fixture_id: head.state for fixture_id, head in shown.heads.items()}


def _boundary_repairs(
    sections: Sequence[PlanSection],
    offer: RigOffer,
    palettes: Mapping[str, SectionPalette],
    beat_grid: BeatGrid,
) -> list[PlanRepair]:
    """The colour changes between consecutive sections that set colours which the render
    may not play from the boundary (see `repair_rig_intent`), one record per section;
    each head judged on its own wheel change time."""
    repairs: list[PlanRepair] = []
    beats = beat_grid.beat_boundaries
    bars = beat_grid.bar_boundaries
    changes = {head.fixture_id: head.change_ms for head in offer.heads}
    if len(beats) < 2:
        return repairs
    # What each head plays, the previous colour where a change was predicted not to.
    played = (
        _head_colors(sections[0], offer, palettes.get(sections[0].section_id)) if sections else {}
    )
    for before, after in pairwise(sections):
        old = played if before.color is not None else {}
        new = played = _head_colors(after, offer, palettes.get(after.section_id))
        successor = _canonical(after.parts[0].template_id)
        # Heads that always enter dark after the previous template turn in the entry.
        dark = offer.dark_entries.get(successor, {}).get(
            _canonical(before.parts[-1].template_id), ()
        )
        heads = sorted(f for f in new if f in old and old[f] != new[f] and f not in dark)
        if not heads or after.start_bar - 1 >= len(bars):
            continue
        boundary = bars[after.start_bar - 1]
        end = bars[after.end_bar] if after.end_bar < len(bars) else beat_grid.duration_ms
        index = min(max(bisect.bisect_left(beats, boundary), 1), len(beats) - 1)
        beat = beats[index] - beats[index - 1]
        slow: dict[str, int] = {
            f: ms for f in heads if (ms := changes.get(f)) is not None and ms > beat / 2
        }
        if not slow:
            continue
        template = offer.templates.get(successor)
        variant = None
        if template is not None:
            preset = after.parts[0].preset_id
            variant = template.variants.get(preset or "base") or next(
                iter(template.variants.values()), None
            )
        starts = {
            f: None if variant is None else variant.first_window(f, ms / beat)
            for f, ms in slow.items()
        }
        never = [f for f, start in starts.items() if start is None]
        played = {**new, **{f: old[f] for f in never}}
        late = [
            f
            for f, start in starts.items()
            if start is not None and is_late(boundary + start * beat, boundary, end)
        ]
        why = (
            f"at this tempo the wheel change of {', '.join(slow)} "
            f"({'/'.join(str(ms) for ms in sorted(set(slow.values())))} ms dark) does not fit "
            f"half the beat before the section ({beat / 2:.0f} ms)"
        )
        if never:
            repairs.append(
                PlanRepair(
                    section_id=after.section_id,
                    item=f"colour change from section '{before.section_id}'",
                    action=RepairAction.RECORDED,
                    reason=f"{why}, and its template has no dark moment long enough to turn "
                    f"the wheel: where {', '.join(never)} play straight into the section they "
                    "keep the previous section's colour; change colour where the heads enter "
                    "dark, or choose a template with a dark phase",
                )
            )
        elif late:
            first = min(start for f, start in starts.items() if f in late and start is not None)
            repairs.append(
                PlanRepair(
                    section_id=after.section_id,
                    item=f"colour change from section '{before.section_id}'",
                    action=RepairAction.RECORDED,
                    reason=f"{why}: where {', '.join(late)} play straight into the section the "
                    f"change waits for the template's first dark moment long enough, beat "
                    f"{round_beats(first)} of its cycle, past half the section",
                )
            )
    return repairs


def _part_beats(beat_grid: BeatGrid, start_bar: int, end_bar: int) -> int:
    """How many detected beats a part's bars hold (`BeatGrid.bar_beat_indices`)."""
    return sum(len(beat_grid.bar_beat_indices(bar)) for bar in range(start_bar, end_bar + 1))


def _fits(
    transition: PlanTransition, before: int | None, after: int | None, beats_per_bar: int
) -> bool:
    """Whether the transition's window fits `before` beats of the part it leaves and
    `after` of the one it enters (None: the heads rest on that side, so its whole length
    lies on the other)."""
    length = length_beats(transition.length, beats_per_bar)
    split = SPLIT_SHARE[transition.split]
    if transition.mode is TransitionMode.SNAP:
        wanted = (length, Fraction(0))
    elif before is None:
        wanted = (Fraction(0), length)
    elif after is None:
        wanted = (length, Fraction(0))
    elif transition.mode in SPLIT_ON_BOUNDARY:
        wanted = (split * length, (1 - split) * length)
    else:
        wanted = (length / 2, length / 2)
    return (before is None or wanted[0] <= before) and (after is None or wanted[1] <= after)


def _transition_repairs(
    sections: Sequence[PlanSection],
    offer: RigOffer,
    palettes: Mapping[str, SectionPalette],
    beat_grid: BeatGrid,
) -> tuple[list[PlanSection], list[PlanRepair]]:
    """Each boundary's transition as the render plays it (`transitions`), for the planner:

    - an EXIT the next section's ENTRY replaces is recorded;
    - one longer than the parts it joins hold (by its placement: a `snap`'s length
      before the boundary; a `crossfade`, `fade_via_black` or `blackout` split by
      `split`; a `morph` or `sweep` centred) is shortened to the longest length that
      fits (adjusted); where even a beat does not fit, recorded;
    - a per-channel strategy for a channel no head has is dropped (adjusted), one only
      some heads have is recorded; one a channel cannot take is recorded with what it
      plays (`transitions.resolved_strategies`);
    - a `crossfade`, `morph` or `sweep` across a colour or gobo change is recorded: the
      wheel turns in a dark cut at its split point, the rest plays lit.
    """
    out = list(sections)
    repairs: list[PlanRepair] = []
    per_bar = beat_grid.beats_per_bar
    has = {
        TransitionChannel.COLOR: [h.fixture_id for h in offer.heads if h.color_wheel],
        TransitionChannel.GOBO: [h.fixture_id for h in offer.heads if h.gobo_wheel],
        TransitionChannel.DIMMER: [] if offer.hit == "none" else ["some"],
        TransitionChannel.SHUTTER: sorted(
            {f for state in offer.strobes.values() for f in (*state.states, *state.missing)}
        ),
    }
    everyone = len(offer.heads)
    for index, section in enumerate(out):
        previous = out[index - 1] if index else None
        following = out[index + 1] if index + 1 < len(out) else None
        changed: list[PlanTransition] = []
        for transition in section.transitions:
            item = f"{transition.edge.value.lower()} transition ({transition.describe()})"

            def note(
                action: RepairAction,
                reason: str,
                item: str = item,
                section_id: str = section.section_id,
            ) -> None:
                repairs.append(
                    PlanRepair(section_id=section_id, item=item, action=action, reason=reason)
                )

            if transition.edge is TransitionEdge.EXIT and following is not None and following.entry:
                note(
                    RepairAction.RECORDED,
                    f"section {following.section_id!r}'s ENTRY plays at this boundary, so this "
                    "EXIT does not",
                )
                changed.append(transition)
                continue
            first, last = section.part_bars()[0], section.part_bars()[-1]
            before: int | None
            after: int | None
            if transition.edge is TransitionEdge.ENTRY:
                before = (
                    None
                    if previous is None
                    else _part_beats(beat_grid, *previous.part_bars()[-1][1:])
                )
                after = _part_beats(beat_grid, first[1], first[2])
            else:
                before = _part_beats(beat_grid, last[1], last[2])
                after = (
                    None
                    if following is None
                    else _part_beats(beat_grid, *following.part_bars()[0][1:])
                )
            kept = transition
            if not _fits(transition, before, after, per_bar):
                shorter = [
                    length
                    for length in TransitionLength
                    if length_beats(length, per_bar) < length_beats(transition.length, per_bar)
                    and _fits(
                        transition.model_copy(update={"length": length}), before, after, per_bar
                    )
                ]
                if shorter:
                    best = max(shorter, key=lambda length: length_beats(length, per_bar))
                    kept = transition.model_copy(update={"length": best})
                    note(
                        RepairAction.ADJUSTED,
                        f"{transition.length.value} does not fit the parts it joins "
                        f"({before if before is not None else 'rest'} beats before the boundary, "
                        f"{after if after is not None else 'rest'} after, by its placement): "
                        f"it is shortened to {best.value}",
                    )
                else:
                    note(
                        RepairAction.RECORDED,
                        "even a beat does not fit the parts it joins: it plays as much as fits",
                    )
            channels = []
            for entry in kept.channels:
                heads = has.get(entry.channel)
                if heads is not None and not heads:
                    note(
                        RepairAction.ADJUSTED,
                        f"{entry.channel.value} {entry.strategy.value}: no head of this rig has "
                        f"a {entry.channel.value} channel, so the strategy is dropped",
                    )
                    continue
                if heads and heads != ["some"] and len(heads) < everyone:
                    note(
                        RepairAction.RECORDED,
                        f"{entry.channel.value} {entry.strategy.value}: only "
                        f"{', '.join(heads)} have a {entry.channel.value} channel and play it",
                    )
                channels.append(entry)
            if len(channels) != len(kept.channels):
                kept = kept.model_copy(update={"channels": channels})
            _, otherwise = resolved_strategies(kept)
            for said in otherwise:
                note(RepairAction.RECORDED, said)
            if kept.mode in LIT_MODES:
                other = previous if kept.edge is TransitionEdge.ENTRY else following
                outgoing, incoming = (
                    (other, section) if kept.edge is TransitionEdge.ENTRY else (section, other)
                )
                if outgoing is not None and incoming is not None:
                    turns = []
                    for wheel in ("colour", "gobo"):
                        before_states = _held_at_end(outgoing, offer, palettes, wheel)
                        after_states = _held_at_start(incoming, offer, palettes, wheel)
                        heads = sorted(
                            f
                            for f in after_states
                            if f in before_states and before_states[f] != after_states[f]
                        )
                        if heads:
                            turns.append(f"the {wheel} changes on {', '.join(heads)}")
                    if turns:
                        slowest = max((h.change_ms or 0 for h in offer.heads), default=0)
                        note(
                            RepairAction.RECORDED,
                            f"{'; '.join(turns)}, and a wheel cannot turn lit: the transition "
                            f"cuts dark at its split point for the turn ({slowest} ms) and plays "
                            "lit around it; where its window is shorter than that, the heads "
                            "enter as without a transition",
                        )
            changed.append(kept)
        if changed != list(section.transitions):
            out[index] = section.model_copy(update={"transitions": changed})
    return out, repairs


def _held_at_start(
    section: PlanSection, offer: RigOffer, palettes: Mapping[str, SectionPalette], wheel: str
) -> dict[str, str]:
    """The colour (or gobo) state each head holds as the section starts."""
    if wheel == "colour":
        return _head_colors(section, offer, palettes.get(section.section_id))
    return _head_gobos(section, offer)


def _held_at_end(
    section: PlanSection, offer: RigOffer, palettes: Mapping[str, SectionPalette], wheel: str
) -> dict[str, str]:
    """The colour (or gobo) state each head holds as the section ends: its own, or its
    last colour (gobo) event's."""
    held = _held_at_start(section, offer, palettes, wheel)
    action = EventAction.COLOR if wheel == "colour" else EventAction.GOBO
    last = [e for e in section.events if e.action is action]
    if not last:
        return held
    event = max(last, key=lambda e: (e.bar, e.beat))
    part = offer.for_templates({_canonical(section.parts[-1].template_id)})
    if action is EventAction.COLOR and event.color is not None:
        asked = requested_color(event.color.value, palettes.get(section.section_id))
        return {**held, **{f: h.state for f, h in part.color(asked.hex).heads.items()}}
    if event.gobo is not None:
        return {**held, **part.gobo(event.gobo.value).states}
    return held
