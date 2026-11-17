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
    PlanRepair,
    PlanSection,
    RepairAction,
)
from twinklr.core.sequencer.moving_heads.intensity import SHAPED_LEVELS
from twinklr.core.sequencer.moving_heads.song_intent import (
    RigOffer,
    SectionPalette,
    excluded_reason,
    is_late,
    partial_reason,
    requested_color,
    round_beats,
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
        sections.append(section.model_copy(update=update) if update else section)
    if beat_grid is not None:
        repairs += _boundary_repairs(sections, offer, palettes, beat_grid)
    if len(repairs) == len(plan.repairs):
        return plan
    return plan.model_copy(update={"sections": sections, "repairs": repairs})


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
