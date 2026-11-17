"""Step compilation.

`compile_step` turns a template step's explicit data into a
`FixtureSegment` whose channels hold typed trajectories: pan/tilt and the zoom's beam
angle in degrees, the dimmer as a normalized level, the shutter and color and gobo
wheels as named states.
A named state selects only the byte the profile declares for it
(`resolve_discrete_state`); a wheel change is one event, never a sweep through the
states between, and an undeclared state or wheel is rejected, never replaced by open
or zero. Motion and pulses are evaluated on musical phase from the step start, never
on sample-index parity or an average tempo; a step distributed over the rig topology
evaluates each fixture at the step phase minus its offset in that domain, and its pan
displacement times its mirror sign. Relative paths (circle, lissajous, sweep) move
about the resolved aim (`evaluate_path`). Nothing is clamped: an out-of-range
value, a travel rate above the configured speed, motion at an unknown speed, a pulse
interval shorter than one frame, or a shutter change faster than its known latency
and settle time is rejected.

The caller supplies the sample times: the encoder's frame starts, at most one frame
apart, so the checked values are exactly the commanded ones. The value at each sample
depends only on that sample's time. Pan and tilt also carry an exact terminal point
at the step end, so the end state is the kernel's, not the last frame's.
"""

from __future__ import annotations

import bisect
from collections import defaultdict
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import pairwise
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.config.fixtures.capabilities import DiscreteCapability, FixtureCapabilities
from twinklr.core.config.fixtures.presets import PoseDegrees
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.context import StepCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    AXIS_KEYS,
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
    Movement,
    PathTransform,
    PulseSpec,
    ShutterPulse,
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


class CompileError(Exception):
    """A step the renderer cannot compile, with its diagnostic."""

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


def compile_step(
    step: TemplateStep,
    context: StepCompileContext,
    *,
    sample_times_ms: tuple[int, ...],
    shared: dict[tuple[Any, ...], PhysicalValue] | None = None,
) -> FixtureSegment:
    """Compile a step's explicit data into typed trajectories.

    Args:
        step: The template step.
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
        shared: The sampled channels other fixtures' compiles of this step instance,
            on the same profile and resolved components, have made and checked, by
            channel and what else the channel reads (its phase offset, and the pan
            sign for pan). A channel found there is reused as it is; one made here is
            added once it passes its checks.

    Returns:
        A segment over the step with PAN and TILT (sampled, plus a terminal point at
        the step end), DIMMER and SHUTTER when the step declares their pulses, and
        SHUTTER, COLOR and GOBO as one held event when it declares a static state,
        and DIMMER as one held level when a referenced attribute preset supplies it.
        On a profile with a zoom axis, ZOOM always: the step's `zoom` sampled
        as pan is, or, without one, the profile's default word held through the step,
        so the transaction pass holds the zoom between cues. Without a zoom axis a step
        whose zoom declares `omit_optional_zoom` gets none and
        `metadata["omitted_optional"]` is `"zoom"`. `metadata["phase_origin_ms"]`
        records the origin.

    Raises:
        CompileError: For a fixture without a physical profile, a start angle
            nothing sets, or a zoom on a profile without a zoom axis that is not
            optional.
        PhysicalChannelError: For a value, rate or state change the profile cannot honor,
            including a state or wheel the profile does not declare.
        OffGridTimeError: For a step bound or sample time off the frame grid.
        ValueError: For invalid sample times or a context without a phase map.
    """
    t0_ms = context.start_ms
    t1_ms = context.start_ms + context.duration_ms
    profile = _require_step(step, context)
    if context.phase_map is None:
        raise ValueError("the step compile needs the song's musical phase map")
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

    movement = step.movement
    components = context.resolved_components
    if components is not None:
        pose = components.pose
    else:
        # Both set: checked by _require_step.
        assert movement.start_pan_deg is not None and movement.start_tilt_deg is not None
        pose = PoseDegrees(pan_deg=movement.start_pan_deg, tilt_deg=movement.start_tilt_deg)
    offsets = context.phase_offset_by_channel
    samples = (*times, t1_ms)
    pan_offset = offsets.get(ChannelName.PAN, Fraction(0))
    shared = {} if shared is None else shared
    poses: list[tuple[float, float]] | None = None
    for channel in (ChannelName.PAN, ChannelName.TILT):
        offset = offsets.get(channel, Fraction(0))
        sign = context.pan_sign if channel is ChannelName.PAN else 1
        key = (channel, offset, sign)
        if _reuse(segment, channel, shared.get(key)):
            continue
        if poses is None or offset != pan_offset:
            # Each sample's path value holds both axes: pan's pass yields tilt's too where
            # both share a phase (tilt ignores the pan sign), so the path is evaluated
            # once per sample.
            poses = _path_values(
                movement, pose, phase_map, samples, t0_ms, offset=offset, sign=context.pan_sign
            )
        axis = 0 if channel is ChannelName.PAN else 1
        trajectory = ContinuousTrajectory(
            unit="degree",
            points=tuple(
                PhysicalPoint(t_ms=t, value=values[axis])
                for t, values in zip(samples, poses, strict=True)
            ),
            interpolation="linear",
        )
        _add(segment, channel, trajectory, profile)
        _check_travel_rate(context.fixture_id, channel, trajectory, profile)
        shared[key] = trajectory

    _add_zoom(step, context, segment, profile, times, t1_ms, shared)

    dimmer = step.dimmer
    if dimmer is not None:
        offset = offsets.get(ChannelName.DIMMER, Fraction(0))
        dimmer_key = (ChannelName.DIMMER, offset)
        if not _reuse(segment, ChannelName.DIMMER, shared.get(dimmer_key)):
            _check_pulse_widths(
                context.fixture_id,
                ChannelName.DIMMER,
                dimmer,
                phase_map,
                t0_ms,
                t1_ms,
                offset=offset,
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
            shared[dimmer_key] = levels

    if components is not None and components.dimmer is not None:
        # A referenced attribute preset's level, held for the whole step.
        level = ContinuousTrajectory(
            unit="normalized",
            points=(PhysicalPoint(t_ms=t0_ms, value=components.dimmer),),
            interpolation="hold",
        )
        _add(segment, ChannelName.DIMMER, level, profile)

    shutter = step.shutter
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
        (step.shutter_state, step.color, step.gobo)
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


def _add_zoom(
    step: TemplateStep,
    context: StepCompileContext,
    segment: FixtureSegment,
    profile: FixtureCapabilities,
    times: tuple[int, ...],
    t1_ms: int,
    shared: dict[tuple[Any, ...], PhysicalValue],
) -> None:
    """The step's ZOOM on a profile with a zoom axis; see `compile_step`."""
    zoom = step.zoom
    axis = profile.axes.get("zoom")
    if axis is None:
        if zoom is None:
            return
        if zoom.if_unsupported != "omit_optional_zoom":
            raise CompileError(
                MHDiagnostic(
                    code="unsupported_attribute",
                    severity="error",
                    message=(
                        f"step {step.step_id!r} of template {context.template_id!r} sets "
                        f"zoom, but profile {profile.profile_id!r} declares no zoom "
                        "axis; declare one, or make the zoom optional with "
                        "if_unsupported 'omit_optional_zoom'"
                    ),
                    fixture_id=context.fixture_id,
                    section_id=context.section_id,
                    action="rejected",
                )
            )
        segment.add_metadata("omitted_optional", "zoom")
        return
    # A wave follows pan's phase offset.
    key = (ChannelName.ZOOM, context.phase_offset_by_channel.get(ChannelName.PAN, Fraction(0)))
    if _reuse(segment, ChannelName.ZOOM, shared.get(key)):
        return
    if zoom is None or zoom.shape == "hold":
        # Unauthored, the encoder would write the default byte between and inside cues;
        # held explicitly, the same bytes, the transaction pass keeps it through gaps.
        value = (
            axis.word_center(axis.default_word(profile.defaults))
            if zoom is None
            else zoom.start_deg
        )
        points: tuple[PhysicalPoint, ...] = (
            PhysicalPoint(t_ms=times[0], value=value),
            PhysicalPoint(t_ms=t1_ms, value=value),
        )
    else:
        movement = step.movement
        phase_map = context.phase_map
        # Both checked: a zoom sine needs a periodic movement; the compile, a phase map.
        assert movement.period_beats is not None
        assert phase_map is not None
        period = movement.period_beats
        offset = context.phase_offset_by_channel.get(ChannelName.PAN, Fraction(0))

        def wave(time_ms: int) -> float:
            phase = musical_phase_fraction(
                phase_map, time_ms, origin_ms=times[0], period_beats=period
            )
            return zoom.start_deg + zoom.extent_deg * math.sin(2 * math.pi * float(phase - offset))

        points = tuple(PhysicalPoint(t_ms=t, value=wave(t)) for t in (*times, t1_ms))
    trajectory = ContinuousTrajectory(unit="degree", points=points, interpolation="linear")
    _add(segment, ChannelName.ZOOM, trajectory, profile)
    _check_travel_rate(context.fixture_id, ChannelName.ZOOM, trajectory, profile)
    shared[key] = trajectory


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

    See `_discrete_changes`. Masking and settle are scheduled by the transaction pass.
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


def slice_segment(segment: FixtureSegment, start_ms: int, end_ms: int) -> FixtureSegment:
    """Return the part of a segment in `[start_ms, end_ms)`.

    Continuous values are interpolated at the boundaries (at the end only when a later
    point defines it, as a compiled pan/tilt terminal point always does, so the slice's
    end point is its terminal point); the discrete state in force at `start_ms` is carried to it.
    Identity, metadata and the phase origin are kept, so motion does not restart.

    Raises:
        ValueError: If the span is empty or outside the segment.
    """
    if not segment.t0_ms <= start_ms < end_ms <= segment.t1_ms:
        raise ValueError(
            f"slice [{start_ms}, {end_ms}) must be non-empty and inside "
            f"[{segment.t0_ms}, {segment.t1_ms}]"
        )
    channels: dict[ChannelName, ChannelValue] = {}
    for channel, value in segment.channels.items():
        channels[channel] = ChannelValue(
            channel=channel, physical=_slice_value(value.physical, start_ms, end_ms)
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


def _require_step(step: TemplateStep, context: StepCompileContext) -> FixtureCapabilities:
    def reject(message: str) -> CompileError:
        return CompileError(
            MHDiagnostic(
                code="unsupported_attribute",
                severity="error",
                message=message,
                fixture_id=context.fixture_id,
                section_id=context.section_id,
                action="rejected",
            )
        )

    if context.physical_profile is None:
        raise reject(f"fixture {context.fixture_id!r} has no physical_profile")
    if context.resolved_components is None:
        for name in ("start_pan_deg", "start_tilt_deg"):
            if getattr(step.movement, name) is None:
                raise reject(
                    f"step {step.step_id!r} of template {context.template_id!r} sets no "
                    f"movement.{name} and no position reference; an axis nothing "
                    "sets is never centered"
                )
    return context.physical_profile


def _check_sample_times(times: Sequence[int], t0_ms: int, t1_ms: int) -> tuple[int, ...]:
    if not times:
        raise ValueError("the step compile needs at least one sample time")
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


def _path_values(
    movement: Movement,
    pose: PoseDegrees,
    phase_map: MusicalPhaseMap,
    times: Sequence[int],
    origin_ms: int,
    *,
    offset: Fraction = Fraction(0),
    sign: int = 1,
) -> list[tuple[float, float]]:
    """The `(pan, tilt)` at each of `times`: `evaluate_path` at the fixture's
    phase, the step phase minus `offset` (exact), with pan sign `sign`."""
    period = movement.period_beats
    if movement.shape == "hold" or period is None:
        return [evaluate_path(movement, pose, 0, 1, sign)] * len(times)
    values = []
    for time_ms in times:
        phase = musical_phase_fraction(phase_map, time_ms, origin_ms=origin_ms, period_beats=period)
        n, d = phase.numerator, phase.denominator
        if offset:
            n, d = n * offset.denominator - offset.numerator * d, d * offset.denominator
        try:
            values.append(evaluate_path(movement, pose, n, d, sign))
        except OverflowError as error:
            raise MusicalPhaseError(
                f"phase at {time_ms} ms over a {period}-beat period is too large"
            ) from error
    return values


def evaluate_path(
    spec: Movement, pose: PoseDegrees, n: int, d: int, pan_sign: int = 1
) -> tuple[float, float]:
    """The `(pan, tilt)` a movement kernel commands at the phase `n / d`, in unwrapped
    degrees.

    `n / d` (`d > 0`, not necessarily reduced) is the fixture's exact phase in cycles of
    `spec.period_beats`: the step phase minus its distribution offset. `pose` is the
    resolved base aim (the step's start angles or its position reference, never both
    added). `pan_sign` is the fixture's mirror sign; it multiplies the pan
    displacement, for a 2-D path the pan component after rotation and scaling, so a
    mirrored wing is the path reflected about the vertical through its aim. With
    `φ = n / d` as a float, `E_p`/`E_t` the pan and tilt extents and `s = pan_sign`:

    - `hold`: `pose`.
    - `linear` (finite): `pose + (s·E_p, E_t) · clamp(φ, 0, 1)`.
    - `sine_pan`/`sine_tilt`: `pose + (s·E_p, E_t) · sin(2πφ)` (the unused extent is 0).

    The relative shapes are a centered displacement `(x, y)` at the path parameter
    `u = n / d + transform.phase_cycles` (exact), or `1 - u` when `transform.reverse`:

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
    frame, not this function's. Only floats of exact values are taken: integer true
    division rounds `n / d` exactly as `float(Fraction(n, d))` does.

    Raises:
        OverflowError: If the phase is too large to evaluate as a float.
    """
    if spec.shape == "hold" or spec.period_beats is None:
        return pose.pan_deg, pose.tilt_deg
    pan_extent = pan_sign * spec.pan_extent_deg
    if spec.shape in RELATIVE_PATH_SHAPES:
        x, y = _centered_displacement(spec, n, d)
        return pose.pan_deg + pan_extent * x, pose.tilt_deg + spec.tilt_extent_deg * y
    fraction = n / d
    if spec.shape == "linear":
        # A lagging head holds its start until its phase reaches zero.
        progress = min(max(fraction, 0.0), 1.0)
    else:
        # sine_pan/sine_tilt: the unused axis has zero extent by validation.
        progress = math.sin(2 * math.pi * fraction)
    return pose.pan_deg + pan_extent * progress, pose.tilt_deg + spec.tilt_extent_deg * progress


_NO_TRANSFORM = PathTransform()
"""A relative path's transform when it sets none, built once rather than per sample."""


def _centered_displacement(spec: Movement, n: int, d: int) -> tuple[float, float]:
    """A relative shape's rotated displacement `(x', y')` at the phase `n / d`; see
    `evaluate_path`."""
    transform = spec.transform or _NO_TRANSFORM
    if transform.phase_cycles:
        shift = exact_decimal(transform.phase_cycles)
        n, d = n * shift.denominator + shift.numerator * d, d * shift.denominator
    u = (d - n if transform.reverse else n) / d
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
    pulse: PulseSpec,
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
    phase = musical_phase_fraction(
        phase_map, time_ms, origin_ms=origin_ms, period_beats=pulse.period_beats
    )
    # The phase as `n / d` (`d > 0`, not necessarily reduced), and its fractional part
    # `phase - floor(phase)`, `(n mod d) / d`, against the duty: exact, in integers.
    n, d = phase.numerator, phase.denominator
    if offset:
        n, d = n * offset.denominator - offset.numerator * d, d * offset.denominator
    if pulse.phase_cycles:
        shift = exact_decimal(pulse.phase_cycles)
        n, d = n * shift.denominator + shift.numerator * d, d * shift.denominator
    duty = exact_decimal(pulse.duty_cycle)
    return n % d * duty.denominator < duty.numerator * d


def _check_pulse_widths(
    fixture_id: str,
    channel: ChannelName,
    pulse: PulseSpec,
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
    pulse: ShutterPulse,
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


def _reuse(segment: FixtureSegment, channel: ChannelName, value: PhysicalValue | None) -> bool:
    """Put a shared channel, already checked on this profile, on `segment`; False when
    there is none (`compile_step`)."""
    if value is None:
        return False
    segment.channels[channel] = ChannelValue(channel=channel, physical=value)
    return True


def _check_travel_rate(
    fixture_id: str,
    channel: ChannelName,
    trajectory: ContinuousTrajectory,
    profile: FixtureCapabilities,
) -> None:
    """Reject travel between consecutive points faster than the configured speed."""
    axis = profile.axes[AXIS_KEYS[channel]]
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
    times = [point.t_ms for point in points]  # strictly increasing
    head = PhysicalPoint(t_ms=start_ms, value=_value_at(value, start_ms, times))
    inside_points = points[bisect.bisect_right(times, start_ms) : bisect.bisect_left(times, end_ms)]
    tail = (
        [PhysicalPoint(t_ms=end_ms, value=_value_at(value, end_ms, times))]
        if value.interpolation == "linear" and points[-1].t_ms >= end_ms
        else []
    )
    return ContinuousTrajectory(
        unit=value.unit, points=(head, *inside_points, *tail), interpolation=value.interpolation
    )


def _value_at(trajectory: ContinuousTrajectory, time_ms: int, times: Sequence[int]) -> float:
    """The value at `time_ms`; `times` are the points' times."""
    points = trajectory.points
    index = bisect.bisect_right(times, time_ms) - 1  # the last point at or before it
    if index < 0:
        raise ValueError(f"no value is defined at {time_ms} ms")
    left = points[index]
    if trajectory.interpolation == "hold" or left.t_ms == time_ms or index + 1 == len(points):
        return left.value
    right = points[index + 1]
    fraction = (time_ms - left.t_ms) / (right.t_ms - left.t_ms)
    return left.value + fraction * (right.value - left.value)
