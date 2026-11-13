"""Explicit fixture capabilities and run initial state for the physical renderer.

Nothing renders from these contracts yet; they are validated and they enter render
identity. Physical-only config paths are evidenced here, not by the legacy-output
fixture snapshot, because by design they do not change legacy output.
"""

from __future__ import annotations

from collections.abc import Callable
import copy
from fractions import Fraction
from functools import cache
from pathlib import Path
import tomllib
from typing import Any, Literal

from packaging.requirements import Requirement
from pydantic import ValidationError
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from tests.golden.harness import RIGS, build_beat_grid, build_fixture_group, build_plan
from tests.support.mh_physical import initial_state_payload, physical_segment, profile_payload
from twinklr.core.config.fixtures import (
    AxisCapability,
    FixtureCapabilities,
    FixtureConfig,
    FixtureGroup,
    InitialFixtureState,
    SimplifiedFixtureInstance,
)
from twinklr.core.config.models import JobConfig, MHRenderPolicy, TransitionConfig
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscreteTrajectory,
    PhysicalChannelError,
)
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    EncodedFixtureFrame,
    encode_fixture_frames,
)
from twinklr.core.sequencer.moving_heads.identity import (
    LEGACY_BACKEND_ID,
    LEGACY_RENDERER_REVISION,
    render_fingerprint,
)
from twinklr.core.sequencer.moving_heads.templates import get_template, load_builtin_templates

_INSTANCE_PREFIX = "fixture.fixtures[FixtureInstance].config.physical_profile"
_BASE_PREFIX = "fixture.base_config.physical_profile"
_INITIAL_STATE_PREFIX = "job.moving_heads.initial_states"


def _profile(payload: dict[str, Any] | None = None) -> FixtureCapabilities:
    return FixtureCapabilities.model_validate(payload or profile_payload())


def test_duplicate_offsets_rejected() -> None:
    payload = profile_payload()
    payload["axes"]["tilt"]["coarse_offset"] = 1

    with pytest.raises(ValidationError, match="offset 1"):
        _profile(payload)

    payload = profile_payload()
    payload["discrete"]["color"]["offset"] = 5
    with pytest.raises(ValidationError, match="offset 5"):
        _profile(payload)


def _wide_payload(*, footprint: int, dimmer_offset: int) -> dict[str, Any]:
    payload = profile_payload()
    payload["footprint"] = footprint
    payload["defaults"] = dict.fromkeys(range(1, footprint + 1), 0)
    payload["defaults"][17] = 64  # the shutter's closed default state
    payload["discrete"]["shutter"]["offset"] = 17
    payload["axes"]["dimmer"]["coarse_offset"] = dimmer_offset
    return payload


def test_backend_offsets_17_and_48_allowed_49_rejected() -> None:
    """xLights' DMX effect addresses 48 model-relative channels; 17 is an ordinary one."""
    profile = _profile(_wide_payload(footprint=48, dimmer_offset=48))
    assert profile.discrete["shutter"].offset == 17
    assert profile.axes["dimmer"].coarse_offset == 48

    with pytest.raises(ValidationError, match="48"):
        _profile(_wide_payload(footprint=48, dimmer_offset=49))
    with pytest.raises(ValidationError, match="48"):
        _profile(_wide_payload(footprint=49, dimmer_offset=48))


def test_missing_default_or_unknown_initial_state_reported() -> None:
    payload = profile_payload()
    del payload["defaults"][5]
    with pytest.raises(ValidationError, match=r"missing defaults for offsets \[5\]"):
        _profile(payload)

    profile = _profile()
    assert profile.check_initial_state(InitialFixtureState(**initial_state_payload())) == ()

    unknown = profile.check_initial_state(None)
    assert len(unknown) == 1
    assert "unknown" in unknown[0]

    state = initial_state_payload()
    state["discrete_states"] = {"shutter": "half"}
    problems = profile.check_initial_state(InitialFixtureState(**state))
    assert any("'half'" in problem and "shutter" in problem for problem in problems)
    assert any("color" in problem for problem in problems)

    state = initial_state_payload()
    state["pan_deg"] = 300.0
    state["dimmer"] = None
    problems = profile.check_initial_state(InitialFixtureState(**state))
    assert any("pan" in problem for problem in problems)
    assert any("dimmer" in problem for problem in problems)


@pytest.mark.parametrize(
    ("axis", "value", "window"),
    [
        pytest.param("tilt", 140.0, {}, id="tilt-above-calibration"),
        pytest.param("tilt", -136.0, {}, id="tilt-below-calibration"),
        pytest.param("pan", 120.0, {"allowed_max": 90.0}, id="pan-above-allowed-window"),
        pytest.param("tilt", -60.0, {"allowed_min": -45.0}, id="tilt-below-allowed-window"),
    ],
)
def test_initial_pose_outside_operable_range_reported(
    axis: str, value: float, window: dict[str, float]
) -> None:
    """A time-zero pose the fixture may not operate at is not a usable known state."""
    payload = profile_payload()
    payload["axes"][axis].update(window)
    state = initial_state_payload()
    state[f"{axis}_deg"] = value

    problems = _profile(payload).check_initial_state(InitialFixtureState(**state))

    assert problems == (f"initial {axis} {value} is outside the operable range",)


def test_allowed_window_does_not_rescale_calibrated_axis() -> None:
    """Narrowing operation limits keeps the calibrated degree-to-word mapping."""
    pan = _profile().axes["pan"]
    narrowed = AxisCapability.model_validate(
        {**pan.model_dump(), "allowed_min": -90.0, "allowed_max": 90.0}
    )

    for angle in (-90.0, 0.0, 45.0, 90.0):
        assert narrowed.dmx_word(angle) == pan.dmx_word(angle)
    assert pan.dmx_word(-270.0) == 0
    assert pan.dmx_word(270.0) == 65535

    assert pan.admits(180.0)
    assert not narrowed.admits(180.0)
    with pytest.raises(ValueError, match="outside"):
        narrowed.dmx_word(180.0)
    with pytest.raises(ValueError, match="outside"):
        pan.dmx_word(270.5)

    inverted = AxisCapability.model_validate({**pan.model_dump(), "inverted": True})
    assert inverted.dmx_word(-270.0) == 65535
    assert inverted.dmx_word(45.0) == 65535 - pan.dmx_word(45.0)

    dimmer = _profile().axes["dimmer"]
    assert [dimmer.dmx_word(value) for value in (0.0, 0.5, 1.0)] == [0, 128, 255]


@pytest.mark.parametrize(
    ("value", "word"),
    [
        pytest.param(0.0, 32768, id="tie-32767.5-rounds-up"),
        pytest.param(180.0, 54613, id="tie-54612.5-rounds-up"),
        # Exactly 65519.4999999999...; float arithmetic rounds the product up to .5.
        pytest.param(269.8722819867246, 65519, id="just-below-tie"),
    ],
)
def test_dmx_word_rounds_half_up_exactly(value: float, word: int) -> None:
    assert _profile().axes["pan"].dmx_word(value) == word


def test_dmx_word_takes_an_exact_fraction() -> None:
    """-270 + 90/4369 degrees scales to exactly 2.5; no float holds that value."""
    pan = _profile().axes["pan"]
    exact = Fraction(-270) + Fraction(90, 4369)

    assert pan.dmx_word(exact) == 3
    assert pan.dmx_word(float(exact)) == 2
    with pytest.raises(ValueError, match="outside"):
        pan.dmx_word(Fraction(271))


def test_discrete_default_byte_must_select_its_default_state() -> None:
    payload = profile_payload()
    payload["defaults"][6] = 8  # the open byte; the shutter's default state is closed (64)

    with pytest.raises(ValidationError, match=r"offset 6 default byte 8 .* 'closed' selects 64"):
        _profile(payload)


@pytest.mark.parametrize(
    ("inverted", "accepted"),
    [(False, True), (True, False)],
    ids=["direct-270-inside", "inverted--270-outside"],
)
def test_axis_default_word_must_lie_in_the_allowed_window(inverted: bool, accepted: bool) -> None:
    """Bytes 255/255 are word 65535: 270 degrees direct, -270 once inversion is undone."""
    payload = profile_payload()
    payload["axes"]["pan"].update(allowed_min=0.0, allowed_max=270.0, inverted=inverted)
    payload["defaults"].update({1: 255, 2: 255})

    if accepted:
        assert _profile(payload).defaults[1] == 255
    else:
        with pytest.raises(ValidationError, match=r"pan default word 65535 at offsets 1/2"):
            _profile(payload)


def test_axis_default_word_outside_a_narrowed_window_is_rejected() -> None:
    payload = profile_payload()
    payload["axes"]["tilt"].update(allowed_min=-90.0, allowed_max=90.0)
    payload["defaults"].update({3: 0, 4: 0})

    with pytest.raises(ValidationError, match=r"tilt default word 0 .* -135"):
        _profile(payload)


def test_inverted_dimmer_dark_default_is_byte_255() -> None:
    payload = profile_payload()
    payload["axes"]["dimmer"]["inverted"] = True
    payload["defaults"][5] = 255

    profile = _profile(payload)

    assert profile.visibility.dimmer_zero_extinguishes
    assert profile.axes["dimmer"].dmx_word(0.0) == profile.defaults[5] == 255


@pytest.mark.parametrize(
    ("update", "match"),
    [
        pytest.param({"allowed_min": -300.0}, "allowed", id="window-below-calibration"),
        pytest.param({"allowed_min": 10.0, "allowed_max": 0.0}, "allowed", id="window-reversed"),
        pytest.param({"physical_min": 270.0}, "physical_min", id="calibration-reversed"),
        pytest.param({"travel_speed_per_s": 0.0}, "greater than 0", id="zero-speed"),
        pytest.param({"settle_ms": -1}, "greater than or equal", id="negative-settle"),
    ],
)
def test_invalid_axis_is_rejected(update: dict[str, Any], match: str) -> None:
    payload = profile_payload()
    payload["axes"]["pan"].update(update)

    with pytest.raises(ValidationError, match=match):
        _profile(payload)


def test_profile_defaults_do_not_supply_live_initial_state() -> None:
    """A complete default byte state is not evidence of where a fixture is now."""
    profile = _profile()

    assert set(profile.defaults) == set(range(1, profile.footprint + 1))
    assert MHRenderPolicy().initial_states == {}
    assert profile.check_initial_state(MHRenderPolicy().initial_states.get("MH1")) == (
        "initial state is unknown: the run supplies no initial state for this fixture",
    )
    assert not {"pan_deg", "tilt_deg", "initial_state", "settled", "dark"} & set(
        FixtureCapabilities.model_fields
    )


def test_unknown_speed_and_latency_stay_unknown() -> None:
    """Nothing is filled in from legacy fixture defaults or assumed to be zero."""
    profile = _profile()

    assert all(axis.travel_speed_per_s is None for axis in profile.axes.values())
    assert all(axis.latency_ms is None for axis in profile.axes.values())
    assert all(axis.settle_ms is None for axis in profile.axes.values())

    payload = profile_payload()
    del payload["visibility"]["close_latency_ms"]
    del payload["visibility"]["open_latency_ms"]
    visibility = _profile(payload).visibility
    assert (visibility.close_latency_ms, visibility.open_latency_ms) == (None, None)


def test_discrete_state_needs_an_explicit_byte_inside_its_range() -> None:
    payload = profile_payload()
    del payload["discrete"]["shutter"]["states"]["open"]["value"]
    with pytest.raises(ValidationError, match="value"):
        _profile(payload)

    payload = profile_payload()
    payload["discrete"]["shutter"]["states"]["open"]["value"] = 40
    with pytest.raises(ValidationError, match="outside"):
        _profile(payload)

    payload = profile_payload()
    payload["discrete"]["shutter"]["open_state"] = "strobe"
    with pytest.raises(ValidationError, match="strobe"):
        _profile(payload)


@pytest.mark.parametrize(
    "states",
    [
        pytest.param(
            {
                "open": {"range_min": 60, "range_max": 100, "value": 70},
                "closed": {"range_min": 64, "range_max": 95, "value": 64},
            },
            id="partial-overlap",
        ),
        pytest.param(
            {
                "open": {"range_min": 64, "range_max": 95, "value": 64},
                "closed": {"range_min": 64, "range_max": 95, "value": 64},
            },
            id="identical-ranges-and-bytes",
        ),
        pytest.param(
            {
                "open": {"range_min": 0, "range_max": 64, "value": 8},
                "closed": {"range_min": 64, "range_max": 95, "value": 80},
            },
            id="shared-endpoint",
        ),
    ],
)
def test_overlapping_discrete_states_rejected(states: dict[str, Any]) -> None:
    """One byte can belong to one semantic state only; the error names both."""
    payload = profile_payload()
    payload["discrete"]["shutter"]["states"] = states

    with pytest.raises(ValidationError, match=r"'closed'.*'open'|'open'.*'closed'"):
        _profile(payload)


def test_visibility_names_only_declared_shutter_states() -> None:
    payload = profile_payload()
    payload["visibility"]["extinguishing_shutter_states"] = ["blackout"]

    with pytest.raises(ValidationError, match="blackout"):
        _profile(payload)


def _without_shutter_extinction(payload: dict[str, Any]) -> None:
    payload["visibility"]["extinguishing_shutter_states"] = []


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        pytest.param(
            lambda p: p["visibility"]["extinguishing_shutter_states"].append("open"),
            "open_state 'open'",
            id="open-state-extinguishes",
        ),
        pytest.param(
            lambda p: p["axes"].pop("dimmer"),
            "dimmer_zero_extinguishes",
            id="dimmer-extinguishes-without-dimmer-axis",
        ),
        pytest.param(
            lambda p: p["axes"]["dimmer"].update(physical_max=255.0),
            "within 0 and 1",
            id="normalized-axis-above-one",
        ),
        pytest.param(
            lambda p: (
                p["axes"]["dimmer"].update(physical_min=-0.5),
                p["visibility"].update(dimmer_zero_extinguishes=False),
            ),
            "within 0 and 1",
            id="normalized-axis-below-zero",
        ),
        pytest.param(
            lambda p: p["axes"]["dimmer"].update(physical_min=0.1),
            "physical_min 0",
            id="dimmer-zero-not-calibrated",
        ),
        pytest.param(
            lambda p: p["axes"]["dimmer"].update(allowed_min=0.2),
            "admit 0",
            id="dimmer-zero-outside-allowed-window",
        ),
    ],
)
def test_contradictory_darkness_declarations_rejected(
    mutate: Callable[[dict[str, Any]], Any], match: str
) -> None:
    """A profile cannot claim darkness it has no way to produce."""
    payload = profile_payload()
    mutate(payload)

    with pytest.raises(ValidationError, match=match):
        _profile(payload)


def test_dimmer_zero_encodes_the_calibrated_dark_endpoint() -> None:
    """Rule: with dimmer_zero_extinguishes, normalized 0 is admitted and is the
    calibrated minimum, so it encodes to word 0, or to the full word when inverted."""
    payload = profile_payload()
    assert _profile(payload).axes["dimmer"].dmx_word(0.0) == 0

    payload["axes"]["dimmer"].update(inverted=True, physical_max=0.8)
    dimmer = _profile(payload).axes["dimmer"]
    assert dimmer.dmx_word(0.0) == 255

    payload["axes"]["dimmer"]["physical_min"] = 0.1
    payload["visibility"]["dimmer_zero_extinguishes"] = False
    assert _profile(payload).axes["dimmer"].physical_min == 0.1


def test_retired_fixture_keys_never_become_a_physical_profile() -> None:
    config = FixtureConfig.model_validate(
        {
            "fixture_id": "MH1",
            "dmx_mapping": {"pan_channel": 1, "tilt_channel": 2, "dimmer_channel": 3},
            "capabilities": {"has_prism": True},
            "movement_speed": 90,
        }
    )

    assert config.physical_profile is None


def test_physical_profile_and_initial_states_load_from_json() -> None:
    config = FixtureConfig.model_validate(
        {
            "fixture_id": "MH1",
            "dmx_mapping": {"pan_channel": 1, "tilt_channel": 2, "dimmer_channel": 3},
            "physical_profile": profile_payload(),
        }
    )
    assert config.physical_profile == _profile()

    job = JobConfig.model_validate(
        {"moving_heads": {"initial_states": {"MH1": initial_state_payload()}}}
    )
    assert job.moving_heads.initial_states["MH1"].discrete_states["shutter"] == "closed"

    with pytest.raises(ValidationError):
        JobConfig.model_validate(
            {"moving_heads": {"initial_states": {"MH1": {**initial_state_payload(), "x": 1}}}}
        )


def test_declared_pydantic_floor_honors_exclude_if() -> None:
    """`exclude_if` keeps absent physical inputs out of legacy fingerprints; pydantic
    before 2.12 ignores it silently, so no older version may satisfy the floor."""
    core = Path(__file__).parents[3] / "packages/twinklr/core/pyproject.toml"
    dependencies = tomllib.loads(core.read_text(encoding="utf-8"))["project"]["dependencies"]
    pydantic = next(Requirement(d) for d in dependencies if Requirement(d).name == "pydantic")

    assert not pydantic.specifier.contains("2.11.9")
    assert pydantic.specifier.contains("2.12.0")


# --- Fixture groups ---------------------------------------------------------------------


def _base_config_group(
    profile: dict[str, Any] | None, overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The mh4_minimal rig in base_config form, profile on the shared base config."""
    harness = build_fixture_group(RIGS["mh4_minimal"]).model_dump(mode="python")
    base = {
        key: value
        for key, value in harness["fixtures"][0]["config"].items()
        if key not in {"fixture_id", "position"}
    }
    if profile is not None:
        base["physical_profile"] = profile
    fixtures: list[dict[str, Any]] = [
        {"fixture_id": f"MH{i}", "xlights_model_name": f"Dmx MH{i}"} for i in range(1, 5)
    ]
    if overrides is not None:
        fixtures[0]["config_overrides"] = overrides
    return {"group_id": "MOVING_HEADS", "base_config": base, "fixtures": fixtures}


def _instance_group(profile: dict[str, Any] | None) -> dict[str, Any]:
    payload = build_fixture_group(RIGS["mh4_minimal"]).model_dump(mode="python")
    payload["fixtures"][0]["config"]["physical_profile"] = profile
    return payload


def test_base_config_profile_reaches_every_expanded_fixture() -> None:
    group = FixtureGroup.model_validate(_base_config_group(profile_payload()))

    profiles = [fixture.config.physical_profile for fixture in group.expand_fixtures()]

    assert profiles == [_profile()] * 4
    assert (
        "physical_profile"
        not in FixtureGroup.model_validate(_base_config_group(None)).model_dump(mode="json")[
            "base_config"
        ]
    )


def test_fixture_override_profile_wins_and_is_typed() -> None:
    other = {**profile_payload(), "profile_id": "override_spot"}
    group = FixtureGroup.model_validate(
        _base_config_group(profile_payload(), overrides={"physical_profile": other})
    )

    expanded = group.expand_fixtures()
    assert [
        f.config.physical_profile.profile_id for f in expanded if f.config.physical_profile
    ] == [
        "override_spot",
        "synthetic_spot",
        "synthetic_spot",
        "synthetic_spot",
    ]
    override = group.fixtures[0]
    assert isinstance(override, SimplifiedFixtureInstance)
    assert isinstance(override.config_overrides["physical_profile"], FixtureCapabilities)


def _broken_profile() -> dict[str, Any]:
    payload = profile_payload()
    payload["axes"]["tilt"]["coarse_offset"] = 1
    return payload


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        pytest.param(
            _instance_group(_broken_profile()),
            r"MH1.*physical_profile.*offset 1",
            id="fixture-instance",
        ),
        pytest.param(
            _base_config_group(None, overrides={"physical_profile": _broken_profile()}),
            r"MH1.*physical_profile.*offset 1",
            id="config-override",
        ),
        pytest.param(
            _base_config_group(_broken_profile()),
            r"base_config\.physical_profile[\s\S]*offset 1",
            id="base-config",
        ),
    ],
)
def test_invalid_profile_fails_at_group_validation_by_name(
    payload: dict[str, Any], match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        FixtureGroup.model_validate(payload)


def test_other_invalid_fixture_config_keeps_its_legacy_behavior() -> None:
    """Only the profile surfaces early; an invalid legacy field still loads as before."""
    payload = build_fixture_group(RIGS["mh4_minimal"]).model_dump(mode="python")
    payload["fixtures"][0]["config"]["dmx_mapping"] = {"pan_channel": "not-a-channel"}

    group = FixtureGroup.model_validate(payload)

    with pytest.raises(ValueError, match="no base_config"):
        group.expand_fixtures()


# --- Registry evidence for physical-only config paths -----------------------------------

Component = Literal["rejected", "words", "frames", "check", "fingerprint"]

_COMPONENT_NOTES: dict[Component, str] = {
    "rejected": "exact path's alternative values are rejected by validation",
    "words": "exact path changes the encoded DMX word",
    "frames": "exact path changes the encoded fixture frames",
    "check": "exact path changes the initial-state check",
    "fingerprint": "identity only; consumer lands in P1.3–P1.5",
}
"""The registry note each evidence component must carry, so none overclaims."""


def _set(target: dict[str, Any], keys: tuple[str | int, ...], value: Any) -> None:
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value


def _add_spare_default(payload: dict[str, Any]) -> None:
    payload["footprint"] = 9
    payload["defaults"][9] = 0


Mutation = tuple[Component, Callable[[dict[str, Any]], Any]]

_PROFILE_MUTATIONS: dict[str, Mutation] = {
    "": ("words", lambda p: p.clear()),
    "schema_version": ("rejected", lambda p: _set(p, ("schema_version",), "2")),
    "profile_id": ("fingerprint", lambda p: _set(p, ("profile_id",), "other_spot")),
    "provenance": ("fingerprint", lambda p: _set(p, ("provenance",), "measured")),
    "footprint": ("frames", _add_spare_default),
    "defaults": ("frames", lambda p: _set(p, ("defaults", 8), 255)),
    "axes": ("words", lambda p: p["axes"].pop("tilt")),
    "axes.unit": ("rejected", lambda p: _set(p, ("axes", "pan", "unit"), "normalized")),
    "axes.physical_min": ("words", lambda p: _set(p, ("axes", "pan", "physical_min"), -180.0)),
    "axes.physical_max": ("words", lambda p: _set(p, ("axes", "pan", "physical_max"), 180.0)),
    "axes.allowed_min": ("words", lambda p: _set(p, ("axes", "pan", "allowed_min"), -90.0)),
    "axes.allowed_max": ("words", lambda p: _set(p, ("axes", "pan", "allowed_max"), 90.0)),
    "axes.coarse_offset": (
        "frames",
        lambda p: _set(p, ("axes", "dimmer", "coarse_offset"), 8),
    ),
    "axes.fine_offset": ("words", lambda p: _set(p, ("axes", "pan", "fine_offset"), None)),
    "axes.inverted": ("words", lambda p: _set(p, ("axes", "pan", "inverted"), True)),
    "axes.travel_speed_per_s": (
        "fingerprint",
        lambda p: _set(p, ("axes", "pan", "travel_speed_per_s"), 90.0),
    ),
    "axes.latency_ms": ("fingerprint", lambda p: _set(p, ("axes", "pan", "latency_ms"), 10)),
    "axes.settle_ms": ("fingerprint", lambda p: _set(p, ("axes", "pan", "settle_ms"), 40)),
    "discrete": ("check", lambda p: p["discrete"].pop("color")),
    "discrete.offset": ("frames", lambda p: _set(p, ("discrete", "color", "offset"), 8)),
    "discrete.states": ("check", lambda p: p["discrete"]["color"]["states"].pop("red")),
    "discrete.states.range_min": (
        "fingerprint",
        lambda p: _set(p, ("discrete", "color", "states", "red", "range_min"), 12),
    ),
    "discrete.states.range_max": (
        "fingerprint",
        lambda p: _set(p, ("discrete", "color", "states", "red", "range_max"), 15),
    ),
    "discrete.states.value": (
        "frames",
        lambda p: _set(p, ("discrete", "color", "states", "red", "value"), 10),
    ),
    "discrete.states.settle_ms": (
        "fingerprint",
        lambda p: _set(p, ("discrete", "color", "states", "red", "settle_ms"), 120),
    ),
    "discrete.default_state": (
        "fingerprint",
        lambda p: (
            _set(p, ("discrete", "color", "default_state"), "red"),
            _set(p, ("defaults", 7), 14),  # the default byte must select the default state
        ),
    ),
    "discrete.closed_state": (
        "fingerprint",
        lambda p: _set(p, ("discrete", "shutter", "closed_state"), None),
    ),
    "discrete.open_state": (
        "fingerprint",
        lambda p: _set(p, ("discrete", "shutter", "open_state"), None),
    ),
    "visibility": ("fingerprint", lambda p: _set(p, ("visibility",), {})),
    "visibility.dimmer_zero_extinguishes": (
        "fingerprint",
        lambda p: _set(p, ("visibility", "dimmer_zero_extinguishes"), False),
    ),
    "visibility.extinguishing_shutter_states": (
        "fingerprint",
        lambda p: _set(p, ("visibility", "extinguishing_shutter_states"), []),
    ),
    "visibility.close_latency_ms": (
        "fingerprint",
        lambda p: _set(p, ("visibility", "close_latency_ms"), 40),
    ),
    "visibility.open_latency_ms": (
        "fingerprint",
        lambda p: _set(p, ("visibility", "open_latency_ms"), 20),
    ),
}
"""Per profile field (path below the profile; "" is the profile itself): the one
contract component its alternative must change, and that alternative."""

_INITIAL_STATE_MUTATIONS: dict[str, Mutation] = {
    "": ("check", lambda s: s.clear()),
    "pan_deg": ("check", lambda s: _set(s, ("pan_deg",), 300.0)),
    "tilt_deg": ("check", lambda s: _set(s, ("tilt_deg",), -140.0)),
    "dimmer": ("check", lambda s: _set(s, ("dimmer",), None)),
    "discrete_states": ("check", lambda s: _set(s, ("discrete_states", "shutter"), "half")),
    "settled": ("fingerprint", lambda s: _set(s, ("settled",), False)),
    "dark": ("fingerprint", lambda s: _set(s, ("dark",), False)),
}


def _registered(test_name: str) -> tuple[str, ...]:
    return tuple(
        path
        for path, disposition in CONFIG_EFFECTS.items()
        if disposition.kind is ConfigDispositionKind.EFFECT_TEST
        and disposition.test_nodeid is not None
        and f"::{test_name}[" in disposition.test_nodeid
    )


PHYSICAL_PROFILE_PATHS = _registered("test_physical_profile_field_changes_contract")
INITIAL_STATE_PATHS = _registered("test_initial_state_field_changes_contract")


def _split(path: str, prefixes: tuple[str, ...]) -> tuple[str, str]:
    for prefix in prefixes:
        if path == prefix:
            return prefix, ""
        if path.startswith(f"{prefix}."):
            return prefix, path.removeprefix(f"{prefix}.")
    raise AssertionError(f"unexpected physical evidence path {path}")


@cache
def _identity_inputs() -> dict[str, Any]:
    load_builtin_templates()
    plan = build_plan()
    template_ids = sorted({s.template_id for s in plan.sections if s.template_id})
    return {
        "plan": plan,
        "beat_grid": build_beat_grid(),
        "templates": [get_template(template_id) for template_id in template_ids],
        "transitions": TransitionConfig(),
        "backend_id": LEGACY_BACKEND_ID,
        "renderer_revision": LEGACY_RENDERER_REVISION,
    }


def _probe_segment() -> FixtureSegment:
    def hold(unit: str, value: float) -> ContinuousTrajectory:
        return ContinuousTrajectory.model_validate(
            {"unit": unit, "points": [{"t_ms": 0, "value": value}], "interpolation": "hold"}
        )

    def state(name: str) -> DiscreteTrajectory:
        return DiscreteTrajectory.model_validate({"events": [{"t_ms": 0, "state": name}]})

    return physical_segment(
        {
            ChannelName.PAN: hold("degree", 10.0),
            ChannelName.TILT: hold("degree", -20.0),
            ChannelName.DIMMER: hold("normalized", 0.75),
            ChannelName.SHUTTER: state("open"),
            ChannelName.COLOR: state("red"),
        },
        t0_ms=0,
        t1_ms=40,
    )


def _contract_snapshot(
    prefix: str, profile: dict[str, Any] | None, initial_states: dict[str, Any]
) -> dict[Component, Any]:
    """What the physical contract makes of MH1's profile and the run's initial states.

    The validation error locations, the encoded DMX word at probe values on every
    declared axis, the frames encoded from a probe segment that writes every attribute
    but leaves channel 8 to its default, MH1's initial-state check, and the render
    fingerprint.
    """
    try:
        group = FixtureGroup.model_validate(
            _instance_group(profile) if prefix == _INSTANCE_PREFIX else _base_config_group(profile)
        )
        policy = MHRenderPolicy.model_validate({"initial_states": initial_states})
    except ValidationError as error:
        return {"rejected": tuple(sorted(str(e["loc"]) for e in error.errors()))}
    capabilities = group.expand_fixtures()[0].config.physical_profile
    words: dict[str, tuple[int | str, ...]] = {}
    frames: tuple[Any, ...] = ()
    check: tuple[str, ...] = ()
    if capabilities is not None:
        for name, axis in capabilities.axes.items():
            probes = (0.0, 0.5, 1.0) if axis.unit == "normalized" else (-180.0, -45.0, 0.0, 180.0)
            words[name] = tuple(
                axis.dmx_word(value) if axis.admits(value) else "rejected" for value in probes
            )
        try:
            frames = encode_fixture_frames(
                [_probe_segment()], capabilities, frame_times_ms=(0, 20, 40)
            )
        except (PhysicalChannelError, ValueError) as error:
            frames = ("unencodable", str(error))
        check = capabilities.check_initial_state(policy.initial_states.get("MH1"))
    return {
        "words": words,
        "frames": frames,
        "check": check,
        "fingerprint": render_fingerprint(fixtures=group, policy=policy, **_identity_inputs()),
    }


def test_physical_evidence_paths_cover_every_mutation() -> None:
    """The registry, its notes and these mutation tables describe the same evidence."""
    expected = {
        f"{prefix}.{suffix}" if suffix else prefix: component
        for prefix in (_INSTANCE_PREFIX, _BASE_PREFIX)
        for suffix, (component, _) in _PROFILE_MUTATIONS.items()
    }
    expected |= {
        f"{_INITIAL_STATE_PREFIX}.{suffix}" if suffix else _INITIAL_STATE_PREFIX: component
        for suffix, (component, _) in _INITIAL_STATE_MUTATIONS.items()
    }

    assert set(PHYSICAL_PROFILE_PATHS) | set(INITIAL_STATE_PATHS) == set(expected)
    for path, component in expected.items():
        assert CONFIG_EFFECTS[path].note == _COMPONENT_NOTES[component], path


def _assert_component_changed(
    component: Component, base: dict[Component, Any], changed: dict[Component, Any]
) -> None:
    assert "rejected" not in base
    if component == "rejected":
        assert "rejected" in changed
    elif component == "frames":
        # Both sides must be frames actually encoded, never an error standing in for them.
        for side in (base, changed):
            assert "rejected" not in side and side["frames"], side
            assert all(isinstance(frame, EncodedFixtureFrame) for frame in side["frames"])
        assert changed["frames"] != base["frames"]
    else:
        assert "rejected" not in changed, changed
        assert changed[component] != base[component]


@pytest.mark.parametrize("config_path", PHYSICAL_PROFILE_PATHS, ids=PHYSICAL_PROFILE_PATHS)
def test_physical_profile_field_changes_contract(config_path: str) -> None:
    """Each profile path changes the one contract component its registry note names."""
    prefix, suffix = _split(config_path, (_INSTANCE_PREFIX, _BASE_PREFIX))
    component, mutate = _PROFILE_MUTATIONS[suffix]
    states = {"MH1": initial_state_payload()}
    payload = copy.deepcopy(profile_payload())
    mutate(payload)

    _assert_component_changed(
        component,
        _contract_snapshot(prefix, profile_payload(), states),
        _contract_snapshot(prefix, payload or None, states),
    )


@pytest.mark.parametrize("config_path", INITIAL_STATE_PATHS, ids=INITIAL_STATE_PATHS)
def test_initial_state_field_changes_contract(config_path: str) -> None:
    """Each initial-state path changes the one contract component its note names."""
    _, suffix = _split(config_path, (_INITIAL_STATE_PREFIX,))
    component, mutate = _INITIAL_STATE_MUTATIONS[suffix]
    state = copy.deepcopy(initial_state_payload())
    mutate(state)

    _assert_component_changed(
        component,
        _contract_snapshot(_INSTANCE_PREFIX, profile_payload(), {"MH1": initial_state_payload()}),
        _contract_snapshot(_INSTANCE_PREFIX, profile_payload(), {"MH1": state} if state else {}),
    )
