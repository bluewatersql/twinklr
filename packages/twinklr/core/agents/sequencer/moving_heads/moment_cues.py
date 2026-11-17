"""Deterministic normalisation of a planner response: section ids, repair, cue binding.

A section id that names no song section, or names one twice, is structural: it is refused
so the refinement loop re-plans. Anything else the plan cannot mean on this song is one
item, and repair keeps as much of the planner's evident intent as the song can hold,
adjusting the item where it can and dropping it only where nothing is left to keep. Each
repair is recorded in the plan's `repairs` (which reach the judge, the render trace and
the next refinement prompt): the run never fails for one item.

Repair rules, per section:

- a part label repeating an earlier part's is cleared (the part takes a letter);
- a moment cue reference naming no lyric cue, a cue of another section, or a cue whose
  timestamp lies outside its own section is dropped;
- an event whose action needs a value it lacks (a `color` event with no colour, a `gobo`
  event with no gobo) is dropped; a colour or gobo on an event whose action does not use
  it is cleared;
- an event bound to an unusable cue keeps its own bar and beat and loses the binding; an
  event bound to a usable cue of the section that the section does not list adds the
  reference;
- an event bound to a usable cue moves to the beat of the section nearest the cue's
  timestamp (the cue's own nearest beat, or the section's first or last beat when that
  lies in a neighbouring section); it is dropped only when the section has no beat on
  the grid; with no beat grid it keeps its binding and its own position;
- an unbound event before the section moves to its first beat, one after it to its last
  beat, and one on a beat its bar does not have to the bar's last beat;
- of events of one kind (shutter, hit, colour, gobo) on the same beat, one is kept: a
  cue-bound one first, then one repair did not change, then the first;
- a referenced cue that no event lands on is recorded (nothing is synthesised).
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable, Collection
from typing import Any

from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import (
    NO_VALUE,
    ChoreographyPlan,
    PlanRepair,
    RepairAction,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def bind_lyric_moment_cues(
    plan: ChoreographyPlan,
    lyric_context: LyricContextModel | None,
    beat_grid: BeatGrid | None,
    song_sections: list[SongSectionRef],
) -> ChoreographyPlan:
    """Canonicalise section ids, repair what the song cannot hold, and snap cue-bound
    events to the beat grid.

    Returns:
        The plan with its `repairs` set to what this call changed.

    Raises:
        ValueError: If a section id names no song section or a song section twice.
    """
    data = _canonical_sections(plan, song_sections)
    cues = (
        {}
        if lyric_context is None or not lyric_context.moment_cues
        else {cue.cue_id: cue for cue in lyric_context.moment_cues}
    )
    unusable = _unusable_cues(cues, song_sections)
    grid = beat_grid if beat_grid is not None and beat_grid.beat_boundaries else None
    repairs: list[PlanRepair] = []
    for section in data["sections"]:
        _repair_section(section, cues, unusable, grid, repairs)
    data["repairs"] = [repair.model_dump(mode="json") for repair in repairs]
    return ChoreographyPlan.model_validate(data)


def _canonical_sections(
    plan: ChoreographyPlan, song_sections: list[SongSectionRef]
) -> dict[str, Any]:
    """The plan's dump with every section id the unique `SongSectionRef.section_id`; a
    display name standing for exactly one section is accepted for it."""
    by_id = {section.section_id for section in song_sections}
    by_name: dict[str, list[SongSectionRef]] = {}
    for section in song_sections:
        by_name.setdefault(section.name, []).append(section)

    data = plan.model_dump(mode="json")
    canonical_ids: list[str] = []
    for section in data["sections"]:
        supplied = section["section_id"]
        if supplied in by_id:
            canonical = supplied
        else:
            candidates = by_name.get(supplied, [])
            if len(candidates) > 1:
                candidate_ids = ", ".join(candidate.section_id for candidate in candidates)
                raise ValueError(
                    f"Plan section name '{supplied}' is ambiguous; use unique section_id: "
                    f"{candidate_ids}"
                )
            if not candidates:
                raise ValueError(
                    f"Plan section '{supplied}' does not match any SongSectionRef.section_id"
                )
            canonical = candidates[0].section_id
        section["section_id"] = canonical
        canonical_ids.append(canonical)

    if len(canonical_ids) != len(set(canonical_ids)):
        raise ValueError(
            "Plan sections must use each unique SongSectionRef.section_id at most once"
        )
    return data


def _unusable_cues(
    cues: dict[str, MomentCue], song_sections: list[SongSectionRef]
) -> dict[str, str]:
    """Why each lyric cue whose own facts cannot be placed is unusable, by cue id."""
    sections = {section.section_id: section for section in song_sections}
    last_section_id = song_sections[-1].section_id if song_sections else None
    unusable: dict[str, str] = {}
    for cue_id, cue in cues.items():
        song_section = sections.get(cue.section_id)
        if song_section is None:
            unusable[cue_id] = (
                f"lyric moment cue '{cue_id}' names unknown song section '{cue.section_id}'"
            )
            continue
        end_is_inclusive = cue.section_id == last_section_id
        in_section = song_section.start_ms <= cue.timestamp_ms and (
            cue.timestamp_ms <= song_section.end_ms
            if end_is_inclusive
            else cue.timestamp_ms < song_section.end_ms
        )
        if not in_section:
            unusable[cue_id] = (
                f"lyric moment cue '{cue_id}' at {cue.timestamp_ms} ms lies outside its "
                f"section '{cue.section_id}' [{song_section.start_ms}, {song_section.end_ms}"
                f"{']' if end_is_inclusive else ')'}"
            )
    return unusable


_Record = Callable[[str, RepairAction, str], None]
"""Records one repair of the section being repaired: item, action, reason."""

_KINDS = {
    "open": "shutter",
    "closed": "shutter",
    "strobe_slow": "shutter",
    "strobe_medium": "shutter",
    "strobe_fast": "shutter",
    "pulse": "shutter",
    "hit": "hit",
    "color": "color",
    "gobo": "gobo",
}
"""Event actions by what they drive: two events of one kind on one beat conflict."""


def _repair_section(
    section: dict[str, Any],
    cues: dict[str, MomentCue],
    unusable: dict[str, str],
    grid: BeatGrid | None,
    repairs: list[PlanRepair],
) -> None:
    section_id = section["section_id"]
    start_bar, end_bar = section["start_bar"], section["end_bar"]

    def record(item: str, action: RepairAction, reason: str) -> None:
        repairs.append(PlanRepair(section_id=section_id, item=item, action=action, reason=reason))

    def unusable_reason(cue_id: str) -> str | None:
        cue = cues.get(cue_id)
        if cue is None:
            return f"no lyric moment cue has id '{cue_id}'"
        if cue.section_id != section_id:
            return f"lyric moment cue '{cue_id}' belongs to section '{cue.section_id}'"
        return unusable.get(cue_id)

    labels: set[str] = set()
    for index, part in enumerate(section["parts"]):
        label = part["label"]
        if label is not None and label in labels:
            part["label"] = None
            record(
                f"part {index + 1} label '{label}'",
                RepairAction.ADJUSTED,
                "an earlier part of the section has this label; the part takes a letter",
            )
        elif label is not None:
            labels.add(label)

    referenced: list[str] = []
    for cue_id in section["moment_cues"]:
        reason = unusable_reason(cue_id)
        if reason is None:
            referenced.append(cue_id)
        else:
            record(f"moment cue '{cue_id}'", RepairAction.DROPPED, reason)

    section_beats = _section_beats(start_bar, end_bar, grid)
    kept: list[dict[str, Any]] = []
    repaired: list[bool] = []  # per kept event: whether repair changed or noted it

    def keep(event: dict[str, Any], item: str, first_record: int) -> None:
        kept.append(event)
        repaired.append(any(repair.item == item for repair in repairs[first_record:]))

    for event in section["events"]:
        item = f"{event['action']} event at bar {event['bar']} beat {event['beat']}"
        first_record = len(repairs)
        if not _repair_fields(event, item, record):
            continue
        cue_id = event["moment_cue_id"]
        if cue_id is not None:
            reason = unusable_reason(cue_id)
            if reason is not None:
                event["moment_cue_id"] = None
                record(item, RepairAction.ADJUSTED, f"unbound from its cue: {reason}")
            else:
                if cue_id not in referenced:
                    referenced.append(cue_id)
                    record(
                        f"moment cue '{cue_id}'",
                        RepairAction.ADJUSTED,
                        "added to the section's moment cues: an event lands on it",
                    )
                if grid is None:
                    record(
                        item,
                        RepairAction.RECORDED,
                        f"kept on its own beat, bound to cue '{cue_id}': there is no beat "
                        "grid to place the cue on",
                    )
                elif section_beats is None:
                    record(
                        item,
                        RepairAction.DROPPED,
                        f"the section (bars {start_bar}-{end_bar}) has no beat on the grid",
                    )
                    continue
                else:
                    _bind(event, item, cues[cue_id], grid, section_beats, record)
                    keep(event, item, first_record)
                    continue
        _clamp(event, item, start_bar, end_bar, grid, record)
        keep(event, item, first_record)

    section["moment_cues"] = referenced
    section["events"] = _one_per_kind_and_beat(kept, repaired, record)
    realised = {event["moment_cue_id"] for event in section["events"]}
    for cue_id in referenced:
        if cue_id not in realised:
            record(
                f"moment cue '{cue_id}'",
                RepairAction.RECORDED,
                f"no event lands on this cue: add an event with moment_cue_id '{cue_id}' "
                "that matches its emphasis, or remove the reference",
            )


def _repair_fields(event: dict[str, Any], item: str, record: _Record) -> bool:
    """Pair the event's colour and gobo with its action; False when it must be dropped."""
    action = event["action"]
    for field in ("color", "gobo"):
        if event[field] == NO_VALUE:  # the dumped spelling of "no colour/gobo"
            event[field] = None
    for field in ("color", "gobo"):
        if action == field and event[field] is None:
            record(item, RepairAction.DROPPED, f"a {field} event names no {field}")
            return False
    for field in ("color", "gobo"):
        if action != field and event[field] is not None:
            record(
                item,
                RepairAction.ADJUSTED,
                f"its {field} '{event[field]}' cleared: a {action} event does not use one",
            )
            event[field] = None
    return True


def _section_beats(start_bar: int, end_bar: int, grid: BeatGrid | None) -> range | None:
    """The beat indices of the grid inside the section's bars, None when there are none."""
    if grid is None:
        return None
    first = (start_bar - 1) * grid.beats_per_bar
    last = min(end_bar * grid.beats_per_bar, len(grid.beat_boundaries)) - 1
    return range(first, last + 1) if first <= last else None


def _bind(
    event: dict[str, Any],
    item: str,
    cue: MomentCue,
    grid: BeatGrid,
    beats: range,
    record: _Record,
) -> None:
    """Move the event to the section's beat nearest the cue."""
    snapped_ms = grid.snap_to_nearest_beat(float(cue.timestamp_ms))
    nearest = bisect_left(grid.beat_boundaries, snapped_ms)
    index = min(max(nearest, beats.start), beats.stop - 1)
    bpb = grid.beats_per_bar
    event["bar"], event["beat"] = index // bpb + 1, index % bpb + 1
    if index != nearest:
        record(
            item,
            RepairAction.ADJUSTED,
            f"lyric moment cue '{cue.cue_id}' is nearest bar {nearest // bpb + 1} beat "
            f"{nearest % bpb + 1}, in a neighbouring section: placed on the section's "
            f"{'first' if index == beats.start else 'last'} beat (bar {event['bar']} beat "
            f"{event['beat']})",
        )


def _clamp(
    event: dict[str, Any],
    item: str,
    start_bar: int,
    end_bar: int,
    grid: BeatGrid | None,
    record: _Record,
) -> None:
    """Move an event that lies outside the section, or on a beat its bar does not have,
    into the section."""
    bpb = grid.beats_per_bar if grid is not None else None
    if event["bar"] < start_bar:
        event["bar"], event["beat"] = start_bar, 1
        record(item, RepairAction.ADJUSTED, f"before the section: moved to bar {start_bar} beat 1")
    elif event["bar"] > end_bar:
        event["bar"], event["beat"] = end_bar, bpb or event["beat"]
        record(
            item,
            RepairAction.ADJUSTED,
            f"after the section: moved to bar {end_bar} beat {event['beat']}",
        )
    elif bpb is not None and event["beat"] > bpb:
        event["beat"] = bpb
        record(item, RepairAction.ADJUSTED, f"a bar has {bpb} beats: moved to beat {bpb}")


def _one_per_kind_and_beat(
    events: list[dict[str, Any]], repaired: list[bool], record: _Record
) -> list[dict[str, Any]]:
    """Keep one event of each kind per beat: a cue-bound one first, then one repair did
    not change, then the first."""

    def rank(index: int) -> tuple[bool, bool, int]:
        return (events[index]["moment_cue_id"] is None, repaired[index], index)

    winners: dict[tuple[int, int, str], int] = {}
    for index, event in enumerate(events):
        key = (event["bar"], event["beat"], _KINDS[event["action"]])
        held = winners.get(key)
        if held is None or rank(index) < rank(held):
            winners[key] = index
    kept_indices = set(winners.values())
    for index, event in enumerate(events):
        if index in kept_indices:
            continue
        winner = events[winners[(event["bar"], event["beat"], _KINDS[event["action"]])]]
        same = event == winner
        record(
            f"{event['action']} event at bar {event['bar']} beat {event['beat']}",
            RepairAction.DROPPED,
            "a duplicate of another event on this beat"
            if same
            else f"another {_KINDS[event['action']]} event on this beat is kept "
            f"({winner['action']}"
            + (f" on cue '{winner['moment_cue_id']}'" if winner["moment_cue_id"] else "")
            + ")",
        )
    return [event for index, event in enumerate(events) if index in kept_indices]


def unanswered_high_cues(
    plan: ChoreographyPlan,
    lyric_context: LyricContextModel | None,
    song_sections: list[SongSectionRef],
    *,
    unplannable: Collection[str] = (),
) -> list[str]:
    """One line per HIGH-emphasis lyric moment cue that no event lands on, its section
    planned or not: an advised revision, not an error. A cue in an `unplannable` section
    (beyond the beat grid, `MovingHeadPlanningContext.song_structure`) is never advised:
    that section must not be planned."""
    if lyric_context is None or not lyric_context.moment_cues:
        return []
    cues = {cue.cue_id: cue for cue in lyric_context.moment_cues}
    unusable = _unusable_cues(cues, song_sections)
    planned = {section.section_id: section for section in plan.sections}
    lines: list[str] = []
    for cue in lyric_context.moment_cues:
        if cue.emphasis != "HIGH" or cue.cue_id in unusable or cue.section_id in unplannable:
            continue
        section = planned.get(cue.section_id)
        if section is None:
            lines.append(
                f"section '{cue.section_id}' is not planned, so its HIGH lyric moment cue "
                f"'{cue.cue_id}' (\"{cue.text}\") is unanswered; plan the section and give "
                f"the cue an event with moment_cue_id '{cue.cue_id}'"
            )
        elif cue.cue_id not in {event.moment_cue_id for event in section.events}:
            lines.append(
                f"section '{section.section_id}': the HIGH lyric moment cue "
                f"'{cue.cue_id}' (\"{cue.text}\") has no event; add one with "
                f"moment_cue_id '{cue.cue_id}': an accent that suits its emphasis and "
                "visual hint"
            )
    return lines
