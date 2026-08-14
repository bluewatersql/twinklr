"""Deterministic binding of lyric MomentCues to moving-head events."""

from __future__ import annotations

from bisect import bisect_left

from twinklr.core.agents.audio.lyrics.models import LyricContextModel, MomentCue
from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def lyric_moment_cue_errors(
    plan: ChoreographyPlan, lyric_context: LyricContextModel | None
) -> list[str]:
    """Return cross-model reference errors before an LLM judge is called."""
    cues = _cue_map(lyric_context)
    errors: list[str] = []
    for section in plan.sections:
        for reference in section.moment_cues:
            cue = cues.get(reference.cue_id)
            if cue is None:
                errors.append(
                    f"Section '{section.section_name}' references unknown lyric MomentCue id "
                    f"'{reference.cue_id}'"
                )
            elif cue.section_id != section.section_name:
                errors.append(
                    f"Lyric MomentCue '{cue.cue_id}' belongs to section '{cue.section_id}', "
                    f"not '{section.section_name}'"
                )
    return errors


def bind_lyric_moment_cues(
    plan: ChoreographyPlan,
    lyric_context: LyricContextModel | None,
    beat_grid: BeatGrid | None,
    song_sections: list[SongSectionRef],
) -> ChoreographyPlan:
    """Canonicalize section joins and snap cue-driven events to the one BeatGrid."""
    plan = _canonicalize_section_ids(plan, song_sections)
    errors = lyric_moment_cue_errors(plan, lyric_context)
    if errors:
        raise ValueError("; ".join(errors))

    cues = _cue_map(lyric_context)
    _validate_referenced_cue_timing(plan, cues, song_sections)
    has_cue_events = any(
        event.moment_cue_id is not None
        for section in plan.sections
        for event in section.shutter_events
    ) or any(
        event.moment_cue_id is not None
        for section in plan.sections
        for event in section.gobo_events
    )
    if not has_cue_events:
        return plan
    if beat_grid is None or not beat_grid.beat_boundaries:
        raise ValueError("Lyric MomentCue events require a populated BeatGrid")

    sections = [_bind_section(section, cues, beat_grid) for section in plan.sections]
    return ChoreographyPlan.model_validate(
        {
            **plan.model_dump(mode="json"),
            "sections": [section.model_dump(mode="json") for section in sections],
        }
    )


def _canonicalize_section_ids(
    plan: ChoreographyPlan, song_sections: list[SongSectionRef]
) -> ChoreographyPlan:
    """Normalize legacy unique names, rejecting ambiguous/repeated display names."""
    by_id = {section.section_id: section for section in song_sections}
    by_name: dict[str, list[SongSectionRef]] = {}
    for section in song_sections:
        by_name.setdefault(section.name, []).append(section)

    data = plan.model_dump(mode="json")
    canonical_ids: list[str] = []
    for section in data["sections"]:
        supplied = section["section_name"]
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
        section["section_name"] = canonical
        canonical_ids.append(canonical)

    if len(canonical_ids) != len(set(canonical_ids)):
        raise ValueError(
            "Plan sections must use each unique SongSectionRef.section_id at most once"
        )
    return ChoreographyPlan.model_validate(data)


def _validate_referenced_cue_timing(
    plan: ChoreographyPlan,
    cues: dict[str, MomentCue],
    song_sections: list[SongSectionRef],
) -> None:
    """Reject invalid cue facts before BeatGrid snapping can clamp an endpoint."""
    sections = {section.section_id: section for section in song_sections}
    last_section_id = song_sections[-1].section_id if song_sections else None
    referenced_ids = {
        reference.cue_id for section in plan.sections for reference in section.moment_cues
    }
    for cue_id in referenced_ids:
        cue = cues.get(cue_id)
        if cue is None:
            continue
        song_section = sections.get(cue.section_id)
        if song_section is None:
            raise ValueError(
                f"Lyric MomentCue '{cue_id}' names unknown SongSectionRef.section_id "
                f"'{cue.section_id}'"
            )
        end_is_inclusive = cue.section_id == last_section_id
        in_section = song_section.start_ms <= cue.timestamp_ms and (
            cue.timestamp_ms <= song_section.end_ms
            if end_is_inclusive
            else cue.timestamp_ms < song_section.end_ms
        )
        if not in_section:
            raise ValueError(
                f"Lyric MomentCue '{cue_id}' timestamp {cue.timestamp_ms}ms is outside section "
                f"'{cue.section_id}' [{song_section.start_ms}, {song_section.end_ms}"
                f"{']' if end_is_inclusive else ')'}"
            )


def _cue_map(lyric_context: LyricContextModel | None) -> dict[str, MomentCue]:
    if lyric_context is None or not lyric_context.moment_cues:
        return {}
    return {cue.cue_id: cue for cue in lyric_context.moment_cues}


def _bind_section(
    section: PlanSection, cues: dict[str, MomentCue], beat_grid: BeatGrid
) -> PlanSection:
    def event_position(cue_id: str) -> tuple[int, int]:
        cue = cues[cue_id]
        snapped_ms = beat_grid.snap_to_nearest_beat(float(cue.timestamp_ms))
        beat_index = bisect_left(beat_grid.beat_boundaries, snapped_ms)
        bar = beat_index // beat_grid.beats_per_bar + 1
        beat = beat_index % beat_grid.beats_per_bar + 1
        if not section.start_bar <= bar <= section.end_bar:
            raise ValueError(
                f"Lyric MomentCue '{cue_id}' resolves to bar {bar}, outside section "
                f"'{section.section_name}' ({section.start_bar}-{section.end_bar})"
            )
        return bar, beat

    data = section.model_dump(mode="json")
    for field_name in ("shutter_events", "gobo_events"):
        for event in data[field_name]:
            cue_id = event["moment_cue_id"]
            if cue_id is not None:
                event["bar"], event["beat"] = event_position(cue_id)
    return PlanSection.model_validate(data)
