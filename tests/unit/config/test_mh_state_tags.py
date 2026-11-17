"""Meaning tags on a profile's discrete states (song-intent rendering W1).

A colour-wheel state may say which colour it shows (`hex`), a gobo state which pattern
it projects (`pattern`), a shutter state how fast it strobes (`strobe`). Tags are never
defaulted; an untagged profile loads and dumps exactly as before. The lookup functions
are what the rig offer (W3) and the section colour and gobo resolution (W4) will call;
nothing renders from a tag yet. Synthetic profiles and layouts only.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from tests.support import moving_heads as m
from tests.support.moving_heads import (
    discrete_profile_payload,
    p1_layout_xml,
    p1_rig,
    profile_payload,
    tagged_p1_rig,
)
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup
from twinklr.core.config.fixtures.state_tags import (
    ColorMatch,
    color_distance,
    gobo_state,
    layout_color_tags,
    nearest_color_state,
    rig_tag_guidance,
    strobe_state,
    tag_guidance,
    tagged_colors,
)
from twinklr.core.formats.xlights.layout.parser import load_layout
from twinklr.core.sequencer.moving_heads.libraries.color import COLOR_PRESET_HEX, ColorPreset
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.theming.catalog import get_palette, list_palettes


def _payload(**states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """`discrete_profile_payload` with each named channel's states updated by `states`."""
    payload = discrete_profile_payload()
    for channel, updates in states.items():
        for name, update in updates.items():
            payload["discrete"][channel]["states"].setdefault(name, {}).update(update)
    return payload


def _profile(payload: dict[str, Any]) -> FixtureCapabilities:
    return FixtureCapabilities.model_validate(payload)


def _wheel(**hexes: str) -> FixtureCapabilities:
    """A colour wheel with one state per `hexes` entry (bytes 0, 10, 20, ...), tagged."""
    payload = discrete_profile_payload()
    payload["discrete"]["color"]["states"] = {
        name: {"value": index * 10, "settle_ms": 120, "hex": color}
        for index, (name, color) in enumerate(hexes.items())
    }
    del payload["discrete"]["color"]["default_state"]  # the state selecting byte 0
    return _profile(payload)


# --- The model --------------------------------------------------------------------------


def test_an_untagged_profile_dumps_exactly_as_before() -> None:
    """No tag key appears in the dump of an untagged profile, so its render fingerprint
    and `show` session id are unchanged."""
    profile = _profile(discrete_profile_payload())

    for channel in profile.model_dump(mode="json")["discrete"].values():
        for state in channel["states"].values():
            assert set(state) == {"range_min", "range_max", "value", "settle_ms"}


def test_tags_load_and_dump_in_one_canonical_form() -> None:
    payload = _payload(
        color={"red": {"hex": "#ff0000"}, "blue": {"hex": "blue"}},
        gobo={"star": {"pattern": "stars"}, "open": {"pattern": "open"}},
        shutter={"strobe": {"range_min": 100, "range_max": 199, "value": 150, "strobe": "fast"}},
    )

    profile = _profile(payload)
    dumped = profile.model_dump(mode="json")

    assert dumped["discrete"]["color"]["states"]["red"]["hex"] == "#FF0000"
    # A colour preset name is a convenience; the profile stores its canonical hex.
    assert dumped["discrete"]["color"]["states"]["blue"]["hex"] == "#0000FF"
    assert dumped["discrete"]["gobo"]["states"]["star"]["pattern"] == "stars"
    assert dumped["discrete"]["shutter"]["states"]["strobe"]["strobe"] == "fast"
    assert "hex" not in dumped["discrete"]["color"]["states"]["white"]
    assert _profile(dumped) == profile


def test_a_tag_is_never_recorded_as_defaulted() -> None:
    profile = _profile(_payload(color={"red": {"hex": "red"}}))

    assert not any(path.endswith((".hex", ".pattern", ".strobe")) for path in profile.defaulted)


def test_every_colour_preset_name_resolves_to_its_canonical_hex() -> None:
    for preset in ColorPreset:
        profile = _profile(_payload(color={"red": {"hex": preset.value}}))
        assert profile.discrete["color"].states["red"].hex == COLOR_PRESET_HEX[preset]


@pytest.mark.parametrize(
    ("channel", "state", "tag", "value", "match"),
    [
        pytest.param(
            "gobo",
            "dots",
            "hex",
            "#FF0000",
            r"discrete\.gobo\.states\.dots\.hex: a gobo state takes `pattern`",
            id="hex-on-gobo",
        ),
        pytest.param(
            "shutter",
            "open",
            "hex",
            "#FF0000",
            r"discrete\.shutter\.states\.open\.hex: a shutter state takes `strobe`",
            id="hex-on-shutter",
        ),
        pytest.param(
            "color",
            "red",
            "pattern",
            "stars",
            r"discrete\.color\.states\.red\.pattern: a color state takes `hex`",
            id="pattern-on-color",
        ),
        pytest.param(
            "color",
            "red",
            "strobe",
            "fast",
            r"discrete\.color\.states\.red\.strobe: a color state takes `hex`",
            id="strobe-on-color",
        ),
        pytest.param(
            "gobo",
            "dots",
            "strobe",
            "slow",
            r"discrete\.gobo\.states\.dots\.strobe: a gobo state takes `pattern`",
            id="strobe-on-gobo",
        ),
    ],
)
def test_a_tag_on_the_wrong_channel_is_refused(
    channel: str, state: str, tag: str, value: str, match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        _profile(_payload(**{channel: {state: {tag: value}}}))


@pytest.mark.parametrize("value", ["FF0000", "#FF00", "#GG0000", "#FF0000FF", "crimson", ""])
def test_a_malformed_hex_is_refused_naming_fixture_channel_state_and_the_form(value: str) -> None:
    rig = p1_rig().model_dump(mode="json")
    rig["fixtures"][0]["config"]["physical_profile"]["discrete"]["color"]["states"]["red"][
        "hex"
    ] = value

    with pytest.raises(ValidationError) as caught:
        FixtureGroup.model_validate(rig)

    message = str(caught.value)
    assert "MH1" in message
    assert "discrete.color.states.red.hex" in message
    assert "'#RRGGBB'" in message and "amber" in message


def test_an_unknown_gobo_pattern_is_refused_listing_the_vocabulary() -> None:
    with pytest.raises(ValidationError) as caught:
        _profile(_payload(gobo={"star": {"pattern": "star"}}))

    (error,) = caught.value.errors()
    assert error["loc"] == ("discrete", "gobo", "states", "star", "pattern")
    assert "'stars'" in error["msg"] and "'open'" in error["msg"]


def test_an_unknown_strobe_speed_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        _profile(
            _payload(
                shutter={"fx": {"range_min": 100, "range_max": 199, "value": 150, "strobe": "x"}}
            )
        )

    (error,) = caught.value.errors()
    assert error["loc"] == ("discrete", "shutter", "states", "fx", "strobe")
    assert "'slow'" in error["msg"] and "'fast'" in error["msg"]


def test_two_states_claiming_one_strobe_speed_are_refused() -> None:
    payload = _payload(
        shutter={
            "strobe_a": {"range_min": 100, "range_max": 149, "value": 120, "strobe": "fast"},
            "strobe_b": {"range_min": 150, "range_max": 199, "value": 170, "strobe": "fast"},
        }
    )

    with pytest.raises(
        ValidationError,
        match=r"discrete\.shutter\.states: 'strobe_a' and 'strobe_b' both claim strobe 'fast'",
    ):
        _profile(payload)


@pytest.mark.parametrize(
    ("state", "role"),
    [
        pytest.param("closed", "closed_state", id="closed"),
        pytest.param("open", "open_state", id="open"),
    ],
)
def test_a_strobe_tag_on_the_open_or_closed_state_is_refused(state: str, role: str) -> None:
    with pytest.raises(
        ValidationError, match=rf"discrete\.shutter\.states\.{state}\.strobe: .*{role}"
    ):
        _profile(_payload(shutter={state: {"strobe": "slow"}}))


def test_a_strobe_tag_on_an_extinguishing_state_is_refused() -> None:
    """The visibility block owns which states extinguish; a strobe tag cannot contradict it."""
    payload = _payload(
        shutter={"blackout": {"range_min": 200, "range_max": 255, "value": 255, "strobe": "slow"}}
    )
    payload["visibility"]["extinguishing_shutter_states"] = ["closed", "blackout"]

    with pytest.raises(
        ValidationError,
        match=r"discrete\.shutter\.states\.blackout\.strobe: .*extinguishing",
    ):
        _profile(payload)


def test_two_colour_states_may_show_the_same_colour() -> None:
    """A wheel may hold two slots of one colour (or an open slot and a white one)."""
    profile = _wheel(open="#FFFFFF", white="white")

    assert tagged_colors(profile) == {"open": "#FFFFFF", "white": "#FFFFFF"}


# --- The lookup API ---------------------------------------------------------------------


def test_tagged_colors_lists_only_tagged_states_by_name() -> None:
    profile = _profile(_payload(color={"red": {"hex": "red"}, "blue": {"hex": "#0000ff"}}))

    assert list(tagged_colors(profile).items()) == [("blue", "#0000FF"), ("red", "#FF0000")]
    assert tagged_colors(_profile(profile_payload())) == {}
    payload = profile_payload()
    del payload["discrete"]["color"]
    payload["defaults"][7] = 0
    assert tagged_colors(_profile(payload)) == {}


_W4 = {"white": "white", "red": "red", "blue": "blue", "green": "green"}
"""The W0 parity rig's wheel."""
_W8 = {
    "white": "white",
    "red": "red",
    "orange": "orange",
    "yellow": "yellow",
    "green": "green",
    "blue": "blue",
    "magenta": "magenta",
    "cyan": "cyan",
}
_WAP = {
    "open": "white",
    "red": "red",
    "amber": "amber",
    "pink": "#FF69B4",
    "blue": "blue",
    "green": "green",
}
"""A wheel with amber and pink slots, and an `open` slot that shows white."""
_WHEELS = {"w4": _W4, "w8": _W8, "wap": _WAP}

_PRESET_STATES: dict[str, tuple[str, str, str]] = {
    # request:      (w4, w8, wap)
    "red": ("red", "red", "red"),
    "blue": ("blue", "blue", "blue"),
    "green": ("green", "green", "green"),
    "yellow": ("green", "yellow", "amber"),
    "magenta": ("red", "magenta", "pink"),
    "cyan": ("green", "cyan", "green"),
    "orange": ("red", "orange", "red"),
    "purple": ("red", "magenta", "pink"),
    "amber": ("red", "yellow", "amber"),
    "lime": ("green", "yellow", "green"),
    "white": ("white", "white", "open"),
    "warm_white": ("white", "white", "open"),
    "cool_white": ("white", "white", "open"),
    "uv": ("blue", "blue", "blue"),
}
"""Every colour preset on three wheels, by hue (OKLCh): the nearest hue among the slots
that have one, whites only for whites. Amber's canonical hue (84°) is nearer yellow
(110°) than orange (53°), so on a wheel with both it shows yellow; purple and magenta
(328°) sit almost midway between red (29°) and blue (264°) on a wheel with neither."""


def test_the_preset_table_covers_every_colour_preset() -> None:
    assert set(_PRESET_STATES) == {preset.value for preset in ColorPreset}


@pytest.mark.parametrize("wheel", sorted(_WHEELS))
@pytest.mark.parametrize("request_color", sorted(_PRESET_STATES))
def test_every_colour_preset_resolves_by_hue_on_realistic_wheels(
    wheel: str, request_color: str
) -> None:
    profile = _wheel(**_WHEELS[wheel])
    expected = _PRESET_STATES[request_color][sorted(_WHEELS).index(wheel)]

    match = nearest_color_state(profile, request_color)

    assert match is not None and match.state == expected
    shown = COLOR_PRESET_HEX[ColorPreset(request_color)]
    assert match.fit == ("exact" if match.hex == shown else "approximate")
    assert match.distance == color_distance(shown, match.hex)


_PALETTE_WHITES = {"#FFFFFF", "#F5F1E8"}
"""The catalog palettes' white and warm white stops (OKLCh chroma 0 and 0.013); every
other stop has chroma 0.060 or more."""


def _palette_stops() -> list[str]:
    return sorted(
        {
            stop.hex[:7].upper()
            for info in list_palettes()
            for stop in get_palette(info.palette_id).stops
        }
    )


@pytest.mark.parametrize("wheel", sorted(_WHEELS))
def test_no_palette_colour_with_a_hue_lands_on_a_white_slot(wheel: str) -> None:
    """Every stop of every catalog palette: one with a hue goes to a slot with a hue, a
    white (or tinted white) to a white slot."""
    profile = _wheel(**_WHEELS[wheel])
    whites = {"white", "open"}

    for stop in _palette_stops():
        match = nearest_color_state(profile, stop)
        assert match is not None
        assert (match.state in whites) == (stop in _PALETTE_WHITES), (stop, match)


@pytest.mark.parametrize(
    ("request_color", "expected"),
    [
        pytest.param("#FF1744", "red", id="rgb-primary-first-stop"),
        pytest.param("#00E676", "green", id="rgb-primary-second-stop"),
        pytest.param("#0D47A1", "blue", id="cosmic-night-first-stop"),
        pytest.param("#00E5FF", "blue", id="cosmic-night-cyan-stop-not-white"),
        pytest.param("#D500F9", "blue", id="cosmic-night-violet-stop"),
    ],
)
def test_the_parity_palettes_resolve_as_the_parity_targets_expect(
    request_color: str, expected: str
) -> None:
    """`core.rgb_primary` PRIMARY→red, ACCENT→green and `spec.cosmic_night`'s first stop
    →blue on the W0 parity wheel, as `tests/regression/test_mh_intent_parity.py` expects."""
    match = nearest_color_state(_wheel(**_W4), request_color)

    assert match is not None and match.state == expected


def test_amber_resolves_to_orange_on_a_wheel_with_orange_and_no_yellow() -> None:
    match = nearest_color_state(
        _wheel(white="white", red="red", orange="orange", blue="blue"), "amber"
    )

    assert match is not None and (match.state, match.fit) == ("orange", "approximate")


def test_a_colour_with_a_hue_uses_a_white_slot_only_when_no_slot_has_a_hue() -> None:
    match = nearest_color_state(_wheel(open="white", cool="cool_white"), "cyan")

    assert match is not None
    assert (match.state, match.fit) == ("cool", "no_chromatic_match_used_neutral")
    assert match.distance == color_distance("cyan", "cool_white")


def test_a_white_request_on_a_wheel_without_white_takes_the_nearest_slot() -> None:
    match = nearest_color_state(_wheel(red="red", yellow="yellow", blue="blue"), "warm_white")

    assert match is not None and (match.state, match.fit) == ("yellow", "approximate")


def test_an_exact_slot_is_at_distance_zero() -> None:
    profile = _wheel(red="red", orange="orange", blue="blue")

    assert nearest_color_state(profile, "#ff0000") == ColorMatch("red", "#FF0000", 0.0, "exact")
    assert nearest_color_state(profile, "orange") == ColorMatch("orange", "#FF8000", 0.0, "exact")


def test_a_tie_goes_to_the_first_state_name() -> None:
    profile = _wheel(zeta="#FF0000", alpha="#FF0000", beta="#0000FF")

    assert nearest_color_state(profile, "#FE0000") == ColorMatch(
        "alpha", "#FF0000", color_distance("#FE0000", "#FF0000"), "approximate"
    )


def test_nearest_color_state_ignores_untagged_states_and_none_when_nothing_is_tagged() -> None:
    profile = _profile(_payload(color={"blue": {"hex": "blue"}}))

    assert nearest_color_state(profile, "red") == ColorMatch(
        "blue", "#0000FF", color_distance("#FF0000", "#0000FF"), "approximate"
    )
    assert nearest_color_state(_profile(discrete_profile_payload()), "red") is None


def test_nearest_color_state_refuses_a_request_that_is_not_a_colour() -> None:
    with pytest.raises(ValueError, match=r"'#RRGGBB'"):
        nearest_color_state(_wheel(red="red"), "crimson")


def test_color_distance_is_the_oklab_difference() -> None:
    """Euclidean distance in Oklab: 0 for one colour, symmetric, 1 from black to white."""
    assert color_distance("#123456", "#123456") == 0.0
    assert color_distance("#FF0000", "#00FF00") == color_distance("#00FF00", "#FF0000")
    assert color_distance("#000000", "#FFFFFF") == pytest.approx(1.0, abs=1e-4)


def test_gobo_state_finds_the_tagged_pattern_first_state_name_on_a_tie() -> None:
    payload = _payload(
        gobo={
            "star": {"pattern": "stars"},
            "open": {"pattern": "open"},
            "star_shake": {"range_min": 24, "range_max": 31, "value": 28, "pattern": "stars"},
        }
    )
    profile = _profile(payload)

    assert gobo_state(profile, GoboPattern.STARS) == "star"
    assert gobo_state(profile, "open") == "open"
    assert gobo_state(profile, GoboPattern.DOTS) is None
    assert gobo_state(_profile(profile_payload()), "open") is None


def test_strobe_state_finds_the_state_tagged_with_that_speed() -> None:
    payload = _payload(
        shutter={
            "strobe_slow": {"range_min": 100, "range_max": 149, "value": 120, "strobe": "slow"},
            "strobe_fast": {"range_min": 150, "range_max": 199, "value": 170, "strobe": "fast"},
        }
    )
    profile = _profile(payload)

    assert strobe_state(profile, "fast") == "strobe_fast"
    assert strobe_state(profile, "slow") == "strobe_slow"
    assert strobe_state(profile, "medium") is None


# --- Guidance ---------------------------------------------------------------------------


def _snippet(guidance: str) -> dict[str, Any]:
    """The JSON object in `guidance`: from its first line starting with `{` to its
    closing brace."""
    start = guidance.index("\n{") + 1
    end = guidance.index("\n}", start) + 2
    return json.loads(guidance[start:end])


def _strobing_payload() -> dict[str, Any]:
    return _payload(
        shutter={
            "strobe_fast": {"range_min": 100, "range_max": 149, "value": 120},
            "strobe": {"range_min": 150, "range_max": 199, "value": 170},
        },
        gobo={"gobo4": {"range_min": 24, "range_max": 31, "value": 28}},
    )


def test_no_guidance_when_every_state_that_can_carry_a_meaning_does() -> None:
    payload = _payload(
        color={"white": {"hex": "white"}, "red": {"hex": "red"}, "blue": {"hex": "blue"}},
        gobo={
            "open": {"pattern": "open"},
            "dots": {"pattern": "dots"},
            "star": {"pattern": "stars"},
        },
    )

    # The shutter's open and closed states mean what the profile already says.
    assert tag_guidance(_profile(payload)) is None


def test_guidance_suggests_tags_from_state_names_and_leaves_placeholders_otherwise() -> None:
    guidance = tag_guidance(_profile(_strobing_payload()))

    assert guidance is not None
    snippet = _snippet(guidance)
    color = snippet["color"]["states"]
    gobo = snippet["gobo"]["states"]
    shutter = snippet["shutter"]["states"]
    assert (color["white"]["hex"], color["red"]["hex"], color["blue"]["hex"]) == (
        "white",
        "red",
        "blue",
    )
    assert (gobo["open"]["pattern"], gobo["dots"]["pattern"], gobo["star"]["pattern"]) == (
        "open",
        "dots",
        "stars",
    )
    assert gobo["gobo4"]["pattern"].startswith("<one of: open, circles")
    assert shutter["strobe_fast"]["strobe"] == "fast"
    assert "settle_ms" not in shutter["strobe_fast"]  # unknown stays unstated
    assert shutter["strobe"]["strobe"].startswith("<slow, medium or fast")
    # Open and closed are already declared: listed unchanged so the replacement keeps them.
    assert shutter["open"] == {"range_min": 0, "range_max": 31, "value": 8, "settle_ms": 0}
    # Every suggestion is named as one, for the user to confirm.
    for line in (
        'color.red: hex "red" (suggested from the state name)',
        'gobo.star: pattern "stars" (suggested from the state name)',
        'shutter.strobe_fast: strobe "fast" (suggested from the state name)',
    ):
        assert line in guidance
    assert "confirm" in guidance


def test_a_filled_snippet_pastes_into_the_profile_and_an_unfilled_one_is_refused() -> None:
    payload = _strobing_payload()
    snippet = _snippet(tag_guidance(_profile(payload)) or "")

    unfilled = copy.deepcopy(payload)
    for channel, block in snippet.items():
        unfilled["discrete"][channel]["states"] = block["states"]
    with pytest.raises(ValidationError, match=r"gobo4"):
        _profile(unfilled)

    snippet["gobo"]["states"]["gobo4"]["pattern"] = "flame"
    snippet["shutter"]["states"]["strobe"]["strobe"] = "medium"
    for channel, block in snippet.items():
        payload["discrete"][channel]["states"] = block["states"]
    profile = _profile(payload)

    assert gobo_state(profile, "flame") == "gobo4"
    assert strobe_state(profile, "medium") == "strobe"
    assert nearest_color_state(profile, "red") == ColorMatch("red", "#FF0000", 0.0, "exact")
    assert tag_guidance(profile) is None


def test_name_suggestions_read_words_inside_a_state_name() -> None:
    payload = _payload(
        color={
            "dark-blue": {"range_min": 30, "range_max": 39, "value": 34},
            "Warm White": {"range_min": 40, "range_max": 49, "value": 44},
            "open": {"range_min": 50, "range_max": 59, "value": 54},
            "cto": {"range_min": 60, "range_max": 69, "value": 64},
        }
    )

    color = _snippet(tag_guidance(_profile(payload)) or "")["color"]["states"]

    assert color["dark-blue"]["hex"] == "blue"
    assert color["Warm White"]["hex"] == "warm_white"
    assert color["open"]["hex"] == "white"
    assert color["cto"]["hex"].startswith("<#RRGGBB or a colour name")


def _layout_model(tmp_path: Path, **slots: tuple[int, str]) -> Any:
    """`Dmx MH1` of a synthetic layout whose colour wheel has `slots` (name: byte, colour)."""
    attributes: dict[str, str] = {}
    for index, (byte, color) in enumerate(slots.values()):
        attributes[f"DmxColorWheelColor{index}"] = color
        attributes[f"DmxColorWheelDMX{index}"] = str(byte)
    path = tmp_path / "xlights_rgbeffects.xml"
    path.write_text(p1_layout_xml({"Dmx MH1": attributes}), encoding="utf-8")
    layout = load_layout(path)
    assert layout.models is not None
    return next(model for model in layout.models.model if model.name == "Dmx MH1")


def test_layout_color_tags_propose_each_slot_colour_for_the_state_its_byte_selects(
    tmp_path: Path,
) -> None:
    model = _layout_model(
        tmp_path,
        white=(0, "#FFFFFF"),
        red=(12, "#ff0000"),
        # Two colours inside blue's range [20, 29]: ambiguous, so no proposal.
        blue=(22, "#0000FF"),
        cyan=(28, "#00FFFF"),
        stray=(200, "#00FF00"),  # selects no state
        bad=(5, "rgb(1,2,3)"),  # not a colour this reads
    )

    assert layout_color_tags(_profile(discrete_profile_payload()), model) == {
        "red": "#FF0000",
        "white": "#FFFFFF",
    }


def test_layout_color_tags_are_empty_for_a_model_without_a_colour_wheel(tmp_path: Path) -> None:
    model = _layout_model(tmp_path)

    assert layout_color_tags(_profile(discrete_profile_payload()), model) == {}


def test_guidance_prefers_a_layout_proposal_and_says_where_it_came_from() -> None:
    guidance = tag_guidance(
        _profile(discrete_profile_payload()),
        layout_hex={"red": "#E01010", "blue": "#0000FF"},
        layout_model="Dmx MH1",
    )

    assert guidance is not None
    color = _snippet(guidance)["color"]["states"]
    assert (color["red"]["hex"], color["blue"]["hex"], color["white"]["hex"]) == (
        "#E01010",
        "#0000FF",
        "white",
    )
    assert "color.red: hex \"#E01010\" (suggested from xLights model 'Dmx MH1')" in guidance
    assert 'color.white: hex "white" (suggested from the state name)' in guidance


def test_rig_tag_guidance_names_every_fixture_sharing_the_same_guidance(tmp_path: Path) -> None:
    """MH1 and MH2 of `p1_rig` differ only in axis inversion: one message names both."""
    rig = p1_rig()

    (guidance,) = rig_tag_guidance(rig.expand_fixtures())

    assert guidance.fixture_ids == ("MH1", "MH2")
    assert guidance.text.startswith("MH1, MH2 (profile 'synthetic_spot'):")


def test_rig_tag_guidance_reads_each_fixture_model_in_the_layout(tmp_path: Path) -> None:
    model = _layout_model(tmp_path, red=(14, "#E01010"))
    rig = p1_rig()

    first, second = rig_tag_guidance(rig.expand_fixtures(), (model,))

    # MH1's model proposes a colour; MH2's has no wheel.
    assert (first.fixture_ids, second.fixture_ids) == (("MH1",), ("MH2",))
    assert first.text.startswith("MH1 (profile 'synthetic_spot'):")
    assert "(suggested from xLights model 'Dmx MH1')" in first.text
    assert second.text.startswith("MH2 (profile 'synthetic_spot'):")


def test_rig_tag_guidance_is_empty_for_a_fully_tagged_rig() -> None:
    assert rig_tag_guidance(tagged_p1_rig().expand_fixtures()) == ()


# --- Ledger evidence: identity only until W3/W4 -----------------------------------------

_INSTANCE_PREFIX = "fixture.fixtures[FixtureInstance].config.physical_profile"
_BASE_PREFIX = "fixture.base_config.physical_profile"
_HEADS = ("MH1", "MH2", "MH3", "MH4")
_STROBE_STATE = {"range_min": 100, "range_max": 149, "value": 120, "settle_ms": 0}

_TAG_MUTATIONS: dict[str, tuple[str, str, str]] = {
    "discrete.states.hex": ("color", "red", "red"),
    "discrete.states.pattern": ("gobo", "star", "stars"),
    "discrete.states.strobe": ("shutter", "strobe", "fast"),
}
"""Per tag path: the channel and state the tag goes on, and its value. The shutter's
`strobe` state is in both renders, so only the tag differs."""

TAG_PATHS = tuple(
    path
    for path, disposition in CONFIG_EFFECTS.items()
    if disposition.kind is ConfigDispositionKind.EFFECT_TEST
    and disposition.test_nodeid is not None
    and "::test_state_tag_changes_identity_not_output[" in disposition.test_nodeid
)


def _tag_rig(prefix: str, tag: str | None) -> FixtureGroup:
    """The four-head family rig (per-fixture profiles, or the minimal one in
    `base_config`) with a `strobe` shutter state, and `tag` set when given."""
    if prefix == _INSTANCE_PREFIX:
        payload = m.family_rig(_HEADS).model_dump(mode="json")
        profiles = [fixture["config"]["physical_profile"] for fixture in payload["fixtures"]]
    else:
        payload = m.minimal_family_rig(_HEADS).model_dump(mode="json")
        profiles = [payload["base_config"]["physical_profile"]]
    for profile in profiles:
        profile["discrete"]["shutter"]["states"]["strobe"] = dict(_STROBE_STATE)
        if tag is not None:
            channel, state, value = _TAG_MUTATIONS[tag]
            profile["discrete"][channel]["states"][state][tag.rsplit(".", 1)[1]] = value
    return FixtureGroup.model_validate(payload)


def test_every_tag_path_is_registered_to_its_evidence() -> None:
    expected = {
        f"{prefix}.{suffix}"
        for prefix in (_INSTANCE_PREFIX, _BASE_PREFIX)
        for suffix in _TAG_MUTATIONS
    }

    assert set(TAG_PATHS) == expected
    for path in TAG_PATHS:
        assert "W3" in CONFIG_EFFECTS[path].note and "W4" in CONFIG_EFFECTS[path].note


@pytest.mark.parametrize("config_path", TAG_PATHS, ids=TAG_PATHS)
def test_state_tag_changes_identity_not_output(config_path: str) -> None:
    """A tag enters the render fingerprint (it is rig data) and changes no frame:
    nothing reads it until the rig offer (W3) and colour and gobo resolution (W4)."""
    prefix, _, suffix = config_path.partition(".discrete.")
    plan = m.sections_plan(("masked_wheel_flick", 1, 8))

    def render(tag: str | None) -> RenderingPipeline:
        pipeline = RenderingPipeline(
            choreography_plan=plan,
            beat_grid=m.bars_grid(*([500.0] * 8)),
            fixture_group=_tag_rig(prefix, tag),
            job_config=m.family_job(_HEADS),
            media_file="silence.wav",
        )
        pipeline.render()
        return pipeline

    with m.family_catalog():
        untagged, tagged = render(None), render(f"discrete.{suffix}")
        fingerprints = untagged.fingerprint(), tagged.fingerprint()

    assert untagged.frames
    assert tagged.frames == untagged.frames
    assert fingerprints[0] != fingerprints[1]


def test_the_user_guide_tag_example_loads_into_its_minimal_profile() -> None:
    """The guide's tagged `discrete` fragment replaces the minimal example's and loads."""
    guide = (Path(__file__).resolve().parents[3] / "docs" / "user-guide.md").read_text(
        encoding="utf-8"
    )
    minimal = guide.split("#### Minimal physical profile", maxsplit=1)[1]
    rig = json.loads(minimal.split("```json\n", maxsplit=1)[1].split("```", maxsplit=1)[0])
    tags = guide.split("#### State meaning tags", maxsplit=1)[1]
    fragment = tags.split("```json\n", maxsplit=1)[1].split("```", maxsplit=1)[0]
    rig["base_config"]["physical_profile"]["discrete"] = json.loads("{" + fragment + "}")

    (fixture, *_) = FixtureGroup.model_validate(rig).expand_fixtures()
    profile = fixture.config.physical_profile

    assert profile is not None
    assert tagged_colors(profile) == {"amber": "#FFBF00", "red": "#E01010", "white": "#FFFFFF"}
    assert gobo_state(profile, "stars") == "star"
    assert strobe_state(profile, "fast") == "strobe_fast"
    assert nearest_color_state(profile, "yellow") == ColorMatch(
        "amber", "#FFBF00", color_distance("yellow", "amber"), "approximate"
    )
