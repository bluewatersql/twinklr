"""Synthetic physical-renderer inputs: a fixture profile, a known initial state and
physical fixture segments.

In-memory payloads only; no owner profile or measured data.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from typing import Any

from twinklr.core.config.fixtures import AxisCapability, FixtureCapabilities, InitialFixtureState
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    AXIS_KEYS,
    DISCRETE_KEYS,
    PhysicalValue,
    RenderLock,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import PrepositionResult
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    encode_fixture_frames,
    frame_times,
)


def physical_segment(
    channels: dict[ChannelName, PhysicalValue],
    *,
    t0_ms: int,
    t1_ms: int,
    fixture_id: str = "MH1",
    segment_id: str = "seg",
    section_id: str = "section",
) -> FixtureSegment:
    """A fixture segment whose channels hold only typed physical values."""
    return FixtureSegment(
        section_id=section_id,
        segment_id=segment_id,
        step_id="step",
        template_id="template",
        fixture_id=fixture_id,
        t0_ms=t0_ms,
        t1_ms=t1_ms,
        channels={
            name: ChannelValue(channel=name, physical=value) for name, value in channels.items()
        },
    )


def profile_payload() -> dict[str, Any]:
    """A synthetic 8-channel spot: 16-bit pan/tilt, dimmer, shutter, color and a spare."""
    return {
        "profile_id": "synthetic_spot",
        "provenance": "synthetic",
        "footprint": 8,
        "defaults": {1: 128, 2: 0, 3: 128, 4: 0, 5: 0, 6: 64, 7: 0, 8: 0},
        "axes": {
            "pan": {
                "unit": "degree",
                "physical_min": -270.0,
                "physical_max": 270.0,
                "coarse_offset": 1,
                "fine_offset": 2,
            },
            "tilt": {
                "unit": "degree",
                "physical_min": -135.0,
                "physical_max": 135.0,
                "coarse_offset": 3,
                "fine_offset": 4,
            },
            "dimmer": {
                "unit": "normalized",
                "physical_min": 0.0,
                "physical_max": 1.0,
                "coarse_offset": 5,
            },
        },
        "discrete": {
            "shutter": {
                "offset": 6,
                "states": {
                    "closed": {"range_min": 64, "range_max": 95, "value": 64},
                    "open": {"range_min": 0, "range_max": 31, "value": 8},
                },
                "default_state": "closed",
                "closed_state": "closed",
                "open_state": "open",
            },
            "color": {
                "offset": 7,
                "states": {
                    "white": {"range_min": 0, "range_max": 9, "value": 0},
                    "red": {"range_min": 10, "range_max": 19, "value": 14},
                },
                "default_state": "white",
            },
        },
        "visibility": {
            "dimmer_zero_extinguishes": True,
            "extinguishing_shutter_states": ["closed"],
            "close_latency_ms": 0,
            "open_latency_ms": 0,
        },
    }


def initial_state_payload() -> dict[str, Any]:
    """A known, settled, dark time-zero state the profile above accepts."""
    return {
        "pan_deg": 0.0,
        "tilt_deg": 0.0,
        "dimmer": 0.0,
        "discrete_states": {"shutter": "closed", "color": "red"},
        "settled": True,
        "dark": True,
    }


def motion_profile_payload() -> dict[str, Any]:
    """`profile_payload` with configured pan/tilt travel speeds and settled shutter states."""
    payload = profile_payload()
    for axis in ("pan", "tilt"):
        payload["axes"][axis]["travel_speed_per_s"] = 720.0
    for state in payload["discrete"]["shutter"]["states"].values():
        state["settle_ms"] = 0
    return payload


def preposition_profile_payload() -> dict[str, Any]:
    """`motion_profile_payload` with every timing the transaction pass reads declared.

    Pan/tilt latency and settle and color settle are explicit zeros, so a test states
    only the timing it is about.
    """
    payload = motion_profile_payload()
    for axis in ("pan", "tilt"):
        payload["axes"][axis].update(latency_ms=0, settle_ms=0)
    for state in payload["discrete"]["color"]["states"].values():
        state["settle_ms"] = 0
    return payload


def discrete_profile_payload() -> dict[str, Any]:
    """`motion_profile_payload` with the shutter on channel 17 and color and gobo wheels.

    Closed is byte 64 and open byte 8, inside ranges whose bounds are not the selected
    bytes; each wheel has a state between its first and last selected bytes.
    """
    payload = motion_profile_payload()
    payload["footprint"] = 18
    payload["defaults"] = {
        **payload["defaults"],
        **dict.fromkeys(range(9, 17), 0),
        17: 64,
        18: 0,
    }
    payload["discrete"]["shutter"].update(
        offset=17,
        states={
            "closed": {"range_min": 60, "range_max": 95, "value": 64, "settle_ms": 0},
            "open": {"range_min": 0, "range_max": 31, "value": 8, "settle_ms": 0},
        },
    )
    payload["discrete"]["color"]["states"] = {
        "white": {"range_min": 0, "range_max": 9, "value": 0, "settle_ms": 120},
        "red": {"range_min": 10, "range_max": 19, "value": 14, "settle_ms": 120},
        "blue": {"range_min": 20, "range_max": 29, "value": 26, "settle_ms": 140},
    }
    payload["discrete"]["gobo"] = {
        "offset": 18,
        "states": {
            "open": {"range_min": 0, "range_max": 7, "value": 0, "settle_ms": 150},
            "dots": {"range_min": 8, "range_max": 15, "value": 10, "settle_ms": 150},
            "star": {"range_min": 16, "range_max": 23, "value": 20, "settle_ms": 160},
        },
        "default_state": "open",
    }
    return payload


def discrete_step_payload() -> dict[str, Any]:
    """A physical step holding its pose with static shutter, color and gobo states."""
    return {
        "step_id": "look",
        "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 0.5}},
        "geometry": {},
        "movement": {
            "physical": {
                "shape": "hold",
                "mode": "periodic",
                "start_pan_deg": 0.0,
                "start_tilt_deg": 0.0,
            }
        },
        "dimmer": {},
        "physical_shutter_state": "open",
        "physical_color": "white",
        "physical_gobo": "open",
    }


def physical_step_payload() -> dict[str, Any]:
    """A physical-only template step: finite linear pan/tilt plus dimmer and shutter pulses."""
    return {
        "step_id": "main",
        "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 0.5}},
        "geometry": {},
        "movement": {
            "physical": {
                "shape": "linear",
                "mode": "finite",
                "start_pan_deg": 10.0,
                "start_tilt_deg": 20.0,
                "pan_extent_deg": 30.0,
                "tilt_extent_deg": 10.0,
                "period_beats": 1.0,
            }
        },
        "dimmer": {"physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}},
        "physical_shutter": {
            "period_beats": 2.0,
            "duty_cycle": 0.5,
            "low_state": "closed",
            "high_state": "open",
        },
    }


def assert_honest_transactions(
    result: PrepositionResult,
    inputs: Sequence[FixtureSegment],
    profile: FixtureCapabilities,
    initial: InitialFixtureState,
    *,
    locks: Sequence[RenderLock] = (),
    fixture_id: str = "MH1",
) -> None:
    """Check one fixture of a planned result from its encoded bytes and the profile alone.

    The head follows its commands: a pan/tilt word change at frame time `c` is reached
    at `max(previous arrival, c + latency_ms) + word distance / travel_speed_per_s` and
    settled `settle_ms` later; a wheel change settles its new state's `settle_ms` after
    `c`; an unknown value never settles. A frame is optically lit unless it is
    commanded dark (declared dimmer zero, or an extinguishing shutter state) by a run
    that started at least `close_latency_ms` (plus the shutter state's `settle_ms`) before;
    a run reaching time zero is dark already only through the mechanism the dark initial
    state evidences (its zero dimmer, or its own extinguishing shutter state).

    Asserted: the result encodes with the full footprint and covers every frame up to
    its end; a feasible cue's frames equal the cue encoded alone, a `preserve_aim` cue
    changes only its held pose, a dropped cue is commanded dark; no change outside a
    cue's own content moves or settles in a lit frame; a cue's own motion still under
    way when light returns after it went dark past its end is a leak; back-to-back cues
    step within one frame's travel and keep their wheels; a lit cue after a transaction
    reveals on its own frame; no locked frame differs from the cues alone.
    """
    assert not result.has_errors, result.diagnostics
    outputs = [s for s in result.segments if s.fixture_id == fixture_id]
    cues = [s for s in inputs if s.fixture_id == fixture_id]
    times = frame_times(max(s.t1_ms for s in outputs))
    count = len(times)
    out = [dict(f.channels) for f in encode_fixture_frames(outputs, profile, frame_times_ms=times)]
    alone = [dict(f.channels) for f in encode_fixture_frames(cues, profile, frame_times_ms=times)]
    footprint = list(range(1, profile.footprint + 1))
    assert all(sorted(frame) == footprint for frame in out)
    covered = {t for s in outputs for t in range(s.t0_ms, s.t1_ms, EFFECT_GRID_MS)}
    assert covered >= set(times), f"frames {sorted(set(times) - covered)[:5]} are not authored"

    status = {d.cue_ms: d.status for d in result.diagnostics if d.fixture_id == fixture_id}
    cue_at: list[FixtureSegment | None] = [None] * count
    for cue in cues:
        for index in range(cue.t0_ms // EFFECT_GRID_MS, cue.t1_ms // EFFECT_GRID_MS):
            cue_at[index] = cue

    visibility = profile.visibility
    dimmer = profile.axes.get("dimmer")
    shutter = profile.discrete.get("shutter")
    by_byte = {} if shutter is None else {s.value: n for n, s in shutter.states.items()}
    infinite = Fraction(10**12)
    # The initial state evidences darkness only through the mechanism it names: a dimmer
    # at zero that the profile declares extinguishing, or its own extinguishing shutter.
    initial_dimmer_dark = (
        initial.dark and visibility.dimmer_zero_extinguishes and initial.dimmer == 0
    )
    initial_shutter = initial.discrete_states.get("shutter") if initial.dark else None

    def dimmer_dark(frame: dict[int, int]) -> bool:
        return (
            visibility.dimmer_zero_extinguishes
            and dimmer is not None
            and _word(frame, dimmer) == dimmer.dmx_word(0)
        )

    def shutter_dark(frame: dict[int, int]) -> str | None:
        state = None if shutter is None else by_byte[frame[shutter.offset]]
        return state if state in visibility.extinguishing_shutter_states else None

    commanded_dark = [dimmer_dark(f) or shutter_dark(f) is not None for f in out]
    # A frame is lit if any part of it is; every query below starts on a frame start.
    lit: list[bool] = []
    dimmer_run = shutter_run = Fraction(0)
    for index, frame in enumerate(out):
        start = Fraction(times[index])
        dark_from = infinite
        close = visibility.close_latency_ms
        if dimmer_dark(frame):
            if index == 0 or not dimmer_dark(out[index - 1]):
                dimmer_run = -infinite if index == 0 and initial_dimmer_dark else start
            if dimmer_run == -infinite:  # dark initial state: evidence, no latency needed
                dark_from = -infinite
            elif close is not None:
                dark_from = min(dark_from, dimmer_run + close)
        state = shutter_dark(frame)
        if state is not None:
            if index == 0 or shutter_dark(out[index - 1]) != state:
                shutter_run = -infinite if index == 0 and state == initial_shutter else start
            settle = shutter.states[state].settle_ms if shutter is not None else None
            if shutter_run == -infinite:
                dark_from = -infinite
            elif close is not None and settle is not None:
                dark_from = min(dark_from, shutter_run + close + settle)
        lit.append(not commanded_dark[index] or dark_from > start)

    def lit_between(begin: Fraction, end: Fraction) -> int | None:
        first = max(0, int(begin // EFFECT_GRID_MS))
        for index in range(first, count):
            if times[index] >= end:
                break
            if lit[index] and times[index] + EFFECT_GRID_MS > begin:
                return times[index]
        return None

    def kind(index: int) -> str:
        if index == 0:
            return "transition"
        before, here = cue_at[index - 1], cue_at[index]
        if before is not None and before is here and status.get(here.t0_ms) != "drop_accent":
            return "content"
        if (
            before is not None
            and here is not None
            and before.t1_ms == here.t0_ms
            and status.get(before.t0_ms) == status.get(here.t0_ms) == "feasible"
        ):
            return "continuation"
        return "transition"

    def relit_after(cue: FixtureSegment) -> int | None:
        """The first lit frame after a commanded-dark frame, both at or after the cue's end."""
        seen_dark = False
        for index in range(cue.t1_ms // EFFECT_GRID_MS, count):
            if commanded_dark[index]:
                seen_dark = True
            elif seen_dark:
                return times[index]
        return None

    def check_busy(index: int, busy_end: Fraction, what: str) -> None:
        change = Fraction(times[index])
        if kind(index) == "transition":
            hit = lit_between(change, busy_end)
            assert hit is None, f"{what} changes at {change} ms and is lit at {hit} ms while busy"
            return
        cue = cue_at[index]
        assert cue is not None
        relit = relit_after(cue)
        if relit is not None:
            hit = lit_between(max(change, Fraction(relit)), busy_end)
            assert hit is None, f"{what} motion from {change} ms in {cue.segment_id} leaks to {hit}"

    initial_words: dict[int, int] = {}
    for name, axis in profile.axes.items():
        if name in ("pan", "tilt"):
            word = axis.dmx_word(initial.pan_deg if name == "pan" else initial.tilt_deg)
            initial_words |= _split(axis, word)
    for name, wheel in profile.discrete.items():
        initial_words[wheel.offset] = wheel.resolve(initial.discrete_states[name])

    for name, axis in profile.axes.items():
        if name not in ("pan", "tilt"):
            continue
        per_word = (Fraction(axis.physical_max) - Fraction(axis.physical_min)) / axis.full_word
        speed, latency, settle = axis.travel_speed_per_s, axis.latency_ms, axis.settle_ms
        arrival = Fraction(0)
        previous = _word(initial_words, axis)
        for index, frame in enumerate(out):
            word = _word(frame, axis)
            if word == previous:
                continue
            distance = abs(word - previous) * per_word
            previous = word
            if kind(index) == "continuation":
                assert speed is not None and distance <= Fraction(speed) * EFFECT_GRID_MS / 1000, (
                    f"{name} jumps {float(distance):g} across the cue at {times[index]} ms"
                )
            if speed is None or latency is None or settle is None:
                arrival = infinite
            else:
                arrival = max(
                    arrival, Fraction(times[index] + latency)
                ) + distance * 1000 / Fraction(speed)
            check_busy(index, arrival + (settle or 0), name)

    for name, wheel in profile.discrete.items():
        if name == "shutter":
            continue
        previous = initial_words[wheel.offset]
        for index, frame in enumerate(out):
            if frame[wheel.offset] == previous:
                continue
            previous = frame[wheel.offset]
            assert kind(index) != "continuation", f"{name} changes between back-to-back cues"
            selected = next(s for s in wheel.states.values() if s.value == previous)
            # A wheel is masked when it turns, so even an instant one needs a dark frame.
            settle_at = (
                infinite
                if selected.settle_ms is None
                else Fraction(times[index] + max(selected.settle_ms, 1))
            )
            check_busy(index, settle_at, name)

    pose_offsets = [o for c in (ChannelName.PAN, ChannelName.TILT) for o in _offsets(profile, c)]
    for cue in cues:
        span = range(cue.t0_ms // EFFECT_GRID_MS, cue.t1_ms // EFFECT_GRID_MS)
        cue_status = status.get(cue.t0_ms)
        if cue_status == "feasible":
            assert all(out[i] == alone[i] for i in span), f"cue {cue.segment_id} was changed"
        elif cue_status == "preserve_aim":
            for i in span:
                assert all(out[i][o] == alone[i][o] for o in footprint if o not in pose_offsets)
                assert all(out[i][o] == out[span[0]][o] for o in pose_offsets)
        elif cue_status == "drop_accent":
            assert all(commanded_dark[i] for i in span), f"dropped {cue.segment_id} is lit"
        else:
            raise AssertionError(f"cue {cue.segment_id} has no diagnostic")
        first = span[0]
        if first and cue_at[first - 1] is None and not commanded_dark[first]:
            assert commanded_dark[first - 1], f"cue {cue.segment_id} is revealed early"

    for lock in locks:
        if fixture_id not in lock.fixture_ids:
            continue
        start = lock.start_ms // EFFECT_GRID_MS * EFFECT_GRID_MS
        end = -(-lock.end_ms // EFFECT_GRID_MS) * EFFECT_GRID_MS
        offsets = [offset for channel in lock.channels for offset in _offsets(profile, channel)]
        for time_ms, frame, cue_frame in zip(times, out, alone, strict=True):
            if start <= time_ms < end:
                assert all(frame[o] == cue_frame[o] for o in offsets), f"lock changed at {time_ms}"


def _word(frame: dict[int, int], axis: AxisCapability) -> int:
    if axis.fine_offset is None:
        return frame[axis.coarse_offset]
    return frame[axis.coarse_offset] << 8 | frame[axis.fine_offset]


def _split(axis: AxisCapability, word: int) -> dict[int, int]:
    if axis.fine_offset is None:
        return {axis.coarse_offset: word}
    return {axis.coarse_offset: word >> 8, axis.fine_offset: word & 0xFF}


def _offsets(profile: FixtureCapabilities, channel: ChannelName) -> list[int]:
    if channel in AXIS_KEYS:
        axis = profile.axes.get(AXIS_KEYS[channel])
        if axis is None:
            return []
        return [axis.coarse_offset] + ([] if axis.fine_offset is None else [axis.fine_offset])
    wheel = profile.discrete.get(DISCRETE_KEYS[channel])
    return [] if wheel is None else [wheel.offset]
