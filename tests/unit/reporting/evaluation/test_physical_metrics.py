"""Physical-output metrics of `eval-report` (P3-C1.1b), against hand-computed values.

A tiny synthetic render: one head's physical segments encoded by the renderer's own
frame encoder, then read back by the report. Pan moves linearly from 0° to 90° over one
second, tilt holds 30°, the dimmer holds 0.5 and the shutter opens at 0 ms and closes at
500 ms. The 50 frames start at 0, 20, ..., 980 ms.
"""

from __future__ import annotations

import math

import pytest

from tests.support.mh_physical import (
    physical_segment,
    profile_payload,
    zoom_pilot_profile_payload,
)
from twinklr.core.config.fixtures import FixtureCapabilities
from twinklr.core.reporting.evaluation.analyze import (
    largest_step,
    lit_motion,
    physical_channel_stats,
)
from twinklr.core.reporting.evaluation.extract import physical_channel_values
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalPoint,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    encode_fixture_frames,
    frame_times,
)

# Pan: 0.09°/ms at frame t, so 1.8° per 20 ms frame; 16-bit over 540° decodes within 0.009°.
PAN = [0.09 * t for t in range(0, 1000, 20)]
DIMMER_ON = 128 / 255  # 0.5 encodes to byte 128 (half up) and decodes to 128/255


def _profile(*, inverted: bool) -> FixtureCapabilities:
    payload = profile_payload()
    for axis in ("pan", "tilt"):
        payload["axes"][axis]["inverted"] = inverted
    return FixtureCapabilities.model_validate(payload)


def _frames(profile: FixtureCapabilities):
    segment = physical_segment(
        {
            ChannelName.PAN: ContinuousTrajectory(
                unit="degree",
                points=(PhysicalPoint(t_ms=0, value=0.0), PhysicalPoint(t_ms=1000, value=90.0)),
                interpolation="linear",
            ),
            ChannelName.TILT: ContinuousTrajectory(
                unit="degree", points=(PhysicalPoint(t_ms=0, value=30.0),), interpolation="hold"
            ),
            ChannelName.DIMMER: ContinuousTrajectory(
                unit="normalized",
                points=(PhysicalPoint(t_ms=0, value=0.5),),
                interpolation="hold",
            ),
            ChannelName.SHUTTER: DiscreteTrajectory(
                events=(
                    DiscretePoint(t_ms=0, state="open"),
                    DiscretePoint(t_ms=500, state="closed"),
                )
            ),
        },
        t0_ms=0,
        t1_ms=1000,
    )
    return encode_fixture_frames([segment], profile, frame_times_ms=frame_times(1000))


@pytest.mark.parametrize("inverted", [False, True], ids=["upright", "inverted"])
def test_frames_read_back_as_physical_values(inverted: bool) -> None:
    """Pan and tilt are read in degrees from the encoded words, inversion undone; the
    dimmer row is the emitted intensity: the dimmer's value, 0 where the shutter is in
    an extinguishing state."""
    profile = _profile(inverted=inverted)
    values = physical_channel_values(_frames(profile), {"MH1": profile}, (0, 1000))

    assert values.keys() == {"MH1"}
    channels = values["MH1"]
    assert channels.keys() == {"pan", "tilt", "dimmer"}
    assert channels["pan"] == pytest.approx(PAN, abs=0.01)
    assert channels["tilt"] == pytest.approx([30.0] * 50, abs=0.01)
    assert channels["dimmer"] == pytest.approx([DIMMER_ON] * 25 + [0.0] * 25, abs=1e-12)


def test_window_keeps_only_the_frames_starting_inside_it() -> None:
    profile = _profile(inverted=False)
    values = physical_channel_values(_frames(profile), {"MH1": profile}, (400, 600))

    assert values["MH1"]["pan"] == pytest.approx(PAN[20:30], abs=0.01)  # 400-580 ms: 36°-52.2°
    assert values["MH1"]["dimmer"] == pytest.approx([DIMMER_ON] * 5 + [0.0] * 5, abs=1e-12)


def test_physical_stats_hand_computed() -> None:
    """Statistics are in the channel's unit; `energy` is the mean rate of change per
    second over the 20 ms frames."""
    profile = _profile(inverted=False)
    channels = physical_channel_values(_frames(profile), {"MH1": profile}, (0, 1000))["MH1"]

    pan = physical_channel_stats(channels["pan"], frame_ms=20)
    # t = 20k for k = 0..49: mean 490 ms, population std 20 * sqrt((50^2 - 1) / 12) ms.
    assert pan.min == pytest.approx(0.0, abs=0.01)
    assert pan.max == pytest.approx(88.2, abs=0.01)
    assert pan.range == pytest.approx(88.2, abs=0.02)
    assert pan.mean == pytest.approx(44.1, abs=0.01)
    assert pan.std == pytest.approx(0.09 * 20 * math.sqrt((50**2 - 1) / 12), abs=0.01)
    assert pan.energy == pytest.approx(90.0, abs=0.01)  # 1.8° per frame = 90°/s

    tilt = physical_channel_stats(channels["tilt"], frame_ms=20)
    assert (tilt.range, tilt.std, tilt.energy) == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    assert tilt.mean == pytest.approx(30.0, abs=0.01)

    dimmer = physical_channel_stats(channels["dimmer"], frame_ms=20)
    assert dimmer.min == 0.0
    assert dimmer.max == pytest.approx(DIMMER_ON)
    assert dimmer.mean == pytest.approx(DIMMER_ON / 2)  # lit half the frames
    assert dimmer.std == pytest.approx(DIMMER_ON / 2)
    # One change of 128/255 across 49 frame steps, per second (50 frames).
    assert dimmer.energy == pytest.approx(DIMMER_ON / 49 * 50)


def test_lit_motion_counts_only_lit_frames() -> None:
    """Pan sweeps 0°-88.2° but is lit only in the first 25 frames (0-480 ms): lit, it
    spans 0°-43.2° at 1.8° per frame. Repositioning dark is left out."""
    profile = _profile(inverted=False)
    channels = physical_channel_values(_frames(profile), {"MH1": profile}, (0, 1000))["MH1"]

    lit_range, lit_rate = lit_motion(channels["pan"], channels["dimmer"], frame_ms=20)
    assert lit_range == pytest.approx(43.2, abs=0.01)
    # 43.2° over 24 lit steps of 20 ms; each end within half a 16-bit word (0.004°).
    assert lit_rate == pytest.approx(90.0, abs=0.02)
    assert lit_motion(channels["pan"], [0.0] * 50, frame_ms=20) is None


def test_lit_rate_leaves_out_steps_into_or_out_of_the_dark() -> None:
    """Lit 0°, 1°, 2°, then dark while moving to 20°, then lit at 21°: the lit range is
    0°-21°, the lit rate the two 1° steps between lit frames, 50°/s."""
    values = [0.0, 1.0, 2.0, 10.0, 20.0, 21.0]
    intensity = [1.0, 1.0, 1.0, 0.0, 0.0, 1.0]

    assert lit_motion(values, intensity, frame_ms=20) == (21.0, 50.0)


def test_largest_step_with_its_time() -> None:
    """Steps between frames 100, 120, ... ms; with `lit`, only between two lit frames."""
    values = [0.0, 1.0, 5.0, 5.0, 20.0, 21.0]
    intensity = [1.0, 1.0, 1.0, 0.0, 1.0, 1.0]

    assert largest_step(values, start_ms=100, frame_ms=20, lit=intensity) == (4.0, 120, 140)
    assert largest_step(values, start_ms=100, frame_ms=20) == (15.0, 160, 180)
    assert largest_step([3.0, 2.0, -6.0], start_ms=0, frame_ms=20) == (-8.0, 20, 40)
    assert largest_step([3.0], start_ms=0, frame_ms=20) is None
    assert largest_step(values, start_ms=0, frame_ms=20, lit=[0.0] * 6) is None


def test_zoom_is_read_in_degrees_where_the_profile_declares_it() -> None:
    """The zoom pilot's 8-bit zoom maps 10°-40° over bytes 20-220: 25° is byte 120."""
    profile = FixtureCapabilities.model_validate(zoom_pilot_profile_payload())
    segment = physical_segment(
        {
            ChannelName.ZOOM: ContinuousTrajectory(
                unit="degree", points=(PhysicalPoint(t_ms=0, value=25.0),), interpolation="hold"
            )
        },
        t0_ms=0,
        t1_ms=100,
    )
    frames = encode_fixture_frames([segment], profile, frame_times_ms=frame_times(100))

    channels = physical_channel_values(frames, {"MH1": profile}, (0, 100))["MH1"]
    assert channels["zoom"] == [25.0] * 5
    assert (
        "zoom"
        not in physical_channel_values(
            _frames(_profile(inverted=False)), {"MH1": _profile(inverted=False)}, (0, 100)
        )["MH1"]
    )
