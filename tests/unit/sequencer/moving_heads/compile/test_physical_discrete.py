"""Physical discrete channels: named shutter, color and gobo states resolve to declared bytes."""

from __future__ import annotations

from collections.abc import Callable
import copy
from typing import Any, Literal

from pydantic import ValidationError
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from tests.support.mh_physical import (
    discrete_profile_payload,
    discrete_step_payload,
    physical_step_payload,
)
from twinklr.core.config.fixtures import FixtureCapabilities
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.context import StepCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    DiscreteTrajectory,
    PhysicalChannelError,
)
from twinklr.core.sequencer.models.template import TemplateStep
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import (
    PhysicalCompileError,
    WheelChange,
    compile_physical_step,
    resolve_discrete_state,
    slice_physical_segment,
    wheel_changes,
)
from twinklr.core.sequencer.moving_heads.compile.step_compiler import compile_step
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

_GRID = BeatGrid.from_tempo(tempo_bpm=120, total_bars=2)


def _context(
    *, start_ms: int = 0, profile: dict[str, Any] | None = None, duration_ms: int = 1000
) -> StepCompileContext:
    registries = create_default_registries()
    return StepCompileContext(
        section_id="verse",
        segment_id="A",
        template_id="physical_probe",
        fixture_id="MH1",
        role="OUTER_LEFT",
        calibration={},
        start_ms=start_ms,
        duration_ms=duration_ms,
        beat_grid=_GRID,
        curve_registry=CurveRegistry(),
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
        physical_profile=FixtureCapabilities.model_validate(profile or discrete_profile_payload()),
        phase_map=build_musical_phase_map(_GRID),
    )


def _compile(
    start_ms: int = 0, profile: dict[str, Any] | None = None, **fields: Any
) -> FixtureSegment:
    payload = {**discrete_step_payload(), **fields}
    for name in [name for name, value in payload.items() if value is None]:
        payload.pop(name)
    return compile_physical_step(
        TemplateStep.model_validate(payload),
        _context(start_ms=start_ms, profile=profile),
        sample_times_ms=tuple(range(start_ms, start_ms + 1000, 20)),
    )


def _events(segment: FixtureSegment, channel: ChannelName) -> list[tuple[int, str]]:
    physical = segment.channels[channel].physical
    assert isinstance(physical, DiscreteTrajectory)
    return [(event.t_ms, event.state) for event in physical.events]


def _profile() -> FixtureCapabilities:
    return FixtureCapabilities.model_validate(discrete_profile_payload())


# --- Semantic resolution --------------------------------------------------------------


def test_shutter_17_uses_profile_closed_value() -> None:
    profile = _profile()
    shutter = profile.discrete["shutter"]
    assert shutter.offset == 17

    closed = _compile(physical_shutter_state="closed")
    assert _events(closed, ChannelName.SHUTTER) == [(0, "closed")]
    assert resolve_discrete_state(shutter, "closed") == 64
    assert resolve_discrete_state(shutter, "open") == 8

    # The pulse form on channel 17 selects exactly the two declared bytes, never 0.
    pulse = _compile(
        physical_shutter_state=None,
        physical_shutter={
            "period_beats": 1.0,
            "duty_cycle": 0.5,
            "low_state": "closed",
            "high_state": "open",
        },
    )
    bytes_sent = [
        resolve_discrete_state(shutter, state) for _, state in _events(pulse, ChannelName.SHUTTER)
    ]
    assert bytes_sent == [8, 64, 8, 64]


def test_wheel_change_never_sweeps_intermediate_modes() -> None:
    profile = _profile()
    first = _compile(physical_color="white", physical_gobo="open")
    second = _compile(1000, physical_color="blue", physical_gobo="star")

    # One event per step: a step function, not a ramp through red or dots.
    assert _events(first, ChannelName.COLOR) == [(0, "white")]
    assert _events(second, ChannelName.COLOR) == [(1000, "blue")]
    assert _events(second, ChannelName.GOBO) == [(1000, "star")]
    color_bytes = {
        resolve_discrete_state(profile.discrete["color"], state)
        for segment in (first, second)
        for _, state in _events(segment, ChannelName.COLOR)
    }
    assert color_bytes == {0, 26}

    # A slice carries the selected state; it never interpolates one.
    assert _events(slice_physical_segment(second, 1500, 2000), ChannelName.COLOR) == [
        (1500, "blue")
    ]

    # What the transaction pass needs to mask and settle the change.
    assert wheel_changes([first, second], profile) == (
        WheelChange(
            fixture_id="MH1",
            channel=ChannelName.COLOR,
            t_ms=0,
            from_state=None,
            to_state="white",
            settle_ms=120,
        ),
        WheelChange(
            fixture_id="MH1",
            channel=ChannelName.GOBO,
            t_ms=0,
            from_state=None,
            to_state="open",
            settle_ms=150,
        ),
        WheelChange(
            fixture_id="MH1",
            channel=ChannelName.COLOR,
            t_ms=1000,
            from_state="white",
            to_state="blue",
            settle_ms=140,
        ),
        WheelChange(
            fixture_id="MH1",
            channel=ChannelName.GOBO,
            t_ms=1000,
            from_state="open",
            to_state="star",
            settle_ms=160,
        ),
    )


def test_unchanged_wheel_state_is_not_a_change() -> None:
    first = _compile(physical_color="red", physical_gobo=None)
    second = _compile(1000, physical_color="red", physical_gobo=None)
    unauthored = _compile(2000, physical_color=None, physical_gobo=None)
    third = _compile(3000, physical_color="red", physical_gobo=None)

    changes = wheel_changes([first, second, unauthored, third], _profile())

    # The unauthored segment emits the declared default byte, not a named state, so
    # the state before the next selection is unknown here.
    assert [(c.t_ms, c.from_state, c.to_state) for c in changes] == [
        (0, None, "red"),
        (3000, None, "red"),
    ]


def test_unknown_state_has_no_open_fallback() -> None:
    profile = _profile()

    for channel, field in (
        (ChannelName.SHUTTER, "physical_shutter_state"),
        (ChannelName.COLOR, "physical_color"),
        (ChannelName.GOBO, "physical_gobo"),
    ):
        with pytest.raises(PhysicalChannelError, match="'magenta'") as error:
            _compile(**{field: "magenta"})
        assert error.value.channel is channel

    with pytest.raises(ValueError, match="'strobe'") as raised:
        resolve_discrete_state(profile.discrete["shutter"], "strobe")
    assert "open" in str(raised.value)  # names the declared states, selects none
    with pytest.raises(ValueError, match="'Open'"):
        resolve_discrete_state(profile.discrete["gobo"], "Open")


def test_absent_required_capability_is_an_error() -> None:
    no_gobo = discrete_profile_payload()
    del no_gobo["discrete"]["gobo"]

    with pytest.raises(PhysicalChannelError, match="declares no gobo") as error:
        _compile(profile=no_gobo)
    assert error.value.channel is ChannelName.GOBO

    # Without a wheel request the same profile compiles.
    segment = _compile(profile=no_gobo, physical_gobo=None)
    assert ChannelName.GOBO not in segment.channels


def test_unrequested_discrete_channels_are_not_authored() -> None:
    segment = _compile(physical_shutter_state=None, physical_color=None, physical_gobo=None)

    assert set(segment.channels) == {ChannelName.PAN, ChannelName.TILT}


# --- Template contract ----------------------------------------------------------------


def test_static_and_pulsed_shutter_are_exclusive() -> None:
    payload = discrete_step_payload()
    payload["physical_shutter"] = physical_step_payload()["physical_shutter"]

    with pytest.raises(ValidationError, match="physical_shutter_state or physical_shutter"):
        TemplateStep.model_validate(payload)


@pytest.mark.parametrize("field", ["physical_shutter_state", "physical_color", "physical_gobo"])
def test_discrete_state_names_are_not_empty(field: str) -> None:
    with pytest.raises(ValidationError, match=rf"{field}\n  String should have at least 1"):
        TemplateStep.model_validate({**discrete_step_payload(), field: ""})


@pytest.mark.parametrize("field", ["physical_shutter_state", "physical_color", "physical_gobo"])
def test_legacy_compile_refuses_discrete_physical_data(field: str) -> None:
    legacy = TemplateStep.model_validate(
        {
            "step_id": "legacy",
            "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 1}},
            "geometry": {},
            "movement": {"movement_type": "sweep_lr"},
            "dimmer": {"dimmer_type": "hold"},
            field: "open",
        }
    )
    assert legacy.has_physical_data

    with pytest.raises(ValueError, match="physical_v2"):
        compile_step(legacy, _context())
    with pytest.raises(PhysicalCompileError, match=r"movement\.physical"):
        compile_physical_step(legacy, _context(), sample_times_ms=tuple(range(0, 1000, 20)))


def test_absent_discrete_fields_stay_out_of_template_dumps() -> None:
    legacy = TemplateStep.model_validate(
        {
            "step_id": "legacy",
            "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 1}},
            "geometry": {},
            "movement": {"movement_type": "sweep_lr"},
            "dimmer": {"dimmer_type": "hold"},
        }
    )

    dumped = legacy.model_dump(mode="json")
    assert not {"physical_shutter_state", "physical_color", "physical_gobo"} & dumped.keys()
    assert not legacy.has_physical_data


# --- Registry evidence for physical discrete template fields -------------------------

Component = Literal["compiled"]

_COMPONENT_NOTES: dict[Component, str] = {
    "compiled": "exact path changes the physical compile result",
}

_STEP_PREFIX = "template.template.steps."

_DISCRETE_MUTATIONS: dict[str, tuple[Component, Callable[[dict[str, Any]], Any]]] = {
    "physical_shutter_state": (
        "compiled",
        lambda s: s.update(physical_shutter_state="closed"),
    ),
    "physical_color": ("compiled", lambda s: s.update(physical_color="blue")),
    "physical_gobo": ("compiled", lambda s: s.update(physical_gobo="star")),
}
"""Per template path below the step: the one component its alternative must change."""

PHYSICAL_DISCRETE_PATHS = tuple(
    path
    for path, disposition in CONFIG_EFFECTS.items()
    if disposition.kind is ConfigDispositionKind.EFFECT_TEST
    and disposition.test_nodeid is not None
    and "::test_physical_discrete_field_changes_compile[" in disposition.test_nodeid
)


def _compile_snapshot(step_payload: dict[str, Any]) -> dict[str, Any]:
    try:
        step = TemplateStep.model_validate(step_payload)
        segment = compile_physical_step(step, _context(), sample_times_ms=tuple(range(0, 1000, 20)))
    except (ValidationError, PhysicalCompileError, PhysicalChannelError) as error:
        return {"rejected": f"{type(error).__name__}: {error}"}
    return {"compiled": segment.model_dump(mode="json")}


def test_physical_discrete_evidence_paths_cover_every_mutation() -> None:
    """The registry, its notes and the mutation table describe the same evidence."""
    expected = {f"{_STEP_PREFIX}{suffix}": c for suffix, (c, _) in _DISCRETE_MUTATIONS.items()}

    assert set(PHYSICAL_DISCRETE_PATHS) == set(expected)
    for path, component in expected.items():
        assert CONFIG_EFFECTS[path].note == _COMPONENT_NOTES[component], path


@pytest.mark.parametrize("config_path", PHYSICAL_DISCRETE_PATHS, ids=PHYSICAL_DISCRETE_PATHS)
def test_physical_discrete_field_changes_compile(config_path: str) -> None:
    """Each physical discrete template path changes the compiled segment."""
    _, mutate = _DISCRETE_MUTATIONS[config_path.removeprefix(_STEP_PREFIX)]
    payload = copy.deepcopy(discrete_step_payload())
    mutate(payload)

    base = _compile_snapshot(discrete_step_payload())
    changed = _compile_snapshot(payload)

    assert "rejected" not in base, base
    assert "rejected" not in changed, changed
    assert changed["compiled"] != base["compiled"]
