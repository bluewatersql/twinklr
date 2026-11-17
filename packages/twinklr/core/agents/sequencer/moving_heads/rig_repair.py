"""Repair of the planner's colours and gobos against what the rig can show.

Deterministic repair, as `moment_cues.bind_lyric_moment_cues` repairs what the song
cannot hold: one planned item at a time, recorded in `ChoreographyPlan.repairs`, shown to
the planner on its next revision, never a refusal. The resolution is the renderer's
(`sequencer/moving_heads/song_intent.py`), so what repair keeps is what plays.
"""

from __future__ import annotations

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
from twinklr.core.sequencer.moving_heads.song_intent import (
    RigOffer,
    SectionPalette,
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
    """The offer for a section: without the states any of its parts' templates cannot
    hold (`RigOffer.for_templates`)."""
    return offer.for_templates({_canonical(part.template_id) for part in section.parts})


def repair_rig_intent(
    plan: ChoreographyPlan,
    offer: RigOffer,
    palettes: Mapping[str, SectionPalette],
    beat_grid: BeatGrid | None = None,
) -> ChoreographyPlan:
    """Repair the colours and gobos the rig cannot show, one item at a time.

    - A palette role the section's macro palette has no stop for (`RequestedColor.
      role_missing`) becomes `PALETTE_PRIMARY` (adjusted).
    - A section colour no head shows (`unavailable`) is cleared to as authored, and a
      colour event's colour that no head shows drops the event; a section gobo, or a gobo
      event's pattern, that no head has likewise. States a part's template cannot hold
      (its overlay masks) count as not shown.
    - One some heads show is kept and recorded, naming the heads that keep their look.
    - With `beat_grid`: a colour change between two sections that set colours, where a
      wheel change does not fit half the beat before the boundary, is recorded when the
      new section's template has no dark phase long enough for the turn in its first
      half (where the heads play straight into it they keep the previous colour, or turn
      late).

    A colour a head shows only approximately is not a repair: the offer says so up front
    and the render trace records what plays. Each repair is appended to `plan.repairs`.
    """
    repairs = list(plan.repairs)
    sections: list[PlanSection] = []
    for section in plan.sections:
        palette = palettes.get(section.section_id)
        rig = section_offer(offer, section)
        update: dict[str, Any] = {}

        def note(
            item: str, action: RepairAction, reason: str, section_id: str = section.section_id
        ) -> None:
            repairs.append(
                PlanRepair(section_id=section_id, item=item, action=action, reason=reason)
            )

        color = section.color
        if color is not None:
            asked = requested_color(color.value, palette)
            item = f"colour {color.value} ({asked.hex}, {asked.source})"
            if asked.role_missing:
                color = update["color"] = PlanColor.PALETTE_PRIMARY
                note(
                    f"colour {section.color.value if section.color else ''}",
                    RepairAction.ADJUSTED,
                    f"the section's palette {palette.palette_id if palette else ''!r} has no "
                    "stop for this role; it plays the palette's PRIMARY colour "
                    "(PALETTE_PRIMARY)",
                )
                asked = requested_color(color.value, palette)
                item = f"colour {color.value} ({asked.hex}, {asked.source})"
            shown = rig.color(asked.hex)
            if shown.status == "unavailable":
                update["color"] = None
                note(
                    item,
                    RepairAction.ADJUSTED,
                    unshown_color_reason(rig) + "; the section keeps its authored colour "
                    "(as_authored)",
                )
            elif shown.status == "partial":
                note(item, RepairAction.RECORDED, partial_reason(shown.heads, shown.missing))
        if section.gobo is not None:
            shown_gobo = rig.gobo(section.gobo)
            item = f"gobo {section.gobo.value}"
            if shown_gobo.available == "none":
                update["gobo"] = None
                note(
                    item,
                    RepairAction.ADJUSTED,
                    unshown_gobo_reason(rig) + "; the section keeps its authored gobo "
                    "(as_authored)",
                )
            elif shown_gobo.available == "some":
                note(
                    item,
                    RepairAction.RECORDED,
                    partial_reason(shown_gobo.states, shown_gobo.missing),
                )
        events = []
        changed_events = False
        for event in section.events:
            if event.action is EventAction.COLOR and event.color is not None:
                asked = requested_color(event.color.value, palette)
                if asked.role_missing:
                    note(
                        f"event at {event.describe()}",
                        RepairAction.ADJUSTED,
                        "the section's palette has no stop for this role; it plays the "
                        "palette's PRIMARY colour (PALETTE_PRIMARY)",
                    )
                    event = event.model_copy(update={"color": PlanColor.PALETTE_PRIMARY})
                    changed_events = True
                    asked = requested_color(PlanColor.PALETTE_PRIMARY.value, palette)
                shown = rig.color(asked.hex)
                item = f"event at {event.describe()} ({asked.hex}, {asked.source})"
                if shown.status == "unavailable":
                    note(item, RepairAction.DROPPED, unshown_color_reason(rig))
                    changed_events = True
                    continue
                if shown.status == "partial":
                    note(item, RepairAction.RECORDED, partial_reason(shown.heads, shown.missing))
            if event.action is EventAction.GOBO and event.gobo is not None:
                shown_gobo = rig.gobo(event.gobo)
                item = f"event at {event.describe()}"
                if shown_gobo.available == "none":
                    note(item, RepairAction.DROPPED, unshown_gobo_reason(rig))
                    changed_events = True
                    continue
                if shown_gobo.available == "some":
                    note(
                        item,
                        RepairAction.RECORDED,
                        partial_reason(shown_gobo.states, shown_gobo.missing),
                    )
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
    may not play from the boundary (see `repair_rig_intent`), one record per section."""
    repairs: list[PlanRepair] = []
    change_ms = offer.wheel_change_ms
    beats = beat_grid.beat_boundaries
    if change_ms is None or len(beats) < 2:
        return repairs
    for before, after in pairwise(sections):
        old = _head_colors(before, offer, palettes.get(before.section_id))
        new = _head_colors(after, offer, palettes.get(after.section_id))
        heads = sorted(f for f in new if f in old and old[f] != new[f])
        if not heads or after.start_bar - 1 >= len(beat_grid.bar_boundaries):
            continue
        boundary = beat_grid.bar_boundaries[after.start_bar - 1]
        index = min(
            max(next((i for i, b in enumerate(beats) if b >= boundary), 1), 1), len(beats) - 1
        )
        beat = beats[index] - beats[index - 1]
        if change_ms <= beat / 2:
            continue
        template = offer.templates.get(_canonical(after.parts[0].template_id))
        variant = None
        if template is not None:
            preset = after.parts[0].preset_id
            variant = template.variants.get(preset or "base") or next(
                iter(template.variants.values()), None
            )
        needed = change_ms / beat
        starts = {
            fixture_id: None if variant is None else variant.first_window(fixture_id, needed)
            for fixture_id in heads
        }
        length = (after.end_bar - after.start_bar + 1) * beat_grid.beats_per_bar
        never = [f for f, start in starts.items() if start is None]
        late = [f for f, start in starts.items() if start is not None and start > length / 2]
        why = (
            f"at this tempo a wheel change ({change_ms} ms dark) does not fit half the beat "
            f"before the section ({beat / 2:.0f} ms)"
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
