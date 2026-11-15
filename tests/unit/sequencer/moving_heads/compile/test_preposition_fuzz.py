"""Seeded fuzz of the preposition pass against the byte-level oracle.

Random profiles (8/16-bit, inverted, narrowed windows, dimmer-only, shutter-only or
both darkness, latencies and speeds including unknown), cue sequences with sweeps and
pulses, locks, fallbacks and initial states. Every result must either carry an error
and no segments, or pass `assert_honest_transactions` for every fixture. The generator
follows the P1.5 reviewer's draw order, so their seeds reproduce the same cases.

The P2.4a arms (the section-entry bound) run the seeds known to catch each mutation
they guard against plus a short random sweep; set `TWINKLR_P24A_FUZZ=full` to sweep
900 and 800 seeds as at review. The P1.5 arms always run in full.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise
import os
import random
from typing import Any

import pytest

from tests.support.mh_physical import (
    assert_honest_transactions,
    discrete_profile_payload,
    preposition_profile_payload,
)
from twinklr.core.config.fixtures import AxisCapability, FixtureCapabilities, InitialFixtureState
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalChannelError,
    PhysicalPoint,
    RenderLock,
    TransitionDiagnostic,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import _check_travel_rate
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    FailureMode,
    follow_cues,
    follow_lag,
    plan_prepositions,
    worst_case_entry_ms,
)

_FRAME = 20
_REVIEW_SEEDS = (3911, 16042, 37040)
"""Seeds whose cases once raised a raw ValueError on a DMX rounding tie."""
TARGETED_SEEDS = 800

type _Case = tuple[
    list[FixtureSegment],
    dict[str, FixtureCapabilities],
    dict[str, InitialFixtureState],
    list[RenderLock],
    FailureMode,
    int,
]


def _profile(rng: random.Random, profile_id: str) -> FixtureCapabilities:
    return FixtureCapabilities.model_validate(_profile_payload(rng, profile_id))


def _profile_payload(
    rng: random.Random, profile_id: str, known: bool | None = None
) -> dict[str, Any]:
    """A random profile payload; `known` forces every timing to be declared."""
    if known is None:
        known = rng.random() < 0.8

    def pick(options: list[Any]) -> Any:
        return rng.choice([o for o in options if o is not None] if known else options)

    offsets = iter(range(1, 49))
    defaults: dict[int, int] = {}
    axes: dict[str, dict[str, Any]] = {}
    for name, (low, high) in (
        ("pan", rng.choice([(-270.0, 270.0), (0.0, 540.0)])),
        ("tilt", (-135.0, 135.0)),
    ):
        if name == "tilt" and rng.random() < 0.08:
            continue
        sixteen = rng.random() < 0.5
        axis: dict[str, Any] = {
            "unit": "degree",
            "physical_min": low,
            "physical_max": high,
            "coarse_offset": next(offsets),
            "inverted": rng.random() < 0.4,
        }
        if sixteen:
            axis["fine_offset"] = next(offsets)
        if rng.random() < 0.3:
            axis["allowed_min"] = low + 20.0
            axis["allowed_max"] = high - 30.0
        axis["travel_speed_per_s"] = pick([None, 90.0, 180.0, 360.0, 720.0, 45.5, 1000.0])
        axis["latency_ms"] = pick([None, 0, 0, 20, 40, 7])
        axis["settle_ms"] = pick([None, 0, 0, 20, 40, 33])
        axes[name] = axis
    has_dimmer = rng.random() < 0.8
    if has_dimmer:
        axes["dimmer"] = {
            "unit": "normalized",
            "physical_min": 0.0,
            "physical_max": 1.0,
            "coarse_offset": next(offsets),
            "inverted": rng.random() < 0.4,
        }
        if rng.random() < 0.3:
            axes["dimmer"]["fine_offset"] = next(offsets)
    discrete: dict[str, dict[str, Any]] = {}
    if rng.random() < 0.75:
        closed_byte = rng.randint(32, 95)
        states: dict[str, dict[str, Any]] = {
            "open": {
                "range_min": 0,
                "range_max": 31,
                "value": 8,
                "settle_ms": pick([None, 0, 0, 20, 30]),
            },
            "closed": {
                "range_min": 32,
                "range_max": 95,
                "value": closed_byte,
                "settle_ms": pick([None, 0, 0, 20, 30]),
            },
        }
        if rng.random() < 0.4:
            states["strobe"] = {
                "range_min": 96,
                "range_max": 127,
                "value": 100,
                "settle_ms": pick([None, 0, 0, 20, 30]),
            }
        discrete["shutter"] = {
            "offset": next(offsets),
            "states": states,
            "default_state": rng.choice(sorted(states)),
            "closed_state": "closed" if rng.random() < 0.8 else None,
            "open_state": "open" if rng.random() < 0.8 else None,
        }
    if rng.random() < 0.6:
        wheel = {
            name: {
                "range_min": low,
                "range_max": low + 9,
                "value": value,
                "settle_ms": pick([None, 0, 40, 120]),
            }
            for name, low, value in (("white", 0, 0), ("red", 10, 14), ("blue", 20, 26))
        }
        discrete["color"] = {
            "offset": next(offsets),
            "states": wheel,
            "default_state": rng.choice(sorted(wheel)),
        }
    if rng.random() < 0.3:
        gobo = {
            name: {
                "range_min": low,
                "range_max": low + 7,
                "value": value,
                "settle_ms": pick([None, 0, 40, 120]),
            }
            for name, low, value in (("open", 0, 0), ("dots", 8, 10))
        }
        discrete["gobo"] = {
            "offset": next(offsets),
            "states": gobo,
            "default_state": rng.choice(sorted(gobo)),
        }
    footprint = next(offsets)
    defaults[footprint] = rng.randint(0, 255)
    extinguishing: tuple[str, ...] = ()
    if "shutter" in discrete:
        names = [
            s
            for s in discrete["shutter"]["states"]
            if s not in (discrete["shutter"]["open_state"], "open")
        ]
        extinguishing = tuple(
            rng.sample(names, rng.randint(1 if known and "closed" in names else 0, len(names)))
        )
        if known and "closed" in names and "closed" not in extinguishing:
            extinguishing += ("closed",)
    visibility = {
        "dimmer_zero_extinguishes": has_dimmer and rng.random() < 0.7,
        "extinguishing_shutter_states": list(extinguishing),
        "close_latency_ms": pick([None, 0, 0, 20, 40, 30]),
        "open_latency_ms": pick([None, 0, 0, 20, 40]),
    }
    payload = {
        "profile_id": profile_id,
        "provenance": rng.choice(["synthetic", "manufacturer", "measured"]),
        "footprint": footprint,
        "defaults": defaults,
        "axes": axes,
        "discrete": discrete,
        "visibility": visibility,
    }
    for name, axis in axes.items():
        capability = AxisCapability.model_validate(axis)
        low, high = capability.operable_range
        value = (
            rng.choice([low, high, (low + high) / 2])
            if name != "dimmer"
            else rng.choice([0.0, 1.0, 0.5])
        )
        word = capability.dmx_word(value)
        if capability.fine_offset is None:
            defaults[capability.coarse_offset] = word
        else:
            defaults[capability.coarse_offset] = word >> 8
            defaults[capability.fine_offset] = word & 0xFF
    for wheel_spec in discrete.values():
        defaults[wheel_spec["offset"]] = wheel_spec["states"][wheel_spec["default_state"]]["value"]
    return payload


def _poses(rng: random.Random, profile: FixtureCapabilities) -> list[dict[str, float]]:
    poses = []
    for _ in range(3):
        pose = {}
        for name in ("pan", "tilt"):
            if name in profile.axes:
                low, high = profile.axes[name].operable_range
                pose[name] = float(
                    rng.choice([low, high, round(rng.uniform(low, high), 1), (low + high) / 2])
                )
        poses.append(pose)
    return poses


def _initial(
    rng: random.Random, profile: FixtureCapabilities, poses: list[dict[str, float]]
) -> InitialFixtureState:
    pose = rng.choice(poses)
    states = {name: rng.choice(sorted(d.states)) for name, d in profile.discrete.items()}
    dimmer = rng.choice([0.0, 0.5, 1.0]) if "dimmer" in profile.axes else None
    visibility = profile.visibility
    declared_dark = (visibility.dimmer_zero_extinguishes and dimmer == 0) or (
        states.get("shutter") in visibility.extinguishing_shutter_states
    )
    dark = declared_dark if rng.random() < 0.9 else rng.random() < 0.5
    return InitialFixtureState(
        pan_deg=pose.get("pan", 0.0),
        tilt_deg=pose.get("tilt", 0.0),
        dimmer=dimmer,
        discrete_states=states,
        settled=rng.random() < 0.97,
        dark=dark,
    )


def _line(start: float, end: float, t0: int, t1: int) -> ContinuousTrajectory:
    return ContinuousTrajectory(
        unit="degree",
        points=(PhysicalPoint(t_ms=t0, value=start), PhysicalPoint(t_ms=t1, value=end)),
        interpolation="linear",
    )


def _cue(
    rng: random.Random,
    profile: FixtureCapabilities,
    fixture_id: str,
    name: str,
    t0: int,
    t1: int,
    pose: dict[str, float],
    bias: bool,
) -> FixtureSegment:
    channels: dict[ChannelName, ContinuousTrajectory | DiscreteTrajectory] = {}
    duration = t1 - t0
    for key, channel in (("pan", ChannelName.PAN), ("tilt", ChannelName.TILT)):
        if key not in profile.axes:
            continue
        axis = profile.axes[key]
        start = end = pose[key]
        if axis.travel_speed_per_s and rng.random() < 0.25 and duration >= 60:
            low, high = axis.operable_range
            reach = axis.travel_speed_per_s * duration / 1000 * 0.9
            end = max(low, min(high, start + rng.uniform(-reach, reach)))
        channels[channel] = _line(start, end, t0, t1)
    if "dimmer" in profile.axes:
        if rng.random() < 0.7:
            points: tuple[PhysicalPoint, ...] = (
                PhysicalPoint(t_ms=t0, value=rng.choice([0.0, 0.3, 1.0, 1.0])),
            )
        else:
            step = rng.choice([1, 2, 5]) * _FRAME
            levels = [1.0, 0.0] if rng.random() < 0.5 else [0.0, 1.0]
            points = tuple(
                PhysicalPoint(t_ms=t, value=levels[i % 2])
                for i, t in enumerate(range(t0, t1, step))
            )
        channels[ChannelName.DIMMER] = ContinuousTrajectory(
            unit="normalized", points=points, interpolation="hold"
        )
    for key, channel in (
        ("shutter", ChannelName.SHUTTER),
        ("color", ChannelName.COLOR),
        ("gobo", ChannelName.GOBO),
    ):
        if key not in profile.discrete or rng.random() < 0.15:
            continue
        states = sorted(profile.discrete[key].states)
        if bias and key != "shutter" and rng.random() < 0.7:
            states = states[:1]
        if key == "shutter" and rng.random() < 0.25 and duration >= 80:
            step = rng.choice([1, 2, 4, 10]) * _FRAME
            a, b = rng.sample(states, 2)
            events = tuple(
                DiscretePoint(t_ms=t, state=(a, b)[i % 2])
                for i, t in enumerate(range(t0, t1, step))
            )
            channels[channel] = DiscreteTrajectory(events=events)
        else:
            channels[channel] = DiscreteTrajectory(
                events=(DiscretePoint(t_ms=t0, state=rng.choice(states)),)
            )
    return FixtureSegment(
        section_id=f"sec-{name}",
        segment_id=name,
        step_id="step",
        template_id="tpl",
        fixture_id=fixture_id,
        t0_ms=t0,
        t1_ms=t1,
        channels={c: ChannelValue(channel=c, physical=v) for c, v in channels.items()},
    )


def _case(
    seed: int, bias: bool
) -> tuple[
    list[FixtureSegment],
    dict[str, FixtureCapabilities],
    dict[str, InitialFixtureState],
    list[RenderLock],
    FailureMode,
    int,
]:
    rng = random.Random(seed)
    profiles: dict[str, FixtureCapabilities] = {}
    initials: dict[str, InitialFixtureState] = {}
    segments: list[FixtureSegment] = []
    for index in range(rng.choice([1, 1, 1, 2])):
        fixture_id = f"MH{index + 1}"
        profile = profiles[fixture_id] = _profile(rng, f"p{index}")
        poses = _poses(rng, profile)
        if rng.random() < 0.97:
            initial = initials[fixture_id] = _initial(rng, profile, poses)
            poses.append({"pan": initial.pan_deg, "tilt": initial.tilt_deg})
        t = 0 if rng.random() < 0.3 else rng.choice([0, 20, 40, 200, 1000, 1040, 1080, 2000])
        for cue_index in range(rng.randint(2, 6)):
            duration = rng.choice([20, 40, 60, 100, 200, 400, 1000])
            pose = {k: v for k, v in rng.choice(poses).items() if k in profile.axes}
            if segments and segments[-1].fixture_id == fixture_id and rng.random() < 0.3:
                # Continue from the previous cue's last frame.
                previous, pose = segments[-1], {}
                for key, channel in (("pan", ChannelName.PAN), ("tilt", ChannelName.TILT)):
                    if channel in previous.channels:
                        trajectory = previous.channels[channel].physical
                        assert isinstance(trajectory, ContinuousTrajectory)
                        a, b = trajectory.points[0], trajectory.points[-1]
                        last = previous.t1_ms - _FRAME
                        value = a.value + (b.value - a.value) * (last - a.t_ms) / (b.t_ms - a.t_ms)
                        low, high = profile.axes[key].operable_range
                        pose[key] = min(high, max(low, value))
            segments.append(
                _cue(
                    rng,
                    profile,
                    fixture_id,
                    f"{fixture_id}-c{cue_index}",
                    t,
                    t + duration,
                    pose,
                    bias,
                )
            )
            gaps = (
                [0, 20, 40, 300, 1040, 2000, 3000, 4000, 6000]
                if bias
                else [0, 0, 20, 40, 60, 100, 300, 1000, 1040, 1080, 2000, 3000]
            )
            t += duration + rng.choice(gaps)
    locks = []
    last_end = max(s.t1_ms for s in segments)
    for _ in range(rng.choice([0, 0, 1, 2])):
        start = rng.randint(0, last_end)
        channels = [ChannelName.PAN, ChannelName.TILT, ChannelName.DIMMER, ChannelName.SHUTTER]
        channels += [ChannelName.COLOR, ChannelName.GOBO]
        locks.append(
            RenderLock(
                start_ms=start,
                end_ms=start + rng.randint(1, 400),
                fixture_ids=tuple(rng.sample(sorted(profiles), 1)),
                channels=tuple(rng.sample(channels, rng.randint(1, 3))),
            )
        )
    mode: FailureMode = rng.choice(["error", "error", "preserve_aim", "drop_accent"])
    for segment in segments:
        if rng.random() < 0.5:
            segment.metadata["preposition_fallback"] = rng.choice(["preserve_aim", "drop_accent"])
    rng.shuffle(segments)
    sequence_end = last_end + rng.choice([0, 0, 200, 1000])
    return segments, profiles, initials, locks, mode, sequence_end


def _last_pose(previous: FixtureSegment, profile: FixtureCapabilities) -> dict[str, float]:
    """The pose a cue commands on its last frame, inside the operable window."""
    pose = {}
    for key, channel in (("pan", ChannelName.PAN), ("tilt", ChannelName.TILT)):
        if channel in previous.channels:
            trajectory = previous.channels[channel].physical
            assert isinstance(trajectory, ContinuousTrajectory)
            a, b = trajectory.points[0], trajectory.points[-1]
            last = previous.t1_ms - _FRAME
            value = a.value + (b.value - a.value) * (last - a.t_ms) / (b.t_ms - a.t_ms)
            low, high = profile.axes[key].operable_range
            pose[key] = min(high, max(low, value))
    return pose


def _targeted_case(seed: int, unknown_rate: float) -> _Case:
    """One fixture planned close to the edge of what the pass claims feasible.

    Timings are declared (each left unknown with `unknown_rate`), darkness is declared,
    the initial state is settled and dark where the profile can be, and a cue is often
    posed at the previous cue's last-frame value. A third of the gaps are "tight": the
    cue is placed exactly the planner's own `required_ms` after the previous one, so
    any under-estimate of travel, latency, settle or leftover motion reaches the oracle
    instead of hiding in slack. Locks fall inside gaps and cues alike.
    """
    rng = random.Random(seed)
    payload = _profile_payload(rng, "p0", known=True)
    visibility = payload["visibility"]
    if (
        not visibility["dimmer_zero_extinguishes"]
        and not visibility["extinguishing_shutter_states"]
    ):
        if "dimmer" in payload["axes"]:
            visibility["dimmer_zero_extinguishes"] = True
        elif "shutter" in payload["discrete"]:
            visibility["extinguishing_shutter_states"] = ["closed"]
    timings = [
        (axis, key)
        for axis in payload["axes"].values()
        if axis["unit"] == "degree"
        for key in ("travel_speed_per_s", "latency_ms", "settle_ms")
    ]
    timings += [
        (state, "settle_ms")
        for wheel in payload["discrete"].values()
        for state in wheel["states"].values()
    ]
    timings += [(visibility, "close_latency_ms"), (visibility, "open_latency_ms")]
    for owner, key in timings:
        if rng.random() < unknown_rate:
            owner[key] = None
    profile = FixtureCapabilities.model_validate(payload)
    visibility_capability = profile.visibility

    poses = _poses(rng, profile)
    states = {name: rng.choice(sorted(d.states)) for name, d in profile.discrete.items()}
    dimmer = 0.0 if visibility_capability.dimmer_zero_extinguishes else 1.0
    if not visibility_capability.dimmer_zero_extinguishes and "shutter" in states:
        extinguishing = visibility_capability.extinguishing_shutter_states
        if extinguishing:
            states["shutter"] = extinguishing[0]
    dark = (visibility_capability.dimmer_zero_extinguishes and dimmer == 0) or (
        states.get("shutter") in visibility_capability.extinguishing_shutter_states
    )
    start_pose = rng.choice(poses)
    initial = InitialFixtureState(
        pan_deg=start_pose.get("pan", 0.0),
        tilt_deg=start_pose.get("tilt", 0.0),
        dimmer=dimmer if "dimmer" in profile.axes else None,
        discrete_states=states,
        settled=True,
        dark=dark,
    )
    # Sometimes the initial state is dark by one mechanism and the first cue, at time
    # zero, darkens by the other while it turns a wheel: initial evidence must not
    # carry over to a mechanism it does not cover.
    switch = _mechanism_switch(rng, profile, initial)
    if switch is not None:
        initial = switch

    # Sometimes a fallback chain: a cue given too little time to reach a far pose (so
    # it is often substituted), then one right after it posed a single frame's travel
    # from the aim the head held, which only a continuation of the emitted state allows.
    chain = switch is None and rng.random() < 0.3
    start_pose = {k: v for k, v in start_pose.items() if k in profile.axes}

    segments: list[FixtureSegment] = []
    t = 0 if switch is not None else rng.choice([0, 1000, 2000, 4000])
    for cue_index in range(rng.randint(1, 2) if switch is not None else rng.randint(2, 6)):
        duration = rng.choice([60, 100, 200, 400, 1000])
        if segments and rng.random() < 0.6:
            pose = _last_pose(segments[-1], profile)
        else:
            pose = {k: v for k, v in rng.choice(poses).items() if k in profile.axes}
        name = f"MH1-c{cue_index}"
        kind = rng.random()
        if chain and cue_index % 2 == 1:
            held = _last_pose(segments[-2], profile) if len(segments) > 1 else start_pose
            pose = _nudged(rng, profile, held)
            cue = _targeted_cue(rng, profile, name, t, t + duration, pose, segments)
        elif chain:
            gap = _FRAME if segments else rng.choice([_FRAME, 2 * _FRAME])
            cue = _targeted_cue(rng, profile, name, t + gap, t + gap + duration, pose, segments)
        elif segments and kind < 0.35:
            # Tight: ask the planner what this cue needs, then give it exactly that.
            far = t + 10_000
            probe = _targeted_cue(rng, profile, name, far, far + duration, pose, segments)
            planned = plan_prepositions(
                [*segments, probe],
                {"MH1": profile},
                initial_states={"MH1": initial},
                locks=(),
                frame_ms=_FRAME,
                sequence_end_ms=far + duration,
            )
            need = next((d.required_ms for d in planned.diagnostics if d.cue_ms == far), None)
            gap = 10_000 if planned.has_errors or need is None else max(need, _FRAME)
            cue = _shifted(probe, t + gap - far)
        else:
            gap = (
                rng.choice([0, 20, 40, 60, 80])
                if kind < 0.7 or not segments
                else rng.choice([2000, 4000, 8000])
            )
            if not segments:
                gap = 0
            cue = _targeted_cue(rng, profile, name, t + gap, t + gap + duration, pose, segments)
        if switch is not None and not segments:
            cue = _darken_by_other_mechanism(rng, profile, initial, cue)
        segments.append(cue)
        t = cue.t1_ms

    locks = []
    if rng.random() < 0.35:
        spans = [(a.t1_ms, b.t0_ms) for a, b in pairwise(segments) if b.t0_ms > a.t1_ms]
        spans += [(c.t0_ms, c.t1_ms) for c in segments]
        low, high = rng.choice(spans)
        start = rng.randrange(low, high, _FRAME)
        locks.append(
            RenderLock(
                start_ms=start,
                end_ms=start + _FRAME * rng.randint(1, 3),
                fixture_ids=("MH1",),
                channels=tuple(rng.sample(list(ChannelName), rng.randint(1, 2))),
            )
        )
    mode: FailureMode = "error"
    if chain or rng.random() < 0.2:
        # Only preserve_aim leaves a cue whose emitted end differs from its content.
        mode = (
            "preserve_aim"
            if chain and rng.random() < 0.8
            else rng.choice(["preserve_aim", "drop_accent"])
        )
        for segment in segments:
            segment.metadata["preposition_fallback"] = mode
    sequence_end = t + rng.choice([0, 20, 200, 2000])
    return segments, {"MH1": profile}, {"MH1": initial}, locks, mode, sequence_end


def _nudged(
    rng: random.Random, profile: FixtureCapabilities, pose: dict[str, float]
) -> dict[str, float]:
    """`pose` moved by less than one frame's travel on each axis, inside the window."""
    nudged = {}
    for key, value in pose.items():
        axis = profile.axes[key]
        reach = (axis.travel_speed_per_s or 0) * _FRAME / 1000 * rng.uniform(0.2, 0.8)
        low, high = axis.operable_range
        nudged[key] = max(low, min(high, value + rng.choice([-1, 1]) * reach))
    return nudged


def _mechanism_switch(
    rng: random.Random, profile: FixtureCapabilities, initial: InitialFixtureState
) -> InitialFixtureState | None:
    """A dark initial state evidenced by only one mechanism, a quarter of the time."""
    visibility = profile.visibility
    shutter = profile.discrete.get("shutter")
    if (
        rng.random() >= 0.25
        or not visibility.dimmer_zero_extinguishes
        or not visibility.extinguishing_shutter_states
        or shutter is None
    ):
        return None
    open_state = next(
        s for s in sorted(shutter.states) if s not in visibility.extinguishing_shutter_states
    )
    by_dimmer = rng.random() < 0.5
    states = {**initial.discrete_states}
    states["shutter"] = open_state if by_dimmer else visibility.extinguishing_shutter_states[0]
    return initial.model_copy(
        update={"dimmer": 0.0 if by_dimmer else 1.0, "discrete_states": states, "dark": True}
    )


def _darken_by_other_mechanism(
    rng: random.Random,
    profile: FixtureCapabilities,
    initial: InitialFixtureState,
    cue: FixtureSegment,
) -> FixtureSegment:
    """The first cue at the initial aim, dark only by the mechanism the initial state
    does not evidence, selecting a different wheel state."""
    visibility = profile.visibility
    shutter = profile.discrete["shutter"]
    by_dimmer = initial.dimmer == 0
    open_state = next(
        s for s in sorted(shutter.states) if s not in visibility.extinguishing_shutter_states
    )
    t0 = cue.t0_ms
    channels = dict(cue.channels)
    pose = {ChannelName.PAN: initial.pan_deg, ChannelName.TILT: initial.tilt_deg}
    for channel in list(channels):
        if channel in pose:
            line = _line(pose[channel], pose[channel], t0, cue.t1_ms)
            channels[channel] = ChannelValue(channel=channel, physical=line)
    level = ContinuousTrajectory(
        unit="normalized",
        points=(PhysicalPoint(t_ms=t0, value=1.0 if by_dimmer else 0.0),),
        interpolation="hold",
    )
    channels[ChannelName.DIMMER] = ChannelValue(channel=ChannelName.DIMMER, physical=level)
    state = visibility.extinguishing_shutter_states[0] if by_dimmer else open_state
    channels[ChannelName.SHUTTER] = ChannelValue(
        channel=ChannelName.SHUTTER,
        physical=DiscreteTrajectory(events=(DiscretePoint(t_ms=t0, state=state),)),
    )
    for key, channel in (("color", ChannelName.COLOR), ("gobo", ChannelName.GOBO)):
        wheel = profile.discrete.get(key)
        if wheel is not None:
            others = [s for s in sorted(wheel.states) if s != initial.discrete_states[key]]
            # A wheel that settles at once leaves only the darkness itself to time.
            instant = [s for s in others if wheel.states[s].settle_ms == 0]
            selected = DiscreteTrajectory(
                events=(DiscretePoint(t_ms=t0, state=rng.choice(instant or others)),)
            )
            channels[channel] = ChannelValue(channel=channel, physical=selected)
    return cue.model_copy(update={"channels": channels})


def _targeted_cue(
    rng: random.Random,
    profile: FixtureCapabilities,
    name: str,
    t0: int,
    t1: int,
    pose: dict[str, float],
    before: list[FixtureSegment],
) -> FixtureSegment:
    """A held or sweeping cue, lit or dark, mostly keeping the previous cue's wheels."""
    channels: dict[ChannelName, ContinuousTrajectory | DiscreteTrajectory] = {}
    for key, channel in (("pan", ChannelName.PAN), ("tilt", ChannelName.TILT)):
        if key not in profile.axes:
            continue
        axis = profile.axes[key]
        start = end = pose[key]
        if axis.travel_speed_per_s and rng.random() < 0.4:
            low, high = axis.operable_range
            reach = axis.travel_speed_per_s * (t1 - t0) / 1000 * 0.9
            end = max(low, min(high, start + rng.uniform(-reach, reach)))
        channels[channel] = _line(start, end, t0, t1)
    lit = rng.random() < 0.75
    if "dimmer" in profile.axes:
        level = rng.choice([1.0, 0.3]) if lit else 0.0
        channels[ChannelName.DIMMER] = ContinuousTrajectory(
            unit="normalized", points=(PhysicalPoint(t_ms=t0, value=level),), interpolation="hold"
        )
    for key, channel in (
        ("shutter", ChannelName.SHUTTER),
        ("color", ChannelName.COLOR),
        ("gobo", ChannelName.GOBO),
    ):
        if key not in profile.discrete:
            continue
        options = sorted(profile.discrete[key].states)
        if key == "shutter":
            dark_states = profile.visibility.extinguishing_shutter_states
            open_states = [state for state in options if state not in dark_states]
            state = rng.choice(open_states if lit or not dark_states else list(dark_states))
        elif before and channel in before[-1].channels and rng.random() < 0.7:
            previous = before[-1].channels[channel].physical
            assert isinstance(previous, DiscreteTrajectory)
            state = previous.events[-1].state
        else:
            state = rng.choice(options)
        channels[channel] = DiscreteTrajectory(events=(DiscretePoint(t_ms=t0, state=state),))
    return FixtureSegment(
        section_id=f"sec-{name}",
        segment_id=name,
        step_id="step",
        template_id="tpl",
        fixture_id="MH1",
        t0_ms=t0,
        t1_ms=t1,
        channels={c: ChannelValue(channel=c, physical=v) for c, v in channels.items()},
    )


def _shifted(segment: FixtureSegment, offset: int) -> FixtureSegment:
    """The same cue `offset` ms earlier or later."""
    channels: dict[ChannelName, ChannelValue] = {}
    for channel, value in segment.channels.items():
        physical = value.physical
        if isinstance(physical, ContinuousTrajectory):
            moved: ContinuousTrajectory | DiscreteTrajectory = physical.model_copy(
                update={
                    "points": tuple(
                        p.model_copy(update={"t_ms": p.t_ms + offset}) for p in physical.points
                    )
                }
            )
        else:
            assert isinstance(physical, DiscreteTrajectory)
            moved = physical.model_copy(
                update={
                    "events": tuple(
                        e.model_copy(update={"t_ms": e.t_ms + offset}) for e in physical.events
                    )
                }
            )
        channels[channel] = ChannelValue(channel=channel, physical=moved)
    return segment.model_copy(
        update={
            "t0_ms": segment.t0_ms + offset,
            "t1_ms": segment.t1_ms + offset,
            "channels": channels,
        }
    )


def _check(case: _Case, seed: int) -> bool:
    """Plan one case and check it; return whether the plan was feasible."""
    segments, profiles, initials, locks, mode, sequence_end = case
    result = plan_prepositions(
        segments,
        profiles,
        initial_states=initials,
        locks=locks,
        frame_ms=_FRAME,
        failure_mode=mode,
        sequence_end_ms=sequence_end,
    )
    if result.has_errors:
        assert result.segments == (), seed
        return False
    for fixture_id, profile in profiles.items():
        assert_honest_transactions(
            result, segments, profile, initials[fixture_id], locks=locks, fixture_id=fixture_id
        )
        covered = max(s.t1_ms for s in result.segments if s.fixture_id == fixture_id)
        assert covered == sequence_end, (seed, fixture_id, covered, sequence_end)
    return True


_ARMS: dict[str, Callable[[int], _Case]] = {
    "unbiased": lambda seed: _case(seed, bias=False),
    "biased": lambda seed: _case(seed, bias=True),
    "targeted": lambda seed: _targeted_case(seed, unknown_rate=0.0),
    "targeted-unknowns": lambda seed: _targeted_case(seed, unknown_rate=0.15),
}


@pytest.mark.parametrize(
    ("arm", "seeds", "min_feasible"),
    [
        pytest.param("unbiased", range(600), 0.03, id="unbiased"),
        pytest.param("biased", range(600), 0.04, id="biased-toward-feasible"),
        pytest.param("targeted", range(TARGETED_SEEDS), 0.17, id="targeted"),
        pytest.param("targeted-unknowns", range(TARGETED_SEEDS), 0.09, id="targeted-unknowns"),
        pytest.param("unbiased", _REVIEW_SEEDS, 0.0, id="review-seeds"),
    ],
)
def test_every_feasible_plan_passes_the_byte_oracle(
    arm: str, seeds: range | tuple[int, ...], min_feasible: float
) -> None:
    feasible = 0
    for seed in seeds:
        try:
            feasible += _check(_ARMS[arm](seed), seed)
        except AssertionError as error:
            raise AssertionError(f"{arm} seed {seed}: {error}") from error
    assert feasible >= min_feasible * len(seeds), (
        f"{arm}: only {feasible} of {len(seeds)} plans feasible; the fuzz has degraded"
    )


# --- The section-entry bound (P2.4a) ------------------------------------------------------

_FULL_FUZZ = os.environ.get("TWINKLR_P24A_FUZZ") == "full"
"""`TWINKLR_P24A_FUZZ=full` runs the P2.4a fuzz at the counts it was reviewed at."""
BOUND_SEEDS = 900 if _FULL_FUZZ else 150
_BOUND_KNOWN: dict[str, tuple[int, ...]] = {
    # Seeds the default run keeps because they catch a dropped bound term: darkness
    # (static 44, 249; moving 49, 132; short-wheel 234, 272) and predecessor motion
    # (moving 120, 187; short-wheel 120, 359). Wheel and travel terms are caught by
    # dozens of seeds in every sweep.
    "static": (44, 249),
    "moving": (49, 132, 120, 187),
    "short-wheel": (234, 272, 120, 359),
}
_POSE_KEYS = (("pan", ChannelName.PAN), ("tilt", ChannelName.TILT))
_WHEEL_KEYS = (("color", ChannelName.COLOR), ("gobo", ChannelName.GOBO))

type _Range = tuple[float, float]


def _span(rng: random.Random, low: float, high: float) -> _Range:
    """A random sub-range of `[low, high]`, a single pose a third of the time."""
    a = rng.choice([low, high, rng.uniform(low, high)])
    b = a if rng.random() < 1 / 3 else rng.choice([low, high, rng.uniform(low, high)])
    return min(a, b), max(a, b)


def _bound_case(
    seed: int, kind: str
) -> tuple[
    FixtureCapabilities,
    InitialFixtureState,
    list[FixtureSegment],
    dict[ChannelName, _Range],
    dict[ChannelName, set[str]],
    dict[ChannelName, _Range],
]:
    """A predecessor, then (a minute later) a target cue entered from it.

    `static`: the run's initial state, anywhere inside a random envelope, with any wheel,
    dimmer and shutter state. `moving`: a predecessor cue moving at exactly the
    configured speed on every axis up to its last frame, enveloped by the pose its last
    frame commands (or a random envelope around it). `short-wheel`: a one-to-three
    frame predecessor, often moving, that selects other wheel states than the initial
    ones. Latency and settle are zero on the pose axes in half the cases. The target
    holds a pose drawn from a random entry range and a wheel state from random entry
    sets. Returns the profile, initial state, cues and the bound's three inputs.
    """
    rng = random.Random(seed)
    payload = _profile_payload(rng, "p0", known=True)
    visibility = payload["visibility"]
    if (
        not visibility["dimmer_zero_extinguishes"]
        and not visibility["extinguishing_shutter_states"]
    ):
        if "dimmer" in payload["axes"]:
            visibility["dimmer_zero_extinguishes"] = True
        elif "shutter" in payload["discrete"]:
            visibility["extinguishing_shutter_states"] = ["closed"]
    if rng.random() < 0.5:
        for key, _ in _POSE_KEYS:
            if key in payload["axes"]:
                payload["axes"][key].update(latency_ms=0, settle_ms=0)
    if kind != "static" and rng.random() < 0.3:
        # Coarse and slow: one 8-bit pan word takes 46 ms at 45.5 degrees/s, more than a
        # frame, so a predecessor at the speed limit can trail its commands by more.
        visibility["close_latency_ms"] = 0
        for key, _ in _POSE_KEYS:
            axis = payload["axes"].get(key)
            if axis is not None:
                axis.pop("fine_offset", None)
                axis["travel_speed_per_s"] = 45.5
                capability = AxisCapability.model_validate(axis)
                payload["defaults"][axis["coarse_offset"]] = capability.dmx_word(
                    sum(capability.operable_range) / 2
                )
    profile = FixtureCapabilities.model_validate(payload)
    axes = {ch: profile.axes[key] for key, ch in _POSE_KEYS if key in profile.axes}
    wheels = {ch: profile.discrete[key] for key, ch in _WHEEL_KEYS if key in profile.discrete}
    shutter = profile.discrete.get("shutter")
    dark_states = profile.visibility.extinguishing_shutter_states

    def uniform(span: _Range) -> float:
        return rng.uniform(*span) if rng.random() < 0.6 else rng.choice(span)

    def looks(lit: bool) -> dict[ChannelName, ContinuousTrajectory | DiscreteTrajectory]:
        """Dimmer and shutter (lit, or dark by every declared mechanism), at time 0."""
        channels: dict[ChannelName, ContinuousTrajectory | DiscreteTrajectory] = {}
        if "dimmer" in profile.axes:
            level = PhysicalPoint(t_ms=0, value=1.0 if lit else 0.0)
            channels[ChannelName.DIMMER] = ContinuousTrajectory(
                unit="normalized", points=(level,), interpolation="hold"
            )
        if shutter is not None:
            options = [s for s in sorted(shutter.states) if (s in dark_states) != lit]
            state = rng.choice(options or sorted(shutter.states))
            channels[ChannelName.SHUTTER] = DiscreteTrajectory(
                events=(DiscretePoint(t_ms=0, state=state),)
            )
        return channels

    def cue(
        name: str,
        t0: int,
        t1: int,
        poses: dict[ChannelName, _Range],
        selected: dict[ChannelName, str],
    ) -> FixtureSegment:
        channels = looks(rng.random() < 0.7)
        channels = {c: _shifted_value(v, t0) for c, v in channels.items()}
        for channel, (start, end) in poses.items():
            channels[channel] = _line(start, end, t0, t1)
        for channel, state in selected.items():
            channels[channel] = DiscreteTrajectory(events=(DiscretePoint(t_ms=t0, state=state),))
        return FixtureSegment(
            section_id=name,
            segment_id=name,
            step_id="step",
            template_id="tpl",
            fixture_id="MH1",
            t0_ms=t0,
            t1_ms=t1,
            channels={c: ChannelValue(channel=c, physical=v) for c, v in channels.items()},
        )

    windows = {ch: axis.operable_range for ch, axis in axes.items()}
    entry_pose = {ch: _span(rng, *window) for ch, window in windows.items()}
    entry_wheels = {
        ch: set(rng.sample(sorted(w.states), rng.randint(1, len(w.states))))
        for ch, w in wheels.items()
    }
    initial_wheels = {ch: rng.choice(sorted(w.states)) for ch, w in wheels.items()}
    states = {key: initial_wheels[ch] for key, ch in _WHEEL_KEYS if ch in initial_wheels}
    if shutter is not None:
        states["shutter"] = rng.choice(sorted(shutter.states))

    cues: list[FixtureSegment] = []
    if kind == "static":
        envelope = {ch: _span(rng, *window) for ch, window in windows.items()}
        start = {ch: uniform(span) for ch, span in envelope.items()}
        end_ms = 0
    else:
        start = {ch: rng.uniform(*window) for ch, window in windows.items()}
        frames = rng.randint(1, 3) if kind == "short-wheel" else rng.choice([1, 2, 5, 20, 60])
        t0 = 60_000
        t1 = t0 + frames * _FRAME
        poses: dict[ChannelName, _Range] = {}
        for ch, axis in axes.items():
            low, high = windows[ch]
            assert axis.travel_speed_per_s is not None
            reach = axis.travel_speed_per_s * frames * _FRAME / 1000
            if kind == "short-wheel" and rng.random() < 0.3:
                reach = 0.0  # a held predecessor that only turns its wheels
            reach = min(reach, high - low)
            direction = rng.choice([-1, 1])
            begin = (
                rng.uniform(low, high - reach) if direction > 0 else rng.uniform(low + reach, high)
            )
            poses[ch] = (begin, begin + direction * reach)
        selected = {ch: rng.choice(sorted(w.states)) for ch, w in wheels.items()}
        if kind == "short-wheel":
            for ch, w in wheels.items():
                others = [s for s in sorted(w.states) if s != initial_wheels[ch]]
                selected[ch] = rng.choice(others or sorted(w.states))
        cues.append(cue("pred", t0, t1, poses, selected))
        # The pose the predecessor's last frame commands, where the next gap starts.
        last = {
            ch: begin + (end - begin) * (frames - 1) / frames for ch, (begin, end) in poses.items()
        }
        envelope = {
            ch: (last[ch], last[ch])
            if rng.random() < 0.6
            else _span_around(rng, last[ch], windows[ch])
            for ch in axes
        }
        if rng.random() < 0.3:
            # Entered at the aim the predecessor left: only its unfinished motion is timed.
            entry_pose = {ch: (last[ch], last[ch]) for ch in axes}
        end_ms = t1

    dimmer = rng.choice([0.0, 1.0]) if "dimmer" in profile.axes else None
    dark = (profile.visibility.dimmer_zero_extinguishes and dimmer == 0) or (
        states.get("shutter") in dark_states
    )
    initial = InitialFixtureState(
        pan_deg=start.get(ChannelName.PAN, 0.0),
        tilt_deg=start.get(ChannelName.TILT, 0.0),
        dimmer=dimmer,
        discrete_states=states,
        settled=True,
        dark=dark,
    )
    target_t0 = end_ms + 60_000
    target_pose = {ch: uniform(span) for ch, span in entry_pose.items()}
    target_wheels = {ch: rng.choice(sorted(options)) for ch, options in entry_wheels.items()}
    cues.append(
        cue(
            "target",
            target_t0,
            target_t0 + 200,
            {ch: (pose, pose) for ch, pose in target_pose.items()},
            target_wheels,
        )
    )
    return profile, initial, cues, entry_pose, entry_wheels, envelope


def _span_around(rng: random.Random, value: float, window: _Range) -> _Range:
    """A random range inside `window` that contains `value`."""
    return rng.uniform(window[0], value), rng.uniform(value, window[1])


def _shifted_value(
    value: ContinuousTrajectory | DiscreteTrajectory, t0: int
) -> ContinuousTrajectory | DiscreteTrajectory:
    """A trajectory authored at time 0, moved to start at `t0`."""
    if isinstance(value, ContinuousTrajectory):
        points = tuple(p.model_copy(update={"t_ms": p.t_ms + t0}) for p in value.points)
        return value.model_copy(update={"points": points})
    events = tuple(e.model_copy(update={"t_ms": e.t_ms + t0}) for e in value.events)
    return value.model_copy(update={"events": events})


def _check_bound(kind: str, seed: int) -> bool:
    """Check one bound case; return whether it had an entry to check.

    A case whose predecessor itself cannot be planned (a shutter state too short for its
    latency, say) has no entry to check.
    """
    profile, initial, cues, entry_pose, entry_wheels, envelope = _bound_case(seed, kind)
    bound = worst_case_entry_ms(
        profile,
        entry_pose=entry_pose,
        entry_wheels=entry_wheels,
        pose_envelope=envelope,
        frame_ms=_FRAME,
    )
    visibility, closer = profile.visibility, profile.discrete.get("shutter")
    if bound is None:
        # Every timing is declared, so only a missing darkness guarantee is unknown: a
        # predecessor may hold an open shutter that no declared state replaces.
        assert not visibility.dimmer_zero_extinguishes, (kind, seed)
        assert closer is None or closer.closed_state not in (
            visibility.extinguishing_shutter_states
        ), (kind, seed)
        return False
    result = plan_prepositions(
        cues,
        {"MH1": profile},
        initial_states={"MH1": initial},
        locks=(),
        frame_ms=_FRAME,
        sequence_end_ms=cues[-1].t1_ms,
    )
    target = cues[-1].t0_ms
    errors = [d for d in result.diagnostics if d.status == "error"]
    if errors and all(d.cue_ms != target for d in errors):
        return False  # the predecessor cannot be planned; there is no entry to check
    entry = next(d for d in result.diagnostics if d.cue_ms == target)
    assert entry.status == "feasible", (kind, seed, entry.reason)
    assert entry.required_ms is not None and entry.required_ms <= bound, (
        f"{kind} seed {seed}: the transaction needs {entry.required_ms} ms but the bound "
        f"is {bound} ms ({entry.reason})"
    )
    return True


@pytest.mark.parametrize(
    ("kind", "known", "min_checked"),
    [
        pytest.param(
            "static", _BOUND_KNOWN["static"], 0.85, id="static-predecessor-in-an-envelope"
        ),
        pytest.param(
            "moving", _BOUND_KNOWN["moving"], 0.8, id="predecessor-moving-at-the-rate-limit"
        ),
        pytest.param(
            "short-wheel",
            _BOUND_KNOWN["short-wheel"],
            0.75,
            id="short-predecessor-with-a-wheel-change",
        ),
    ],
)
def test_worst_case_entry_bound_dominates_the_transaction(
    kind: str, known: tuple[int, ...], min_checked: float
) -> None:
    """The time `worst_case_entry_ms` claims a section entry may need is never less than
    what the transaction pass then requires; the entry window is sized from it.

    Runs the seeds known to catch each dropped bound term, then a random sweep whose
    checked fraction is floored so skipped cases cannot hollow the fuzz out.
    """
    for seed in known:
        assert _check_bound(kind, seed), (kind, seed)
    checked = sum(_check_bound(kind, seed) for seed in range(BOUND_SEEDS))
    assert checked >= min_checked * BOUND_SEEDS, f"{kind}: only {checked} entries checked"


@pytest.mark.parametrize(
    "unknown",
    [
        "pan.travel_speed_per_s",
        "pan.latency_ms",
        "tilt.settle_ms",
        "visibility.close_latency_ms",
        "color.red.settle_ms",
        "shutter-only.closed.settle_ms",
    ],
)
def test_worst_case_entry_bound_is_unknown_when_a_needed_term_is(unknown: str) -> None:
    """Unknown is never treated as zero: the bound is None, which is never feasible."""
    entry = {ChannelName.PAN: (0.0, 90.0), ChannelName.TILT: (0.0, 0.0)}
    envelope = {ChannelName.PAN: (-90.0, -90.0), ChannelName.TILT: (10.0, 10.0)}
    wheels = {ChannelName.COLOR: {"red"}}

    def bound(payload: dict[str, Any]) -> int | None:
        return worst_case_entry_ms(
            FixtureCapabilities.model_validate(payload),
            entry_pose=entry,
            entry_wheels=wheels,
            pose_envelope=envelope,
            frame_ms=_FRAME,
        )

    payload = preposition_profile_payload()
    if unknown.startswith("shutter-only"):
        payload["visibility"]["dimmer_zero_extinguishes"] = False
    assert bound(payload) is not None
    owner, *path, key = unknown.split(".")
    if owner in ("pan", "tilt"):
        payload["axes"][owner][key] = None
    elif owner == "visibility":
        payload["visibility"][key] = None
    elif owner == "color":
        payload["discrete"]["color"]["states"][path[0]][key] = None
    else:
        payload["discrete"]["shutter"]["states"][path[0]][key] = None
    assert bound(payload) is None


# --- Non-monotonic predecessors on coarse axes (P2.4a review) ---------------------------

COARSE_SEEDS = 800 if _FULL_FUZZ else 100
_ADMITTED_KNOWN: dict[int, str] = {44: "refused", 52: "refused", 198: "checked", 313: "checked"}
"""Seeds whose outcome catches a mutation: 44 and 52 are wobbles only `follow_lag`
refuses; 198 and 313 need the darkness term."""
FOLLOWED_SEEDS = 800 if _FULL_FUZZ else 60
_FOLLOWED_KNOWN = (0, 4, 8, 12, 20, 28)
"""Seeds that catch ignoring `residual_ms` (0, 8), dropping the predecessor (0, 4),
follow (12, 20) or darkness (20, 28) term."""
_COARSE_KINDS = ("wobble", "triangle", "turn", "random")


def _coarse_profile(rng: random.Random) -> FixtureCapabilities:
    """The discrete test profile with random 8- or 16-bit, inverted, slow or fast axes."""
    payload = discrete_profile_payload()
    for key in ("pan", "tilt"):
        axis = payload["axes"][key]
        if rng.random() < 0.5:
            axis.pop("fine_offset")
        axis["inverted"] = rng.random() < 0.5
        if key == "pan" and rng.random() < 0.4:
            axis["physical_min"], axis["physical_max"] = rng.choice(
                [(0.0, 540.0), (-100.0, 440.0), (-30.0, 250.0)]
            )
        axis["travel_speed_per_s"] = rng.choice([45.0, 45.5, 30.0, 90.0, 180.0, 720.0, 13.0])
        axis["latency_ms"] = rng.choice([0, 0, 7, 20, 40, 55])
        axis["settle_ms"] = rng.choice([0, 0, 13, 33, 40])
        capability = AxisCapability.model_validate(axis)
        word = capability.dmx_word(sum(capability.operable_range) / 2)
        if "fine_offset" in axis:
            payload["defaults"][axis["coarse_offset"]] = word >> 8
            payload["defaults"][axis["fine_offset"]] = word & 0xFF
        else:
            payload["defaults"][axis["coarse_offset"]] = word
    visibility = payload["visibility"]
    visibility["close_latency_ms"] = rng.choice([0, 0, 10, 30])
    visibility["open_latency_ms"] = rng.choice([0, 10])
    mode = rng.choice(["dimmer", "shutter", "both"])
    visibility["dimmer_zero_extinguishes"] = mode != "shutter"
    visibility["extinguishing_shutter_states"] = [] if mode == "dimmer" else ["closed"]
    for state in payload["discrete"]["shutter"]["states"].values():
        state["settle_ms"] = rng.choice([0, 0, 20, 30])
    return FixtureCapabilities.model_validate(payload)


def _coarse_path(
    rng: random.Random, axis: AxisCapability, frames: int, kind: str, start: float | None = None
) -> list[float]:
    """Per-frame poses within the configured speed: straddling a word boundary every frame
    (`wobble`), bouncing or reversing at full speed (`triangle`, `turn`), or random."""
    low, high = axis.operable_range
    assert axis.travel_speed_per_s is not None
    step = axis.travel_speed_per_s * _FRAME / 1000
    word = (axis.physical_max - axis.physical_min) / axis.full_word
    x = rng.uniform(low, high) if start is None else start
    xs = [x]
    direction = rng.choice([-1, 1])
    for index in range(frames):
        if kind == "wobble":
            amplitude = min(step * 0.49, word * 0.49)
            nx = xs[0] + (amplitude if index % 2 == 0 else -amplitude)
        elif kind == "triangle":
            nx = x + direction * step
            if not low <= nx <= high or rng.random() < 0.15:
                direction = -direction
                nx = x + direction * step
        elif kind == "turn":
            if index % rng.choice([2, 3, 5]) == 0:
                direction = -direction
            nx = x + direction * step
        else:
            nx = x + rng.uniform(-step, step)
        x = min(max(nx, low), high)
        xs.append(x)
    return xs


def _coarse_cue(
    name: str,
    t0: int,
    poses: dict[ChannelName, list[float]],
    wheels: dict[ChannelName, str],
    *,
    lit: bool = True,
) -> FixtureSegment:
    """A cue commanding `poses[ch][i]` at frame `i`, ending with a terminal point."""
    frames = len(next(iter(poses.values()))) - 1
    t1 = t0 + frames * _FRAME
    channels: dict[ChannelName, ContinuousTrajectory | DiscreteTrajectory] = {
        channel: ContinuousTrajectory(
            unit="degree",
            points=tuple(
                PhysicalPoint(t_ms=t0 + index * _FRAME if index < frames else t1, value=x)
                for index, x in enumerate(xs)
            ),
            interpolation="linear",
        )
        for channel, xs in poses.items()
    }
    channels[ChannelName.DIMMER] = ContinuousTrajectory(
        unit="normalized",
        points=(PhysicalPoint(t_ms=t0, value=1.0 if lit else 0.0),),
        interpolation="hold",
    )
    channels[ChannelName.SHUTTER] = DiscreteTrajectory(
        events=(DiscretePoint(t_ms=t0, state="open" if lit else "closed"),)
    )
    for channel, state in wheels.items():
        channels[channel] = DiscreteTrajectory(events=(DiscretePoint(t_ms=t0, state=state),))
    return FixtureSegment(
        section_id=name,
        segment_id=name,
        step_id="step",
        template_id="tpl",
        fixture_id="MH1",
        t0_ms=t0,
        t1_ms=t1,
        channels={c: ChannelValue(channel=c, physical=v) for c, v in channels.items()},
    )


def _coarse_case(
    seed: int, chain: int
) -> tuple[
    FixtureCapabilities,
    list[FixtureSegment],
    FixtureSegment,
    dict[ChannelName, float],
    dict[ChannelName, str],
]:
    """`chain` back-to-back predecessor cues, the first a minute in, then a target cue a
    minute after them; returns the profile, the predecessors, the target, the target's
    pose and wheels."""
    rng = random.Random(seed)
    profile = _coarse_profile(rng)
    axes = {ChannelName.PAN: profile.axes["pan"], ChannelName.TILT: profile.axes["tilt"]}
    kind = _COARSE_KINDS[seed % len(_COARSE_KINDS)]
    wheels = {
        ChannelName.COLOR: rng.choice(["white", "red", "blue"]),
        ChannelName.GOBO: rng.choice(["open", "dots", "star"]),
    }
    cues: list[FixtureSegment] = []
    starts: dict[ChannelName, float | None] = dict.fromkeys(axes)
    t = 60_000
    for index in range(chain):
        frames = rng.choice([2, 5, 20, 50, 150, 400])
        poses = {c: _coarse_path(rng, a, frames, kind, starts[c]) for c, a in axes.items()}
        cue = _coarse_cue(f"pred{index}", t, poses, wheels)
        cues.append(cue)
        # The next cue continues from this one's last commanded frame.
        starts = {c: xs[-2] for c, xs in poses.items()}
        t = cue.t1_ms
    target_pose = {
        c: rng.choice([*a.operable_range, rng.uniform(*a.operable_range)]) for c, a in axes.items()
    }
    target_wheels = {
        ChannelName.COLOR: rng.choice(["white", "red", "blue"]),
        ChannelName.GOBO: rng.choice(["open", "dots", "star"]),
    }
    target = _coarse_cue(
        "target",
        t + 60_000,
        {c: [x] * 11 for c, x in target_pose.items()},
        target_wheels,
    )
    return profile, cues, target, target_pose, target_wheels


def _plan_entry(
    profile: FixtureCapabilities, cues: list[FixtureSegment], target: FixtureSegment
) -> TransitionDiagnostic | None:
    """The target's transaction, or None when a predecessor itself cannot be planned."""
    initial = InitialFixtureState(
        pan_deg=sum(profile.axes["pan"].operable_range) / 2,
        tilt_deg=sum(profile.axes["tilt"].operable_range) / 2,
        dimmer=0.0,
        discrete_states={"shutter": "closed", "color": "white", "gobo": "open"},
        settled=True,
        dark=True,
    )
    result = plan_prepositions(
        [*cues, target],
        {"MH1": profile},
        initial_states={"MH1": initial},
        locks=(),
        frame_ms=_FRAME,
        sequence_end_ms=target.t1_ms,
    )
    errors = [d for d in result.diagnostics if d.status == "error"]
    if errors and all(d.cue_ms != target.t0_ms for d in errors):
        return None
    return next(d for d in result.diagnostics if d.cue_ms == target.t0_ms)


def _last_frame_envelope(cue: FixtureSegment) -> dict[ChannelName, tuple[float, float]]:
    """The pose a cue's last frame commands, as a degenerate envelope."""
    pose = {}
    for channel in (ChannelName.PAN, ChannelName.TILT):
        trajectory = cue.channels[channel].physical
        assert isinstance(trajectory, ContinuousTrajectory)
        value = next(p.value for p in trajectory.points if p.t_ms == cue.t1_ms - _FRAME)
        pose[channel] = (value, value)
    return pose


def _check_admitted(seed: int) -> str:
    """Check one compile-admitted predecessor case: `checked`, `refused` (unfollowable)
    or `skipped` (over the speed limit, or a predecessor that cannot be planned)."""
    profile, (cue,), target, pose, wheels = _coarse_case(seed, chain=1)
    try:
        for channel in (ChannelName.PAN, ChannelName.TILT):
            trajectory = cue.channels[channel].physical
            assert isinstance(trajectory, ContinuousTrajectory)
            _check_travel_rate("MH1", channel, trajectory, profile)
    except PhysicalChannelError:
        return "skipped"
    if follow_lag(cue, profile, frame_ms=_FRAME) is not None:
        return "refused"
    entry = _plan_entry(profile, [cue], target)
    if entry is None:
        return "skipped"
    bound = worst_case_entry_ms(
        profile,
        entry_pose={c: (x, x) for c, x in pose.items()},
        entry_wheels={c: {s} for c, s in wheels.items()},
        pose_envelope=_last_frame_envelope(cue),
        frame_ms=_FRAME,
    )
    assert bound is not None
    assert entry.status == "feasible", (seed, entry.reason)
    assert entry.required_ms is not None and entry.required_ms <= bound, (
        f"seed {seed}: the transaction needs {entry.required_ms} ms but the bound is "
        f"{bound} ms ({entry.reason})"
    )
    return "checked"


def test_entry_bound_dominates_after_any_cue_the_compile_admits() -> None:
    """The envelope bound (no followed predecessor) holds after any one cue the physical
    compile admits: within the configured speed (`_check_travel_rate`) and followable
    by the head (`follow_lag`). Word-boundary wobble on a coarse axis, which once left
    the head 20 s behind, is refused by the compile instead. Known catching seeds first,
    then a random sweep."""
    for seed, outcome in _ADMITTED_KNOWN.items():
        assert _check_admitted(seed) == outcome, seed
    outcomes = [_check_admitted(seed) for seed in range(COARSE_SEEDS)]
    assert outcomes.count("checked") >= 0.5 * COARSE_SEEDS, outcomes.count("checked")
    assert outcomes.count("refused") >= 0.4 * COARSE_SEEDS, outcomes.count("refused")


def _check_followed(seed: int) -> bool:
    """Check one followed-chain case; return whether it had an entry to check."""
    rng = random.Random(seed)
    profile, cues, target, pose, wheels = _coarse_case(seed, chain=rng.randint(1, 3))
    try:
        for cue in cues:
            for channel in (ChannelName.PAN, ChannelName.TILT):
                trajectory = cue.channels[channel].physical
                assert isinstance(trajectory, ContinuousTrajectory)
                _check_travel_rate("MH1", channel, trajectory, profile)
    except PhysicalChannelError:
        return False
    entry = _plan_entry(profile, cues, target)
    if entry is None:
        return False
    followed = follow_cues(cues, profile, frame_ms=_FRAME)[-1]
    assert followed.settled_ms is not None
    last = cues[-1]
    held = {
        channel: {value.physical.events[-1].state}
        for channel, value in last.channels.items()
        if channel in (ChannelName.COLOR, ChannelName.GOBO)
        and isinstance(value.physical, DiscreteTrajectory)
    }
    bound = worst_case_entry_ms(
        profile,
        entry_pose={c: (x, x) for c, x in pose.items()},
        entry_wheels={c: {s} for c, s in wheels.items()},
        pose_envelope=_last_frame_envelope(last),
        held_wheels=held,
        residual_ms=max(0, followed.settled_ms - last.t1_ms),
        frame_ms=_FRAME,
    )
    assert bound is not None
    assert entry.status == "feasible", (seed, entry.reason)
    assert entry.required_ms is not None and entry.required_ms <= bound, (
        f"seed {seed}: the transaction needs {entry.required_ms} ms but the bound is "
        f"{bound} ms ({entry.reason})"
    )
    return True


def test_entry_bound_from_the_followed_predecessor_dominates() -> None:
    """With the actual predecessor chain followed (`follow_cues`), the bound holds even
    after motion the compile would refuse, across back-to-back cues and with the
    predecessor's wheels known to be held. Known catching seeds first, then a random
    sweep."""
    for seed in _FOLLOWED_KNOWN:
        assert _check_followed(seed), seed
    checked = sum(_check_followed(seed) for seed in range(FOLLOWED_SEEDS))
    assert checked >= 0.9 * FOLLOWED_SEEDS, f"only {checked} entries checked"
