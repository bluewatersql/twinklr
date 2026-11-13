"""Physical step compilation: explicit template data to typed trajectories on musical phase."""

from __future__ import annotations

from collections.abc import Callable
import copy
import math
from typing import Any, Literal

from pydantic import ValidationError
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from tests.support.mh_physical import motion_profile_payload, physical_step_payload
from twinklr.core.config.fixtures import FixtureCapabilities
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.context import StepCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscreteTrajectory,
    PhysicalChannelError,
)
from twinklr.core.sequencer.models.template import PhysicalMovementSpec, TemplateStep
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import (
    OffGridTimeError,
    PhysicalCompileError,
    compile_physical_step,
    slice_physical_segment,
)
from twinklr.core.sequencer.moving_heads.compile.step_compiler import compile_step
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

_TEMPO_GRID = BeatGrid.from_tempo(tempo_bpm=120, total_bars=2)
_FAST_GRID = BeatGrid.from_tempo(tempo_bpm=150, total_bars=2)
"""A 400 ms beat, so quarter periods fall on 20 ms frames."""
_VARIABLE_GRID = BeatGrid(
    bar_boundaries=[0.0],
    beat_boundaries=[0.0, 500.0, 1000.0, 2000.0],
    eighth_boundaries=BeatGrid._calculate_eighth_boundaries([0.0, 500.0, 1000.0, 2000.0]),
    sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries([0.0, 500.0, 1000.0, 2000.0]),
    tempo_bpm=90.0,
    beats_per_bar=4,
    duration_ms=2000.0,
)
_FRAMES = tuple(range(0, 1000, 20))


def _frames(duration_ms: int, *extra: int) -> tuple[int, ...]:
    return tuple(sorted({*range(0, duration_ms, 20), *extra}))


def _context(
    *,
    duration_ms: int = 1000,
    grid: BeatGrid = _TEMPO_GRID,
    profile: dict[str, Any] | None = None,
    with_profile: bool = True,
) -> StepCompileContext:
    registries = create_default_registries()
    return StepCompileContext(
        section_id="verse",
        segment_id="A",
        template_id="physical_probe",
        fixture_id="MH1",
        role="OUTER_LEFT",
        calibration={},
        start_ms=0,
        duration_ms=duration_ms,
        beat_grid=grid,
        curve_registry=CurveRegistry(),
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
        physical_profile=(
            FixtureCapabilities.model_validate(profile or motion_profile_payload())
            if with_profile
            else None
        ),
        phase_map=build_musical_phase_map(grid),
    )


def _step(**updates: Any) -> TemplateStep:
    payload = physical_step_payload()
    for path, value in updates.items():
        target = payload
        *parents, leaf = path.split("__")
        for key in parents:
            target = target[key]
        if value is _DELETE:
            target.pop(leaf)
        else:
            target[leaf] = value
    return TemplateStep.model_validate(payload)


_DELETE = object()


def _values(segment: FixtureSegment, channel: ChannelName) -> dict[int, float]:
    physical = segment.channels[channel].physical
    assert isinstance(physical, ContinuousTrajectory)
    return {point.t_ms: point.value for point in physical.points}


def _states(segment: FixtureSegment, times: tuple[int, ...]) -> dict[int, str]:
    physical = segment.channels[ChannelName.SHUTTER].physical
    assert isinstance(physical, DiscreteTrajectory)
    return {t: [event.state for event in physical.events if event.t_ms <= t][-1] for t in times}


def _sine(shape: str, **values: float) -> dict[str, Any]:
    return {
        "shape": shape,
        "mode": "periodic",
        "start_pan_deg": 0.0,
        "start_tilt_deg": 0.0,
        "period_beats": 1.0,
        **values,
    }


# --- Movement kernels ---------------------------------------------------------------


def test_finite_linear_ends_at_its_final_value_and_holds() -> None:
    segment = compile_physical_step(_step(), _context(), sample_times_ms=_FRAMES)

    pan = _values(segment, ChannelName.PAN)
    tilt = _values(segment, ChannelName.TILT)
    assert pan[0] == 10.0 and tilt[0] == 20.0
    assert pan[240] == pytest.approx(24.4) and tilt[240] == pytest.approx(24.8)
    assert {pan[t] for t in _FRAMES if t >= 500} == {40.0}
    assert {tilt[t] for t in _FRAMES if t >= 500} == {30.0}
    assert segment.channels[ChannelName.PAN].physical.interpolation == "linear"  # type: ignore[union-attr]


def test_finite_path_stores_its_exact_terminal_value() -> None:
    linear = {
        "shape": "linear",
        "mode": "finite",
        "start_pan_deg": 0.0,
        "start_tilt_deg": 0.0,
        "pan_extent_deg": 90.0,
        "period_beats": 2.0,
    }

    # The period fills the step: the last frame starts at 980 ms, the path ends at 90.
    filled = compile_physical_step(
        _step(movement__physical=linear), _context(), sample_times_ms=_FRAMES
    )
    pan = _values(filled, ChannelName.PAN)
    assert max(pan) == 1000
    assert pan[980] == pytest.approx(88.2)
    assert pan[1000] == 90.0

    # A shorter period holds the final value through the terminal point.
    held = compile_physical_step(_step(), _context(), sample_times_ms=_FRAMES)
    assert _values(held, ChannelName.PAN)[1000] == 40.0
    assert _values(held, ChannelName.TILT)[1000] == 30.0


def test_periodic_terminal_value_is_the_kernel_at_the_step_end() -> None:
    sine = _sine("sine_pan", pan_extent_deg=30, period_beats=0.75)
    segment = compile_physical_step(
        _step(movement__physical=sine), _context(), sample_times_ms=_FRAMES
    )

    pan = _values(segment, ChannelName.PAN)
    assert max(pan) == 1000
    assert pan[1000] == pytest.approx(30 * math.sin(2 * math.pi * 1000 / 375))


def test_single_sample_cannot_hide_motion() -> None:
    unknown = motion_profile_payload()
    del unknown["axes"]["pan"]["travel_speed_per_s"]

    with pytest.raises(PhysicalChannelError, match="unknown travel speed"):
        compile_physical_step(
            _step(), _context(duration_ms=20, profile=unknown), sample_times_ms=(0,)
        )


@pytest.mark.parametrize("shape", ["hold", "sine_pan", "sine_tilt", "linear"])
def test_each_kernel_shapes_the_compiled_path(shape: str) -> None:
    movement: dict[str, Any] = {
        "hold": {"shape": "hold", "mode": "periodic", "start_pan_deg": 5, "start_tilt_deg": 6},
        "sine_pan": _sine("sine_pan", start_pan_deg=5, start_tilt_deg=6, pan_extent_deg=30),
        "sine_tilt": _sine("sine_tilt", start_pan_deg=5, start_tilt_deg=6, tilt_extent_deg=30),
        "linear": {
            "shape": "linear",
            "mode": "finite",
            "start_pan_deg": 5,
            "start_tilt_deg": 6,
            "pan_extent_deg": 30,
            "tilt_extent_deg": -30,
            "period_beats": 1,
        },
    }[shape]
    times = (0, 100, 200, 300, 400)
    segment = compile_physical_step(
        _step(movement__physical=movement),
        _context(grid=_FAST_GRID),
        sample_times_ms=_FRAMES,
    )
    pan = [_values(segment, ChannelName.PAN)[t] for t in times]
    tilt = [_values(segment, ChannelName.TILT)[t] for t in times]

    expected = {
        "hold": ([5, 5, 5, 5, 5], [6, 6, 6, 6, 6]),
        "sine_pan": ([5, 35, 5, -25, 5], [6, 6, 6, 6, 6]),
        "sine_tilt": ([5, 5, 5, 5, 5], [6, 36, 6, -24, 6]),
        "linear": ([5, 12.5, 20, 27.5, 35], [6, -1.5, -9, -16.5, -24]),
    }[shape]
    assert pan == pytest.approx(expected[0], abs=1e-9)
    assert tilt == pytest.approx(expected[1], abs=1e-9)


def test_reach_and_rate_are_independent() -> None:
    times = (0, 100, 200, 300, 400, 500, 600, 700)
    context = _context(grid=_FAST_GRID)

    def pan(**values: float) -> list[float]:
        step = _step(movement__physical=_sine("sine_pan", **values))
        segment = compile_physical_step(step, context, sample_times_ms=_FRAMES)
        return [_values(segment, ChannelName.PAN)[t] for t in times]

    base = pan(pan_extent_deg=20)
    wider = pan(pan_extent_deg=40)
    slower = pan(pan_extent_deg=20, period_beats=2)

    # Reach scales amplitude only: same zero crossings and peak times.
    assert wider == pytest.approx([2 * v for v in base], abs=1e-9)
    # Rate changes timing only: the slower path reaches the same peak, later.
    assert max(base) == pytest.approx(20) and max(slower) == pytest.approx(20)
    assert base.index(max(base)) == 1 and slower.index(max(slower)) == 2


@pytest.mark.parametrize(
    ("movement", "match"),
    [
        ({"shape": "linear", "mode": "periodic", "period_beats": 1}, "periodic linear"),
        ({"shape": "sine_pan", "mode": "finite", "period_beats": 1}, "finite sine"),
        ({"shape": "sine_pan", "mode": "periodic", "tilt_extent_deg": 5}, "period_beats|other"),
        (
            {"shape": "sine_tilt", "mode": "periodic", "pan_extent_deg": 5, "period_beats": 1},
            "other extent",
        ),
        ({"shape": "hold", "mode": "finite", "pan_extent_deg": 5}, "hold"),
        ({"shape": "linear", "mode": "finite"}, "period_beats"),
    ],
)
def test_unsupported_kernel_variants_are_rejected(movement: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        PhysicalMovementSpec.model_validate({"start_pan_deg": 0, "start_tilt_deg": 0, **movement})


# --- Bounds and travel rate -------------------------------------------------------


def test_axis_bounds_reject_instead_of_clamping() -> None:
    step = _step(movement__physical__start_pan_deg=250.0)  # 250 + 30 exceeds 270

    with pytest.raises(PhysicalChannelError, match="outside the operable range") as error:
        compile_physical_step(step, _context(), sample_times_ms=_FRAMES)
    assert error.value.channel is ChannelName.PAN

    narrowed = motion_profile_payload()
    narrowed["axes"]["tilt"]["allowed_max"] = 25.0
    with pytest.raises(PhysicalChannelError) as error:
        compile_physical_step(_step(), _context(profile=narrowed), sample_times_ms=_FRAMES)
    assert error.value.channel is ChannelName.TILT


def test_travel_rate_is_validated_against_configured_speed() -> None:
    slow = motion_profile_payload()
    slow["axes"]["pan"]["travel_speed_per_s"] = 59.0  # the path needs 60 deg/s

    with pytest.raises(PhysicalChannelError, match="speed") as error:
        compile_physical_step(_step(), _context(profile=slow), sample_times_ms=_FRAMES)
    assert error.value.channel is ChannelName.PAN

    exact = motion_profile_payload()
    exact["axes"]["pan"]["travel_speed_per_s"] = 60.0
    compile_physical_step(_step(), _context(profile=exact), sample_times_ms=_FRAMES)


def test_unknown_speed_rejects_motion_but_not_a_hold() -> None:
    unknown = motion_profile_payload()
    del unknown["axes"]["tilt"]["travel_speed_per_s"]

    with pytest.raises(PhysicalChannelError, match="unknown travel speed") as error:
        compile_physical_step(_step(), _context(profile=unknown), sample_times_ms=_FRAMES)
    assert error.value.channel is ChannelName.TILT

    hold = {"shape": "hold", "mode": "periodic", "start_pan_deg": 0, "start_tilt_deg": 0}
    compile_physical_step(
        _step(movement__physical=hold), _context(profile=unknown), sample_times_ms=_FRAMES
    )


# --- Legacy steps under physical compile ---------------------------------------------


def test_legacy_normalized_circle_cannot_enter_physical_compile() -> None:
    circle = TemplateStep.model_validate(
        {
            "step_id": "circle",
            "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 1}},
            "geometry": {"geometry_type": "fan"},
            "movement": {"movement_type": "circle", "cycles": 1.0},
            "dimmer": {"dimmer_type": "hold"},
        }
    )

    with pytest.raises(PhysicalCompileError, match="migrat") as error:
        compile_physical_step(circle, _context(), sample_times_ms=_FRAMES)
    assert error.value.diagnostic.code == "unsupported_attribute"
    assert error.value.diagnostic.action == "rejected"
    assert error.value.diagnostic.fixture_id == "MH1"


@pytest.mark.parametrize(
    "legacy",
    [
        {"movement__movement_type": "circle"},
        {"geometry__geometry_type": "fan"},
        {"dimmer__dimmer_type": "pulse"},
        {"shutter": {"pattern": "open"}},
        {"color": {"preset": "red"}},
        {"gobo": {"pattern": "open"}},
        {"timing__phase_offset": {"mode": "GROUP_ORDER", "spread_bars": 0.25}},
        {"movement__cycles": 2.0},
        {"movement__intensity": "FAST"},
        {"movement__params": {"amplitude": 0.5}},
        {"dimmer__min_norm": 0.2},
        {"dimmer__max_norm": 0.8},
        {"dimmer__intensity": "INTENSE"},
        {"dimmer__params": {"period_bars": 0.5}},
        {"geometry__tilt_pose": "ceiling"},
    ],
)
def test_legacy_data_beside_physical_data_is_rejected(legacy: dict[str, Any]) -> None:
    with pytest.raises(PhysicalCompileError) as error:
        compile_physical_step(_step(**legacy), _context(), sample_times_ms=_FRAMES)
    assert error.value.diagnostic.code == "unsupported_attribute"


def test_legacy_fields_at_their_defaults_do_not_reject_a_physical_step() -> None:
    """A preset round trip sets every legacy field explicitly, at its default."""
    step = _step()
    round_tripped = TemplateStep.model_validate(
        {
            **step.model_dump(),
            "movement": step.movement.model_dump(exclude_unset=False),
            "dimmer": step.dimmer.model_dump(exclude_unset=False),
            "geometry": step.geometry.model_dump(exclude_unset=False),
        }
    )
    assert "cycles" in round_tripped.movement.model_fields_set

    compile_physical_step(round_tripped, _context(), sample_times_ms=_FRAMES)


def test_fixture_without_physical_profile_is_rejected() -> None:
    with pytest.raises(PhysicalCompileError, match="physical_profile"):
        compile_physical_step(_step(), _context(with_profile=False), sample_times_ms=_FRAMES)


def test_legacy_compile_refuses_a_physical_step() -> None:
    with pytest.raises(ValueError, match="physical_v2"):
        compile_step(_step(), _context())


def test_absent_physical_fields_stay_out_of_template_dumps() -> None:
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
    assert "physical" not in dumped["movement"]
    assert "physical" not in dumped["dimmer"]
    assert "physical_shutter" not in dumped
    assert not legacy.has_physical_data


@pytest.mark.parametrize(
    ("times", "match"),
    [
        ((), "at least one"),
        ((20, 40), "start"),
        ((0, 40, 20), "increasing"),
        ((0, 1000), "inside"),
        ((0, 40), "frame"),
        (tuple(range(0, 960, 20)), "frame"),
    ],
)
def test_sample_times_must_cover_the_step_from_its_start(
    times: tuple[int, ...], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        compile_physical_step(_step(), _context(), sample_times_ms=times)


@pytest.mark.parametrize(
    ("start_ms", "duration_ms", "extra", "name", "value"),
    [
        (15, 1000, (), "step start", 15),
        (0, 1005, (), "step end", 1005),
        (0, 1000, (250,), "sample time", 250),
    ],
)
def test_off_grid_step_bounds_and_samples_are_rejected(
    start_ms: int, duration_ms: int, extra: tuple[int, ...], name: str, value: int
) -> None:
    """The frame grid is the only source of sample times; callers quantize bounds first."""
    context = _context(duration_ms=duration_ms).model_copy(update={"start_ms": start_ms})
    times = tuple(sorted({*range(start_ms, start_ms + duration_ms, 20), *extra}))

    with pytest.raises(OffGridTimeError, match=f"{name} {value} ms") as error:
        compile_physical_step(_step(), context, sample_times_ms=times)
    assert (error.value.name, error.value.time_ms) == (name, value)


# --- Pulses on variable tempo ----------------------------------------------------------


_BEAT_TIMES = (0, 240, 260, 500, 740, 760, 1000, 1260, 1480, 1500)
"""Frames around each half beat (250, 750 and the long third beat's 1500)."""


def test_variable_tempo_dimmer_pulse_follows_musical_phase() -> None:
    hold = {"shape": "hold", "mode": "periodic", "start_pan_deg": 0, "start_tilt_deg": 0}
    step = _step(movement__physical=hold, physical_shutter=_DELETE)
    context = _context(duration_ms=2000, grid=_VARIABLE_GRID)

    segment = compile_physical_step(step, context, sample_times_ms=_frames(2000))
    dimmer = {t: _values(segment, ChannelName.DIMMER)[t] for t in _BEAT_TIMES}

    # High at each beat onset, low from the first frame of each half beat; the third
    # beat is 1000 ms long, so its half falls exactly at 1500 ms, not at 1250 ms as an
    # average tempo would say.
    assert dimmer == {
        0: 1.0,
        240: 1.0,
        260: 0.0,
        500: 1.0,
        740: 1.0,
        760: 0.0,
        1000: 1.0,
        1260: 1.0,
        1480: 1.0,
        1500: 0.0,
    }
    assert segment.channels[ChannelName.DIMMER].physical.interpolation == "hold"  # type: ignore[union-attr]

    # Each value depends only on its time: a shorter step from the same origin agrees.
    shorter = _values(
        compile_physical_step(
            step, _context(duration_ms=1000, grid=_VARIABLE_GRID), sample_times_ms=_FRAMES
        ),
        ChannelName.DIMMER,
    )
    assert {t: shorter[t] for t in _BEAT_TIMES if t < 1000} == {
        t: v for t, v in dimmer.items() if t < 1000
    }


def test_variable_tempo_shutter_pulse_follows_musical_phase() -> None:
    hold = {"shape": "hold", "mode": "periodic", "start_pan_deg": 0, "start_tilt_deg": 0}
    step = _step(
        movement__physical=hold,
        dimmer__physical=_DELETE,
        physical_shutter={
            "period_beats": 1,
            "duty_cycle": 0.5,
            "low_state": "closed",
            "high_state": "open",
        },
    )
    context = _context(duration_ms=2000, grid=_VARIABLE_GRID)

    segment = compile_physical_step(step, context, sample_times_ms=_frames(2000))
    states = _states(segment, _BEAT_TIMES)
    assert states == {
        0: "open",
        240: "open",
        260: "closed",
        500: "open",
        740: "open",
        760: "closed",
        1000: "open",
        1260: "open",
        1480: "open",
        1500: "closed",
    }

    shorter = compile_physical_step(
        step, _context(duration_ms=1000, grid=_VARIABLE_GRID), sample_times_ms=_FRAMES
    )
    early = tuple(t for t in _BEAT_TIMES if t < 1000)
    assert _states(shorter, early) == {t: states[t] for t in early}


_HOLD = {"shape": "hold", "mode": "periodic", "start_pan_deg": 0, "start_tilt_deg": 0}
_NARROW = {"period_beats": 0.25, "duty_cycle": 0.1}  # 12.5 ms high every 125 ms at 120 BPM


def test_dimmer_pulse_narrower_than_a_frame_is_rejected() -> None:
    step = _step(
        movement__physical=_HOLD,
        physical_shutter=_DELETE,
        dimmer__physical={**_NARROW, "low": 0.0, "high": 1.0},
    )

    with pytest.raises(PhysicalChannelError, match=r"12\.5 ms") as error:
        compile_physical_step(step, _context(), sample_times_ms=_FRAMES)
    assert error.value.channel is ChannelName.DIMMER


def test_shutter_pulse_narrower_than_a_frame_is_rejected() -> None:
    step = _step(
        movement__physical=_HOLD,
        dimmer__physical=_DELETE,
        physical_shutter={**_NARROW, "low_state": "closed", "high_state": "open"},
    )

    with pytest.raises(PhysicalChannelError, match=r"12\.5 ms") as error:
        compile_physical_step(step, _context(), sample_times_ms=_FRAMES)
    assert error.value.channel is ChannelName.SHUTTER


def test_narrow_low_interval_is_rejected_and_truncated_ends_are_exempt() -> None:
    def dimmer(**pulse: float) -> TemplateStep:
        return _step(
            movement__physical=_HOLD,
            physical_shutter=_DELETE,
            dimmer__physical={"period_beats": 1.0, "low": 0.0, "high": 1.0, **pulse},
        )

    with pytest.raises(PhysicalChannelError, match=r"15 ms"):
        compile_physical_step(dimmer(duty_cycle=0.97), _context(), sample_times_ms=_FRAMES)

    # The step opens 10 ms before the end of a high interval and closes 10 ms into a
    # low one; both truncated intervals are shorter than a frame.
    shifted = dimmer(duty_cycle=0.5, phase_cycles=0.48)
    segment = compile_physical_step(
        shifted, _context(duration_ms=1020), sample_times_ms=_frames(1020)
    )
    assert _values(segment, ChannelName.DIMMER)[0] == 1.0


@pytest.mark.parametrize("period", [1e-310, 1e-3])
def test_absurdly_short_periods_are_rejected_by_the_model(period: float) -> None:
    with pytest.raises(ValidationError, match="period_beats"):
        TemplateStep.model_validate(
            {
                **physical_step_payload(),
                "dimmer": {
                    "physical": {"period_beats": period, "duty_cycle": 0.5, "low": 0, "high": 1}
                },
            }
        )
    with pytest.raises(ValidationError, match="period_beats"):
        PhysicalMovementSpec.model_validate(
            _sine("sine_pan", pan_extent_deg=10, period_beats=period)
        )


def test_pulse_decision_is_exact_at_a_shifted_half_beat() -> None:
    """Phase 0.84 at 420 ms shifted by -0.34 is exactly 1/2, so a 0.5 duty is low.

    In floats the sum is 0.49999999999999994, which would read as high.
    """
    step = _step(
        movement__physical=_HOLD,
        physical_shutter=_DELETE,
        dimmer__physical={
            "period_beats": 1.0,
            "duty_cycle": 0.5,
            "phase_cycles": -0.34,
            "low": 0.0,
            "high": 1.0,
        },
    )
    context = _context(duration_ms=2000, grid=_VARIABLE_GRID)

    segment = compile_physical_step(step, context, sample_times_ms=_frames(2000))
    dimmer = _values(segment, ChannelName.DIMMER)
    assert (dimmer[400], dimmer[420], dimmer[700]) == (1.0, 0.0, 1.0)


def test_unresolved_shutter_latency_rejects_a_pulse_schedule() -> None:
    unknown = motion_profile_payload()
    unknown["visibility"]["close_latency_ms"] = None

    with pytest.raises(PhysicalChannelError, match="latency") as error:
        compile_physical_step(_step(), _context(profile=unknown), sample_times_ms=_FRAMES)
    assert error.value.channel is ChannelName.SHUTTER

    unsettled = motion_profile_payload()
    del unsettled["discrete"]["shutter"]["states"]["closed"]["settle_ms"]
    with pytest.raises(PhysicalChannelError, match="settle"):
        compile_physical_step(_step(), _context(profile=unsettled), sample_times_ms=_FRAMES)


def test_shutter_pulse_faster_than_latency_is_rejected() -> None:
    step = _step(physical_shutter__period_beats=1.0)  # open again for 250 ms from 500 ms
    slow = motion_profile_payload()
    slow["visibility"]["open_latency_ms"] = 300

    with pytest.raises(PhysicalChannelError, match="needs 300 ms") as error:
        compile_physical_step(step, _context(profile=slow), sample_times_ms=_FRAMES)
    assert error.value.time_ms == 500

    slow["visibility"]["open_latency_ms"] = 250
    compile_physical_step(step, _context(profile=slow), sample_times_ms=_FRAMES)


def test_pulse_state_must_be_declared_by_the_profile() -> None:
    step = _step(physical_shutter__high_state="strobe")

    with pytest.raises(PhysicalChannelError, match="strobe"):
        compile_physical_step(step, _context(), sample_times_ms=_FRAMES)


# --- Slicing --------------------------------------------------------------------------


def test_slice_interpolates_boundaries_and_carries_discrete_state() -> None:
    segment = compile_physical_step(_step(), _context(), sample_times_ms=_FRAMES)

    sliced = slice_physical_segment(segment, 310, 710)

    assert (sliced.t0_ms, sliced.t1_ms) == (310, 710)
    pan = _values(sliced, ChannelName.PAN)
    assert min(pan) == 310 and max(pan) == 710
    assert pan[310] == pytest.approx(28.6)
    assert pan[400] == pytest.approx(34.0)
    assert pan[710] == 40.0
    dimmer = _values(sliced, ChannelName.DIMMER)
    assert (dimmer[310], dimmer[500], dimmer[700]) == (0.0, 1.0, 1.0)
    shutter = sliced.channels[ChannelName.SHUTTER].physical
    assert isinstance(shutter, DiscreteTrajectory)
    assert [(e.t_ms, e.state) for e in shutter.events] == [(310, "open"), (500, "closed")]

    # The original phase origin and provenance survive; the motion does not restart.
    assert sliced.metadata == segment.metadata
    assert sliced.metadata["phase_origin_ms"] == "0"
    assert (sliced.section_id, sliced.step_id, sliced.template_id) == (
        segment.section_id,
        segment.step_id,
        segment.template_id,
    )


def test_slice_to_the_step_end_keeps_the_terminal_point() -> None:
    linear = {
        "shape": "linear",
        "mode": "finite",
        "start_pan_deg": 0.0,
        "start_tilt_deg": 0.0,
        "pan_extent_deg": 90.0,
        "period_beats": 2.0,
    }
    segment = compile_physical_step(
        _step(movement__physical=linear), _context(), sample_times_ms=_FRAMES
    )

    tail = slice_physical_segment(segment, 990, 1000)
    assert _values(tail, ChannelName.PAN) == pytest.approx({990: 89.1, 1000: 90.0})


def test_slice_bounds_must_lie_inside_the_segment() -> None:
    segment = compile_physical_step(_step(), _context(), sample_times_ms=_FRAMES)

    with pytest.raises(ValueError):
        slice_physical_segment(segment, 500, 500)
    with pytest.raises(ValueError):
        slice_physical_segment(segment, 500, 1001)


# --- Registry evidence for physical-only template fields -----------------------------

Component = Literal["rejected", "compiled"]

_COMPONENT_NOTES: dict[Component, str] = {
    "rejected": "exact path's alternative is rejected by physical validation or compile",
    "compiled": "exact path changes the physical compile result",
}

_STEP_PREFIX = "template.template.steps."

_TEMPLATE_MUTATIONS: dict[str, tuple[Component, Callable[[dict[str, Any]], Any]]] = {
    "movement.physical": ("rejected", lambda s: s["movement"].pop("physical")),
    "movement.physical.mode": (
        "rejected",
        lambda s: s["movement"]["physical"].update(mode="periodic"),
    ),
    "movement.physical.start_pan_deg": (
        "compiled",
        lambda s: s["movement"]["physical"].update(start_pan_deg=15.0),
    ),
    "movement.physical.start_tilt_deg": (
        "compiled",
        lambda s: s["movement"]["physical"].update(start_tilt_deg=25.0),
    ),
    "movement.physical.pan_extent_deg": (
        "compiled",
        lambda s: s["movement"]["physical"].update(pan_extent_deg=40.0),
    ),
    "movement.physical.tilt_extent_deg": (
        "compiled",
        lambda s: s["movement"]["physical"].update(tilt_extent_deg=5.0),
    ),
    "movement.physical.period_beats": (
        "compiled",
        lambda s: s["movement"]["physical"].update(period_beats=2.0),
    ),
    "dimmer.physical": ("compiled", lambda s: s["dimmer"].pop("physical")),
    "dimmer.physical.period_beats": (
        "compiled",
        lambda s: s["dimmer"]["physical"].update(period_beats=0.5),
    ),
    "dimmer.physical.duty_cycle": (
        "compiled",
        lambda s: s["dimmer"]["physical"].update(duty_cycle=0.25),
    ),
    "dimmer.physical.phase_cycles": (
        "compiled",
        lambda s: s["dimmer"]["physical"].update(phase_cycles=0.25),
    ),
    "dimmer.physical.low": ("compiled", lambda s: s["dimmer"]["physical"].update(low=0.2)),
    "dimmer.physical.high": ("compiled", lambda s: s["dimmer"]["physical"].update(high=0.8)),
    "physical_shutter": ("compiled", lambda s: s.pop("physical_shutter")),
    "physical_shutter.period_beats": (
        "compiled",
        lambda s: s["physical_shutter"].update(period_beats=1.0),
    ),
    "physical_shutter.duty_cycle": (
        "compiled",
        lambda s: s["physical_shutter"].update(duty_cycle=0.75),
    ),
    "physical_shutter.phase_cycles": (
        "compiled",
        lambda s: s["physical_shutter"].update(phase_cycles=0.5),
    ),
    "physical_shutter.low_state": (
        "compiled",
        lambda s: s["physical_shutter"].update(low_state="open"),
    ),
    "physical_shutter.high_state": (
        "compiled",
        lambda s: s["physical_shutter"].update(high_state="closed"),
    ),
}
"""Per template path below the step: the one component its alternative must change."""

_SHAPE_PATH = f"{_STEP_PREFIX}movement.physical.shape"
_SHAPE_NOTE = "each kernel shapes the compiled path"
"""`shape` is coupled to `mode`, extents and period, so no single-field alternative
is valid; its evidence is the kernel test, which fails if the compiler ignored it."""

PHYSICAL_TEMPLATE_PATHS = tuple(
    path
    for path, disposition in CONFIG_EFFECTS.items()
    if disposition.kind is ConfigDispositionKind.EFFECT_TEST
    and disposition.test_nodeid is not None
    and "::test_physical_template_field_changes_compile[" in disposition.test_nodeid
)


def _compile_snapshot(step_payload: dict[str, Any]) -> dict[str, Any]:
    try:
        step = TemplateStep.model_validate(step_payload)
        segment = compile_physical_step(step, _context(), sample_times_ms=_FRAMES)
    except (ValidationError, PhysicalCompileError, PhysicalChannelError) as error:
        return {"rejected": f"{type(error).__name__}: {error}"}
    return {"compiled": segment.model_dump(mode="json")}


def test_physical_template_evidence_paths_cover_every_mutation() -> None:
    """The registry, its notes and the mutation table describe the same evidence."""
    expected = {f"{_STEP_PREFIX}{suffix}": c for suffix, (c, _) in _TEMPLATE_MUTATIONS.items()}

    assert set(PHYSICAL_TEMPLATE_PATHS) == set(expected)
    for path, component in expected.items():
        assert CONFIG_EFFECTS[path].note == _COMPONENT_NOTES[component], path
    assert CONFIG_EFFECTS[_SHAPE_PATH].note == _SHAPE_NOTE
    assert CONFIG_EFFECTS[_SHAPE_PATH].test_nodeid.endswith(  # type: ignore[union-attr]
        "::test_each_kernel_shapes_the_compiled_path[sine_tilt]"
    )


@pytest.mark.parametrize("config_path", PHYSICAL_TEMPLATE_PATHS, ids=PHYSICAL_TEMPLATE_PATHS)
def test_physical_template_field_changes_compile(config_path: str) -> None:
    """Each physical template path changes the one compile component its note names."""
    component, mutate = _TEMPLATE_MUTATIONS[config_path.removeprefix(_STEP_PREFIX)]
    payload = copy.deepcopy(physical_step_payload())
    mutate(payload)

    base = _compile_snapshot(physical_step_payload())
    changed = _compile_snapshot(payload)

    assert "rejected" not in base, base
    if component == "rejected":
        assert "rejected" in changed, changed
    else:
        assert "rejected" not in changed, changed
        assert changed["compiled"] != base["compiled"]
