"""Physical step compilation for the physical_v2 renderer.

`compile_physical_step` turns a template step's explicit physical data into a
`FixtureSegment` whose channels hold typed trajectories: pan/tilt in degrees, the
dimmer as a normalized level, the shutter and color and gobo wheels as named states.
A named state selects only the byte the profile declares for it
(`resolve_discrete_state`); a wheel change is one event, never a sweep through the
states between, and an undeclared state or wheel is rejected, never replaced by open
or zero. Motion and pulses are evaluated on musical phase from the step start, never
on sample-index parity or an average tempo; a step distributed over the rig topology
evaluates each fixture at the step phase minus its offset in that domain, and its pan
displacement times its mirror sign. Relative paths (circle, lissajous, sweep) move
about the resolved aim (`evaluate_physical_path`). Nothing is clamped: an out-of-range
value, a travel rate above the configured speed, motion at an unknown speed, a pulse
interval shorter than one frame, or a shutter change faster than its known latency
and settle time is rejected. A legacy step is never reinterpreted.

The caller supplies the sample times: the encoder's frame starts, at most one frame
apart, so the checked values are exactly the commanded ones. The value at each sample
depends only on that sample's time. Pan and tilt also carry an exact terminal point
at the step end, so the end state is the kernel's, not the last frame's.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import pairwise
import math

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.config.fixtures.capabilities import DiscreteCapability, FixtureCapabilities
from twinklr.core.config.fixtures.presets import PoseDegrees
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.context import StepCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    DISCRETE_KEYS,
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalChannelError,
    PhysicalPoint,
    PhysicalValue,
    check_physical_value,
)
from twinklr.core.sequencer.models.template import (
    RELATIVE_PATH_SHAPES,
    PathTransform,
    PhaseOffset,
    PhysicalMovementSpec,
    PhysicalPulseSpec,
    PhysicalShutterPulse,
    Template,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.diagnostics import MHDiagnostic
from twinklr.core.sequencer.timing.musical_phase import (
    MusicalPhaseError,
    MusicalPhaseMap,
    exact_decimal,
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


class OffGridTimeError(ValueError):
    """A step bound or sample time off the effect frame grid.

    The frame grid is the single source of sample times: the caller quantizes step
    bounds with the encoder's `quantize_cue` before compiling.
    """

    def __init__(self, name: str, time_ms: int) -> None:
        self.name = name
        self.time_ms = time_ms
        super().__init__(
            f"{name} {time_ms} ms is not on the {EFFECT_GRID_MS} ms frame grid; quantize "
            "step bounds with quantize_cue before compiling"
        )


class DiscreteChange(BaseModel):
    """A discrete state selection the transaction pass must schedule around.

    A wheel selection is masked and given its settle time; a shutter selection takes
    the visibility latency it crosses. This records the selection, not a schedule.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_id: str
    channel: ChannelName
    t_ms: int
    from_state: str | None = Field(
        description="State in force before; None only before the fixture's first state"
    )
    to_state: str
    settle_ms: int | None = Field(description="Declared settle of `to_state`; None when unknown")


def compile_physical_step(
    step: TemplateStep, context: StepCompileContext, *, sample_times_ms: tuple[int, ...]
) -> FixtureSegment:
    """Compile a step's explicit physical data into typed trajectories.

    Args:
        step: A physical step: `movement.physical` set and no legacy handler data.
        context: Step identity, timing, the fixture's physical profile and the
            song's musical phase map. Phase is measured from `context.start_ms`. For a
            step with component references, `resolved_components` supplies the start
            aim, and the held shutter, color, gobo and dimmer level in place of the
            step's own static states. `phase_offset_by_channel` and `pan_sign` carry
            the fixture's place in the step's phase distribution.
        sample_times_ms: The encoder's frame starts in the step's half-open span:
            every frame from its start to the last before its end. The step's start
            and end (`context`) must already be frame-grid times: the caller quantizes
            musical bounds with the encoder's `quantize_cue`. Phase is evaluated at
            these frame times against the exact musical phase map.

    Returns:
        A segment over the step with PAN and TILT (sampled, plus a terminal point at
        the step end), DIMMER and SHUTTER when the step declares their pulses, and
        SHUTTER, COLOR and GOBO as one held event when it declares a static state,
        and DIMMER as one held level when a referenced attribute preset supplies it.
        `metadata["phase_origin_ms"]` records the origin.

    Raises:
        PhysicalCompileError: For a legacy step, legacy data on a physical step, a
            fixture without a physical profile, or a start angle nothing sets.
        PhysicalChannelError: For a value, rate or state change the profile cannot honor,
            including a state or wheel the profile does not declare.
        OffGridTimeError: For a step bound or sample time off the frame grid.
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
    components = context.resolved_components
    if components is not None:
        pose = components.pose
    else:
        # Both set: checked by _require_physical_step.
        assert movement.start_pan_deg is not None and movement.start_tilt_deg is not None
        pose = PoseDegrees(pan_deg=movement.start_pan_deg, tilt_deg=movement.start_tilt_deg)
    offsets = context.phase_offset_by_channel
    for channel in (ChannelName.PAN, ChannelName.TILT):
        sign = context.pan_sign if channel is ChannelName.PAN else 1
        offset = offsets.get(channel, Fraction(0))
        trajectory = ContinuousTrajectory(
            unit="degree",
            points=tuple(
                PhysicalPoint(
                    t_ms=t,
                    value=_movement_value(
                        movement, pose, channel, phase_map, t, t0_ms, offset=offset, sign=sign
                    ),
                )
                for t in (*times, t1_ms)
            ),
            interpolation="linear",
        )
        _add(segment, channel, trajectory, profile)
        _check_travel_rate(context.fixture_id, channel, trajectory, profile)

    dimmer = step.dimmer.physical
    if dimmer is not None:
        offset = offsets.get(ChannelName.DIMMER, Fraction(0))
        _check_pulse_widths(
            context.fixture_id, ChannelName.DIMMER, dimmer, phase_map, t0_ms, t1_ms, offset=offset
        )
        levels = ContinuousTrajectory(
            unit="normalized",
            points=tuple(
                PhysicalPoint(
                    t_ms=t,
                    value=(
                        dimmer.high
                        if _pulse_high(dimmer, phase_map, t, t0_ms, offset=offset)
                        else dimmer.low
                    ),
                )
                for t in times
            ),
            interpolation="hold",
        )
        _add(segment, ChannelName.DIMMER, levels, profile)

    if components is not None and components.dimmer is not None:
        # A referenced attribute preset's level, held for the whole step.
        level = ContinuousTrajectory(
            unit="normalized",
            points=(PhysicalPoint(t_ms=t0_ms, value=components.dimmer),),
            interpolation="hold",
        )
        _add(segment, ChannelName.DIMMER, level, profile)

    shutter = step.physical_shutter
    if shutter is not None:
        offset = offsets.get(ChannelName.SHUTTER, Fraction(0))
        _check_pulse_widths(
            context.fixture_id, ChannelName.SHUTTER, shutter, phase_map, t0_ms, t1_ms, offset=offset
        )
        states = _shutter_states(shutter, phase_map, times, t0_ms, offset=offset)
        _add(segment, ChannelName.SHUTTER, states, profile)
        _check_shutter_timing(context.fixture_id, states, t1_ms, profile)

    # Static named states hold for the whole step. Entering one from the preceding
    # state (wheel masking and settle) is the transaction pass's work. Resolved
    # components already carry the step's own states where it sets them.
    held_states = (
        (step.physical_shutter_state, step.physical_color, step.physical_gobo)
        if components is None
        else (components.shutter, components.color, components.gobo)
    )
    for channel, state in zip(
        (ChannelName.SHUTTER, ChannelName.COLOR, ChannelName.GOBO), held_states, strict=True
    ):
        if state is not None:
            held = DiscreteTrajectory(events=(DiscretePoint(t_ms=t0_ms, state=state),))
            _add(segment, channel, held, profile)

    return segment


def resolve_discrete_state(capability: DiscreteCapability, state: str) -> int:
    """Return the byte the profile declares to select a named state.

    The one resolver the encoder also uses (`DiscreteCapability.resolve`): only the
    state's declared `value`, never a range bound, a byte between two states, or the
    open, closed or default state in place of an unknown one.

    Raises:
        ValueError: If the capability does not declare `state`.
    """
    return capability.resolve(state)


def wheel_changes(
    segments: Sequence[FixtureSegment], profiles: Mapping[str, FixtureCapabilities]
) -> tuple[DiscreteChange, ...]:
    """List every color and gobo wheel selection the encoded frames make.

    See `_discrete_changes`. Masking and settle are scheduled by the transaction pass,
    never by the legacy channel blender.
    """
    return _discrete_changes(segments, profiles, (ChannelName.COLOR, ChannelName.GOBO))


def shutter_changes(
    segments: Sequence[FixtureSegment], profiles: Mapping[str, FixtureCapabilities]
) -> tuple[DiscreteChange, ...]:
    """List every shutter selection the encoded frames make, within and across steps.

    See `_discrete_changes`. A step checks only the changes inside it; the change into
    its first state is the transaction pass's to time against close/open latency.
    """
    return _discrete_changes(segments, profiles, (ChannelName.SHUTTER,))


def _discrete_changes(
    segments: Sequence[FixtureSegment],
    profiles: Mapping[str, FixtureCapabilities],
    channels: tuple[ChannelName, ...],
) -> tuple[DiscreteChange, ...]:
    """Each fixture's selections on `channels`, as the encoder's frames carry them.

    Segments may come in any order and from any fixtures; each fixture uses its own
    profile. Where no segment authors a channel (before, between or after the
    segments that do) the encoder writes the default byte, which selects the
    profile's `default_state`, so that span holds the default state from time zero.
    A selection is reported where the state differs from the one before it, with the
    selected state's declared settle time; `from_state` is None only for a fixture's
    first state, whose predecessor is the run's initial state. Results are ordered by
    fixture, time and channel.

    Raises:
        ValueError: If a fixture has no profile, a channel is not a discrete physical
            value, or two of a fixture's segments overlap while both author a channel.
        PhysicalChannelError: If the profile does not declare an authored channel or
            state.
    """
    by_fixture: dict[str, list[FixtureSegment]] = defaultdict(list)
    for segment in segments:
        by_fixture[segment.fixture_id].append(segment)

    changes: list[DiscreteChange] = []
    for fixture_id, fixture_segments in sorted(by_fixture.items()):
        profile = profiles.get(fixture_id)
        if profile is None:
            raise ValueError(f"fixture {fixture_id!r} has no physical profile")
        ordered = sorted(fixture_segments, key=lambda segment: (segment.t0_ms, segment.t1_ms))
        for channel in channels:
            authored: list[tuple[FixtureSegment, DiscreteTrajectory]] = []
            for segment in ordered:
                value = segment.channels.get(channel)
                if value is None:
                    continue
                if not isinstance(value.physical, DiscreteTrajectory):
                    raise ValueError(f"{channel.value} is not a discrete physical value")
                check_physical_value(fixture_id, channel, value.physical, profile)
                authored.append((segment, value.physical))
            capability = profile.discrete.get(DISCRETE_KEYS[channel])
            if capability is None:
                continue

            timeline: list[tuple[int, str]] = []
            end_ms = 0
            for index, (segment, trajectory) in enumerate(authored):
                if segment.t0_ms < end_ms:
                    raise ValueError(
                        f"segments {authored[index - 1][0].segment_id!r} and "
                        f"{segment.segment_id!r} of {fixture_id} overlap and both author "
                        f"{channel.value}"
                    )
                if segment.t0_ms > end_ms:
                    timeline.append((end_ms, capability.default_state))
                timeline.extend((event.t_ms, event.state) for event in trajectory.events)
                end_ms = segment.t1_ms
            timeline.append((end_ms, capability.default_state))

            previous: str | None = None
            for t_ms, state in timeline:
                if state == previous:
                    continue
                changes.append(
                    DiscreteChange(
                        fixture_id=fixture_id,
                        channel=channel,
                        t_ms=t_ms,
                        from_state=previous,
                        to_state=state,
                        settle_ms=capability.states[state].settle_ms,
                    )
                )
                previous = state
    return tuple(
        sorted(
            changes,
            key=lambda change: (change.fixture_id, change.t_ms, channels.index(change.channel)),
        )
    )


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
    legacy = _legacy_fields(step)
    if legacy:
        raise reject(
            f"step {step.step_id!r} of template {context.template_id!r} sets legacy "
            f"{legacy}, which the physical renderer does not apply"
        )
    if context.physical_profile is None:
        raise reject(f"fixture {context.fixture_id!r} has no physical_profile")
    if context.resolved_components is None:
        for name in ("start_pan_deg", "start_tilt_deg"):
            if getattr(step.movement.physical, name) is None:
                raise reject(
                    f"step {step.step_id!r} of template {context.template_id!r} sets no "
                    f"movement.physical.{name} and no position reference; an axis nothing "
                    "sets is never centered"
                )
    return context.physical_profile


def is_physical_template(template: Template) -> bool:
    """Whether the physical renderer can compile every step of `template` as authored.

    Each step needs `movement.physical` and no legacy data, which the physical compile
    refuses. A preset applied at render time can still add legacy data.
    """
    return bool(template.steps) and all(
        step.movement.physical is not None and not _legacy_fields(step) for step in template.steps
    )


def _legacy_fields(step: TemplateStep) -> list[str]:
    """The legacy data a step sets, which the physical renderer does not apply."""
    return [
        *_non_default_fields("geometry", step.geometry),
        *_non_default_fields("movement", step.movement, keep="physical"),
        *_non_default_fields("dimmer", step.dimmer, keep="physical"),
        *(name for name in ("color", "shutter", "gobo") if getattr(step, name) is not None),
        *(["timing.phase_offset"] if step.timing.phase_offset != PhaseOffset() else []),
    ]


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
    grid_times = (("step start", t0_ms), ("step end", t1_ms), *(("sample time", t) for t in times))
    for name, time_ms in grid_times:
        if time_ms % EFFECT_GRID_MS:
            raise OffGridTimeError(name, time_ms)
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
    pose: PoseDegrees,
    channel: ChannelName,
    phase_map: MusicalPhaseMap,
    time_ms: int,
    origin_ms: int,
    *,
    offset: Fraction = Fraction(0),
    sign: int = 1,
) -> float:
    """The axis value at `time_ms`: `evaluate_physical_path` at the fixture's phase in
    this axis's domain, the step phase minus `offset` (exact), with pan sign `sign`."""
    is_pan = channel is ChannelName.PAN
    if movement.shape == "hold" or movement.period_beats is None:
        return pose.pan_deg if is_pan else pose.tilt_deg
    phase = (
        musical_phase_fraction(
            phase_map, time_ms, origin_ms=origin_ms, period_beats=movement.period_beats
        )
        - offset
    )
    try:
        at = evaluate_physical_path(movement, pose=pose, phase=phase, pan_sign=sign)
    except OverflowError as error:
        raise MusicalPhaseError(
            f"phase at {time_ms} ms over a {movement.period_beats}-beat period is too large"
        ) from error
    return at.pan_deg if is_pan else at.tilt_deg


def evaluate_physical_path(
    spec: PhysicalMovementSpec, *, pose: PoseDegrees, phase: Fraction, pan_sign: int = 1
) -> PoseDegrees:
    """The pose a movement kernel commands at `phase`, in unwrapped degrees.

    `phase` is the fixture's exact phase in cycles of `spec.period_beats`: the step
    phase minus its distribution offset. `pose` is the resolved base aim (the step's
    start angles or its position reference, never both added). `pan_sign` is the
    fixture's mirror sign; it multiplies the pan displacement, for a 2-D path the pan
    component after rotation and scaling, so a mirrored wing is the path reflected
    about the vertical through its aim. With `φ = float(phase)`, `E_p`/`E_t` the pan
    and tilt extents and `s = pan_sign`:

    - `hold`: `pose`.
    - `linear` (finite): `pose + (s·E_p, E_t) · clamp(φ, 0, 1)`.
    - `sine_pan`/`sine_tilt`: `pose + (s·E_p, E_t) · sin(2πφ)` (the unused extent is 0).

    The relative shapes are a centered displacement `(x, y)` at the path parameter
    `u = phase + transform.phase_cycles` (exact), or `1 - u` when `transform.reverse`:

    - `circle`: `(cos 2πu, sin 2πu)`, starting at `(1, 0)`.
    - `lissajous` with `lissajous_ratio` `(a, b)`, default `(1, 2)`: `(sin 2πau, sin 2πbu)`,
      starting at `(0, 0)`, the aim.
    - `sweep`, periodic: `(-cos 2πu, 0)`, from `(-1, 0)` edge to edge and back each
      period; finite: `(-cos π·clamp(u, 0, 1), 0)`, one way, then held at `(1, 0)`.

    It is rotated by `θ = transform.rotation_deg` (exact at quarter turns),
    `(x', y') = (x cos θ - y sin θ, x sin θ + y cos θ)`, then scaled and added:
    `pose + (s·E_p·x', E_t·y')`. Each extent is that axis's maximum signed displacement
    of the unrotated path. Turning a circle only shifts its phase, and a sweep stays
    within its extents; a lissajous turned off a quarter turn can exceed them, by up to
    √2 (about 1.24 for 1:2 at 45°). Extents are never normalized to a common radius
    and no endpoint is closed. Bounds and rate are the compile's checks, on every
    frame, not this function's.

    Raises:
        OverflowError: If the phase is too large to evaluate as a float.
    """
    if spec.shape == "hold" or spec.period_beats is None:
        return pose
    pan_extent = pan_sign * spec.pan_extent_deg
    if spec.shape in RELATIVE_PATH_SHAPES:
        x, y = _centered_displacement(spec, phase)
        return PoseDegrees.model_construct(
            pan_deg=pose.pan_deg + pan_extent * x, tilt_deg=pose.tilt_deg + spec.tilt_extent_deg * y
        )
    fraction = float(phase)
    if spec.shape == "linear":
        # A lagging head holds its start until its phase reaches zero.
        progress = min(max(fraction, 0.0), 1.0)
    else:
        # sine_pan/sine_tilt: the unused axis has zero extent by validation.
        progress = math.sin(2 * math.pi * fraction)
    return PoseDegrees.model_construct(
        pan_deg=pose.pan_deg + pan_extent * progress,
        tilt_deg=pose.tilt_deg + spec.tilt_extent_deg * progress,
    )


def _centered_displacement(spec: PhysicalMovementSpec, phase: Fraction) -> tuple[float, float]:
    """A relative shape's rotated displacement `(x', y')`; see `evaluate_physical_path`."""
    transform = spec.transform or PathTransform()
    travel = phase + exact_decimal(transform.phase_cycles)
    u = float(1 - travel if transform.reverse else travel)
    if spec.shape == "circle":
        x, y = math.cos(2 * math.pi * u), math.sin(2 * math.pi * u)
    elif spec.shape == "lissajous":
        a, b = spec.lissajous_ratio or (1, 2)
        x, y = math.sin(2 * math.pi * a * u), math.sin(2 * math.pi * b * u)
    elif spec.mode == "finite":
        x, y = -math.cos(math.pi * min(max(u, 0.0), 1.0)), 0.0
    else:
        x, y = -math.cos(2 * math.pi * u), 0.0
    if not transform.rotation_deg:
        return x, y
    quarters, rest = divmod(transform.rotation_deg, 90)
    if rest == 0:
        cos, sin = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[int(quarters) % 4]
    else:
        angle = math.radians(transform.rotation_deg)
        cos, sin = math.cos(angle), math.sin(angle)
    return x * cos - y * sin, x * sin + y * cos


def _pulse_high(
    pulse: PhysicalPulseSpec,
    phase_map: MusicalPhaseMap,
    time_ms: int,
    origin_ms: int,
    *,
    offset: Fraction = Fraction(0),
) -> bool:
    """High while the exact fractional pulse phase is in `[0, duty_cycle)`.

    The pulse phase is the step phase minus the fixture's `offset`, plus the pulse's
    own `phase_cycles`; a lagging head starts its step mid-cycle.
    """
    phase = (
        musical_phase_fraction(
            phase_map, time_ms, origin_ms=origin_ms, period_beats=pulse.period_beats
        )
        - offset
        + exact_decimal(pulse.phase_cycles)
    )
    return phase - math.floor(phase) < exact_decimal(pulse.duty_cycle)


def _check_pulse_widths(
    fixture_id: str,
    channel: ChannelName,
    pulse: PhysicalPulseSpec,
    phase_map: MusicalPhaseMap,
    t0_ms: int,
    t1_ms: int,
    *,
    offset: Fraction = Fraction(0),
) -> None:
    """Reject a high or low interval inside the step shorter than one frame.

    Edges are the exact times the fixture's pulse phase (`_pulse_high`) crosses a whole
    cycle (rising) or `duty_cycle` (falling). An interval cut by the step start or end
    is exempt, for a lagging head as for any phase shift: the cut interval at the start
    holds at least the step's first frame, one at the end shorter than a frame reaches
    no frame, and the transaction pass owns both boundaries.
    """
    duty = exact_decimal(pulse.duty_cycle)
    if duty == 1:
        return
    shift = exact_decimal(pulse.phase_cycles) - offset
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
    *,
    offset: Fraction = Fraction(0),
) -> DiscreteTrajectory:
    events: list[DiscretePoint] = []
    for t in times:
        high = _pulse_high(pulse, phase_map, t, origin_ms, offset=offset)
        state = pulse.high_state if high else pulse.low_state
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
