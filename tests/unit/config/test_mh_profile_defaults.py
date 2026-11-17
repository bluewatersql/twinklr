"""Profile and initial-state defaults (C1.0): a rig states only what cannot be known.

A minimal profile resolves, when it loads, to exactly the explicit profile it stands
for, and records which values were filled; each default and each refusal of an
ambiguous inference is pinned here. Synthetic values only: no owner profile.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
import pytest

from tests.support.moving_heads import (
    INITIAL_STATE,
    minimal_head_profile_payload,
    p1_job,
    p1_rig,
    physical_head_profile,
    profile_payload,
    zoom_pilot_profile_payload,
)
from twinklr.core.config.fixtures import (
    FixtureCapabilities,
    FixtureGroup,
    InitialFixtureState,
)
from twinklr.core.config.render_policy import UnsupportedRenderModeError, preflight_render_policy


def explicit_head() -> dict[str, Any]:
    """A synthetic 16-channel spot written out in full: color 1, shutter 2, dimmer 3,
    gobo 4, 16-bit pan 11/12 and tilt 13/14, every other channel spare."""
    timing = {"travel_speed_per_s": 150.0, "latency_ms": 20, "settle_ms": 60}

    def states(settle: int, **values: int) -> dict[str, Any]:
        return {
            name: {"range_min": value, "range_max": value, "value": value, "settle_ms": settle}
            for name, value in values.items()
        }

    return {
        "profile_id": "example_spot_16ch",
        "provenance": "synthetic",
        "footprint": 16,
        # Pan word 32768 and tilt word 7282 encode 0 degrees; the rest is 0.
        "defaults": dict.fromkeys(range(1, 17), 0) | {11: 128, 13: 28, 14: 114},
        "axes": {
            "pan": {
                "unit": "degree",
                "physical_min": -270.0,
                "physical_max": 270.0,
                "allowed_min": -170.0,
                "allowed_max": 170.0,
                "coarse_offset": 11,
                "fine_offset": 12,
                **timing,
            },
            "tilt": {
                "unit": "degree",
                "physical_min": -30.0,
                "physical_max": 240.0,
                "allowed_min": -20.0,
                "allowed_max": 110.0,
                "coarse_offset": 13,
                "fine_offset": 14,
                **timing,
            },
            "dimmer": {
                "unit": "normalized",
                "physical_min": 0.0,
                "physical_max": 1.0,
                "coarse_offset": 3,
            },
        },
        "discrete": {
            "shutter": {
                "offset": 2,
                "states": states(0, closed=0, open=255),
                "default_state": "closed",
                "closed_state": "closed",
                "open_state": "open",
            },
            "color": {
                "offset": 1,
                "states": states(150, white=0, red=10, green=20, blue=30, amber=40),
                "default_state": "white",
            },
            "gobo": {
                "offset": 4,
                "states": states(150, open=0, dots=10, star=20),
                "default_state": "open",
            },
        },
        "visibility": {
            "dimmer_zero_extinguishes": True,
            "extinguishing_shutter_states": ["closed"],
            "close_latency_ms": 20,
            "open_latency_ms": 20,
        },
    }


def minimal_head() -> dict[str, Any]:
    """`explicit_head` as a rig author writes it: only what cannot be known."""
    timing = {"travel_speed_per_s": 150.0, "latency_ms": 20, "settle_ms": 60}

    def states(**values: int) -> dict[str, Any]:
        return {name: {"value": value} for name, value in values.items()}

    return {
        "profile_id": "example_spot_16ch",
        "provenance": "synthetic",
        "footprint": 16,
        "axes": {
            "pan": {
                "physical_min": -270.0,
                "physical_max": 270.0,
                "allowed_min": -170.0,
                "allowed_max": 170.0,
                "coarse_offset": 11,
                "fine_offset": 12,
                **timing,
            },
            "tilt": {
                "physical_min": -30.0,
                "physical_max": 240.0,
                "allowed_min": -20.0,
                "allowed_max": 110.0,
                "coarse_offset": 13,
                "fine_offset": 14,
                **timing,
            },
            "dimmer": {"coarse_offset": 3},
        },
        "discrete": {
            "shutter": {"offset": 2, "settle_ms": 0, "states": states(closed=0, open=255)},
            "color": {
                "offset": 1,
                "settle_ms": 150,
                "states": states(white=0, red=10, green=20, blue=30, amber=40),
            },
            "gobo": {"offset": 4, "settle_ms": 150, "states": states(open=0, dots=10, star=20)},
        },
        "visibility": {"close_latency_ms": 20, "open_latency_ms": 20},
    }


def _load(payload: dict[str, Any]) -> FixtureCapabilities:
    return FixtureCapabilities.model_validate(payload)


def _refusal(payload: dict[str, Any]) -> str:
    with pytest.raises(ValidationError) as raised:
        _load(payload)
    return str(raised.value)


# --- The whole profile ----------------------------------------------------------------


def test_minimal_profile_resolves_to_the_explicit_profile() -> None:
    """Every default fills only what was absent, so the minimal profile dumps exactly as
    the explicit one, and records each value it filled."""
    minimal, explicit = _load(minimal_head()), _load(explicit_head())

    assert minimal.model_dump(mode="json") == explicit.model_dump(mode="json")
    # The same JSON text too: filled default bytes are in offset order.
    assert minimal.model_dump_json() == explicit.model_dump_json()
    assert explicit.defaulted == ()
    ranges = [
        f"discrete.{channel}.states.{state}.{bound}"
        for channel, names in (
            ("shutter", ("closed", "open")),
            ("color", ("white", "red", "green", "blue", "amber")),
            ("gobo", ("open", "dots", "star")),
        )
        for state in names
        for bound in ("range_min", "range_max")
    ]
    assert set(minimal.defaulted) == {
        "axes.pan.unit",
        "axes.tilt.unit",
        "axes.dimmer.unit",
        "axes.dimmer.physical_min",
        "axes.dimmer.physical_max",
        *(f"defaults.{offset}" for offset in range(1, 17)),
        *ranges,
        "discrete.shutter.default_state",
        "discrete.shutter.closed_state",
        "discrete.shutter.open_state",
        "discrete.color.default_state",
        "discrete.gobo.default_state",
        "visibility.dimmer_zero_extinguishes",
        "visibility.extinguishing_shutter_states",
    }
    assert len(minimal.defaulted) == len(set(minimal.defaulted))


def test_minimal_family_head_resolves_to_the_family_rig_profile() -> None:
    """The test rig's head stated minimally is the explicit head the families render on."""
    minimal = _load(minimal_head_profile_payload())

    assert minimal.model_dump(mode="json") == _load(
        physical_head_profile(inverted=False)
    ).model_dump(mode="json")


@pytest.mark.parametrize(
    "payload",
    [profile_payload(), physical_head_profile(inverted=True), zoom_pilot_profile_payload()],
    ids=["spot", "head", "zoom"],
)
def test_a_fully_specified_profile_has_nothing_defaulted(payload: dict[str, Any]) -> None:
    """A profile that states every value is loaded as written: nothing is filled."""
    assert _load(payload).defaulted == ()


@pytest.mark.parametrize("footprint", ["16", 16.0, None])
def test_a_footprint_that_is_not_a_whole_number_is_reported_before_any_filling(
    footprint: object,
) -> None:
    payload = minimal_head()
    if footprint is None:
        del payload["footprint"]
    else:
        payload["footprint"] = footprint

    message = _refusal(payload)

    assert "footprint must be a whole number of channels" in message
    assert "1 validation error" in message


def test_shorthand_states_are_reported_by_field_validation_naming_fixture_and_guide() -> None:
    """A state written as a bare byte is not accepted input: it gets the normal
    validation message, never a crash."""
    profile = minimal_head()
    profile["discrete"]["color"]["states"] = {"white": 0, "red": 10}
    payload = p1_rig().model_dump(mode="json")
    payload["fixtures"][0]["config"]["physical_profile"] = profile

    with pytest.raises(ValidationError) as raised:
        FixtureGroup.model_validate(payload)

    message = str(raised.value)
    assert "fixture 'MH1' has an invalid physical_profile" in message
    assert "discrete.color.states.white" in message
    assert "docs/user-guide.md#minimal-physical-profile" in message


# --- Axes -----------------------------------------------------------------------------


def test_axis_unit_is_implied_by_the_axis() -> None:
    payload = zoom_pilot_profile_payload()
    for axis in payload["axes"].values():
        del axis["unit"]

    units = {name: axis.unit for name, axis in _load(payload).axes.items()}

    assert units == {"pan": "degree", "tilt": "degree", "dimmer": "normalized", "zoom": "degree"}


def test_a_stated_unit_other_than_the_axis_unit_is_still_refused() -> None:
    payload = minimal_head()
    payload["axes"]["dimmer"]["unit"] = "degree"

    assert "dimmer axis unit must be 'normalized'" in _refusal(payload)


def test_dimmer_range_defaults_to_normalized_zero_to_one() -> None:
    dimmer = _load(minimal_head()).axes["dimmer"]

    assert (dimmer.unit, dimmer.physical_min, dimmer.physical_max) == ("normalized", 0.0, 1.0)


def test_unlisted_spare_channels_default_to_zero() -> None:
    payload = minimal_head()
    payload["defaults"] = {6: 7}

    defaults = _load(payload).defaults

    assert defaults[6] == 7
    assert [defaults[offset] for offset in (5, 7, 8, 9, 10, 15, 16)] == [0] * 7


@pytest.mark.parametrize("offset", [5.5, "5.5"])
def test_a_default_key_that_is_not_a_whole_offset_is_refused_not_truncated(
    offset: object,
) -> None:
    payload = minimal_head()
    payload["defaults"] = {offset: 3}

    message = _refusal(payload)

    assert "defaults." in message and "valid integer" in message


def test_a_bool_default_key_is_not_taken_as_an_offset() -> None:
    """Field validation alone would read True as offset 1; filling stops instead."""
    payload = minimal_head()
    payload["defaults"] = {True: 3}

    _refusal(payload)


def test_whole_number_string_default_keys_are_offsets() -> None:
    payload = minimal_head()
    payload["defaults"] = {"6": 7}

    assert _load(payload).defaults[6] == 7


def test_pan_and_tilt_default_bytes_encode_their_zero_position() -> None:
    """Unlisted pan/tilt bytes are the word that encodes 0 degrees, inversion applied;
    a listed byte is kept and its axis' other unlisted byte is 0."""
    payload = minimal_head()
    payload["axes"]["pan"]["inverted"] = True
    payload["defaults"] = {13: 40}

    profile = _load(payload)

    pan = profile.axes["pan"]
    assert pan.default_word(profile.defaults) == pan.dmx_word(0.0) == 32767
    assert (profile.defaults[11], profile.defaults[12]) == (127, 255)
    assert (profile.defaults[13], profile.defaults[14]) == (40, 0)
    assert "defaults.11" in profile.defaulted and "defaults.13" not in profile.defaulted


def test_dimmer_default_byte_is_dark() -> None:
    """The dimmer's unlisted byte encodes 0: byte 0, or 255 when the dimmer is inverted."""
    assert _load(minimal_head()).defaults[3] == 0
    payload = minimal_head()
    payload["axes"]["dimmer"]["inverted"] = True

    assert _load(payload).defaults[3] == 255


def test_axis_default_is_refused_when_zero_is_outside_its_window() -> None:
    payload = minimal_head()
    payload["axes"]["tilt"]["allowed_min"] = 5.0

    message = _refusal(payload)

    assert "tilt" in message and "offsets 13/14" in message
    assert "0 is outside its allowed window [5, 110]" in message
    assert "list them in `defaults`" in message


def test_zoom_unlisted_byte_is_zero_and_refused_when_that_word_is_not_admitted() -> None:
    payload = zoom_pilot_profile_payload()
    del payload["defaults"][9]

    message = _refusal(payload)

    assert "zoom" in message and "offset 9" in message and "defaulted to 0" in message
    assert "list it in `defaults`" in message
    payload["axes"]["zoom"].update(dmx_min=0)
    assert _load(payload).defaults[9] == 0


# --- Discrete channels ----------------------------------------------------------------


def test_state_range_defaults_to_its_selected_byte() -> None:
    state = _load(minimal_head()).discrete["color"].states["red"]

    assert (state.range_min, state.range_max, state.value) == (10, 10, 10)


def test_channel_settle_is_inherited_by_states_without_their_own() -> None:
    payload = minimal_head()
    payload["discrete"]["gobo"]["states"]["star"]["settle_ms"] = 400
    payload["discrete"]["gobo"]["states"]["dots"]["settle_ms"] = None

    states = _load(payload).discrete["gobo"].states

    assert {name: state.settle_ms for name, state in states.items()} == {
        "open": 150,
        "dots": None,
        "star": 400,
    }


def test_channel_settle_is_left_out_of_the_dump() -> None:
    """The states carry the settle, so the dump is the explicit form."""
    dumped = _load(minimal_head()).model_dump(mode="json")

    assert "settle_ms" not in dumped["discrete"]["color"]


def test_default_state_and_its_byte_follow_each_other() -> None:
    """A stated default state sets an unlisted byte; a listed byte names the state."""
    payload = minimal_head()
    payload["discrete"]["color"]["default_state"] = "blue"
    payload["defaults"] = {4: 20}

    profile = _load(payload)

    assert profile.defaults[1] == 30
    assert profile.discrete["gobo"].default_state == "star"


def test_default_state_without_a_byte_is_the_state_at_byte_zero() -> None:
    profile = _load(minimal_head())

    assert {name: wheel.default_state for name, wheel in profile.discrete.items()} == {
        "shutter": "closed",
        "color": "white",
        "gobo": "open",
    }


def test_default_state_is_refused_when_no_state_selects_byte_zero() -> None:
    payload = minimal_head()
    payload["discrete"]["gobo"]["states"]["open"]["value"] = 5

    message = _refusal(payload)

    assert "discrete.gobo" in message and "no state selects byte 0" in message
    assert "set default_state" in message


def test_a_listed_default_byte_that_selects_no_state_is_refused() -> None:
    payload = minimal_head()
    payload["defaults"] = {1: 15}

    message = _refusal(payload)

    assert "discrete.color" in message and "default byte 15 at offset 1" in message
    assert "selects no declared state" in message


def test_shutter_closed_and_open_states_are_inferred_by_exact_name() -> None:
    profile = _load(minimal_head())

    shutter = profile.discrete["shutter"]
    assert (shutter.closed_state, shutter.open_state) == ("closed", "open")
    # Only the shutter's open and closed states are read; other wheels are left as given.
    assert profile.discrete["gobo"].open_state is None


def test_shutter_states_are_not_inferred_from_other_names_or_over_an_explicit_null() -> None:
    payload = minimal_head()
    payload["discrete"]["shutter"]["states"] = {"shut": {"value": 0}, "lit": {"value": 255}}
    payload["discrete"]["shutter"]["default_state"] = "shut"
    profile = _load(payload)
    assert (profile.discrete["shutter"].closed_state, profile.discrete["shutter"].open_state) == (
        None,
        None,
    )
    assert profile.visibility.extinguishing_shutter_states == ()

    payload = minimal_head()
    payload["discrete"]["shutter"]["closed_state"] = None
    profile = _load(payload)
    assert profile.discrete["shutter"].closed_state is None
    assert profile.visibility.extinguishing_shutter_states == ()


# --- Visibility -----------------------------------------------------------------------


def test_extinguishing_shutter_states_default_to_the_closed_state() -> None:
    assert _load(minimal_head()).visibility.extinguishing_shutter_states == ("closed",)


def test_dimmer_zero_extinguishes_defaults_to_whether_the_dimmer_starts_at_zero() -> None:
    assert _load(minimal_head()).visibility.dimmer_zero_extinguishes is True

    windowed = minimal_head()
    windowed["axes"]["dimmer"]["allowed_min"] = 0.1
    windowed["defaults"] = {3: 26}
    assert _load(windowed).visibility.dimmer_zero_extinguishes is False

    no_dimmer = minimal_head()
    del no_dimmer["axes"]["dimmer"]
    assert _load(no_dimmer).visibility.dimmer_zero_extinguishes is False

    stated = minimal_head()
    stated["visibility"]["dimmer_zero_extinguishes"] = False
    assert _load(stated).visibility.dimmer_zero_extinguishes is False


def test_absent_visibility_derives_darkness_and_leaves_latencies_unknown() -> None:
    payload = minimal_head()
    del payload["visibility"]

    visibility = _load(payload).visibility

    assert visibility.dimmer_zero_extinguishes is True
    assert visibility.extinguishing_shutter_states == ("closed",)
    assert (visibility.close_latency_ms, visibility.open_latency_ms) == (None, None)


def test_timings_are_never_defaulted() -> None:
    """Unknown speed, latency and settle stay null: a guessed time could be too fast."""
    payload = minimal_head()
    for axis in ("pan", "tilt"):
        for key in ("travel_speed_per_s", "latency_ms", "settle_ms"):
            del payload["axes"][axis][key]
    for wheel in payload["discrete"].values():
        del wheel["settle_ms"]
    del payload["visibility"]

    profile = _load(payload)

    for axis in profile.axes.values():
        assert (axis.travel_speed_per_s, axis.latency_ms, axis.settle_ms) == (None, None, None)
    for wheel in profile.discrete.values():
        assert all(state.settle_ms is None for state in wheel.states.values())
    assert not any("ms" in path or "speed" in path for path in profile.defaulted)


# --- One profile for identical heads ---------------------------------------------------


def _shared_rig(**base: Any) -> FixtureGroup:
    mapping = {"pan_channel": 11, "tilt_channel": 13, "dimmer_channel": 3}
    return FixtureGroup.model_validate(
        {
            "group_id": "MOVING_HEADS",
            "base_config": {"dmx_mapping": mapping, "physical_profile": minimal_head(), **base},
            "fixtures": [
                {
                    "fixture_id": f"MH{index}",
                    "xlights_model_name": f"Dmx MH{index}",
                    "position": {"position_index": index},
                }
                for index in (1, 2)
            ],
        }
    )


def test_base_config_profile_is_shared_with_its_defaulted_record() -> None:
    """Identical heads state one profile in base_config; each expanded head carries it,
    and what was defaulted, for the trace."""
    fixtures = _shared_rig().expand_fixtures()

    expected = _load(minimal_head())
    for fixture in fixtures:
        profile = fixture.config.physical_profile
        assert profile is not None
        assert profile.model_dump(mode="json") == expected.model_dump(mode="json")
        assert profile.defaulted == expected.defaulted


# --- Initial states -------------------------------------------------------------------


def test_default_initial_state_is_the_head_at_its_default_bytes_settled() -> None:
    """Each axis at the value its default bytes encode, each wheel in its default
    state, settled, and dark exactly when those bytes extinguish."""
    profile = FixtureCapabilities.model_validate(physical_head_profile(inverted=False))

    assert profile.default_initial_state() == InitialFixtureState.model_validate(INITIAL_STATE)


def test_default_initial_state_is_lit_when_the_default_bytes_are_lit() -> None:
    payload = minimal_head()
    payload["defaults"] = {3: 255, 2: 255}

    state = _load(payload).default_initial_state()

    assert state is not None
    assert (state.dimmer, state.discrete_states["shutter"], state.dark) == (1.0, "open", False)
    assert state.settled


def test_default_initial_state_keeps_a_word_that_does_not_encode_zero() -> None:
    payload = zoom_pilot_profile_payload()
    payload["defaults"][1] = 140

    state = FixtureCapabilities.model_validate(payload).default_initial_state()

    assert state is not None
    assert state.zoom_deg == 10.0
    assert state.pan_deg == pytest.approx((140 * 256 - 32767.5) / 65535 * 540, abs=0.01)


def _suggested_states(message: str) -> dict[str, Any]:
    """The ready-to-paste `initial_states` object a refusal prints."""
    marker = "add to moving_heads.initial_states: "
    states, _ = json.JSONDecoder().raw_decode(message, message.index(marker) + len(marker))
    return states


def test_a_fixture_without_an_entry_is_refused_with_a_ready_to_paste_entry() -> None:
    """No entry stays unknown and is refused; the refusal prints the entry the profile's
    default bytes give, what pasting it asserts and the guide. Pasted, it passes."""
    rig = p1_rig()
    job = p1_job(initial_states={"MH2": INITIAL_STATE})

    with pytest.raises(UnsupportedRenderModeError) as raised:
        preflight_render_policy(job, rig)

    message = str(raised.value)
    assert "MH1: moving_heads.initial_states['MH1']: initial state is unknown" in message
    assert "'MH2'" not in message
    assert (
        "pasting it asserts that each head really rests there, settled and dark as stated, "
        "when the sequence starts"
    ) in message
    assert message.count("docs/user-guide.md#minimal-physical-profile") == 1
    suggested = _suggested_states(message)
    profile = rig.expand_fixtures()[0].config.physical_profile
    assert profile is not None
    assert suggested == {"MH1": profile.default_initial_state().model_dump(mode="json")}
    assert suggested["MH1"] == InitialFixtureState.model_validate(INITIAL_STATE).model_dump(
        mode="json"
    )
    preflight_render_policy(p1_job(initial_states={"MH2": INITIAL_STATE, **suggested}), rig)


@pytest.mark.parametrize("holder", ["fixture", "base_config"])
def test_a_missing_required_field_names_the_fixture_the_field_and_the_guide(holder: str) -> None:
    profile = minimal_head()
    del profile["axes"]["pan"]["physical_min"]
    if holder == "fixture":
        payload = p1_rig().model_dump(mode="json")
        payload["fixtures"][0]["config"]["physical_profile"] = profile
        owner = "fixture 'MH1'"
    else:
        payload = _shared_rig().model_dump(mode="json")
        payload["base_config"]["physical_profile"] = profile
        owner = "base_config"

    with pytest.raises(ValidationError) as raised:
        FixtureGroup.model_validate(payload)

    message = str(raised.value)
    assert f"{owner} has an invalid physical_profile" in message
    assert "axes.pan.physical_min: Field required" in message
    assert "docs/user-guide.md#minimal-physical-profile" in message


def test_user_guide_minimal_example_loads_as_the_explicit_head() -> None:
    """The guide's example is `minimal_head` on four heads: it loads and each head
    carries the explicit profile. Without initial states it is refused; with the
    entries the refusal prints it passes preflight."""
    guide = (Path(__file__).resolve().parents[3] / "docs" / "user-guide.md").read_text(
        encoding="utf-8"
    )
    section = guide.split("#### Minimal physical profile", maxsplit=1)[1]
    example = section.split("```json\n", maxsplit=1)[1].split("```", maxsplit=1)[0]

    rig = FixtureGroup.model_validate(json.loads(example))

    explicit = _load(explicit_head()).model_dump(mode="json")
    fixtures = rig.expand_fixtures()
    assert [fixture.fixture_id for fixture in fixtures] == ["MH1", "MH2", "MH3", "MH4"]
    for fixture in fixtures:
        assert fixture.config.physical_profile is not None
        assert fixture.config.physical_profile.model_dump(mode="json") == explicit
    with pytest.raises(UnsupportedRenderModeError) as raised:
        preflight_render_policy(p1_job(initial_states={}), rig)
    suggested = _suggested_states(str(raised.value))
    assert sorted(suggested) == ["MH1", "MH2", "MH3", "MH4"]
    preflight_render_policy(p1_job(initial_states=suggested), rig)


def test_minimal_head_round_trips_through_its_dump() -> None:
    """The explicit dump loads to the same profile, with nothing left to default."""
    profile = _load(minimal_head())

    reloaded = _load(copy.deepcopy(profile.model_dump(mode="json")))

    assert reloaded.model_dump(mode="json") == profile.model_dump(mode="json")
    assert reloaded.defaulted == ()
