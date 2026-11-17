"""Song intent resolved on a rig: the palette stop policy, the rig offer, a section's
look per head, and the repair of what no head can show (song-intent rendering W3/W4)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.support import moving_heads as m
from tests.support.moving_heads import discrete_profile_payload, plan_section
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    EventAction,
    PlanColor,
    PlanEvent,
    RepairAction,
)
from twinklr.core.config.fixtures import FixtureCapabilities
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.moving_heads.song_intent import (
    COOL_HUE,
    WARM_HUE,
    HeadWheels,
    RigOffer,
    SectionPalette,
    color_offer,
    describe_look,
    gobo_offer,
    offer_for_prompt,
    palette_role_color,
    repair_rig_intent,
    requested_color,
    resolve_section_look,
    rig_offer,
    wheel_change_ms,
)
from twinklr.core.sequencer.vocabulary.visual import PaletteRole

RGB_PRIMARY = SectionPalette(
    palette_id="core.rgb_primary", stops=("#FF1744", "#00E676", "#2979FF", "#FFFFFF")
)


def _profile(
    colors: dict[str, str] | None = None,
    gobos: dict[str, str] | None = None,
    *,
    strobes: tuple[str, ...] = (),
    color_wheel: bool = True,
    gobo_wheel: bool = True,
    **visibility: Any,
) -> FixtureCapabilities:
    """`discrete_profile_payload` with its colour states tagged by `colors` (state → hex or
    preset; an absent state keeps no tag), its gobo states by `gobos`, a shutter state
    per strobe speed, and `visibility` updated."""
    payload = discrete_profile_payload()
    discrete = payload["discrete"]
    for name, color in (colors or {}).items():
        discrete["color"]["states"][name]["hex"] = color
    for name, pattern in (gobos or {}).items():
        discrete["gobo"]["states"][name]["pattern"] = pattern
    for index, speed in enumerate(strobes):
        discrete["shutter"]["states"][f"strobe_{speed}"] = {
            "range_min": 100 + 40 * index,
            "range_max": 139 + 40 * index,
            "value": 120 + 40 * index,
            "settle_ms": 0,
            "strobe": speed,
        }
    if not color_wheel:
        del discrete["color"]
    if not gobo_wheel:
        del discrete["gobo"]
    payload["visibility"].update(visibility)
    return FixtureCapabilities.model_validate(payload)


TAGGED = {"white": "white", "red": "red", "blue": "blue"}


def _heads(**profiles: FixtureCapabilities) -> list[HeadWheels]:
    return [HeadWheels.from_profile(fixture_id, p) for fixture_id, p in profiles.items()]


# --- The palette stop policy --------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (PaletteRole.PRIMARY, 0),  # the first stop
        (PaletteRole.ACCENT, 1),  # the second
        (PaletteRole.WARM, 0),  # red (21°) is nearest the warm hue
        (PaletteRole.COOL, 2),  # blue (260°) is nearest the cool hue, not green (152°)
        (PaletteRole.NEUTRAL, 3),  # white, the least saturated
    ],
)
def test_a_palette_role_takes_its_stop(role: PaletteRole, expected: int) -> None:
    assert (WARM_HUE, COOL_HUE) == (55.0, 230.0)
    assert palette_role_color(role, RGB_PRIMARY.stops) == expected


def test_warm_and_cool_have_no_stop_in_a_palette_of_whites() -> None:
    whites = ("#FFFFFF", "#F5F1E8")

    assert palette_role_color(PaletteRole.WARM, whites) is None
    assert palette_role_color(PaletteRole.COOL, whites) is None
    assert palette_role_color(PaletteRole.NEUTRAL, whites) == 0  # #F5F1E8 has a faint tint


def test_neutral_takes_the_least_saturated_stop() -> None:
    assert palette_role_color(PaletteRole.NEUTRAL, ("#F5F1E8", "#FFFFFF")) == 1
    assert palette_role_color(PaletteRole.ACCENT, ("#FF0000",)) == 0  # one stop: the first


def test_requested_colour_names_its_source() -> None:
    explicit = requested_color(PlanColor.BLUE, RGB_PRIMARY)
    stop = requested_color(PlanColor.PALETTE_ACCENT, RGB_PRIMARY)
    fixed = requested_color(PlanColor.PALETTE_WARM, None)
    whites = requested_color(
        PlanColor.PALETTE_COOL, SectionPalette(palette_id="w", stops=("#FFFFFF", "#FFFFFE"))
    )

    assert (explicit.hex, explicit.source) == ("#0000FF", "explicit")
    assert (stop.hex, stop.source) == ("#00E676", "palette 'core.rgb_primary' stop 2")
    assert (fixed.hex, fixed.source) == (
        "#FFA000",
        "fixed table (amber: no macro palette for this section)",
    )
    assert (whites.hex, whites.source) == (
        "#00FFFF",
        "fixed table (cyan: palette 'w' has no stop with a hue)",
    )


# --- What a head and a rig offer ----------------------------------------------------------


def test_a_head_offers_only_tagged_states_with_a_known_settle() -> None:
    payload = discrete_profile_payload()
    payload["discrete"]["color"]["states"]["red"] |= {"hex": "red"}
    payload["discrete"]["color"]["states"]["blue"] |= {"hex": "blue", "settle_ms": None}
    payload["discrete"]["gobo"]["states"]["star"] |= {"pattern": "stars"}

    head = HeadWheels.from_profile("MH1", FixtureCapabilities.model_validate(payload))

    assert head.colors == {"red": "#FF0000"}  # white is untagged; blue's settle unknown
    assert head.gobos == {"star": "stars"}
    assert (head.color_wheel, head.gobo_wheel) == (True, True)


def test_a_colour_offer_grades_a_mixed_rig() -> None:
    """MH1/MH2 tagged white/red/blue, MH3 only white/red, MH4 without a colour wheel."""
    heads = _heads(
        MH1=_profile(TAGGED),
        MH2=_profile(TAGGED),
        MH3=_profile({"white": "white", "red": "red"}),
        MH4=_profile(color_wheel=False),
    )

    red = color_offer(heads, "red")
    magenta = color_offer(heads, "magenta")
    blue = color_offer(heads, "blue")
    green = color_offer(heads, "green")

    assert (red.status, red.missing) == ("faithful", ())
    assert set(red.heads) == {"MH1", "MH2", "MH3"}  # the head without a wheel is not asked
    assert (magenta.status, {h.state for h in magenta.heads.values()}) == ("approximate", {"red"})
    assert (blue.status, set(blue.heads), blue.missing) == ("partial", {"MH1", "MH2"}, ("MH3",))
    assert (green.status, green.heads, green.missing) == ("unavailable", {}, ("MH1", "MH2", "MH3"))


def test_a_gobo_offer_says_all_some_or_none() -> None:
    heads = _heads(
        MH1=_profile(gobos={"star": "stars", "dots": "dots"}),
        MH2=_profile(gobos={"star": "stars"}),
        MH3=_profile(gobo_wheel=False),
    )

    assert gobo_offer(heads, "stars").model_dump() == {
        "available": "all",
        "states": {"MH1": "star", "MH2": "star"},
        "missing": (),
    }
    assert gobo_offer(heads, GoboPattern.DOTS).available == "some"
    assert gobo_offer(heads, "flame").available == "none"


def test_the_rig_offer_lists_gobos_strobes_hit_and_the_wheel_change() -> None:
    rig = m.tagged_family_rig(("MH1", "MH2"))

    offer = rig_offer(rig, m.bars_grid(500.0, 500.0))

    assert offer.gobos["stars"].available == "all"
    assert offer.gobos["flame"].available == "none"
    assert {speed: s.available for speed, s in offer.strobes.items()} == dict.fromkeys(
        ("slow", "medium", "fast"), "none"
    )
    assert offer.hit == "all"
    # Dark at once (close latency 0, the dimmer extinguishes), then the slowest offered
    # state's settle: the star gobo's 160 ms.
    assert offer.wheel_change_ms == 160
    assert offer.beat_ms == 500.0 and offer.wheel_change_beats == pytest.approx(0.32)
    assert offer.preset_colors()["red"].status == "faithful"


def test_an_untagged_rig_offers_nothing_but_its_hit() -> None:
    offer = m.untagged_offer()

    assert not offer.offers_colors()
    assert offer.wheel_change_ms is None
    assert all(c.status == "unavailable" for c in offer.preset_colors().values())
    assert all(g.available == "none" for g in offer.gobos.values())


@pytest.mark.parametrize(
    ("visibility", "settle", "expected"),
    [
        ({"close_latency_ms": 30}, 150, 40 + 160),  # each term rounded up to the frame grid
        ({"close_latency_ms": 0}, 0, 20),  # at least one frame for the turn
        ({"close_latency_ms": None}, 150, None),
        # Only the shutter extinguishes: its closed state's settle joins the darkness.
        ({"close_latency_ms": 20, "dimmer_zero_extinguishes": False}, 150, 20 + 0 + 160),
    ],
)
def test_a_wheel_change_takes_darkness_then_turn_and_settle(
    visibility: dict[str, Any], settle: int, expected: int | None
) -> None:
    assert wheel_change_ms(_profile(**visibility), settle) == expected


# --- A section's look and its repair ------------------------------------------------------


def _section(**intent: Any) -> Any:
    return plan_section("s1", 1, 4, "mirror_wings").model_copy(update=intent)


def test_a_section_look_holds_each_head_that_shows_it_and_keeps_the_rest() -> None:
    heads = _heads(
        MH1=_profile(TAGGED, {"star": "stars"}),
        MH2=_profile({"white": "white"}),
        MH3=_profile(color_wheel=False, gobo_wheel=False),
    )

    look = resolve_section_look(
        _section(color=PlanColor.PALETTE_COOL, gobo=GoboPattern.STARS), heads, RGB_PRIMARY
    )

    assert look.requested is not None and look.requested.hex == "#2979FF"
    assert look.states == {"MH1": {ChannelName.COLOR: "blue", ChannelName.GOBO: "star"}}
    record = look.record()
    assert record["color"]["status"] == "partial"
    assert record["color"]["kept_authored"] == ["MH2"]
    assert record["gobo"] == {
        "asked": "stars",
        "available": "some",
        "heads": {"MH1": "star"},
        "kept_authored": ["MH2"],
    }
    assert describe_look(record) == [
        "colour PALETTE_COOL (#2979FF, palette 'core.rgb_primary' stop 3): blue (approximate) on "
        "MH1; MH2 keep their authored colour",
        "gobo stars: star on MH1; MH2 keep their authored gobo",
    ]


def test_without_a_macro_palette_a_role_takes_the_fixed_table() -> None:
    look = resolve_section_look(
        _section(color=PlanColor.PALETTE_PRIMARY), _heads(MH1=_profile(TAGGED)), None
    )

    assert look.requested is not None and look.requested.source.startswith("fixed table (red")
    assert look.states == {"MH1": {ChannelName.COLOR: "red"}}


def test_an_as_authored_section_holds_nothing() -> None:
    look = resolve_section_look(_section(), _heads(MH1=_profile(TAGGED)), RGB_PRIMARY)

    assert look.states == {} and look.record() == {"section_id": "s1"}


def _offer(*profiles: FixtureCapabilities) -> RigOffer:
    heads = tuple(_heads(**{f"MH{i + 1}": p for i, p in enumerate(profiles)}))
    return RigOffer(
        heads=heads,
        gobos={pattern.value: gobo_offer(heads, pattern) for pattern in GoboPattern},
        strobes={},
        hit="all",
        wheel_change_ms=None,
        beat_ms=None,
    )


def _event(action: EventAction, **values: Any) -> PlanEvent:
    return PlanEvent(
        **{"bar": 2, "beat": 1, "moment_cue_id": None, "color": None, "gobo": None} | values,
        action=action,
    )


def test_repair_clears_what_no_head_shows_and_records_what_some_cannot() -> None:
    offer = _offer(_profile(TAGGED, {"star": "stars"}), _profile({"red": "red"}))
    plan = ChoreographyPlan(
        sections=[
            _section(
                color=PlanColor.GREEN,
                gobo=GoboPattern.STARS,
                events=[
                    _event(EventAction.COLOR, color=PlanColor.YELLOW),
                    _event(EventAction.COLOR, color=PlanColor.BLUE),
                    _event(EventAction.GOBO, gobo=GoboPattern.FLAME),
                    _event(EventAction.HIT),
                ],
            )
        ],
        overall_strategy="",
    )

    repaired = repair_rig_intent(plan, offer, {})

    (section,) = repaired.sections
    assert section.color is None  # green: no head shows anything like it
    assert section.gobo is GoboPattern.STARS  # MH1 has it; MH2 keeps its own
    assert [event.action for event in section.events] == [EventAction.COLOR, EventAction.HIT]
    assert [(r.item.split(" (")[0], r.action) for r in repaired.repairs] == [
        ("colour green", RepairAction.ADJUSTED),
        ("gobo stars", RepairAction.RECORDED),
        ("event at bar 2 beat 1: color yellow", RepairAction.DROPPED),
        ("event at bar 2 beat 1: color blue", RepairAction.RECORDED),
        ("event at bar 2 beat 1: gobo flame", RepairAction.DROPPED),
    ]
    assert "keeps its authored colour (as_authored)" in repaired.repairs[0].reason
    assert repaired.repairs[1].reason == (
        "plays on MH1; MH2 cannot show it and keep their authored look"
    )


def test_repair_leaves_an_approximate_colour_and_a_plan_it_need_not_touch() -> None:
    offer = _offer(_profile(TAGGED))
    plan = ChoreographyPlan(sections=[_section(color=PlanColor.MAGENTA)], overall_strategy="")

    assert repair_rig_intent(plan, offer, {}) is plan


def test_repair_resolves_a_palette_role_through_the_section_palette() -> None:
    offer = _offer(_profile({"white": "white", "red": "red"}))
    plan = ChoreographyPlan(
        sections=[_section(color=PlanColor.PALETTE_ACCENT)], overall_strategy=""
    )

    with_palette = repair_rig_intent(plan, offer, {"s1": RGB_PRIMARY})  # green: not shown
    fixed = repair_rig_intent(plan, offer, {})  # magenta: shown as red

    assert with_palette.sections[0].color is None
    assert "palette 'core.rgb_primary' stop 2" in with_palette.repairs[0].item
    assert fixed is plan


def test_repair_on_a_rig_without_tags_says_so() -> None:
    plan = ChoreographyPlan(sections=[_section(color=PlanColor.RED)], overall_strategy="")

    (repair,) = repair_rig_intent(plan, m.untagged_offer(), {}).repairs

    assert repair.reason.startswith(
        "this rig's colour wheel states carry no `hex` tag, so no colour is offered"
    )


def test_the_prompt_groups_sections_that_share_a_palette() -> None:
    offer = m.tagged_offer(("MH1",))
    palettes = {"verse": RGB_PRIMARY, "chorus": RGB_PRIMARY}

    shown = offer_for_prompt(offer, palettes, ["verse", "chorus", "outro"])

    first, second = shown["sections"]
    assert first["section_ids"] == ["verse", "chorus"]
    assert first["palette_id"] == "core.rgb_primary"
    assert second == {
        "section_ids": ["outro"],
        "palette_id": None,
        "roles": [
            {"role": "PALETTE_PRIMARY", "hex": "#FF0000", "status": "faithful", "shown": "red"},
            {"role": "PALETTE_ACCENT", "hex": "#FF00FF", "status": "approximate", "shown": "red"},
            {"role": "PALETTE_WARM", "hex": "#FFA000", "status": "approximate", "shown": "red"},
            {"role": "PALETTE_COOL", "hex": "#00FFFF", "status": "approximate", "shown": "blue"},
            {"role": "PALETTE_NEUTRAL", "hex": "#FFFFFF", "status": "faithful", "shown": "white"},
        ],
    }
    assert shown["colors"]["unavailable"] == [
        {"color": c, "kept": "MH1"} for c in ("green", "yellow", "lime")
    ]
    assert shown["wheel_change_beats"] == "0.4"
