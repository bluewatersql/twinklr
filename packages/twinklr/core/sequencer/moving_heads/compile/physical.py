"""Physical step compilation for the physical_v2 renderer.

`compile_physical_step` turns a template step's explicit physical data into a
`FixtureSegment` whose channels hold typed trajectories: pan/tilt in degrees, the
dimmer as a normalized level, the shutter and color and gobo wheels as named states.
A named state selects only the byte the profile declares for it
(`resolve_discrete_state`); a wheel change is one event, never a sweep through the
states between, and an undeclared state or wheel is rejected, never replaced by open
or zero. Motion and pulses are evaluated on musical phase from the step start, never
on sample-index parity or an average tempo. Nothing is clamped: an out-of-range
value, a travel rate above the configured speed, motion at an unknown speed, a pulse
interval shorter than one frame, or a shutter change faster than its known latency
and settle time is rejected. A legacy step is never reinterpreted.

The caller supplies the sample times: the encoder's frame starts, at most one frame
apart, so the checked values are exactly the commanded ones. The value at each sample
depends only on that sample's time. Pan and tilt also carry an exact terminal point
at the step end, so the end state is the kernel's, not the last frame's.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from itertools import pairwise
import math

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.config.fixtures.capabilities import (
    DiscreteCapability,
    DiscreteName,
    FixtureCapabilities,
)
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.context import StepCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalChannelError,
    PhysicalPoint,
    PhysicalValue,
    check_physical_value,
)
from twinklr.core.sequencer.models.template import (
    PhaseOffset,
    PhysicalMovementSpec,
    PhysicalPulseSpec,
    PhysicalShutterPulse,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.diagnostics import MHDiagnostic
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseMap,
    exact_decimal,
    musical_phase_at,
    musical_phase_fraction,
    musical_time_at,
)

_RATE_TOLERANCE = 1e-9
"""Relative slack so float noise on a path exactly at the configured speed passes."""


class PhysicalCompileError(Exception):
    """A step the physical renderer cannot compile, with its diagnostic."""

    def __init__(self, diagnostic: MHDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)


class WheelChange(BaseModel):
    """A color or gobo wheel selection the transaction pass must mask and let settle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_id: str
    channel: ChannelName
    t_ms: int
    from_state: str | None = Field(description="State in force before; None when unknown")
    to_state: str
    settle_ms: int | None = Field(description="Declared settle of `to_state`; None when unknown")


_WHEELS: dict[ChannelName, DiscreteName] = {ChannelName.COLOR: "color", ChannelName.GOBO: "gobo"}


def compile_physical_step(
    step: TemplateStep, context: StepCompileContext, *, sample_times_ms: tuple[int, ...]
) -> FixtureSegment:
    """Compile a step's explicit physical data into typed trajectories.

    Args:
        step: A physical step: `movement.physical` set and no legacy handler data.
        context: Step identity, timing, the fixture's physical profile and the
            song's musical phase map. Phase is measured from `context.start_ms`.
        sample_times_ms: The encoder's frame starts in the step's half-open span:
            strictly increasing, starting at its start, at most one frame apart and
            ending within one frame of the step end.

    Returns:
        A segment over the step with PAN and TILT (sampled, plus a terminal point at
        the step end), DIMMER and SHUTTER when the step declares their pulses, and
        SHUTTER, COLOR and GOBO as one held event when it declares a static state.
        `metadata["phase_origin_ms"]` records the origin.

    Raises:
        PhysicalCompileError: For a legacy step, legacy data on a physical step, or a
            fixture without a physical profile.
        PhysicalChannelError: For a value, rate or state change the profile cannot honor,
            including a state or wheel the profile does not declare.
        ValueError: For invalid sample times or a context without a phase map.
    """
    t0_ms = context.start_ms
    t1_ms = context.start_ms + context.duration_ms
    profile = _require_physical_step(step, context)
    if context.phase_map is None:
        raise ValueError("physical compile needs the song's musical phase map")
    times = _check_sample_times(sample_times_ms, t0_ms, t1_ms)
    phase_map = context.phase_map

    segment = FixtureSegment(
        section_id=context.section_id,
        segment_id=context.segment_id,
        step_id=step.step_id,
        template_id=context.template_id,
        preset_id=context.preset_id,
        fixture_id=context.fixture_id,
        t0_ms=t0_ms,
        t1_ms=t1_ms,
    )
    segment.add_metadata("phase_origin_ms", t0_ms)

    movement = step.movement.physical
    assert movement is not None  # checked by _require_physical_step
    for channel in (ChannelName.PAN, ChannelName.TILT):
        trajectory = ContinuousTrajectory(
            unit="degree",
            points=tuple(
                PhysicalPoint(t_ms=t, value=_movement_value(movement, channel, phase_map, t, t0_ms))
                for t in (*times, t1_ms)
            ),
            interpolation="linear",
        )
        _add(segment, channel, trajectory, profile)
        _check_travel_rate(context.fixture_id, channel, trajectory, profile)

    dimmer = step.dimmer.physical
    if dimmer is not None:
        _check_pulse_widths(context.fixture_id, ChannelName.DIMMER, dimmer, phase_map, t0_ms, t1_ms)
        levels = ContinuousTrajectory(
            unit="normalized",
            points=tuple(
                PhysicalPoint(
                    t_ms=t,
                    value=dimmer.high if _pulse_high(dimmer, phase_map, t, t0_ms) else dimmer.low,
                )
                for t in times
            ),
            interpolation="hold",
        )
        _add(segment, ChannelName.DIMMER, levels, profile)

    shutter = step.physical_shutter
    if shutter is not None:
        _check_pulse_widths(
            context.fixture_id, ChannelName.SHUTTER, shutter, phase_map, t0_ms, t1_ms
        )
        states = _shutter_states(shutter, phase_map, times, t0_ms)
        _add(segment, ChannelName.SHUTTER, states, profile)
        _check_shutter_timing(context.fixture_id, states, t1_ms, profile)

    # Static named states hold for the whole step. Entering one from the preceding
    # state (wheel masking and settle) is the transaction pass's work.
    for channel, state in (
        (ChannelName.SHUTTER, step.physical_shutter_state),
        (ChannelName.COLOR, step.physical_color),
        (ChannelName.GOBO, step.physical_gobo),
    ):
        if state is not None:
            held = DiscreteTrajectory(events=(DiscretePoint(t_ms=t0_ms, state=state),))
            _add(segment, channel, held, profile)

    return segment


def resolve_discrete_state(capability: DiscreteCapability, state: str) -> int:
    """Return the byte the profile declares to select a named state.

    Only the state's declared `value`: never a range bound, a byte between two states,
    or the open, closed or default state in place of an unknown one.

    Raises:
        ValueError: If the capability does not declare `state`.
    """
    declared = capability.states.get(state)
    if declared is None:
        raise ValueError(f"state {state!r} is not one of {sorted(capability.states)}")
    return declared.value


def wheel_changes(
    segments: Sequence[FixtureSegment], profile: FixtureCapabilities
) -> tuple[WheelChange, ...]:
    """List the color and gobo wheel selections across one fixture's ordered segments.

    A selection is reported where a wheel event names a state other than the one in
    force before it, with the selected state's settle time. `from_state` is None where
    the preceding state is not known here: before the first segment (the run's initial
    state) and after a segment that does not author the wheel (the encoder emits the
    declared default byte there, not a named state). Masking and settle are scheduled
    by the transaction pass, never by the legacy channel blender.

    Raises:
        ValueError: If the segments are not one fixture's, in order without overlap, or
            a wheel channel is not a discrete physical value.
        PhysicalChannelError: If the profile does not declare a wheel or state.
    """
    if len({segment.fixture_id for segment in segments}) > 1:
        raise ValueError("wheel changes are listed for one fixture at a time")
    if any(later.t0_ms < earlier.t1_ms for earlier, later in pairwise(segments)):
        raise ValueError("segments must be in time order without overlap")

    changes: list[WheelChange] = []
    current: dict[ChannelName, str | None] = dict.fromkeys(_WHEELS)
    for segment in segments:
        for channel, key in _WHEELS.items():
            value = segment.channels.get(channel)
            if value is None:
                current[channel] = None
                continue
            if not isinstance(value.physical, DiscreteTrajectory):
                raise ValueError(f"{channel.value} is not a discrete physical value")
            check_physical_value(segment.fixture_id, channel, value.physical, profile)
            for event in value.physical.events:
                if event.state == current[channel]:
                    continue
                changes.append(
                    WheelChange(
                        fixture_id=segment.fixture_id,
                        channel=channel,
                        t_ms=event.t_ms,
                        from_state=current[channel],
                        to_state=event.state,
                        settle_ms=profile.discrete[key].states[event.state].settle_ms,
                    )
                )
                current[channel] = event.state
    return tuple(sorted(changes, key=lambda change: change.t_ms))


def slice_physical_segment(segment: FixtureSegment, start_ms: int, end_ms: int) -> FixtureSegment:
    """Return the part of a physical segment in `[start_ms, end_ms)`.

    Continuous values are interpolated at the boundaries (at the end only when a later
    point defines it, as a compiled pan/tilt terminal point always does, so the slice's
    end point is its terminal point); the discrete state in force at `start_ms` is carried to it.
    Identity, metadata and the phase origin are kept, so motion does not restart.

    Raises:
        ValueError: If the span is empty or outside the segment, or a channel is not
            a physical value.
    """
    if not segment.t0_ms <= start_ms < end_ms <= segment.t1_ms:
        raise ValueError(
            f"slice [{start_ms}, {end_ms}) must be non-empty and inside "
            f"[{segment.t0_ms}, {segment.t1_ms}]"
        )
    channels: dict[ChannelName, ChannelValue] = {}
    for channel, value in segment.channels.items():
        physical = value.physical
        if physical is None:
            raise ValueError(f"{channel.value} is not a physical value")
        channels[channel] = ChannelValue(
            channel=channel, physical=_slice_value(physical, start_ms, end_ms)
        )
    return FixtureSegment(
        **{
            **dict(segment),
            "t0_ms": start_ms,
            "t1_ms": end_ms,
            "channels": channels,
            "metadata": dict(segment.metadata),
        }
    )


def _require_physical_step(step: TemplateStep, context: StepCompileContext) -> FixtureCapabilities:
    def reject(message: str) -> PhysicalCompileError:
        return PhysicalCompileError(
            MHDiagnostic(
                code="unsupported_attribute",
                severity="error",
                message=message,
                fixture_id=context.fixture_id,
                section_id=context.section_id,
                action="rejected",
            )
        )

    if step.movement.physical is None:
        raise reject(
            f"step {step.step_id!r} of template {context.template_id!r} has no "
            "movement.physical data. Legacy normalized curves are never reinterpreted as "
            "angles: migrate the template with explicit physical data to render it under "
            "physical_v2"
        )
    legacy = [
        *_non_default_fields("geometry", step.geometry),
        *_non_default_fields("movement", step.movement, keep="physical"),
        *_non_default_fields("dimmer", step.dimmer, keep="physical"),
        *(name for name in ("color", "shutter", "gobo") if getattr(step, name) is not None),
        *(["timing.phase_offset"] if step.timing.phase_offset != PhaseOffset() else []),
    ]
    if legacy:
        raise reject(
            f"step {step.step_id!r} of template {context.template_id!r} sets legacy "
            f"{legacy}, which the physical renderer does not apply"
        )
    if context.physical_profile is None:
        raise reject(f"fixture {context.fixture_id!r} has no physical_profile")
    return context.physical_profile


def _non_default_fields(prefix: str, component: BaseModel, *, keep: str = "") -> list[str]:
    """Legacy fields set away from their default; the physical renderer applies none.

    Compared by value, not `model_fields_set`: a preset round trip sets every field
    explicitly, at its default, and that changes nothing.
    """
    return [
        f"{prefix}.{name}"
        for name, field in type(component).model_fields.items()
        if name != keep and getattr(component, name) != field.get_default(call_default_factory=True)
    ]


def _check_sample_times(times: Sequence[int], t0_ms: int, t1_ms: int) -> tuple[int, ...]:
    if not times:
        raise ValueError("physical compile needs at least one sample time")
    if times[0] != t0_ms:
        raise ValueError(f"sample times must start at the step start {t0_ms} ms")
    if any(later <= earlier for earlier, later in pairwise(times)):
        raise ValueError("sample times must be strictly increasing")
    if times[-1] >= t1_ms:
        raise ValueError(f"sample times must lie inside the step span [{t0_ms}, {t1_ms})")
    for earlier, later in pairwise((*times, t1_ms)):
        if later - earlier > EFFECT_GRID_MS:
            raise ValueError(
                f"samples at {earlier} and {later} ms are more than one {EFFECT_GRID_MS} ms "
                "frame apart; pass the encoder's frame starts"
            )
    return tuple(times)


def _movement_value(
    movement: PhysicalMovementSpec,
    channel: ChannelName,
    phase_map: MusicalPhaseMap,
    time_ms: int,
    origin_ms: int,
) -> float:
    is_pan = channel is ChannelName.PAN
    start = movement.start_pan_deg if is_pan else movement.start_tilt_deg
    extent = movement.pan_extent_deg if is_pan else movement.tilt_extent_deg
    if movement.shape == "hold" or movement.period_beats is None:
        return start
    phase = musical_phase_at(
        phase_map, time_ms, origin_ms=origin_ms, period_beats=movement.period_beats
    )
    if movement.shape == "linear":
        return start + extent * min(phase, 1.0)
    # sine_pan/sine_tilt: the unused axis has zero extent by validation.
    return start + extent * math.sin(2 * math.pi * phase)


def _pulse_high(
    pulse: PhysicalPulseSpec, phase_map: MusicalPhaseMap, time_ms: int, origin_ms: int
) -> bool:
    """High while the exact fractional pulse phase is in `[0, duty_cycle)`."""
    phase = musical_phase_fraction(
        phase_map, time_ms, origin_ms=origin_ms, period_beats=pulse.period_beats
    ) + exact_decimal(pulse.phase_cycles)
    return phase - math.floor(phase) < exact_decimal(pulse.duty_cycle)


def _check_pulse_widths(
    fixture_id: str,
    channel: ChannelName,
    pulse: PhysicalPulseSpec,
    phase_map: MusicalPhaseMap,
    t0_ms: int,
    t1_ms: int,
) -> None:
    """Reject a high or low interval inside the step shorter than one frame.

    Edges are the exact times the pulse phase crosses a whole cycle (rising) or
    `duty_cycle` (falling). An interval cut by the step start or end is exempt.
    """
    duty = exact_decimal(pulse.duty_cycle)
    if duty == 1:
        return
    shift = exact_decimal(pulse.phase_cycles)
    end = (
        musical_phase_fraction(phase_map, t1_ms, origin_ms=t0_ms, period_beats=pulse.period_beats)
        + shift
    )
    edges = sorted(
        musical_time_at(phase_map, edge - shift, origin_ms=t0_ms, period_beats=pulse.period_beats)
        for cycle in range(math.floor(shift), math.floor(end) + 1)
        for edge in (Fraction(cycle), cycle + duty)
        if shift <= edge <= end
    )
    widths = [(later - earlier, earlier, later) for earlier, later in pairwise(edges)]
    if not widths:
        return
    width, start, stop = min(widths)
    if width < EFFECT_GRID_MS:
        raise PhysicalChannelError(
            fixture_id=fixture_id,
            channel=channel,
            time_ms=math.floor(start),
            reason=(
                f"pulse interval [{float(start):g}, {float(stop):g}) ms lasts "
                f"{float(width):g} ms, shorter than one {EFFECT_GRID_MS} ms frame"
            ),
        )


def _shutter_states(
    pulse: PhysicalShutterPulse,
    phase_map: MusicalPhaseMap,
    times: tuple[int, ...],
    origin_ms: int,
) -> DiscreteTrajectory:
    events: list[DiscretePoint] = []
    for t in times:
        state = pulse.high_state if _pulse_high(pulse, phase_map, t, origin_ms) else pulse.low_state
        if not events or events[-1].state != state:
            events.append(DiscretePoint(t_ms=t, state=state))
    return DiscreteTrajectory(events=tuple(events))


def _add(
    segment: FixtureSegment,
    channel: ChannelName,
    value: PhysicalValue,
    profile: FixtureCapabilities,
) -> None:
    check_physical_value(segment.fixture_id, channel, value, profile)
    segment.channels[channel] = ChannelValue(channel=channel, physical=value)


def _check_travel_rate(
    fixture_id: str,
    channel: ChannelName,
    trajectory: ContinuousTrajectory,
    profile: FixtureCapabilities,
) -> None:
    """Reject travel between consecutive points faster than the configured speed."""
    axis = profile.axes["pan" if channel is ChannelName.PAN else "tilt"]
    speed = axis.travel_speed_per_s
    for earlier, later in pairwise(trajectory.points):
        delta = abs(later.value - earlier.value)
        if delta == 0:
            continue
        if speed is None:
            raise PhysicalChannelError(
                fixture_id=fixture_id,
                channel=channel,
                time_ms=earlier.t_ms,
                reason="moves with unknown travel speed; configure travel_speed_per_s",
            )
        rate = delta * 1000 / (later.t_ms - earlier.t_ms)
        if rate > speed * (1 + _RATE_TOLERANCE):
            raise PhysicalChannelError(
                fixture_id=fixture_id,
                channel=channel,
                time_ms=earlier.t_ms,
                reason=f"travels {rate:.6g} {axis.unit}/s, above the configured speed {speed}",
            )


def _check_shutter_timing(
    fixture_id: str,
    trajectory: DiscreteTrajectory,
    t1_ms: int,
    profile: FixtureCapabilities,
) -> None:
    """Reject a state change that cannot take effect before the next one.

    Each change after the first must hold its state for the visibility latency the
    change crosses (close when entering darkness, open when leaving it) plus the
    state's settle time. Either being unknown rejects the schedule. The first
    state's entry depends on the preceding state, which this step does not know.
    """
    shutter = profile.discrete["shutter"]
    visibility = profile.visibility
    dark = set(visibility.extinguishing_shutter_states)
    events = trajectory.events
    ends = [event.t_ms for event in events[1:]] + [t1_ms]

    def fail(time_ms: int, reason: str) -> PhysicalChannelError:
        return PhysicalChannelError(
            fixture_id=fixture_id, channel=ChannelName.SHUTTER, time_ms=time_ms, reason=reason
        )

    for previous, event, end_ms in zip(events[:-1], events[1:], ends[1:], strict=True):
        latency: int | None = 0
        latency_name = ""
        if event.state in dark and previous.state not in dark:
            latency, latency_name = visibility.close_latency_ms, "close_latency_ms"
        elif previous.state in dark and event.state not in dark:
            latency, latency_name = visibility.open_latency_ms, "open_latency_ms"
        if latency is None:
            raise fail(event.t_ms, f"{latency_name} is unknown, so this pulse cannot be honored")
        settle = shutter.states[event.state].settle_ms
        if settle is None:
            raise fail(event.t_ms, f"settle time of state {event.state!r} is unknown")
        needed = latency + settle
        if end_ms - event.t_ms < needed:
            raise fail(
                event.t_ms,
                f"state {event.state!r} holds {end_ms - event.t_ms} ms but needs {needed} ms "
                "of latency and settle",
            )


def _slice_value(value: PhysicalValue, start_ms: int, end_ms: int) -> PhysicalValue:
    if isinstance(value, DiscreteTrajectory):
        current = [event for event in value.events if event.t_ms <= start_ms]
        if not current:
            raise ValueError(f"no discrete state is defined at {start_ms} ms")
        inside = [event for event in value.events if start_ms < event.t_ms < end_ms]
        return DiscreteTrajectory(
            events=(DiscretePoint(t_ms=start_ms, state=current[-1].state), *inside)
        )

    points = value.points
    head = PhysicalPoint(t_ms=start_ms, value=_value_at(value, start_ms))
    inside_points = [point for point in points if start_ms < point.t_ms < end_ms]
    tail = (
        [PhysicalPoint(t_ms=end_ms, value=_value_at(value, end_ms))]
        if value.interpolation == "linear" and points[-1].t_ms >= end_ms
        else []
    )
    return ContinuousTrajectory(
        unit=value.unit, points=(head, *inside_points, *tail), interpolation=value.interpolation
    )


def _value_at(trajectory: ContinuousTrajectory, time_ms: int) -> float:
    points = trajectory.points
    before = [index for index, point in enumerate(points) if point.t_ms <= time_ms]
    if not before:
        raise ValueError(f"no value is defined at {time_ms} ms")
    left = points[before[-1]]
    if trajectory.interpolation == "hold" or left.t_ms == time_ms or before[-1] + 1 == len(points):
        return left.value
    right = points[before[-1] + 1]
    fraction = (time_ms - left.t_ms) / (right.t_ms - left.t_ms)
    return left.value + fraction * (right.value - left.value)
