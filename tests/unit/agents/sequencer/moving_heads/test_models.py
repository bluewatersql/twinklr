"""Tests for the moving-head planner response model (the song-intent contract)."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
import pytest

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    EventAction,
    PlanColor,
    flatten_section,
    load_plan,
)
from twinklr.core.curves.library import CurveLibrary
from twinklr.core.sequencer.models.enum import Intensity, TransitionMode
from twinklr.core.sequencer.models.transition import (
    TransitionChannel,
    TransitionEdge,
    TransitionStrategy,
)
from twinklr.core.sequencer.moving_heads.libraries.color import ColorPreset
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.vocabulary.visual import PaletteRole


def part(start_bar: int, template_id: str = "fan", **fields: Any) -> dict[str, Any]:
    return {
        "start_bar": start_bar,
        "template_id": template_id,
        "preset_id": None,
        "modifiers": [],
        "label": None,
        "reasoning": "",
        **fields,
    }


def event(bar: int, beat: int, action: str, **fields: Any) -> dict[str, Any]:
    return {
        "bar": bar,
        "beat": beat,
        "moment_cue_id": None,
        "action": action,
        "color": None,
        "gobo": None,
        **fields,
    }


def transition(edge: str, mode: str = "crossfade", **fields: Any) -> dict[str, Any]:
    return {
        "edge": edge,
        "mode": mode,
        "length": "BAR",
        "curve": "linear",
        "split": "HALF",
        "channels": [],
        **fields,
    }


def section(**fields: Any) -> dict[str, Any]:
    return {
        "section_id": "verse_1",
        "start_bar": 1,
        "end_bar": 8,
        "section_role": None,
        "energy_level": None,
        "parts": [part(1)],
        "intensity": None,
        "color": None,
        "gobo": None,
        "moment_cues": [],
        "events": [],
        "motif_id": None,
        "variation": "NONE",
        "density": "BALANCED",
        "transitions": [],
        "reasoning": "",
        **fields,
    }


def plan(*sections: dict[str, Any]) -> ChoreographyPlan:
    return ChoreographyPlan.model_validate(
        {"sections": list(sections) or [section()], "overall_strategy": ""}
    )


# --- the contract keeps every old value and adds the new ones -----------------------


def test_colour_keeps_both_old_arms_in_one_vocabulary() -> None:
    palette = {color for color in PlanColor if color.name.startswith("PALETTE_")}
    presets = set(PlanColor) - palette

    assert {color.name.removeprefix("PALETTE_") for color in palette} == {
        role.value for role in PaletteRole
    }
    assert {color.value for color in presets} == {preset.value for preset in ColorPreset}


def test_event_actions_keep_every_shutter_pattern_and_add_hit_colour_and_gobo() -> None:
    old_shutter_patterns = {
        "open",
        "closed",
        "strobe_fast",
        "strobe_medium",
        "strobe_slow",
        "pulse",
    }

    assert {action.value for action in EventAction} == old_shutter_patterns | {
        "hit",
        "color",
        "gobo",
    }


def test_a_full_section_round_trips_every_intent() -> None:
    full = section(
        section_role="chorus",
        energy_level=82,
        parts=[
            part(1, "fan", preset_id="narrow", modifiers=[{"key": "k", "value": "v"}]),
            part(5, "orbit"),
        ],
        intensity="DRAMATIC",
        color="PALETTE_ACCENT",
        gobo="stars",
        moment_cues=["hook"],
        events=[
            event(2, 3, "strobe_medium", moment_cue_id="hook"),
            event(3, 1, "gobo", gobo="dots"),
            event(4, 1, "color", color="blue"),
            event(6, 1, "hit"),
        ],
        motif_id="motif_a",
        variation="WIDEN",
        density="BUSY",
        transitions=[
            transition("ENTRY", "morph", channels=[{"channel": "pan", "strategy": "smooth"}]),
            transition("EXIT", "blackout", length="EIGHT_BARS", split="THREE_QUARTERS"),
        ],
    )
    planned = plan(full)
    round_tripped = ChoreographyPlan.model_validate_json(planned.model_dump_json())

    assert round_tripped == planned
    (only,) = round_tripped.sections
    assert only.intensity is Intensity.DRAMATIC
    assert only.color is PlanColor.PALETTE_ACCENT
    assert only.gobo is GoboPattern.STARS
    assert [e.action for e in only.events] == [
        EventAction.STROBE_MEDIUM,
        EventAction.GOBO,
        EventAction.COLOR,
        EventAction.HIT,
    ]
    assert only.events[2].color is PlanColor.BLUE
    assert only.entry is not None and only.entry.mode is TransitionMode.MORPH
    assert only.entry.channels[0].channel is TransitionChannel.PAN
    assert only.entry.channels[0].strategy is TransitionStrategy.SMOOTH_INTERPOLATION
    assert only.exit is not None and only.exit.mode is TransitionMode.BLACKOUT
    assert only.exit.edge is TransitionEdge.EXIT
    assert only.parts[0].modifiers[0].key == "k"


def test_null_intent_means_as_authored_and_is_the_neutral_section() -> None:
    neutral = plan().sections[0]

    assert (neutral.intensity, neutral.color, neutral.gobo) == (None, None, None)
    assert neutral.entry is None and neutral.exit is None
    assert neutral.set_intent_fields() == ()


def test_set_intent_fields_names_each_field_the_planner_set() -> None:
    planned = plan(
        section(
            intensity="SMOOTH",
            color="red",
            events=[event(2, 1, "hit")],
            variation="SLOWER",
            transitions=[transition("EXIT")],
        )
    ).sections[0]

    assert planned.set_intent_fields() == ("intensity", "color", "events", "variation", "exit")


# --- context-free rules ---------------------------------------------------------------


def test_bars_are_ordered_and_one_indexed() -> None:
    with pytest.raises(ValidationError, match="end_bar"):
        plan(section(start_bar=8, end_bar=1, parts=[part(8)]))
    with pytest.raises(ValidationError):
        plan(section(start_bar=0, parts=[part(0)]))


@pytest.mark.parametrize(
    ("parts", "message"),
    [
        ([part(2)], "first part"),
        ([part(1), part(1)], "ordered"),
        ([part(1), part(5), part(3)], "ordered"),
        ([part(1), part(9)], "inside the section"),
        ([], "at least 1"),
        ([part(1), part(2), part(3), part(4)], "at most 3"),
    ],
)
def test_parts_start_at_the_section_and_are_ordered_inside_it(
    parts: list[dict[str, Any]], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        plan(section(parts=parts))


@pytest.mark.parametrize(
    "unpaired",
    [
        event(2, 1, "color"),
        event(2, 1, "gobo"),
        event(2, 1, "color", color="red", gobo="dots"),
        event(2, 1, "hit", color="red"),
        event(2, 1, "closed", gobo="dots"),
    ],
)
def test_an_unpaired_event_is_accepted_for_repair_not_refused(unpaired: dict[str, Any]) -> None:
    """Pairing an event's colour and gobo with its action is repair's job
    (`bind_lyric_moment_cues`): a paid response is never refused for one event."""
    assert plan(section(events=[unpaired])).sections[0].events[0].action == unpaired["action"]


def test_event_cue_ids_and_part_labels_are_stripped() -> None:
    planned = plan(
        section(
            parts=[part(1, label="  pickup "), part(3, label="   ")],
            events=[
                event(2, 1, "hit", moment_cue_id=" hook "),
                event(3, 1, "hit", moment_cue_id=" "),
            ],
        )
    ).sections[0]

    assert [p.label for p in planned.parts] == ["pickup", None]
    assert [e.moment_cue_id for e in planned.events] == ["hook", None]


def test_moment_cue_ids_are_unique_and_not_blank() -> None:
    with pytest.raises(ValidationError, match="unique"):
        plan(section(moment_cues=["hook", "hook"]))
    with pytest.raises(ValidationError, match="blank"):
        plan(section(moment_cues=["  "]))


def test_a_section_has_at_most_one_entry_and_one_exit() -> None:
    with pytest.raises(ValidationError, match="ENTRY"):
        plan(section(transitions=[transition("ENTRY"), transition("ENTRY")]))
    with pytest.raises(ValidationError, match="channel"):
        plan(
            section(
                transitions=[
                    transition(
                        "ENTRY",
                        channels=[
                            {"channel": "pan", "strategy": "snap"},
                            {"channel": "pan", "strategy": "smooth"},
                        ],
                    )
                ]
            )
        )


def test_a_plan_has_at_least_one_section() -> None:
    with pytest.raises(ValidationError):
        ChoreographyPlan.model_validate({"sections": [], "overall_strategy": ""})


def test_curve_choice_is_the_curve_library() -> None:
    planned = plan(section(transitions=[transition("ENTRY", curve="ease_in_out_sine")]))

    assert planned.sections[0].transitions[0].curve is CurveLibrary.EASE_IN_OUT_SINE


def test_repairs_are_not_part_of_the_response_schema() -> None:
    schema = ChoreographyPlan.model_json_schema()

    assert set(schema["properties"]) == {"sections", "overall_strategy"}
    assert plan().repairs == []


# --- flattening -------------------------------------------------------------------------


def test_one_part_flattens_to_the_section_itself() -> None:
    only = plan().sections[0]

    assert flatten_section(only) == [only]


def test_parts_flatten_to_derived_ids_with_their_events_and_edges() -> None:
    planned = plan(
        section(
            parts=[part(1, "fan", preset_id="narrow"), part(3, "orbit"), part(7, "wave")],
            moment_cues=["hook"],
            events=[event(2, 1, "hit"), event(3, 1, "closed"), event(8, 4, "open")],
            transitions=[transition("ENTRY"), transition("EXIT")],
            intensity="FAST",
        )
    ).sections[0]

    units = flatten_section(planned)

    assert [(u.section_id, u.start_bar, u.end_bar) for u in units] == [
        ("verse_1|A", 1, 2),
        ("verse_1|B", 3, 6),
        ("verse_1|C", 7, 8),
    ]
    assert [(u.parts[0].template_id, u.parts[0].preset_id) for u in units] == [
        ("fan", "narrow"),
        ("orbit", None),
        ("wave", None),
    ]
    assert [[e.bar for e in u.events] for u in units] == [[2], [3], [8]]
    assert [u.moment_cues for u in units] == [["hook"]] * 3
    assert [(u.entry is not None, u.exit is not None) for u in units] == [
        (True, False),
        (False, False),
        (False, True),
    ]
    assert {u.intensity for u in units} == {Intensity.FAST}


def test_part_labels_name_the_flattened_parts() -> None:
    """A labelled part is named by its label; an unlabelled one by its letter; a single
    labelled part is a named part of its section; a clash takes the first free letter."""

    def ids(*parts: dict[str, Any]) -> list[str]:
        return [u.section_id for u in flatten_section(plan(section(parts=list(parts))).sections[0])]

    assert ids(part(1, label="pickup"), part(3, label="drop")) == ["verse_1|pickup", "verse_1|drop"]
    assert ids(part(1, label="pickup"), part(3)) == ["verse_1|pickup", "verse_1|B"]
    assert ids(part(1, label="drop")) == ["verse_1|drop"]
    assert ids(part(1)) == ["verse_1"]
    assert ids(part(1, label="B"), part(3)) == ["verse_1|B", "verse_1|A"]


# --- old saved plans ----------------------------------------------------------------------


def test_an_old_shape_plan_is_refused_by_name_with_the_remedy() -> None:
    old = {
        "sections": [
            {"section_name": "verse_1", "start_bar": 1, "end_bar": 8, "template_id": "fan"}
        ],
        "overall_strategy": "",
    }

    with pytest.raises(ValueError, match=r"before 2026-11-17.*re-run `twinklr inject`"):
        load_plan(old, remedy="re-run `twinklr inject`")


def test_a_current_plan_loads() -> None:
    planned = plan()

    assert load_plan(planned.model_dump(mode="json"), remedy="unused") == planned


def test_an_invalid_current_plan_is_not_called_old() -> None:
    broken = plan().model_dump(mode="json")
    broken["sections"][0]["start_bar"] = 0

    with pytest.raises(ValidationError):
        load_plan(broken, remedy="unused")


# --- "no choice" is a string member, None in Python -------------------------------------


def test_no_choice_is_a_sentinel_member_in_the_schema_and_none_in_python() -> None:
    schema = ChoreographyPlan.model_json_schema()
    section_fields = schema["$defs"]["PlanSection"]["properties"]
    event_fields = schema["$defs"]["PlanEvent"]["properties"]

    for field, sentinel in (
        (section_fields["intensity"], "as_authored"),
        (section_fields["color"], "as_authored"),
        (section_fields["gobo"], "as_authored"),
        (event_fields["color"], "none"),
        (event_fields["gobo"], "none"),
    ):
        assert field["type"] == "string"
        assert field["enum"][-1] == sentinel
        assert None not in field["enum"]

    planned = plan(
        section(
            intensity="as_authored",
            color="as_authored",
            gobo="as_authored",
            events=[event(2, 1, "hit", color="none", gobo="none")],
        )
    ).sections[0]
    assert (planned.intensity, planned.color, planned.gobo) == (None, None, None)
    assert (planned.events[0].color, planned.events[0].gobo) == (None, None)


def test_the_dump_spells_no_choice_as_the_sentinel_and_reads_back() -> None:
    """The dumped (and hashed) form names the sentinel; Python None reads in as well."""
    planned = plan(section(events=[event(2, 1, "hit")]))
    dumped = planned.model_dump(mode="json")["sections"][0]

    assert (dumped["intensity"], dumped["color"], dumped["gobo"]) == ("as_authored",) * 3
    assert (dumped["events"][0]["color"], dumped["events"][0]["gobo"]) == ("none", "none")
    assert ChoreographyPlan.model_validate(planned.model_dump(mode="json")) == planned
    assert planned.model_dump()["sections"][0]["intensity"] == "as_authored"
