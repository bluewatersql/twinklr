"""Deterministic normalisation of a planner response: section ids, repair, cue binding.

A section id that names no song section, or names one twice, is structural: it is refused
so the refinement loop re-plans. Anything else the plan cannot mean on this song is one
item, and repair drops or adjusts that item alone, recording what it did and why in the
plan's `repairs` (which reach the render trace and the next refinement prompt): the run
never fails for one bad item.

Repair rules, per section:

- a moment cue reference naming no lyric cue, a cue of another section, or a cue whose
  timestamp lies outside its own section is dropped;
- an event bound to such a cue keeps its own bar and beat and loses the binding; an event
  bound to a usable cue of the section that the section does not list adds the reference;
- an event bound to a usable cue moves to the cue's timestamp snapped to the nearest beat
  of the song's beat grid; one that snaps outside the section is dropped;
- an unbound event outside the section's bars, or on a beat the bar does not have, is
  dropped;
- a referenced cue that no event lands on is recorded (nothing is synthesised).
"""

from __future__ import annotations

from bisect import bisect_left
from typing import Any

from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import (
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

    referenced: list[str] = []
    for cue_id in section["moment_cues"]:
        reason = unusable_reason(cue_id)
        if reason is None:
            referenced.append(cue_id)
        else:
            record(f"moment cue '{cue_id}'", RepairAction.DROPPED, reason)

    kept: list[dict[str, Any]] = []
    for event in section["events"]:
        item = f"{event['action']} event at bar {event['bar']} beat {event['beat']}"
        cue_id = event["moment_cue_id"]
        if cue_id is not None:
            reason = unusable_reason(cue_id)
            if reason is None and grid is None:
                reason = "there is no beat grid to place the cue on"
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
                assert grid is not None
                event["bar"], event["beat"] = _snapped_position(cues[cue_id], grid)
                if not start_bar <= event["bar"] <= end_bar:
                    record(
                        item,
                        RepairAction.DROPPED,
                        f"lyric moment cue '{cue_id}' snaps to bar {event['bar']}, outside "
                        f"the section (bars {start_bar}-{end_bar})",
                    )
                    continue
                kept.append(event)
                continue
        if not start_bar <= event["bar"] <= end_bar:
            record(item, RepairAction.DROPPED, f"outside the section (bars {start_bar}-{end_bar})")
            continue
        if grid is not None and event["beat"] > grid.beats_per_bar:
            record(item, RepairAction.DROPPED, f"a bar has {grid.beats_per_bar} beats")
            continue
        kept.append(event)

    section["moment_cues"] = referenced
    section["events"] = kept
    realised = {event["moment_cue_id"] for event in kept}
    for cue_id in referenced:
        if cue_id not in realised:
            record(
                f"moment cue '{cue_id}'",
                RepairAction.RECORDED,
                "no event lands on this cue, so nothing marks it",
            )


def _snapped_position(cue: MomentCue, grid: BeatGrid) -> tuple[int, int]:
    """The 1-indexed bar and beat of the beat nearest the cue's timestamp."""
    snapped_ms = grid.snap_to_nearest_beat(float(cue.timestamp_ms))
    beat_index = bisect_left(grid.beat_boundaries, snapped_ms)
    return beat_index // grid.beats_per_bar + 1, beat_index % grid.beats_per_bar + 1
