"""Song intent resolved on a rig: the palette stop policy, the rig offer and a
section's look per head (song-intent rendering W3/W4). The repair of what no head can
show is in `tests/unit/agents/sequencer/moving_heads/test_rig_repair.py`."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest

from tests.support import moving_heads as m
from tests.support.moving_heads import discrete_profile_payload, plan_section
from twinklr.core.agents.sequencer.moving_heads.models import PlanColor
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup
from twinklr.core.config.fixtures.state_tags import NEUTRAL_CHROMA, oklch
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.moving_heads.song_intent import (
    COOL_HUE,
    ROLE_HUE_RANGE,
    WARM_HUE,
    DarkPhases,
    HeadWheels,
    SectionPalette,
    TemplateOffer,
    color_offer,
    describe_look,
    gobo_offer,
    is_late,
    offer_for_prompt,
    palette_role_color,
    requested_color,
    resolve_section_look,
    rig_offer,
    wheel_change_ms,
)
from twinklr.core.sequencer.theming.catalog import get_palette, list_palettes
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

    assert (explicit.hex, explicit.source, explicit.role_missing) == ("#0000FF", "explicit", False)
    assert (stop.hex, stop.source) == ("#00E676", "palette 'core.rgb_primary' stop 2")
    assert (fixed.hex, fixed.source) == (
        "#FFA000",
        "fixed table (amber: no macro palette for this section)",
    )
    # A role the palette has no stop for is never substituted from the fixed table: the
    # palette is the song's. PRIMARY's stop stands in, marked.
    assert (whites.hex, whites.source, whites.role_missing) == (
        "#FFFFFF",
        "palette 'w' has no COOL stop: PRIMARY's stop 1",
        True,
    )


_SMALL_WHEELS = {
    "w/r/b/g": {"white": "white", "red": "red", "blue": "blue", "green": "green"},
    "w/r/b": {"white": "white", "red": "red", "blue": "blue"},
    "open/red/amber/pink/blue/green": {
        "open": "white",
        "red": "red",
        "amber": "amber",
        "pink": "#FF69B4",
        "blue": "blue",
        "green": "green",
    },
    "eight-slot": {
        n: n for n in ("white", "red", "orange", "yellow", "green", "blue", "magenta", "cyan")
    },
}


def _away(hue: float, target: float) -> float:
    turn = abs(hue - target) % 360
    return min(turn, 360 - turn)


@pytest.mark.parametrize("palette_id", [info.palette_id for info in list_palettes()])
def test_every_catalog_palette_resolves_a_role_only_to_a_stop_that_fits_it(
    palette_id: str,
) -> None:
    """WARM and COOL take a stop with a hue within 90° of theirs, NEUTRAL a white; a
    palette without such a stop has no such role (never a colour from outside it)."""
    stops = tuple(stop.hex[:7].upper() for stop in get_palette(palette_id).stops)
    colours = [oklch(stop) for stop in stops]
    palette = SectionPalette(palette_id=palette_id, stops=stops)

    for role, target in ((PaletteRole.WARM, WARM_HUE), (PaletteRole.COOL, COOL_HUE)):
        index = palette_role_color(role, stops)
        fitting = [c for c in colours if c[1] >= NEUTRAL_CHROMA and _away(c[2], target) <= 90]
        assert (index is None) == (not fitting), (role, stops)
        if index is not None:
            assert _away(colours[index][2], target) <= ROLE_HUE_RANGE
    neutral = palette_role_color(PaletteRole.NEUTRAL, stops)
    assert (neutral is None) == all(c[1] >= NEUTRAL_CHROMA for c in colours)
    assert neutral is None or colours[neutral][1] < NEUTRAL_CHROMA
    for role in PaletteRole:
        asked = requested_color(f"PALETTE_{role.value}", palette)
        assert asked.hex in stops  # never the fixed table under a macro palette


def test_catalog_palettes_without_a_role_are_named() -> None:
    """Measured over the 19 catalog palettes (the review's count of misplaced roles)."""
    missing = {
        role.value: sorted(
            info.palette_id
            for info in list_palettes()
            if palette_role_color(
                role, tuple(s.hex[:7].upper() for s in get_palette(info.palette_id).stops)
            )
            is None
        )
        for role in (PaletteRole.WARM, PaletteRole.COOL, PaletteRole.NEUTRAL)
    }

    assert missing == {
        "WARM": [
            "core.ice_neon",
            "core.mono_cool",
            "core.uv_party",
            "spec.cosmic_night",
            "spec.futuristic_teal",
        ],
        "COOL": ["core.gold_warm", "core.magma", "core.mono_warm", "spec.gritty_embers"],
        "NEUTRAL": ["core.magma", "core.rainbow_bright"],
    }


@pytest.mark.parametrize("wheel", sorted(_SMALL_WHEELS))
def test_the_prompt_says_where_two_roles_share_a_wheel_colour(wheel: str) -> None:
    """On every catalog palette and four realistic wheels, a role that lands on the same
    wheel colour as an earlier one says so, and a missing role is marked missing."""
    profile = _wheel(_SMALL_WHEELS[wheel])
    offer = rig_offer_of({"MH1": profile})
    for info in list_palettes():
        stops = tuple(s.hex[:7].upper() for s in get_palette(info.palette_id).stops)
        palette = SectionPalette(palette_id=info.palette_id, stops=stops)
        (entry,) = offer_for_prompt(offer, {"s": palette}, ["s"])["sections"]
        seen: dict[str, str] = {}
        for role in entry["roles"]:
            if role["missing"]:
                assert palette_role_color(PaletteRole(role["role"][8:]), stops) is None
                continue
            if role["shown"]:
                assert role["same_as"] == seen.get(role["shown"], "")
                seen.setdefault(role["shown"], role["role"])


# --- What a head and a rig offer ----------------------------------------------------------


def test_a_head_offers_a_wheel_only_when_every_state_has_a_settle() -> None:
    """A tagged wheel with one state of unknown settle offers nothing (a turn back to the
    authored state could not be timed); the other wheel is unaffected."""
    payload = discrete_profile_payload()
    payload["discrete"]["color"]["states"]["red"] |= {"hex": "red"}
    payload["discrete"]["color"]["states"]["blue"] |= {"hex": "blue", "settle_ms": None}
    payload["discrete"]["gobo"]["states"]["star"] |= {"pattern": "stars"}

    head = HeadWheels.from_profile("MH1", FixtureCapabilities.model_validate(payload))

    assert head.colors == {}
    assert head.unsettled == {"color": ("blue",)}
    assert head.gobos == {"star": "stars"}
    assert (head.color_wheel, head.gobo_wheel) == (True, True)
    settled = FixtureCapabilities.model_validate(
        payload
        | {
            "discrete": payload["discrete"]
            | {
                "color": {
                    **payload["discrete"]["color"],
                    "states": {
                        **payload["discrete"]["color"]["states"],
                        "blue": {
                            **payload["discrete"]["color"]["states"]["blue"],
                            "settle_ms": 140,
                        },
                    },
                }
            }
        }
    )
    assert HeadWheels.from_profile("MH1", settled).colors == {"blue": "#0000FF", "red": "#FF0000"}


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

    assert gobo_offer(heads, "stars").model_dump(mode="json") == {
        "available": "all",
        "states": {"MH1": "star", "MH2": "star"},
        "missing": [],
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
    # Darkness through the dimmer, which follows one frame each way.
    assert (offer.dark, offer.flash_ms) == ("all", 20)
    # Dark at once (close latency 0, the dimmer extinguishes), then the slowest offered
    # state's settle: the star gobo's 160 ms.
    assert offer.wheel_change_ms == 160
    assert offer.beat_ms == 500.0 and offer.wheel_change_beats == pytest.approx(0.32)
    assert offer.preset_colors()["red"].status == "faithful"


def test_strobe_speeds_say_all_some_or_missing_on_a_mixed_rig() -> None:
    """Restored from W1's helpers: per speed, the heads with a shutter that have it."""
    offer = rig_offer_of(
        {
            "MH1": _profile(strobes=("slow", "medium", "fast")),
            "MH2": _profile(strobes=("fast",)),
            "MH3": _profile(),
        }
    )

    assert offer.strobes["fast"].model_dump(mode="json") == {
        "available": "some",
        "states": {"MH1": "strobe_fast", "MH2": "strobe_fast"},
        "missing": ["MH3"],
    }
    assert offer.strobes["slow"].missing == ("MH2", "MH3")
    single = rig_offer_of({"MH1": _profile(strobes=("medium",))})
    assert single.strobes["medium"].available == "all"
    assert single.strobes["slow"].available == "none"


def test_black_is_shown_by_no_head() -> None:
    offer = rig_offer_of({"MH1": _profile(TAGGED)})

    assert offer.color("#000000").status == "unavailable"


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
        "heads": {"MH1": {"state": "star"}},
        "kept_authored": ["MH2"],
    }
    assert describe_look(record) == [
        "colour PALETTE_COOL (#2979FF, palette 'core.rgb_primary' stop 3): blue (approximate) on "
        "MH1; MH2 keep their authored colour",
        "gobo stars: star on MH1; MH2 keep their authored gobo",
    ]


def test_a_look_record_says_which_heads_turn_late_or_keep_the_previous_colour() -> None:
    record = {
        "section_id": "s2",
        "color": {
            "asked": "blue",
            "hex": "#0000FF",
            "source": "explicit",
            "status": "faithful",
            "heads": {"MH1": {"state": "blue", "hex": "#0000FF", "fit": "exact"}},
            "kept_authored": [],
            "deferred": {"MH2": {"state": "blue", "from_ms": 9020}},
            "kept_previous": {"MH3": "red"},
        },
        "boundaries": [
            {
                "fixture_id": "MH2",
                "boundary_ms": 8020,
                "wheels": {"color": {"from": "red", "to": "blue"}},
                "deferred": {"turn_ms": 9020, "waited_ms": 1000, "late": False, "reason": "x"},
            }
        ],
    }

    assert describe_look(record) == [
        "colour blue (#0000FF, explicit): blue (exact) on MH1; MH2 turns to blue at 9020 ms; "
        "MH3 keeps the previous colour red",
        "MH2 at 8020 ms: color red → blue: turned in a dark window at 9020 ms",
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
            _role("PALETTE_PRIMARY", "#FF0000", "faithful", "red"),
            _role("PALETTE_ACCENT", "#FF00FF", "approximate", "red", "PALETTE_PRIMARY"),
            _role("PALETTE_WARM", "#FFA000", "approximate", "red", "PALETTE_PRIMARY"),
            _role("PALETTE_COOL", "#00FFFF", "approximate", "blue"),
            _role("PALETTE_NEUTRAL", "#FFFFFF", "faithful", "white"),
        ],
    }
    assert shown["colors"]["unavailable"] == [
        {"color": c, "kept": "MH1"} for c in ("green", "yellow", "lime")
    ]
    assert shown["wheel_change_beats"] == "0.4"


def _role(role: str, hex_: str, status: str, shown: str, same_as: str = "") -> dict[str, Any]:
    return {
        "role": role,
        "missing": False,
        "hex": hex_,
        "status": status,
        "shown": shown,
        "same_as": same_as,
    }


def test_the_prompt_says_whether_a_wheel_change_fits_half_a_beat_and_where_it_can_wait() -> None:
    """At 200 BPM (beat 300 ms) a 160 ms change does not fit half a beat: the prompt says
    so and names the templates with a dark phase long enough."""
    phases = DarkPhases(cycle_beats=8.0, heads={"MH1": ((2.0, 3.0),)})
    short = DarkPhases(cycle_beats=8.0, heads={"MH1": ((1.0, 1.25),)})
    fast = rig_offer(
        m.tagged_family_rig(("MH1",)),
        m.bars_grid(300.0, 300.0),
        {
            "masked_wheel_flick": TemplateOffer(variants={"base": phases}),
            "mirror_wings": TemplateOffer(variants={"base": short}),
        },
    )
    slow = m.tagged_offer(("MH1",))

    shown = offer_for_prompt(fast, {}, ["s"])

    assert (shown["dip_fits"], shown["half_beat_ms"]) == (False, 150)
    assert shown["dark_windows"] == ["masked_wheel_flick (from beat 2 of its cycle)"]
    assert offer_for_prompt(slow, {}, ["s"])["dip_fits"] is True


def test_the_prompt_counts_the_boundaries_a_dip_fits_before() -> None:
    """Given half the beat before each boundary, the offer says how many a 160 ms change
    fits (the render decides per boundary); without them, the median beat decides."""
    offer = m.tagged_offer(("MH1",))

    shown = offer_for_prompt(offer, {}, ["s"], [250.0, 150.0, 250.0])

    assert shown["dip_boundaries"] == {"fit": 2, "of": 3, "shortest_half_beat_ms": 150}
    assert offer_for_prompt(offer, {}, ["s"])["dip_boundaries"] is None


def test_a_deferral_is_late_when_its_window_opens_past_half_the_section() -> None:
    """One definition for the render's trace and the plan repair, a frame of tolerance
    for the frame grid."""
    assert not is_late(1500 + EFFECT_GRID_MS, 1000, 2000)
    assert is_late(1500 + 2 * EFFECT_GRID_MS, 1000, 2000)


def test_a_template_exclusion_removes_states_from_its_offer_only() -> None:
    offer = m.tagged_offer(("MH1", "MH2")).model_copy(
        update={
            "templates": {
                "masked_wheel_flick": TemplateOffer(
                    variants={}, excluded={"MH1": {"color": ("blue",)}}
                )
            }
        }
    )

    flick = offer.for_templates({"masked_wheel_flick"})

    assert set(flick.color("blue").heads) == {"MH2"}
    assert set(offer.for_templates({"mirror_wings"}).color("blue").heads) == {"MH1", "MH2"}
    assert offer_for_prompt(offer, {}, ["s"])["exclusions"] == [
        {"template_id": "masked_wheel_flick", "states": ["blue"]}
    ]


def rig_offer_of(profiles: dict[str, FixtureCapabilities]) -> Any:
    """`rig_offer` over a hand-made rig of these profiles."""
    from twinklr.core.config.fixtures import FixtureGroup

    payload = m.family_rig(tuple(profiles)).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        fixture["config"]["physical_profile"] = profiles[fixture["fixture_id"]].model_dump(
            mode="json"
        )
    payload.pop("presets", None)
    return rig_offer(FixtureGroup.model_validate(payload), m.bars_grid(500.0))


def _wheel(colors: dict[str, str]) -> FixtureCapabilities:
    payload = discrete_profile_payload()
    payload["discrete"]["color"]["states"] = {
        name: {"value": index * 10, "settle_ms": 120, "hex": color}
        for index, (name, color) in enumerate(colors.items())
    }
    del payload["discrete"]["color"]["default_state"]
    return FixtureCapabilities.model_validate(payload)


@pytest.mark.parametrize(
    "module",
    [
        "twinklr.core.sequencer.moving_heads.song_intent",
        "twinklr.core.agents.sequencer.moving_heads.rig_repair",
        "twinklr.core.sequencer.moving_heads.pipeline",
        "twinklr.core.agents.sequencer.moving_heads.context",
    ],
)
def test_each_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    """No import cycle between the renderer's song-intent module and the planner package."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr


def test_the_offer_says_how_fast_the_heads_can_flash_and_what_each_strobe_plays() -> None:
    """Through the dimmer at 8 units/s a flash phase takes 140 ms: at 120 BPM no strobe
    rate fits but one a beat, and the pulse every beat; through the shutter, its 40 ms
    latency each way allows sixteenths."""
    payload = m.tagged_family_rig(("MH1",)).model_dump(mode="json")
    payload["fixtures"][0]["config"]["physical_profile"]["axes"]["dimmer"]["travel_speed_per_s"] = (
        8.0
    )
    slow = rig_offer(FixtureGroup.model_validate(payload), m.bars_grid(500.0, 500.0))
    shutter = m.tagged_family_rig(("MH1",)).model_dump(mode="json")
    profile = shutter["fixtures"][0]["config"]["physical_profile"]
    profile["visibility"].update(
        dimmer_zero_extinguishes=False, close_latency_ms=40, open_latency_ms=40
    )
    closed = rig_offer(FixtureGroup.model_validate(shutter), m.bars_grid(500.0, 500.0))

    assert slow.flash_ms == 140
    events = offer_for_prompt(slow, {}, ["s1"])["events"]
    assert [s["plays"] for s in events["strobes"]] == [1, 1, 1]
    assert events["pulse_beats"] == 1
    assert (closed.dark, closed.flash_ms) == ("all", 40)
    assert [s["plays"] for s in offer_for_prompt(closed, {}, ["s1"])["events"]["strobes"]] == [
        2,
        4,
        4,
    ]
