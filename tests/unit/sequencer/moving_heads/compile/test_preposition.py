"""Dark reposition transactions between physical cues: extinguish, move, settle, reveal.

Every feasible plan below is encoded and checked from its bytes
(`assert_honest_transactions`): frames that move pan/tilt or a wheel inside a
transaction are dark by the profile's declaration and stay dark through travel and
settle, locked frames keep the input's bytes, and a lit cue reveals on its own frame.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.support.mh_physical import (
    assert_honest_transactions,
    physical_segment,
    preposition_profile_payload,
)
from twinklr.core.config.fixtures import FixtureCapabilities, InitialFixtureState
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalPoint,
    RenderLock,
    TransitionDiagnostic,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    FALLBACK_METADATA_KEY,
    TRANSACTION_METADATA_KEY,
    FailureMode,
    PrepositionResult,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    encode_fixture_frames,
    frame_times,
)

_PAN, _TILT, _DIMMER = ChannelName.PAN, ChannelName.TILT, ChannelName.DIMMER
_SHUTTER, _COLOR = ChannelName.SHUTTER, ChannelName.COLOR
_SLOW_PAN = {"travel_speed_per_s": 90.0, "settle_ms": 40}
"""90°/s with a 40 ms settle: a 90° move needs 1000 + 40 ms."""


def _profile(
    *,
    pan: dict[str, Any] | None = None,
    tilt: dict[str, Any] | None = None,
    visibility: dict[str, Any] | None = None,
    edit: Callable[[dict[str, Any]], None] | None = None,
) -> FixtureCapabilities:
    payload = preposition_profile_payload()
    payload["axes"]["pan"].update(pan or {})
    payload["axes"]["tilt"].update(tilt or {})
    payload["visibility"].update(visibility or {})
    if edit is not None:
        edit(payload)
    return FixtureCapabilities.model_validate(payload)


def _line(value: float, t0: int, t1: int) -> ContinuousTrajectory:
    points = (PhysicalPoint(t_ms=t0, value=value), PhysicalPoint(t_ms=t1, value=value))
    return ContinuousTrajectory(unit="degree", points=points, interpolation="linear")


def _states(*events: tuple[int, str]) -> DiscreteTrajectory:
    return DiscreteTrajectory(events=tuple(DiscretePoint(t_ms=t, state=s) for t, s in events))


def _cue(
    name: str,
    t0: int,
    t1: int,
    *,
    pan: float = 0.0,
    tilt: float = 0.0,
    dimmer: float = 1.0,
    shutter: str = "open",
    color: str = "white",
    fixture_id: str = "MH1",
) -> FixtureSegment:
    """A held cue as the compile emits it: pan/tilt with a terminal point, static states."""
    level = ContinuousTrajectory(
        unit="normalized", points=(PhysicalPoint(t_ms=t0, value=dimmer),), interpolation="hold"
    )
    return physical_segment(
        {
            _PAN: _line(pan, t0, t1),
            _TILT: _line(tilt, t0, t1),
            _DIMMER: level,
            _SHUTTER: _states((t0, shutter)),
            _COLOR: _states((t0, color)),
        },
        t0_ms=t0,
        t1_ms=t1,
        fixture_id=fixture_id,
        segment_id=name,
        section_id=name,
    )


def _initial(*, dark: bool = True, **fields: Any) -> InitialFixtureState:
    payload: dict[str, Any] = {
        "pan_deg": 0.0,
        "tilt_deg": 0.0,
        "dimmer": 0.0 if dark else 1.0,
        "discrete_states": {"shutter": "closed" if dark else "open", "color": "white"},
        "settled": True,
        "dark": dark,
    }
    return InitialFixtureState.model_validate({**payload, **fields})


def _plan(
    segments: list[FixtureSegment],
    profile: FixtureCapabilities,
    initial: InitialFixtureState | None,
    *,
    locks: tuple[RenderLock, ...] = (),
    mode: FailureMode = "error",
    end_ms: int | None = None,
) -> PrepositionResult:
    """Plan MH1's cues; the sequence ends at `end_ms`, by default with the last cue."""
    return plan_prepositions(
        segments,
        {"MH1": profile},
        initial_states={} if initial is None else {"MH1": initial},
        locks=locks,
        frame_ms=20,
        failure_mode=mode,
        sequence_end_ms=max(s.t1_ms for s in segments) if end_ms is None else end_ms,
    )


def _at(result: PrepositionResult, cue_ms: int) -> TransitionDiagnostic:
    (diagnostic,) = [d for d in result.diagnostics if d.cue_ms == cue_ms]
    return diagnostic


def _bytes(
    result: PrepositionResult, profile: FixtureCapabilities, end_ms: int
) -> dict[int, dict[int, int]]:
    frames = encode_fixture_frames(result.segments, profile, frame_times_ms=frame_times(end_ms))
    return {frame.time_ms: dict(frame.channels) for frame in frames}


def _pan_word(frame: dict[int, int]) -> int:
    return frame[1] << 8 | frame[2]


def _opt_in(segment: FixtureSegment, mode: str) -> FixtureSegment:
    segment.metadata[FALLBACK_METADATA_KEY] = mode
    return segment


# --- Required time, rounding and darkness ------------------------------------------------


def test_90_degrees_at_90_per_s_with_40_ms_settle_needs_1040_ms() -> None:
    profile = _profile(pan=_SLOW_PAN)
    initial = _initial()

    short = _plan([_cue("A", 1020, 1200, pan=90.0)], profile, initial)
    assert short.has_errors and short.segments == ()
    assert (_at(short, 1020).code, _at(short, 1020).required_ms) == ("infeasible_transition", 1040)
    assert _at(short, 1020).available_ms == 1020

    inputs = [_cue("A", 1040, 1200, pan=90.0)]
    result = _plan(inputs, profile, initial)
    diagnostic = _at(result, 1040)
    assert (diagnostic.status, diagnostic.required_ms, diagnostic.available_ms) == (
        "feasible",
        1040,
        1040,
    )
    assert diagnostic.optical_reveal_ms == 1040
    assert_honest_transactions(result, inputs, profile, initial)

    frames = _bytes(result, profile, 1200)
    target = profile.axes["pan"].dmx_word(90.0)
    # Travel spans the first 1000 ms, then 40 ms of settle hold the arrived pose dark.
    assert _pan_word(frames[0]) != profile.axes["pan"].dmx_word(0.0)
    assert _pan_word(frames[960]) != target
    assert {_pan_word(frames[t]) for t in range(980, 1200, 20)} == {target}
    assert frames[1020][5] == 0 and frames[1040][5] == 255  # dark, then revealed on the cue


def test_close_latency_delays_the_move_and_moving_at_the_close_command_fails() -> None:
    profile = _profile(pan=_SLOW_PAN, visibility={"close_latency_ms": 40})
    initial = _initial(dark=False)
    lit = _cue("A", 0, 200)

    short = _plan([lit, _cue("B", 1240, 1400, pan=90.0)], profile, initial)
    assert (_at(short, 1240).code, _at(short, 1240).required_ms) == ("infeasible_transition", 1080)

    inputs = [lit, _cue("B", 1280, 1400, pan=90.0)]
    result = _plan(inputs, profile, initial)
    assert (_at(result, 1280).status, _at(result, 1280).required_ms) == ("feasible", 1080)
    assert_honest_transactions(result, inputs, profile, initial)
    frames = _bytes(result, profile, 1400)
    start = profile.axes["pan"].dmx_word(0.0)
    assert {_pan_word(frames[t]) for t in (200, 220)} == {start}  # closing, not yet dark
    assert _pan_word(frames[240]) != start

    # The same plan moving from the close command is caught from the bytes.
    transaction = next(s for s in result.segments if TRANSACTION_METADATA_KEY in s.metadata)
    early = ContinuousTrajectory(
        unit="degree",
        points=(PhysicalPoint(t_ms=200, value=1.8), PhysicalPoint(t_ms=1180, value=90.0)),
        interpolation="linear",
    )
    moved = transaction.model_copy(
        update={
            "channels": {**transaction.channels, _PAN: ChannelValue(channel=_PAN, physical=early)}
        }
    )
    doctored = result.model_copy(
        update={"segments": tuple(moved if s is transaction else s for s in result.segments)}
    )
    with pytest.raises(AssertionError, match="lit at 200 ms while busy"):
        assert_honest_transactions(doctored, inputs, profile, initial)


@pytest.mark.parametrize(("dark_from", "required"), [(360, 1040), (380, 1060)])
def test_a_cue_already_dark_for_the_close_latency_needs_no_extra_wait(
    dark_from: int, required: int
) -> None:
    profile = _profile(pan=_SLOW_PAN, visibility={"close_latency_ms": 40})
    initial = _initial(dark=False)
    fading = _cue("A", 0, 400)
    fading.channels[_DIMMER] = ChannelValue(
        channel=_DIMMER,
        physical=ContinuousTrajectory(
            unit="normalized",
            points=(PhysicalPoint(t_ms=0, value=1.0), PhysicalPoint(t_ms=dark_from, value=0.0)),
            interpolation="hold",
        ),
    )
    inputs = [fading, _cue("B", 400 + required, 1600, pan=90.0)]

    result = _plan(inputs, profile, initial)

    assert _at(result, 400 + required).required_ms == required
    assert_honest_transactions(result, inputs, profile, initial)
    early = _plan([fading, _cue("B", 380 + required, 1600, pan=90.0)], profile, initial)
    assert _at(early, 380 + required).code == "infeasible_transition"


def test_open_latency_reports_the_optical_reveal_after_the_aligned_command() -> None:
    profile = _profile(pan=_SLOW_PAN, visibility={"open_latency_ms": 20})
    initial = _initial()
    inputs = [_cue("A", 1040, 1200, pan=90.0)]

    result = _plan(inputs, profile, initial)

    diagnostic = _at(result, 1040)
    assert (diagnostic.cue_ms, diagnostic.optical_reveal_ms) == (1040, 1060)
    assert "1060" in diagnostic.reason and "20 ms after" in diagnostic.reason
    assert_honest_transactions(result, inputs, profile, initial)
    assert _bytes(result, profile, 1200)[1040][5] == 255  # the command lands on the cue


@pytest.mark.parametrize(
    ("visibility", "dark", "needle"),
    [
        pytest.param({"close_latency_ms": None}, False, "close_latency_ms", id="close"),
        pytest.param({"open_latency_ms": None}, True, "open_latency_ms", id="open"),
    ],
)
def test_unknown_visibility_latency_never_passes_as_zero(
    visibility: dict[str, Any], dark: bool, needle: str
) -> None:
    profile = _profile(visibility=visibility)
    initial = _initial(dark=dark)
    first = [_cue("A", 0, 200)] if not dark else []

    result = _plan([*first, _cue("B", 1000, 1200, pan=90.0)], profile, initial)

    assert result.has_errors and result.segments == ()
    assert _at(result, 1000).code == "infeasible_transition"
    assert needle in _at(result, 1000).reason


@pytest.mark.parametrize("closed", [64, 200])
def test_shutter_darkness_uses_the_declared_closed_byte(closed: int) -> None:
    def shutter_only(payload: dict[str, Any]) -> None:
        payload["visibility"]["dimmer_zero_extinguishes"] = False
        payload["discrete"]["shutter"]["states"]["closed"].update(
            range_min=closed - 4, range_max=closed + 4, value=closed
        )
        payload["defaults"][6] = closed

    profile = _profile(edit=shutter_only)
    initial = _initial(dark=False)
    inputs = [_cue("A", 0, 200), _cue("B", 1400, 1600, pan=90.0)]

    result = _plan(inputs, profile, initial)

    assert_honest_transactions(result, inputs, profile, initial)
    frames = _bytes(result, profile, 1600)
    assert {frames[t][6] for t in range(200, 1400, 20)} == {closed}
    # The dimmer is held lit: the darkness came from the shutter declaration alone.
    assert {frames[t][5] for t in range(200, 1400, 20)} == {255}


def test_axes_travel_simultaneously_and_the_slowest_sets_the_time() -> None:
    profile = _profile(pan=_SLOW_PAN, tilt={"travel_speed_per_s": 40.0, "settle_ms": 20})
    initial = _initial()

    short = _plan([_cue("A", 1520, 1700, pan=90.0, tilt=60.0)], profile, initial)
    assert _at(short, 1520).required_ms == 1540

    inputs = [_cue("A", 1540, 1700, pan=90.0, tilt=60.0)]
    result = _plan(inputs, profile, initial)
    assert_honest_transactions(result, inputs, profile, initial)
    frames = _bytes(result, profile, 1700)
    # Both axes leave on the first dark frame and arrive together.
    assert _pan_word(frames[0]) != profile.axes["pan"].dmx_word(0.0)
    assert (frames[0][3] << 8 | frames[0][4]) != profile.axes["tilt"].dmx_word(0.0)
    assert _pan_word(frames[1480]) == profile.axes["pan"].dmx_word(90.0)
    assert _pan_word(frames[1460]) != profile.axes["pan"].dmx_word(90.0)


def _with_blue(payload: dict[str, Any]) -> None:
    payload["discrete"]["color"]["states"]["blue"] = {
        "range_min": 20,
        "range_max": 29,
        "value": 26,
        "settle_ms": 140,
    }


def test_an_instant_wheel_still_turns_on_a_dark_frame_before_the_cue() -> None:
    """Darkness reached only at the cue leaves no dark frame to turn the wheel on."""
    profile = _profile(visibility={"close_latency_ms": 40})
    initial = _initial(dark=False)

    short = _plan([_cue("A", 0, 200), _cue("B", 240, 400, color="red")], profile, initial)
    assert (_at(short, 240).code, _at(short, 240).required_ms) == ("infeasible_transition", 60)

    inputs = [_cue("A", 0, 200), _cue("B", 260, 400, color="red")]
    result = _plan(inputs, profile, initial)
    assert _at(result, 260).status == "feasible"
    assert _bytes(result, profile, 400)[240][7] == 14  # red selected on the dark frame
    assert_honest_transactions(result, inputs, profile, initial)


def test_wheel_change_settles_dark_before_the_move_without_declared_independence() -> None:
    profile = _profile(pan=_SLOW_PAN, edit=_with_blue)
    initial = _initial()

    alone = _plan([_cue("A", 140, 300, color="blue")], profile, initial)
    assert (_at(alone, 140).status, _at(alone, 140).required_ms) == ("feasible", 140)

    short = _plan([_cue("A", 1160, 1300, pan=90.0, color="blue")], profile, initial)
    assert _at(short, 1160).required_ms == 1180  # 140 + 1000 + 40, sequential

    inputs = [_cue("A", 1180, 1300, pan=90.0, color="blue")]
    result = _plan(inputs, profile, initial)
    assert_honest_transactions(result, inputs, profile, initial)
    frames = _bytes(result, profile, 1300)
    assert frames[0][7] == 26  # the wheel turns on the first dark frame
    assert _pan_word(frames[120]) == profile.axes["pan"].dmx_word(0.0)
    assert _pan_word(frames[140]) != profile.axes["pan"].dmx_word(0.0)


@pytest.mark.parametrize(
    ("pan", "missing"),
    [
        pytest.param({"travel_speed_per_s": None}, "travel_speed_per_s", id="speed"),
        pytest.param({"latency_ms": None}, "latency_ms", id="latency"),
        pytest.param({"settle_ms": None}, "settle_ms", id="settle"),
    ],
)
def test_unknown_motion_timing_fails_only_for_a_needed_move(
    pan: dict[str, Any], missing: str
) -> None:
    profile = _profile(pan=pan)
    initial = _initial()

    moving = _plan([_cue("A", 2000, 2200, pan=90.0)], profile, initial)
    assert (_at(moving, 2000).code, _at(moving, 2000).required_ms) == ("unknown_motion_rate", None)
    assert missing in _at(moving, 2000).reason

    held = [_cue("A", 2000, 2200)]
    result = _plan(held, profile, initial)
    assert _at(result, 2000).status == "feasible"
    assert_honest_transactions(result, held, profile, initial)


# --- Residual motion, encoded words and the sequence edges -------------------------------


def _sweep_cue(
    name: str, t0: int, t1: int, start: float, end: float, *, lit: bool
) -> FixtureSegment:
    cue = _cue(name, t0, t1, dimmer=1.0 if lit else 0.0, shutter="open" if lit else "closed")
    cue.channels[_PAN] = ChannelValue(
        channel=_PAN,
        physical=ContinuousTrajectory(
            unit="degree",
            points=(PhysicalPoint(t_ms=t0, value=start), PhysicalPoint(t_ms=t1, value=end)),
            interpolation="linear",
        ),
    )
    return cue


_LAGGING_PAN = {"travel_speed_per_s": 90.0, "latency_ms": 40, "settle_ms": 40}


def test_a_reveal_waits_for_the_previous_cues_own_motion_to_settle() -> None:
    """A dark sweep's last command at 380 ms settles near 480 ms: a lit cue at 420 at the
    same aim would show it still moving."""
    profile = _profile(pan=_LAGGING_PAN)
    initial = _initial()
    sweep = _sweep_cue("A", 0, 400, 0.0, 36.0, lit=False)
    still = _cue("B", 420, 600, pan=34.2)

    result = _plan([sweep, still], profile, initial)

    failure = _at(result, 420)
    assert (failure.status, failure.code) == ("error", "infeasible_transition")
    assert failure.required_ms is not None and failure.required_ms > failure.available_ms == 20

    inputs = [sweep, _cue("B", 520, 700, pan=34.2)]
    later = _plan(inputs, profile, initial)
    assert _at(later, 520).status == "feasible"
    assert_honest_transactions(later, inputs, profile, initial)


def test_preserve_aim_does_not_reveal_an_aim_still_settling() -> None:
    profile = _profile(pan=_LAGGING_PAN)
    initial = _initial(dark=False)
    inputs = [
        _sweep_cue("A", 0, 400, 0.0, 36.0, lit=True),
        _opt_in(_cue("B", 420, 600, pan=-90.0), "preserve_aim"),
    ]

    result = _plan(inputs, profile, initial, mode="preserve_aim")

    assert _at(result, 420).status == "error"
    assert "preserve_aim cannot apply" in _at(result, 420).reason


def test_travel_is_timed_on_encoded_words_not_physical_values() -> None:
    """On an 8-bit 540° pan one word is 2.1176°: 0.9° apart still costs a whole word."""

    def coarse_pan(payload: dict[str, Any]) -> None:
        pan = payload["axes"]["pan"]
        pan.update(physical_min=0.0, physical_max=540.0, travel_speed_per_s=45.5)
        del pan["fine_offset"]
        payload["defaults"].update({1: 0, 2: 0})

    profile = _profile(edit=coarse_pan)
    initial = _initial(pan_deg=22.0)
    assert profile.axes["pan"].dmx_word(22.9) == profile.axes["pan"].dmx_word(22.0) + 1

    result = _plan([_cue("A", 20, 200, pan=22.9)], profile, initial)

    assert (_at(result, 20).code, _at(result, 20).required_ms) == ("infeasible_transition", 60)
    inputs = [_cue("A", 60, 200, pan=22.9)]
    feasible = _plan(inputs, profile, initial)
    assert _at(feasible, 60).status == "feasible"
    assert_honest_transactions(feasible, inputs, profile, initial)


def test_after_the_last_cue_the_head_parks_dark_at_its_last_aim() -> None:
    def lit_default(payload: dict[str, Any]) -> None:
        payload["discrete"]["shutter"]["default_state"] = "open"
        payload["defaults"][6] = 8

    profile = _profile(edit=lit_default)
    initial = _initial(dark=False, pan_deg=90.0)
    inputs = [_cue("A", 0, 200, pan=90.0)]

    result = _plan(inputs, profile, initial, end_ms=400)

    frames = _bytes(result, profile, 400)
    aim = profile.axes["pan"].dmx_word(90.0)
    assert {_pan_word(frames[t]) for t in range(0, 400, 20)} == {aim}
    assert {(frames[t][5], frames[t][6]) for t in range(200, 400, 20)} == {(0, 64)}
    assert_honest_transactions(result, inputs, profile, initial)


def test_a_fixture_without_cues_parks_dark_at_its_initial_state_or_fails() -> None:
    profile = _profile()
    cue = _cue("A", 0, 200)
    profiles = {"MH1": profile, "MH2": profile}
    states = {"MH1": _initial(dark=False), "MH2": _initial(pan_deg=45.0)}

    result = plan_prepositions(
        [cue], profiles, initial_states=states, locks=(), frame_ms=20, sequence_end_ms=400
    )

    (park,) = [s for s in result.segments if s.fixture_id == "MH2"]
    assert (park.t0_ms, park.t1_ms, park.metadata[TRANSACTION_METADATA_KEY]) == (0, 400, "")
    frames = encode_fixture_frames([park], profile, frame_times_ms=frame_times(400))
    aim = profile.axes["pan"].dmx_word(45.0)
    assert {(_pan_word(dict(f.channels)), dict(f.channels)[5]) for f in frames} == {(aim, 0)}
    assert_honest_transactions(result, [cue], profile, states["MH1"])

    unknown = plan_prepositions(
        [cue],
        profiles,
        initial_states={"MH1": states["MH1"]},
        locks=(),
        frame_ms=20,
        sequence_end_ms=400,
    )
    assert unknown.segments == ()
    assert [(d.fixture_id, d.code) for d in unknown.diagnostics if d.status == "error"] == [
        ("MH2", "unknown_initial_state")
    ]


@pytest.mark.parametrize(
    ("visibility", "needle"),
    [
        pytest.param({"close_latency_ms": None}, "close_latency_ms", id="unknown-close"),
        pytest.param(
            {"dimmer_zero_extinguishes": False, "extinguishing_shutter_states": []},
            "extinguish",
            id="no-darkness",
        ),
    ],
)
def test_fallbacks_never_cover_unknown_latency_or_missing_darkness(
    visibility: dict[str, Any], needle: str
) -> None:
    profile = _profile(visibility=visibility)
    inputs = [_cue("A", 0, 200), _opt_in(_cue("B", 1000, 1200, pan=90.0), "drop_accent")]

    result = _plan(inputs, profile, _initial(dark=False), mode="drop_accent")

    assert _at(result, 1000).status == "error"
    assert needle in _at(result, 1000).reason


def test_shutter_darkness_waits_for_the_closed_states_settle() -> None:
    """Shutter-only darkness: close latency 0 plus a 30 ms closed settle delays the move."""

    def shutter_only(payload: dict[str, Any]) -> None:
        payload["visibility"]["dimmer_zero_extinguishes"] = False
        payload["discrete"]["shutter"]["states"]["closed"]["settle_ms"] = 30

    profile = _profile(pan=_SLOW_PAN, edit=shutter_only)
    initial = _initial(dark=False)

    short = _plan([_cue("A", 0, 200), _cue("B", 1260, 1400, pan=90.0)], profile, initial)
    assert _at(short, 1260).required_ms == 1080  # 40 (30 rounded up) + 1000 + 40

    inputs = [_cue("A", 0, 200), _cue("B", 1280, 1400, pan=90.0)]
    result = _plan(inputs, profile, initial)
    assert _at(result, 1280).status == "feasible"
    assert_honest_transactions(result, inputs, profile, initial)


# --- Time zero and initial state ----------------------------------------------------------


@pytest.mark.parametrize(
    ("initial", "cue_dimmer", "cue_shutter"),
    [
        pytest.param({"dimmer": 1.0}, 0.0, "open", id="shutter-evidence-to-dimmer"),
        pytest.param(
            {"discrete_states": {"shutter": "open", "color": "white"}},
            1.0,
            "closed",
            id="dimmer-evidence-to-shutter",
        ),
    ],
)
@pytest.mark.parametrize("close", [40, None])
def test_initial_darkness_counts_only_while_its_own_mechanism_holds(
    initial: dict[str, Any], cue_dimmer: float, cue_shutter: str, close: int | None
) -> None:
    """A dark cue at time zero that darkens by the other mechanism is not dark yet: its
    wheel change must wait for the close latency, so it cannot be planned at zero."""
    profile = _profile(visibility={"close_latency_ms": close})
    start = _initial(**initial)
    assert profile.check_initial_state(start) == ()
    cue = _cue("A", 0, 200, dimmer=cue_dimmer, shutter=cue_shutter, color="red")

    result = _plan([cue], profile, start)

    at_zero = [d for d in result.diagnostics if d.cue_ms == 0]
    assert at_zero and all(d.status == "error" for d in at_zero), at_zero
    assert result.segments == ()
    assert all(d.required_ms is None or d.required_ms >= 40 for d in at_zero)


@pytest.mark.parametrize("close", [40, None])
def test_oracle_credits_initial_darkness_only_to_its_evidenced_mechanism(
    close: int | None,
) -> None:
    """Dark by a closed shutter at time zero, a transaction that opens the shutter and
    zeroes the dimmer while moving is lit for the close latency (or for ever)."""
    profile = _profile(visibility={"close_latency_ms": close})
    initial = _initial(dimmer=1.0)
    cue = _cue("A", 400, 600, pan=45.0)
    planned = _plan([cue], profile, initial)
    switched = physical_segment(
        {
            _PAN: _line(45.0, 0, 400),
            _TILT: _line(0.0, 0, 400),
            _DIMMER: ContinuousTrajectory(
                unit="normalized", points=(PhysicalPoint(t_ms=0, value=0.0),), interpolation="hold"
            ),
            _SHUTTER: _states((0, "open")),
            _COLOR: _states((0, "white")),
        },
        t0_ms=0,
        t1_ms=400,
        segment_id="A/preposition",
        section_id="A",
    )
    doctored = planned.model_copy(
        update={
            "segments": (switched, cue),
            "diagnostics": tuple(d for d in planned.diagnostics if d.status != "error"),
        }
    )

    with pytest.raises(AssertionError, match="lit at 0 ms while busy"):
        assert_honest_transactions(doctored, [cue], profile, initial)


def test_visible_cue_at_time_zero_needs_the_initial_state_to_already_match() -> None:
    profile = _profile()
    cue = [_cue("A", 0, 200)]

    result = _plan(cue, profile, _initial(dark=False))
    assert _at(result, 0).status == "feasible"
    assert result.segments == tuple(cue)

    for initial, code in (
        (_initial(dark=True), "infeasible_transition"),  # no pre-roll before time zero
        (_initial(dark=False, pan_deg=10.0), "infeasible_transition"),
        (_initial(dark=False, settled=False), "unknown_initial_state"),
        (None, "unknown_initial_state"),
    ):
        failed = _plan(cue, profile, initial)
        assert failed.has_errors and failed.segments == ()
        assert _at(failed, 0).code == code

    dark_cue = [_cue("A", 0, 200, dimmer=0.0, shutter="closed")]
    assert _at(_plan(dark_cue, profile, _initial()), 0).status == "feasible"


def test_unknown_initial_state_is_never_planned_around() -> None:
    profile = _profile()
    cue = _opt_in(_cue("A", 1000, 1200, pan=90.0), "drop_accent")

    for initial in (None, _initial(settled=False), _initial(pan_deg=400.0)):
        result = _plan([cue], profile, initial, mode="drop_accent")
        assert result.has_errors and result.segments == ()
        assert _at(result, 1000).code == "unknown_initial_state"
        assert _at(result, 1000).required_ms is None


def test_no_declared_darkness_fails_any_transaction() -> None:
    profile = _profile(
        visibility={"dimmer_zero_extinguishes": False, "extinguishing_shutter_states": []}
    )

    result = _plan([_cue("A", 0, 200), _cue("B", 1000, 1200)], profile, _initial(dark=False))

    assert _at(result, 1000).code == "infeasible_transition"
    assert "extinguish" in _at(result, 1000).reason


# --- Locks --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end"),
    [pytest.param(500, 520, id="one-frame"), pytest.param(505, 506, id="snapped-outward")],
)
def test_a_lock_inside_the_travel_window_is_a_conflict(start: int, end: int) -> None:
    profile = _profile(pan=_SLOW_PAN)
    lock = RenderLock(start_ms=start, end_ms=end, fixture_ids=("MH1",), channels=(_PAN,))

    result = _plan([_cue("A", 1040, 1200, pan=90.0)], profile, _initial(), locks=(lock,))

    assert result.has_errors and result.segments == ()
    assert _at(result, 1040).code == "lock_conflict"
    assert _at(result, 1040).required_ms == 1040


def test_locks_outside_the_transaction_leave_the_plan_and_their_frames_unchanged() -> None:
    profile = _profile(pan=_SLOW_PAN)
    initial = _initial()
    inputs = [_cue("A", 1040, 1200, pan=90.0)]
    locks = (
        RenderLock(start_ms=1100, end_ms=1180, fixture_ids=("MH1",), channels=(_PAN, _DIMMER)),
        RenderLock(start_ms=500, end_ms=520, fixture_ids=("MH2",), channels=(_PAN,)),
    )

    result = _plan(inputs, profile, initial, locks=locks)

    assert result == _plan(inputs, profile, initial)
    assert_honest_transactions(result, inputs, profile, initial, locks=locks)


# --- Visible motion and continuity ---------------------------------------------------------


def _sweep(t0: int, t1: int) -> FixtureSegment:
    """A lit cue sweeping pan 0 → 30 → 0 degrees: intentional visible motion."""
    middle = (t0 + t1) // 2
    sweep = ContinuousTrajectory(
        unit="degree",
        points=tuple(
            PhysicalPoint(t_ms=t, value=v) for t, v in ((t0, 0.0), (middle, 30.0), (t1, 0.0))
        ),
        interpolation="linear",
    )
    cue = _cue("A", t0, t1)
    cue.channels[_PAN] = ChannelValue(channel=_PAN, physical=sweep)
    return cue


def test_visible_sweep_stays_visible_and_continues_into_the_next_cue() -> None:
    profile = _profile()
    initial = _initial(dark=False)
    inputs = [_sweep(0, 1000), _cue("B", 1000, 1400)]

    result = _plan(inputs, profile, initial)

    assert result.segments == tuple(inputs)
    assert [d.status for d in result.diagnostics] == ["feasible", "feasible"]
    frames = _bytes(result, profile, 1400)
    assert len({_pan_word(frames[t]) for t in range(0, 1000, 20)}) > 20
    assert {frames[t][5] for t in range(0, 1000, 20)} == {255}

    jump = _plan([_sweep(0, 1000), _cue("B", 1000, 1400, pan=90.0)], profile, initial)
    assert _at(jump, 1000).code == "infeasible_transition"


# --- Explicit fallbacks --------------------------------------------------------------------


def test_preserve_aim_needs_the_mode_and_the_cue_to_opt_in() -> None:
    profile = _profile(pan=_SLOW_PAN)
    initial = _initial()

    for mode, opted in (
        ("preserve_aim", None),
        ("error", "preserve_aim"),
        ("preserve_aim", "drop_accent"),
    ):
        cue = _cue("A", 520, 800, pan=90.0)
        if opted is not None:
            _opt_in(cue, opted)
        result = _plan([cue], profile, initial, mode=mode)  # type: ignore[arg-type]
        assert _at(result, 520).status == "error", (mode, opted)

    inputs = [_opt_in(_cue("A", 520, 800, pan=90.0), "preserve_aim")]
    result = _plan(inputs, profile, initial, mode="preserve_aim")

    diagnostic = _at(result, 520)
    assert (diagnostic.status, diagnostic.code) == ("preserve_aim", "infeasible_transition")
    assert diagnostic.required_ms == 1040 and "preserve_aim" in diagnostic.reason
    assert_honest_transactions(result, inputs, profile, initial)
    frames = _bytes(result, profile, 800)
    held = profile.axes["pan"].dmx_word(0.0)
    assert {_pan_word(frames[t]) for t in range(0, 800, 20)} == {held}
    assert frames[520][5] == 255  # the cue still plays, at the settled aim


def test_preserve_aim_cannot_bypass_a_lock() -> None:
    profile = _profile(pan=_SLOW_PAN)
    lock = RenderLock(start_ms=600, end_ms=620, fixture_ids=("MH1",), channels=(_PAN,))
    inputs = [_opt_in(_cue("A", 520, 800, pan=90.0), "preserve_aim")]

    result = _plan(inputs, profile, _initial(), locks=(lock,), mode="preserve_aim")

    assert _at(result, 520).code == "lock_conflict"


def test_a_cue_right_after_a_preserved_one_cannot_continue_motion_it_never_saw() -> None:
    """A at pan 90 is played at the held aim 0; B right after it at pan 10 would step
    0 → 10 while lit, a move no cue authored."""
    profile = _profile()
    initial = _initial()
    held = _opt_in(_cue("A", 20, 200, pan=90.0), "preserve_aim")

    result = _plan([held, _cue("B", 200, 400, pan=10.0)], profile, initial, mode="preserve_aim")

    assert _at(result, 20).status == "preserve_aim"
    assert (_at(result, 200).status, _at(result, 200).code) == ("error", "infeasible_transition")
    assert "preserve_aim" in _at(result, 200).reason and result.segments == ()

    inputs = [_opt_in(_cue("A", 20, 200, pan=90.0), "preserve_aim"), _cue("B", 200, 400)]
    at_aim = _plan(inputs, profile, initial, mode="preserve_aim")
    assert _at(at_aim, 200).status == "feasible"
    assert_honest_transactions(at_aim, inputs, profile, initial)


def test_a_chain_of_preserved_cues_is_judged_on_what_was_emitted() -> None:
    profile = _profile()
    initial = _initial()

    def chain(pan_c: float) -> list[FixtureSegment]:
        return [
            _opt_in(_cue("A", 20, 200, pan=90.0), "preserve_aim"),
            _opt_in(_cue("B", 200, 400, pan=10.0), "preserve_aim"),
            _cue("C", 400, 600, pan=pan_c),
        ]

    moved = _plan(chain(10.0), profile, initial, mode="preserve_aim")
    assert [d.status for d in moved.diagnostics] == ["preserve_aim", "preserve_aim", "error"]

    inputs = chain(0.0)
    held = _plan(inputs, profile, initial, mode="preserve_aim")
    assert [d.status for d in held.diagnostics] == ["preserve_aim", "preserve_aim", "feasible"]
    assert_honest_transactions(held, inputs, profile, initial)


def test_a_cue_right_after_a_dropped_one_is_planned_across_the_dropped_span() -> None:
    profile = _profile(pan=_SLOW_PAN)
    initial = _initial()
    inputs = [
        _opt_in(_cue("A", 20, 200, pan=90.0), "drop_accent"),
        _cue("B", 200, 400, pan=10.0),
    ]

    result = _plan(inputs, profile, initial, mode="drop_accent")

    assert [d.status for d in result.diagnostics] == ["drop_accent", "feasible"]
    assert _at(result, 200).available_ms == 200  # from time zero, not a continuation
    assert_honest_transactions(result, inputs, profile, initial)


def test_drop_accent_keeps_the_cue_dark_and_plans_on_from_the_held_aim() -> None:
    profile = _profile(pan=_SLOW_PAN)
    initial = _initial()
    inputs = [
        _opt_in(_cue("A", 520, 800, pan=90.0), "drop_accent"),
        _cue("B", 2000, 2200, pan=45.0),
    ]

    result = _plan(inputs, profile, initial, mode="drop_accent")

    assert [(d.cue_ms, d.status) for d in result.diagnostics] == [
        (520, "drop_accent"),
        (2000, "feasible"),
    ]
    assert "A" not in {s.segment_id for s in result.segments}
    assert _at(result, 2000).available_ms == 2000  # planned from time zero's held aim
    assert_honest_transactions(result, inputs, profile, initial)
    frames = _bytes(result, profile, 2200)
    assert {frames[t][5] for t in range(520, 800, 20)} == {0}
    assert result.dependencies[1].source_section_id is None

    last = _plan(inputs[:1], profile, initial, mode="drop_accent")
    assert max(s.t1_ms for s in last.segments) == 800
    assert {frames[5] for frames in _bytes(last, profile, 800).values()} == {0}


# --- Shutter timing across step boundaries -------------------------------------------------


def test_a_steps_first_shutter_state_must_fit_its_latency_and_settle() -> None:
    profile = _profile(visibility={"open_latency_ms": 40})
    cue = _cue("A", 200, 600)
    cue.channels[_SHUTTER] = ChannelValue(
        channel=_SHUTTER, physical=_states((200, "open"), (220, "closed"))
    )

    result = _plan([cue], profile, _initial())

    (failure,) = [d for d in result.diagnostics if d.status == "error"]
    assert failure.cue_ms == 200 and result.segments == ()
    assert (failure.code, failure.required_ms, failure.available_ms) == (
        "infeasible_transition",
        40,
        20,
    )


# --- Dependencies, determinism and input contracts ----------------------------------------


def test_dependencies_span_predecessor_state_through_reveal_and_are_deterministic() -> None:
    profile = _profile(visibility={"open_latency_ms": 30})
    initial = _initial()
    inputs = [_cue("A", 400, 800, pan=45.0), _cue("B", 1600, 2000, pan=90.0)]

    result = _plan(inputs, profile, initial)

    assert result == _plan(list(reversed(inputs)), profile, initial)
    first, second = result.dependencies
    assert (first.source_section_id, first.target_section_id, first.start_ms, first.end_ms) == (
        None,
        "A",
        0,
        440,
    )
    assert (second.source_section_id, second.start_ms, second.end_ms) == ("A", 400, 1640)
    assert first.channels == (_PAN, _TILT, _DIMMER, _SHUTTER, _COLOR)
    assert_honest_transactions(result, inputs, profile, initial)


@pytest.mark.parametrize(
    ("segments", "frame_ms", "match"),
    [
        pytest.param([_cue("A", 1000, 1200)], 40, "frame", id="frame-ms"),
        pytest.param([_cue("A", 1010, 1200)], 20, "grid", id="off-grid"),
        pytest.param([_cue("A", 0, 400), _cue("B", 200, 600)], 20, "overlap", id="overlap"),
    ],
)
def test_input_contract_violations_raise(
    segments: list[FixtureSegment], frame_ms: int, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        plan_prepositions(
            segments,
            {"MH1": _profile()},
            initial_states={"MH1": _initial()},
            locks=(),
            frame_ms=frame_ms,
            sequence_end_ms=1200,
        )


def test_a_cue_without_its_pose_is_rejected() -> None:
    cue = _cue("A", 1000, 1200)
    del cue.channels[_TILT]

    with pytest.raises(ValueError, match="tilt"):
        _plan([cue], _profile(), _initial())
