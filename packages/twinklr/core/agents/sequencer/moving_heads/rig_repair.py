"""Repair of the planner's colours, gobos and intensity against what the rig can show.

Deterministic repair, as `moment_cues.bind_lyric_moment_cues` repairs what the song
cannot hold: one planned item at a time, recorded in `ChoreographyPlan.repairs`, shown to
the planner on its next revision, never a refusal. The resolution is the renderer's
(`sequencer/moving_heads/song_intent.py`), so what repair keeps is what plays.
"""

from __future__ import annotations

import bisect
from collections.abc import Mapping, Sequence
from itertools import pairwise
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
from twinklr.core.sequencer.moving_heads.events import (
    HIT_LATE_FRAMES,
    HIT_MIN_LIT_FRAMES,
    strobe_beats,
)
from twinklr.core.sequencer.moving_heads.intensity import SHAPED_LEVELS
from twinklr.core.sequencer.moving_heads.song_intent import (
    STROBE_FLASHES_PER_BEAT,
    WHEEL_LATE_BEATS,
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
        for item, reason in _event_records(section, events, parts, offer, beat_grid):
            note(item, RepairAction.RECORDED, reason)
        sections.append(section.model_copy(update=update) if update else section)
    if beat_grid is not None:
        repairs += _boundary_repairs(sections, offer, palettes, beat_grid)
    if len(repairs) == len(plan.repairs):
        return plan
    return plan.model_copy(update={"sections": sections, "repairs": repairs})


def _event_records(
    section: PlanSection,
    events: Sequence[PlanEvent],
    parts: Sequence[tuple[str, int, int, RigOffer]],
    offer: RigOffer,
    beat_grid: BeatGrid | None,
) -> list[tuple[str, str]]:
    """What the render will play differently from what an event asks, for the planner
    (`(item, reason)`; the plan keeps the event, the render decides and traces), each on
    the bar grid (`BeatGrid.beat_index`) and with the render's own tests:

    - a shutter event on a rig whose heads cannot go dark;
    - a strobe or pulse slower than asked on some beat of its span at this tempo, or not
      at all (`strobe_flashes` per beat, `pulse_period`);
    - a hit on heads without a dimmer; on a beat the part's template is dark on some or
      every head (published dark phases: it plays on the others, or moves); on a beat a
      colour or gobo change's dark lead covers (it moves);
    - a colour or gobo change whose wheel change does not fit half the beat before it on
      some head (`dip_fits`, that head's change time) where no darkness is already
      there: it turns up to `WHEEL_LATE_BEATS` late in a dark phase of the template, or
      does not play; one closer to the previous change than the wheel change time."""
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
    wheel_leads = []  # (start, end) of each colour/gobo change's dark lead, in ms
    previous: dict[str, float] = {}
    closed_from: list[tuple[float, float]] = []
    for position, (event, index) in enumerate(shutter):
        following = next((beats[i] for _, i in shutter[position + 1 :]), end_ms)
        if event.action.value == "closed":
            closed_from.append((beats[index], following))
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
            wheel = _wheel_event_records(
                event, item, index, at, parts, offer, beat_grid, closed_from
            )
            records += wheel
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
            if slowest and not wheel:  # it turns before its beat, dark from `slowest` before
                wheel_leads.append((at - slowest, at))
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
                    "the heads are dark there for a colour or gobo change's wheel turn: the hit "
                    "moves to the beat within a bar the most heads show, a later one first, or "
                    "does not play where none does",
                )
            )
            continue
        dark = _dark_heads_on(event, index, parts, offer, beat_grid, length)
        if dark is not None:
            template, heads, every = dark
            records.append(
                (
                    item,
                    f"template {template!r} is dark on this beat on every head (between "
                    "its cues): the hit moves to the beat within a bar the most heads show, "
                    "a later one first"
                    if every
                    else f"template {template!r} is dark on this beat on {', '.join(heads)} "
                    "(between its cues): only the other heads play it",
                )
            )
    return records


SHUTTER_KINDS = frozenset(
    {"open", "closed", "strobe_slow", "strobe_medium", "strobe_fast", "pulse"}
)


def _wheel_event_records(
    event: PlanEvent,
    item: str,
    index: int,
    at: float,
    parts: Sequence[tuple[str, int, int, RigOffer]],
    offer: RigOffer,
    beat_grid: BeatGrid,
    closed_from: Sequence[tuple[float, float]],
) -> list[tuple[str, str]]:
    """A colour or gobo change some head cannot dip for before its beat (`dip_fits` on its
    own wheel change time and the beat before it), unless a `closed` already darkens the
    head there or the part's template is dark through the lead: where the template has a
    dark phase long enough within `WHEEL_LATE_BEATS` after the beat, it turns late; else
    it does not play."""
    beats = beat_grid.beat_boundaries
    before = at - beats[index - 1] if index > 0 else (offer.beat_ms or 0.0)
    if any(start < at <= end for start, end in closed_from):
        return []
    slow = {
        h.fixture_id: h.change_ms
        for h in offer.heads
        if h.change_ms is not None and not dip_fits(h.change_ms, before)
    }
    if not slow:
        return []
    part = next((p for p in parts if p[1] <= event.bar <= p[2]), None)
    template = None if part is None else offer.templates.get(part[0])
    phases = (
        None
        if template is None or not template.variants
        else template.variants.get("base") or next(iter(template.variants.values()))
    )
    late, never = [], []
    for fixture_id, change in slow.items():
        window = None
        if phases is not None and phases.cycle_beats > 0 and part is not None:
            start_index = beat_grid.beat_index(part[1], 1)
            position = (
                ((index - (start_index or 0)) % phases.cycle_beats)
                if start_index is not None
                else None
            )
            beat_ms = at - beats[index - 1] if index > 0 else (offer.beat_ms or 1.0)
            needed = change / beat_ms
            for start, end in phases.heads.get(fixture_id, ()):
                for shift in (0.0, -phases.cycle_beats, phases.cycle_beats):
                    a, b = start + shift, end + shift
                    if (
                        position is not None
                        and b - a >= needed
                        and position <= a <= position + WHEEL_LATE_BEATS
                    ):
                        window = a
            if window is not None:
                late.append(fixture_id)
                continue
        never.append(fixture_id)
    why = (
        f"at this tempo the wheel change of {', '.join(slow)} "
        f"({'/'.join(str(ms) for ms in sorted(set(slow.values())))} ms dark) does not fit half "
        f"the beat before it ({before / 2:.0f} ms)"
    )
    if never:
        return [
            (
                item,
                f"{why}, and its template has no dark moment long enough within "
                f"{WHEEL_LATE_BEATS:g} beat after it: on {', '.join(never)} it does not play; "
                "put the change where the heads are dark, on a slower passage, or after a "
                "`closed`",
            )
        ]
    return [
        (
            item,
            f"{why}: on {', '.join(late)} it turns in the template's next dark moment, up to "
            f"{WHEEL_LATE_BEATS:g} beat late",
        )
    ]


def _dark_heads_on(
    event: PlanEvent,
    index: int,
    parts: Sequence[tuple[str, int, int, RigOffer]],
    offer: RigOffer,
    beat_grid: BeatGrid,
    beat_ms: float | None,
) -> tuple[str, list[str], bool] | None:
    """The part's template, the heads it is dark on at the event's beat (its published
    steady-state dark phases, `RigOffer.templates`, counted in detected beats from the
    part's downbeat, at the render's frame tolerances: a beat within the frames a hit
    needs lit before a dark window counts as dark, one within the frames a hit may play
    late before a lit window as lit), and whether that is every head; None when it is lit
    there on every head or nothing is published. The render decides and traces what
    played."""
    part = next((p for p in parts if p[1] <= event.bar <= p[2]), None)
    template = None if part is None else offer.templates.get(part[0])
    if part is None or template is None or not template.variants:
        return None
    phases = template.variants.get("base") or next(iter(template.variants.values()))
    start_index = beat_grid.beat_index(part[1], 1)
    if phases.cycle_beats <= 0 or start_index is None:
        return None
    position = (index - start_index) % phases.cycle_beats
    frame = 0.0 if not beat_ms else EFFECT_GRID_MS / beat_ms
    heads = sorted(
        fixture_id
        for fixture_id, windows in phases.heads.items()
        # A window may run past the cycle's end into the next cycle's start.
        if any(
            start - HIT_MIN_LIT_FRAMES * frame <= at < end - HIT_LATE_FRAMES * frame
            for start, end in windows
            for at in (position, position + phases.cycle_beats)
        )
    )
    if not heads:
        return None
    return part[0], heads, set(heads) >= {h.fixture_id for h in offer.heads}


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
