"""Physical steps from off-grid musical bounds through compile, preposition, frame
encoding and emission."""

from __future__ import annotations

from typing import Any

from tests.support.mh_physical import (
    assert_honest_transactions,
    discrete_profile_payload,
    discrete_step_payload,
)
from twinklr.core.config.fixtures import FixtureCapabilities, InitialFixtureState
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.context import StepCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import ContinuousTrajectory
from twinklr.core.sequencer.models.template import TemplateStep
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import compile_physical_step
from twinklr.core.sequencer.moving_heads.compile.preposition import plan_prepositions
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    coalesce_frames,
    encode_fixture_frames,
    frame_times,
    quantize_cue,
)
from twinklr.core.sequencer.moving_heads.export.xsq_adapter import physical_run_requests
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map, musical_phase_at

# Variable tempo with every beat off the 20 ms grid; the step spans beats 2 to 4.
_BEATS = [15.0, 545.0, 1015.0, 1550.0, 2085.0, 2600.0, 3115.0, 3650.0]
_GRID = BeatGrid(
    bar_boundaries=[15.0, 2085.0],
    beat_boundaries=_BEATS,
    eighth_boundaries=BeatGrid._calculate_eighth_boundaries(_BEATS),
    sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(_BEATS),
    tempo_bpm=115.0,
    beats_per_bar=4,
    duration_ms=4000.0,
)
_PAN_EXTENT = 90.0
_PERIOD_BEATS = 2.0


def _context(
    profile: FixtureCapabilities, t0: int, t1: int, section_id: str = "verse"
) -> StepCompileContext:
    registries = create_default_registries()
    return StepCompileContext(
        section_id=section_id,
        segment_id=section_id,
        template_id="physical_probe",
        fixture_id="MH1",
        role="OUTER_LEFT",
        calibration={},
        start_ms=t0,
        duration_ms=t1 - t0,
        beat_grid=_GRID,
        curve_registry=CurveRegistry(),
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
        physical_profile=profile,
        phase_map=build_musical_phase_map(_GRID),
    )


def test_off_grid_step_compiles_encodes_and_emits_on_the_frame_grid() -> None:
    profile = FixtureCapabilities.model_validate(discrete_profile_payload())
    phase_map = build_musical_phase_map(_GRID)
    # The caller quantizes the musical bounds with the encoder's policy, then compiles.
    t0 = quantize_cue(1015).actual_ms
    t1 = quantize_cue(2085).actual_ms
    assert (t0, t1) == (1020, 2080)

    context = _context(profile, t0, t1)
    step = TemplateStep.model_validate(
        {
            **discrete_step_payload(),
            "movement": {
                "physical": {
                    "shape": "linear",
                    "mode": "finite",
                    "start_pan_deg": 0.0,
                    "start_tilt_deg": 0.0,
                    "pan_extent_deg": _PAN_EXTENT,
                    "period_beats": _PERIOD_BEATS,
                }
            },
            "dimmer": {
                "physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}
            },
            "physical_shutter_state": "open",
            "physical_color": "red",
            "physical_gobo": None,
        }
    )
    segment = compile_physical_step(step, context, sample_times_ms=tuple(range(t0, t1, 20)))

    def kernel_pan(time_ms: int) -> float:
        phase = musical_phase_at(phase_map, time_ms, origin_ms=t0, period_beats=_PERIOD_BEATS)
        return _PAN_EXTENT * min(phase, 1.0)

    pan = segment.channels[ChannelName.PAN].physical
    assert isinstance(pan, ContinuousTrajectory)
    assert (pan.points[-1].t_ms, pan.points[-1].value) == (t1, kernel_pan(t1))

    times = frame_times(2200)
    frames = encode_fixture_frames([segment], profile, frame_times_ms=times)
    runs = coalesce_frames(frames)
    requests = physical_run_requests(runs, [segment], {"MH1": "Head 1"})

    assert len(requests) == len(runs)
    assert all(request.effect == "DMX" for request in requests)
    footprint = list(range(1, profile.footprint + 1))
    assert all([offset for offset, _ in frame.channels] == footprint for frame in frames)

    by_time = {frame.time_ms: dict(frame.channels) for frame in frames}
    pan_axis = profile.axes["pan"]
    shutter = profile.discrete["shutter"]
    color = profile.discrete["color"]
    # The last frame before t1 is the kernel's value there.
    last = by_time[t1 - 20]
    word = pan_axis.dmx_word(kernel_pan(t1 - 20))
    assert (last[1], last[2]) == (word >> 8, word & 0xFF)
    # Channel 17 carries the declared closed byte outside the step and open inside it.
    assert {by_time[t][17] for t in times if t0 <= t < t1} == {shutter.resolve("open")} == {8}
    assert {by_time[t][17] for t in times if not t0 <= t < t1} == {shutter.resolve("closed")}
    assert shutter.resolve("closed") == 64
    # The color wheel selects red's declared byte, not a range bound or a neighbor.
    assert {by_time[t][color.offset] for t in times if t0 <= t < t1} == {14}
    # The dimmer pulse is high at the step start and changes on frames inside it.
    assert by_time[t0][5] == 255
    assert {by_time[t][5] for t in times if t0 <= t < t1} == {0, 255}


def test_two_cues_compile_preposition_and_encode_dark_between_them() -> None:
    """A lit hold, a dark reposition planned between, then a lit hold 90° away."""
    payload = discrete_profile_payload()
    for axis in ("pan", "tilt"):
        payload["axes"][axis].update(latency_ms=0, settle_ms=40)
    profile = FixtureCapabilities.model_validate(payload)
    initial = InitialFixtureState(
        pan_deg=0.0,
        tilt_deg=0.0,
        dimmer=0.0,
        discrete_states={"shutter": "closed", "color": "white", "gobo": "open"},
        settled=True,
        dark=True,
    )

    def cue(name: str, start_ms: int, end_ms: int, pan: float) -> FixtureSegment:
        t0, t1 = quantize_cue(start_ms).actual_ms, quantize_cue(end_ms).actual_ms
        step: dict[str, Any] = {
            **discrete_step_payload(),
            "movement": {
                "physical": {
                    "shape": "hold",
                    "mode": "periodic",
                    "start_pan_deg": pan,
                    "start_tilt_deg": 0.0,
                }
            },
            "dimmer": {
                "physical": {"period_beats": 1.0, "duty_cycle": 1.0, "low": 0.0, "high": 1.0}
            },
        }
        return compile_physical_step(
            TemplateStep.model_validate(step),
            _context(profile, t0, t1, section_id=name),
            sample_times_ms=tuple(range(t0, t1, 20)),
        )

    cues = [cue("verse", 1015, 1550, 0.0), cue("chorus", 2600, 3115, 90.0)]
    result = plan_prepositions(
        cues,
        {"MH1": profile},
        initial_states={"MH1": initial},
        locks=(),
        frame_ms=20,
        sequence_end_ms=3120,
    )

    assert [(d.cue_ms, d.status) for d in result.diagnostics] == [
        (1020, "feasible"),
        (2600, "feasible"),
    ]
    # 90° at 720°/s is 125 ms, rounded up to 140, plus 40 ms of settle.
    assert result.diagnostics[1].required_ms == 180
    assert_honest_transactions(result, cues, profile, initial)

    frames = {
        frame.time_ms: dict(frame.channels)
        for frame in encode_fixture_frames(
            result.segments, profile, frame_times_ms=frame_times(3120)
        )
    }
    shutter = profile.discrete["shutter"]
    # Channel 17 closes between the cues on its declared byte and opens on each cue frame.
    gap = range(cues[0].t1_ms, cues[1].t0_ms, 20)
    assert (cues[0].t1_ms, cues[1].t0_ms) == (1560, 2600)
    assert {frames[t][17] for t in gap} == {shutter.resolve("closed")}
    assert (frames[2580][17], frames[2600][17]) == (64, shutter.resolve("open"))
    assert (frames[1000][17], frames[1020][17]) == (64, 8)
    pan_word = profile.axes["pan"].dmx_word(90.0)
    assert (frames[2600][1] << 8 | frames[2600][2]) == pan_word
