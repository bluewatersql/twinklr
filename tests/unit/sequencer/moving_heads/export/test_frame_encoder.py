"""Frame-accurate byte encoding for the opt-in physical moving-head path (P1.3).

Physical segments are sampled at every 20 ms frame start, composed into the complete
declared channel footprint, encoded to coarse/fine bytes without carry artifacts,
run-length merged only when every byte is identical, and serialized as constant DMX
effects. Output budgets fail; they never drop frames.
"""

from __future__ import annotations

import copy
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError
import pytest

from scripts.validation._core.mh_xsq_validation import parse_dmx_settings
from tests.support.mh_physical import physical_segment, profile_payload
from twinklr.core.config.fixtures.capabilities import FixtureCapabilities
from twinklr.core.config.models import MHRenderPolicy
from twinklr.core.formats.xlights.sequence.emission import EmissionSession
from twinklr.core.formats.xlights.sequence.exporter import XSQExporter
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS, build_fresh_sequence
from twinklr.core.formats.xlights.sequence.trace import MovingHeadEmissionTrace
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalChannelError,
    PhysicalPoint,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import DmxSettingsBuilder
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    CueTiming,
    EncodedFixtureFrame,
    FrameRun,
    PhysicalOutputError,
    check_output_budget,
    coalesce_frames,
    encode_fixture_frames,
    frame_times,
    measure_output,
    quantize_cue,
    quantized_cues,
)
from twinklr.core.sequencer.moving_heads.export.xsq_adapter import physical_run_requests

PAN = ChannelName.PAN
TILT = ChannelName.TILT
DIMMER = ChannelName.DIMMER
SHUTTER = ChannelName.SHUTTER
COLOR = ChannelName.COLOR


def _profile(payload: dict[str, Any] | None = None) -> FixtureCapabilities:
    return FixtureCapabilities.model_validate(payload or profile_payload())


def _word_axis_profile(*, inverted: bool = False) -> FixtureCapabilities:
    """Pan calibrated 0..65535 degrees, so a degree is exactly one 16-bit DMX step."""
    payload = profile_payload()
    payload["axes"]["pan"].update(physical_min=0.0, physical_max=65535.0, inverted=inverted)
    return _profile(payload)


def _hold(value: float, *, unit: str = "degree", t_ms: int = 0) -> ContinuousTrajectory:
    return ContinuousTrajectory.model_validate(
        {"unit": unit, "points": [{"t_ms": t_ms, "value": value}], "interpolation": "hold"}
    )


def _linear(*points: tuple[int, float]) -> ContinuousTrajectory:
    return ContinuousTrajectory(
        unit="degree",
        points=tuple(PhysicalPoint(t_ms=t, value=v) for t, v in points),
        interpolation="linear",
    )


def _states(*events: tuple[int, str]) -> DiscreteTrajectory:
    return DiscreteTrajectory(events=tuple(DiscretePoint(t_ms=t, state=s) for t, s in events))


def _bytes(frame: EncodedFixtureFrame) -> dict[int, int]:
    return dict(frame.channels)


def _word(frame: EncodedFixtureFrame, coarse: int, fine: int) -> int:
    channels = _bytes(frame)
    return (channels[coarse] << 8) | channels[fine]


def _grid(end_ms: int) -> tuple[int, ...]:
    return tuple(range(0, end_ms, EFFECT_GRID_MS))


# --- 16-bit and 8-bit encoding -------------------------------------------------------


@pytest.mark.parametrize("word", [255, 256, 257, 65535])
@pytest.mark.parametrize("inverted", [False, True], ids=["direct", "inverted"])
def test_coarse_fine_pairs_reconstruct_word_and_inverted_complement(
    word: int, inverted: bool
) -> None:
    capabilities = _word_axis_profile(inverted=inverted)
    segment = physical_segment({PAN: _hold(float(word))}, t0_ms=0, t1_ms=20)

    (frame,) = encode_fixture_frames([segment], capabilities, frame_times_ms=(0,))

    expected = 65535 - word if inverted else word
    assert _word(frame, 1, 2) == expected
    assert _bytes(frame)[1] == expected >> 8
    assert _bytes(frame)[2] == expected & 255


def test_sweep_across_coarse_carry_has_no_intermediate_glitch() -> None:
    """Each frame carries its own complete coarse/fine pair; no carry is interpolated."""
    capabilities = _word_axis_profile()
    segment = physical_segment({PAN: _linear((0, 250.0), (240, 262.0))}, t0_ms=0, t1_ms=240)

    frames = encode_fixture_frames([segment], capabilities, frame_times_ms=_grid(240))

    assert [_word(frame, 1, 2) for frame in frames] == list(range(250, 262))
    assert [_bytes(frame)[1] for frame in frames] == [0] * 6 + [1] * 6


def test_calibrated_sweep_is_monotonic_and_matches_the_profile_mapping() -> None:
    capabilities = _profile()
    pan = capabilities.axes["pan"]
    # About 0.03 degrees per frame crosses several coarse carries in 1 s.
    segment = physical_segment({PAN: _linear((0, -1.0), (1000, 0.5))}, t0_ms=0, t1_ms=1000)

    frames = encode_fixture_frames([segment], capabilities, frame_times_ms=_grid(1000))

    words = [_word(frame, 1, 2) for frame in frames]
    angles = [Fraction(-1) + Fraction(3, 2) * Fraction(frame.time_ms, 1000) for frame in frames]
    expected = [pan.dmx_word(float(angle)) for angle in angles]
    assert words == expected
    assert all(later > earlier for earlier, later in pairwise(words))
    assert len({word >> 8 for word in words}) > 1


def test_sampled_value_stays_exact_through_the_word_mapping() -> None:
    """At 20 ms the exact scaled word is 2.5, a tie that rounds up; a float rounds it down."""
    segment = physical_segment({PAN: _linear((0, -270.0), (4369, -265.5))}, t0_ms=0, t1_ms=40)

    frames = encode_fixture_frames([segment], _profile(), frame_times_ms=(0, 20))

    assert [_word(frame, 1, 2) for frame in frames] == [0, 3]


def test_downward_sweep_across_coarse_carry_has_no_intermediate_glitch() -> None:
    segment = physical_segment({PAN: _linear((0, 262.0), (240, 250.0))}, t0_ms=0, t1_ms=240)

    frames = encode_fixture_frames([segment], _word_axis_profile(), frame_times_ms=_grid(240))

    assert [_word(frame, 1, 2) for frame in frames] == list(range(262, 250, -1))


def test_inverted_sweep_across_coarse_carry_has_no_intermediate_glitch() -> None:
    segment = physical_segment({PAN: _linear((0, 250.0), (240, 262.0))}, t0_ms=0, t1_ms=240)

    frames = encode_fixture_frames(
        [segment], _word_axis_profile(inverted=True), frame_times_ms=_grid(240)
    )

    words = [_word(frame, 1, 2) for frame in frames]
    assert words == [65535 - word for word in range(250, 262)]
    assert [word >> 8 for word in words] == [255] * 6 + [254] * 6


@pytest.mark.parametrize(
    ("level", "direct", "inverted"),
    [(0.0, 0, 255), (0.5, 128, 127), (1.0, 255, 0)],
)
def test_eight_bit_endpoints_and_midpoint(level: float, direct: int, inverted: int) -> None:
    for is_inverted, expected in ((False, direct), (True, inverted)):
        payload = profile_payload()
        payload["axes"]["dimmer"]["inverted"] = is_inverted
        segment = physical_segment({DIMMER: _hold(level, unit="normalized")}, t0_ms=0, t1_ms=20)

        (frame,) = encode_fixture_frames([segment], _profile(payload), frame_times_ms=(0,))

        assert _bytes(frame)[5] == expected


def test_eight_bit_pan_has_no_fine_byte() -> None:
    payload = profile_payload()
    payload["axes"]["pan"]["fine_offset"] = None
    segment = physical_segment({PAN: _hold(270.0)}, t0_ms=0, t1_ms=20)

    (frame,) = encode_fixture_frames([segment], _profile(payload), frame_times_ms=(0,))

    assert _bytes(frame)[1] == 255
    assert _bytes(frame)[2] == payload["defaults"][2]


# --- Complete footprint --------------------------------------------------------------


def test_absent_authored_channels_receive_declared_defaults() -> None:
    capabilities = _profile()
    segment = physical_segment({PAN: _hold(0.0)}, t0_ms=20, t1_ms=40)

    frames = encode_fixture_frames([segment], capabilities, frame_times_ms=(0, 20, 40))

    defaults = capabilities.defaults
    for frame in frames:
        assert [offset for offset, _ in frame.channels] == list(range(1, 9))
    assert _bytes(frames[0]) == defaults
    assert _bytes(frames[2]) == defaults
    authored = _bytes(frames[1])
    assert _word(frames[1], 1, 2) == capabilities.axes["pan"].dmx_word(0.0)
    assert {k: v for k, v in authored.items() if k > 2} == {
        k: v for k, v in defaults.items() if k > 2
    }


def test_undefined_default_is_rejected() -> None:
    payload = profile_payload()
    del payload["defaults"][8]
    with pytest.raises(ValidationError, match=r"missing defaults for offsets \[8\]"):
        _profile(payload)

    incomplete = _profile().model_copy(update={"defaults": dict.fromkeys(range(1, 8), 0)})
    segment = physical_segment({PAN: _hold(0.0)}, t0_ms=0, t1_ms=20)
    with pytest.raises(ValueError, match=r"no default byte for offsets \[8\]"):
        encode_fixture_frames([segment], incomplete, frame_times_ms=(0,))


def test_footprint_beyond_the_backend_is_a_typed_error() -> None:
    oversized = _profile().model_copy(update={"footprint": 49})
    segment = physical_segment({PAN: _hold(0.0)}, t0_ms=0, t1_ms=20)

    with pytest.raises(PhysicalOutputError) as excinfo:
        encode_fixture_frames([segment], oversized, frame_times_ms=(0,))

    assert excinfo.value.diagnostic.code == "unsupported_backend_channel"


def test_discrete_states_emit_their_declared_bytes() -> None:
    segment = physical_segment(
        {SHUTTER: _states((0, "closed"), (40, "open")), COLOR: _states((0, "red"))},
        t0_ms=0,
        t1_ms=80,
    )

    frames = encode_fixture_frames([segment], _profile(), frame_times_ms=_grid(80))

    assert [_bytes(frame)[6] for frame in frames] == [64, 64, 8, 8]
    assert {_bytes(frame)[7] for frame in frames} == {14}


def test_segments_for_different_channels_compose_into_one_frame() -> None:
    pan = physical_segment({PAN: _hold(0.0)}, t0_ms=0, t1_ms=40, segment_id="pan")
    shutter = physical_segment({SHUTTER: _states((0, "open"))}, t0_ms=0, t1_ms=40, segment_id="s")

    frames = encode_fixture_frames([pan, shutter], _profile(), frame_times_ms=(0, 20))

    for frame in frames:
        assert _bytes(frame)[6] == 8
        assert _word(frame, 1, 2) == _profile().axes["pan"].dmx_word(0.0)


# --- Conflicts and rejected input ----------------------------------------------------


def test_equal_priority_overlap_on_one_attribute_fails() -> None:
    first = physical_segment({PAN: _hold(0.0)}, t0_ms=0, t1_ms=60, segment_id="a")
    second = physical_segment({PAN: _hold(10.0, t_ms=40)}, t0_ms=40, t1_ms=100, segment_id="b")

    with pytest.raises(PhysicalChannelError) as excinfo:
        encode_fixture_frames([first, second], _profile(), frame_times_ms=_grid(100))

    assert excinfo.value.channel is PAN
    assert excinfo.value.time_ms == 40


def test_adjacent_half_open_segments_do_not_conflict() -> None:
    first = physical_segment({PAN: _hold(0.0)}, t0_ms=0, t1_ms=40, segment_id="a")
    second = physical_segment({PAN: _hold(10.0, t_ms=40)}, t0_ms=40, t1_ms=80, segment_id="b")

    frames = encode_fixture_frames([first, second], _profile(), frame_times_ms=_grid(80))

    pan = _profile().axes["pan"]
    assert [_word(frame, 1, 2) for frame in frames] == [pan.dmx_word(0.0)] * 2 + [
        pan.dmx_word(10.0)
    ] * 2


def test_legacy_value_is_refused_by_the_physical_encoder() -> None:
    segment = FixtureSegment(
        section_id="s",
        segment_id="seg",
        step_id="step",
        template_id="t",
        fixture_id="MH1",
        t0_ms=0,
        t1_ms=20,
        channels={PAN: ChannelValue(channel=PAN, static_dmx=100)},
    )

    with pytest.raises(PhysicalChannelError, match="not a physical value"):
        encode_fixture_frames([segment], _profile(), frame_times_ms=(0,))


@pytest.mark.parametrize(
    ("channels", "match"),
    [
        pytest.param({PAN: _hold(300.0)}, "operable range", id="out-of-range"),
        pytest.param({SHUTTER: _states((0, "strobe"))}, "not declared", id="unknown-state"),
        pytest.param({PAN: _hold(0.0, t_ms=40)}, "before its first point", id="before-first"),
    ],
)
def test_unencodable_physical_values_fail(channels: dict[ChannelName, Any], match: str) -> None:
    segment = physical_segment(channels, t0_ms=0, t1_ms=60)

    with pytest.raises(PhysicalChannelError, match=match):
        encode_fixture_frames([segment], _profile(), frame_times_ms=_grid(60))


def test_frame_times_must_lie_on_the_effect_grid() -> None:
    segment = physical_segment({PAN: _hold(0.0)}, t0_ms=0, t1_ms=60)

    for times in ((0, 30), (20, 0), (0, 0)):
        with pytest.raises(ValueError, match="frame times"):
            encode_fixture_frames([segment], _profile(), frame_times_ms=times)


def test_segments_must_belong_to_one_fixture() -> None:
    first = physical_segment({PAN: _hold(0.0)}, t0_ms=0, t1_ms=20)
    other = physical_segment({TILT: _hold(0.0)}, t0_ms=0, t1_ms=20, fixture_id="MH2")

    with pytest.raises(ValueError, match="one fixture"):
        encode_fixture_frames([first, other], _profile(), frame_times_ms=(0,))


# --- Cue quantization and sequence tail ----------------------------------------------


@pytest.mark.parametrize(
    ("requested", "actual"),
    [(0, 0), (9, 0), (10, 20), (29, 20), (30, 40), (1015, 1020)],
)
def test_cue_quantization_is_nearest_grid_ties_later(requested: int, actual: int) -> None:
    cue = quantize_cue(requested)

    assert (cue.requested_ms, cue.actual_ms) == (requested, actual)
    assert abs(cue.actual_ms - cue.requested_ms) <= EFFECT_GRID_MS // 2
    assert cue.actual_ms == EmissionSession.quantize_interval(requested, requested + 20)[0]


def test_segment_bounds_and_discrete_cues_are_quantized_once() -> None:
    payload = profile_payload()
    payload["discrete"]["shutter"]["states"]["strobe"] = {
        "range_min": 128,
        "range_max": 191,
        "value": 160,
    }
    segment = physical_segment({SHUTTER: _states((5, "open"), (49, "strobe"))}, t0_ms=5, t1_ms=85)

    frames = encode_fixture_frames([segment], _profile(payload), frame_times_ms=_grid(120))

    # Segment [5, 85) samples frames [0, 80); the 49 ms cue lands on 40, not 60; the
    # frames after it take the closed default byte 64.
    assert [_bytes(frame)[6] for frame in frames] == [8, 8, 160, 160, 64, 64]


def test_quantized_cues_report_requested_and_actual_times() -> None:
    segment = physical_segment(
        {SHUTTER: _states((0, "closed"), (45, "open")), COLOR: _states((30, "red"))},
        t0_ms=5,
        t1_ms=100,
    )

    cues = quantized_cues([segment])

    assert cues == (
        CueTiming("MH1", "seg", None, "segment_start", 5, 0),
        CueTiming("MH1", "seg", None, "segment_end", 100, 100),
        CueTiming("MH1", "seg", SHUTTER, "cue", 0, 0),
        CueTiming("MH1", "seg", SHUTTER, "cue", 45, 40),
        CueTiming("MH1", "seg", COLOR, "cue", 30, 40),
    )


def test_discrete_cue_at_or_past_the_segment_end_fails() -> None:
    """[0, 49) samples frames [0, 40); an open landing on 40 would never emit."""
    segment = physical_segment({SHUTTER: _states((0, "closed"), (45, "open"))}, t0_ms=0, t1_ms=49)

    with pytest.raises(PhysicalChannelError, match="at or after the segment's end"):
        encode_fixture_frames([segment], _profile(), frame_times_ms=_grid(100))


def test_hold_point_past_the_segment_end_fails() -> None:
    segment = physical_segment(
        {
            PAN: ContinuousTrajectory.model_validate(
                {
                    "unit": "degree",
                    "points": [{"t_ms": 0, "value": 0.0}, {"t_ms": 60, "value": 5.0}],
                    "interpolation": "hold",
                }
            )
        },
        t0_ms=0,
        t1_ms=60,
    )

    with pytest.raises(PhysicalChannelError, match="at or after the segment's end"):
        encode_fixture_frames([segment], _profile(), frame_times_ms=_grid(100))


def test_segment_outside_every_frame_fails() -> None:
    segment = physical_segment({PAN: _hold(0.0, t_ms=500)}, t0_ms=500, t1_ms=1000)

    with pytest.raises(ValueError, match="samples no frame"):
        encode_fixture_frames([segment], _profile(), frame_times_ms=(0, 20))


def test_empty_frame_times_fail() -> None:
    segment = physical_segment({PAN: _hold(0.0)}, t0_ms=0, t1_ms=20)

    with pytest.raises(ValueError, match="frame times"):
        encode_fixture_frames([segment], _profile(), frame_times_ms=())


def test_cues_collapsing_onto_one_frame_fail() -> None:
    segment = physical_segment({SHUTTER: _states((20, "closed"), (25, "open"))}, t0_ms=0, t1_ms=60)

    with pytest.raises(PhysicalChannelError, match="same frame"):
        encode_fixture_frames([segment], _profile(), frame_times_ms=_grid(60))


def test_segment_quantized_to_zero_length_fails() -> None:
    segment = physical_segment({PAN: _hold(0.0, t_ms=0)}, t0_ms=0, t1_ms=5)

    with pytest.raises(ValueError, match="zero-length"):
        encode_fixture_frames([segment], _profile(), frame_times_ms=_grid(40))


def test_tail_frames_cover_every_start_below_duration() -> None:
    assert frame_times(1000) == _grid(1000)
    assert frame_times(1010)[-1] == 1000
    assert frame_times(1) == (0,)

    segment = physical_segment({PAN: _hold(0.0)}, t0_ms=0, t1_ms=1010)
    runs = coalesce_frames(
        encode_fixture_frames([segment], _profile(), frame_times_ms=frame_times(1010))
    )

    # The final frame's interval ends on the next grid boundary, past the duration.
    assert [(run.start_ms, run.end_ms) for run in runs] == [(0, 1020)]


# --- Run-length merging and serialization --------------------------------------------


def _frame(time_ms: int, *channels: tuple[int, int]) -> EncodedFixtureFrame:
    return EncodedFixtureFrame(time_ms=time_ms, fixture_id="MH1", channels=channels)


def test_identical_adjacent_frames_merge_and_any_byte_change_splits() -> None:
    a = ((1, 10), (2, 20))
    b = ((1, 10), (2, 21))

    runs = coalesce_frames([_frame(0, *a), _frame(20, *a), _frame(40, *b), _frame(60, *a)])

    assert [(run.start_ms, run.end_ms, run.frame.channels) for run in runs] == [
        (0, 40, a),
        (40, 60, b),
        (60, 80, a),
    ]


@pytest.mark.parametrize("times", [(10, 30), (-20, 0)], ids=["off-grid", "negative"])
def test_coalescing_enforces_the_frame_grid(times: tuple[int, int]) -> None:
    with pytest.raises(ValueError, match="grid"):
        coalesce_frames([_frame(t, (1, 0)) for t in times])


def test_runs_do_not_bridge_a_gap_between_frames() -> None:
    a = ((1, 10),)

    runs = coalesce_frames([_frame(0, *a), _frame(40, *a)])

    assert [(run.start_ms, run.end_ms) for run in runs] == [(0, 20), (40, 60)]


def _settings_bytes(settings: str) -> dict[int, int]:
    """Decode a DMX effect string as xLights does: an absent channel is zero."""
    pairs = dict(part.split("=", 1) for part in settings.split(","))
    return {channel: int(pairs.get(f"E_SLIDER_DMX{channel}", "0")) for channel in range(1, 49)}


def _wide_profile() -> FixtureCapabilities:
    """A 48-channel profile: shutter on 17, color on 48, a distinct default per channel."""
    payload = copy.deepcopy(profile_payload())
    payload["footprint"] = 48
    payload["defaults"] = {offset: offset for offset in range(1, 49)}
    payload["discrete"]["shutter"]["offset"] = 17
    payload["discrete"]["color"]["offset"] = 48
    # Discrete defaults are their default states' bytes: closed 64, white 0.
    payload["defaults"].update({17: 64, 48: 0})
    return _profile(payload)


def test_channels_17_and_48_emit_and_settings_round_trip() -> None:
    segment = physical_segment(
        {SHUTTER: _states((0, "open")), COLOR: _states((0, "red")), PAN: _hold(90.0)},
        t0_ms=0,
        t1_ms=20,
    )
    (frame,) = encode_fixture_frames([segment], _wide_profile(), frame_times_ms=(0,))

    settings = DmxSettingsBuilder.build_frame_settings(frame)

    assert _bytes(frame)[17] == 8
    assert _bytes(frame)[48] == 14
    assert _settings_bytes(settings) == _bytes(frame)
    assert parse_dmx_settings(settings) == (_bytes(frame), {})
    keys = [part.split("=", 1)[0] for part in settings.split(",")]
    assert [k for k in keys if k.startswith("E_SLIDER_DMX")] == [
        f"E_SLIDER_DMX{n}" for n in range(1, 49)
    ]
    assert {part for part in settings.split(",") if part.startswith("E_CHECKBOX_INVDMX")} == {
        f"E_CHECKBOX_INVDMX{n}=0" for n in range(1, 49)
    }
    assert "E_VALUECURVE" not in settings


@pytest.mark.parametrize(
    "channels",
    [((1, 0), (3, 0)), ((0, 1),), ((1, 0), (1, 0)), tuple((n, 0) for n in range(1, 50))],
    ids=["gap", "offset-zero", "duplicate", "offset-49"],
)
def test_settings_refuse_an_incomplete_or_unaddressable_frame(
    channels: tuple[tuple[int, int], ...],
) -> None:
    with pytest.raises(PhysicalOutputError) as excinfo:
        DmxSettingsBuilder.build_frame_settings(_frame(0, *channels))

    assert excinfo.value.diagnostic.code == "unsupported_backend_channel"


def test_settings_refuse_a_value_that_is_not_a_byte() -> None:
    with pytest.raises(ValueError, match="not a DMX byte"):
        DmxSettingsBuilder.build_frame_settings(_frame(0, (1, 256)))


# --- Emission ------------------------------------------------------------------------


def _show_segments() -> list[FixtureSegment]:
    return [
        physical_segment(
            {
                PAN: _linear((0, -10.0), (200, 10.0)),
                DIMMER: _hold(1.0, unit="normalized"),
                SHUTTER: _states((0, "open"), (100, "closed")),
            },
            t0_ms=0,
            t1_ms=200,
        )
    ]


def _show(tmp_path: Path) -> tuple[tuple[EncodedFixtureFrame, ...], tuple[FrameRun, ...], bytes]:
    segments = _show_segments()
    frames = encode_fixture_frames(segments, _profile(), frame_times_ms=frame_times(300))
    runs = coalesce_frames(frames)
    sequence = build_fresh_sequence(media_file="song.mp3", duration_ms=300)
    EmissionSession(sequence).emit_batch(physical_run_requests(runs, segments, {"MH1": "Dmx MH1"}))
    path = tmp_path / "physical.xsq"
    XSQExporter().export(sequence, path)
    return frames, runs, path.read_bytes()


def _expand(runs: tuple[FrameRun, ...]) -> list[tuple[int, tuple[tuple[int, int], ...]]]:
    return [
        (time_ms, run.frame.channels)
        for run in runs
        for time_ms in range(run.start_ms, run.end_ms, EFFECT_GRID_MS)
    ]


def test_aligned_runs_pass_through_emission_unchanged() -> None:
    segments = _show_segments()
    runs = coalesce_frames(
        encode_fixture_frames(segments, _profile(), frame_times_ms=frame_times(300))
    )
    sequence = build_fresh_sequence(media_file="song.mp3", duration_ms=300)

    records = EmissionSession(sequence).emit_batch(
        physical_run_requests(runs, segments, {"MH1": "Dmx MH1"})
    )

    assert [(r.start_ms, r.end_ms) for r in records] == [(r.start_ms, r.end_ms) for r in runs]
    assert {r.target for r in records} == {"Dmx MH1"}
    assert [r.settings for r in records] == [
        DmxSettingsBuilder.build_frame_settings(run.frame) for run in runs
    ]
    # Runs inside the segment name it; the trailing default-only run names none.
    assert records[0].trace.get("sources") == [
        {"fixture_id": "MH1", "segment_id": "seg", "step_id": "step"}
    ]
    assert records[-1].trace.get("sources") == []
    assert sequence.head.sequence_duration_ms == 300


def test_run_sources_are_every_overlapping_segment_earliest_first() -> None:
    """A long early segment still overlaps late runs; the earliest source represents."""
    long_dimmer = physical_segment(
        {DIMMER: _hold(1.0, unit="normalized")}, t0_ms=0, t1_ms=200, segment_id="z_long"
    )
    pans = [
        physical_segment(
            {PAN: _hold(float(i), t_ms=i * 40)},
            t0_ms=i * 40,
            t1_ms=(i + 1) * 40,
            segment_id=f"a_pan{i}",
        )
        for i in range(1, 5)
    ]
    segments = [*pans, long_dimmer]
    runs = coalesce_frames(encode_fixture_frames(segments, _profile(), frame_times_ms=_grid(200)))

    requests = physical_run_requests(runs, segments, {"MH1": "Dmx MH1"})

    assert [r.start_ms for r in requests] == [0, 40, 80, 120, 160]
    for i, request in enumerate(requests):
        trace = cast("MovingHeadEmissionTrace", request.trace)
        expected = ["z_long"] + ([f"a_pan{i}"] if i else [])
        assert [s["segment_id"] for s in trace["sources"]] == expected
        assert request.label == long_dimmer.metatag


def test_misaligned_or_unmapped_run_is_refused() -> None:
    frame = _frame(10, (1, 0))
    with pytest.raises(ValueError, match="frame-aligned"):
        physical_run_requests([FrameRun(frame=frame, end_ms=30)], [], {"MH1": "Dmx MH1"})

    aligned = FrameRun(frame=_frame(0, (1, 0)), end_ms=20)
    with pytest.raises(ValueError, match="no xLights model"):
        physical_run_requests([aligned], [], {})


# --- Output budgets ------------------------------------------------------------------


def test_default_budgets_accept_and_report_the_actual_measure(tmp_path: Path) -> None:
    frames, runs, serialized = _show(tmp_path)

    measure = measure_output(runs, serialized)
    check_output_budget(measure, MHRenderPolicy())

    assert measure.effect_count == len(runs) > 1
    assert measure.xsq_bytes == len(serialized)
    assert _expand(runs) == [(frame.time_ms, frame.channels) for frame in frames]


BUDGET_PATHS = ("job.moving_heads.max_effects", "job.moving_heads.max_xsq_bytes")


@pytest.mark.parametrize("config_path", BUDGET_PATHS, ids=BUDGET_PATHS)
def test_budget_field_changes_accept_reject(config_path: str, tmp_path: Path) -> None:
    """A limit at the measured output accepts it; one below rejects it, dropping nothing."""
    frames, runs, serialized = _show(tmp_path)
    measure = measure_output(runs, serialized)
    field = config_path.rsplit(".", 1)[1]
    actual = measure.effect_count if field == "max_effects" else measure.xsq_bytes

    check_output_budget(measure, MHRenderPolicy.model_validate({field: actual}))
    with pytest.raises(PhysicalOutputError) as excinfo:
        check_output_budget(measure, MHRenderPolicy.model_validate({field: actual - 1}))

    assert excinfo.value.diagnostic.code == "output_budget_exceeded"
    assert excinfo.value.diagnostic.severity == "error"
    assert excinfo.value.measure == measure
    assert _expand(runs) == [(frame.time_ms, frame.channels) for frame in frames]


def test_budget_defaults() -> None:
    policy = MHRenderPolicy()

    assert (policy.max_effects, policy.max_xsq_bytes) == (1_000_000, 134_217_728)


@pytest.mark.parametrize("field", ["max_effects", "max_xsq_bytes"])
def test_budgets_are_positive_and_stay_out_of_default_dumps(field: str) -> None:
    with pytest.raises(ValidationError):
        MHRenderPolicy.model_validate({field: 0})

    assert field not in MHRenderPolicy().model_dump()
    assert MHRenderPolicy.model_validate({field: 7}).model_dump()[field] == 7
