"""Frame-accurate DMX byte encoding for the physical moving-head renderer.

Physical segments are sampled at every effect-grid frame start and composed into the
fixture's complete declared channel footprint: declared default bytes plus the states
the segments resolve to. A pan or tilt word is encoded once per frame, from the exact
sampled value, and split into its coarse and fine bytes, so a coarse carry is never
interpolated apart from its fine byte. Identical adjacent frames merge into runs that
the exporter writes as constant DMX effects. Output budgets fail the render; they never
drop frames.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from typing import Literal, NamedTuple

from twinklr.core.config.fixtures.capabilities import MAX_DMX_EFFECT_CHANNELS, FixtureCapabilities
from twinklr.core.config.models import MHRenderPolicy
from twinklr.core.formats.xlights.sequence.emission import EmissionSession
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    AXIS_KEYS,
    DISCRETE_KEYS,
    ContinuousTrajectory,
    PhysicalChannelError,
    PhysicalValue,
    check_physical_value,
)
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.diagnostics import MHDiagnostic

ENCODER_VERSION = "1"
"""Bumped by hand in the commit that intentionally changes encoded physical bytes."""


@dataclass(frozen=True)
class EncodedFixtureFrame:
    """One fixture's complete byte state for the frame `[time_ms, time_ms + 20)`.

    `channels` holds `(offset, byte)` for every model-relative offset 1..footprint.
    """

    time_ms: int
    fixture_id: str
    channels: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class FrameRun:
    """Adjacent identical frames, written as one constant DMX effect."""

    frame: EncodedFixtureFrame
    end_ms: int

    @property
    def start_ms(self) -> int:
        return self.frame.time_ms


@dataclass(frozen=True)
class QuantizedCue:
    """A cue's requested time and the frame it lands on."""

    requested_ms: int
    actual_ms: int


@dataclass(frozen=True)
class CueTiming:
    """One cue the encoder quantizes, with its requested and actual time, for trace.

    `channel` is None for a segment's own start and end.
    """

    fixture_id: str
    segment_id: str
    channel: ChannelName | None
    kind: Literal["segment_start", "segment_end", "cue"]
    requested_ms: int
    actual_ms: int


@dataclass(frozen=True)
class OutputMeasure:
    """Actual size of a physical render's output."""

    effect_count: int
    xsq_bytes: int


class PhysicalOutputError(Exception):
    """Physical output the backend cannot carry or the job's budgets do not allow."""

    def __init__(self, diagnostic: MHDiagnostic, measure: OutputMeasure | None = None) -> None:
        self.diagnostic = diagnostic
        self.measure = measure
        super().__init__(diagnostic.message)


class _Linear(NamedTuple):
    """Linear points: raw times, exact values, sampled from the first point's frame."""

    times: list[int]
    values: list[Fraction]
    start_frame: int


class _Steps(NamedTuple):
    """Hold points or discrete events: the frames their cues land on, and their values."""

    frames: list[int]
    values: list[float] | list[str]


type _Sampler = _Linear | _Steps


def quantize_cue(requested_ms: int) -> QuantizedCue:
    """Snap a cue to the emission seam's nearest grid frame, ties to the later frame.

    The displacement is at most half a frame (10 ms).
    """
    actual_ms, _ = EmissionSession.quantize_interval(requested_ms, requested_ms + EFFECT_GRID_MS)
    return QuantizedCue(requested_ms=requested_ms, actual_ms=actual_ms)


def frame_times(duration_ms: int) -> tuple[int, ...]:
    """Every frame start below `duration_ms`; the last frame may end past it."""
    return tuple(range(0, duration_ms, EFFECT_GRID_MS))


def segment_frame_span(segment: FixtureSegment) -> tuple[int, int]:
    """The half-open frame span `[start, end)` a physical segment samples.

    Raises:
        ValueError: If quantizing its bounds leaves no frame.
    """
    start = quantize_cue(segment.t0_ms).actual_ms
    end = quantize_cue(segment.t1_ms).actual_ms
    if end <= start:
        raise ValueError(
            f"segment {segment.segment_id!r} of {segment.fixture_id} "
            f"({segment.t0_ms}-{segment.t1_ms} ms) is zero-length on the {EFFECT_GRID_MS} ms grid"
        )
    return start, end


def quantized_cues(segments: Sequence[FixtureSegment]) -> tuple[CueTiming, ...]:
    """Every cue the encoder quantizes, with requested and actual times, for trace.

    Per segment in order: its start and end, then each physical channel's step cues
    (hold points and discrete events). Linear points are sampled exactly at frame
    starts, so they are not cues.
    """
    cues: list[CueTiming] = []
    for segment in segments:
        bounds: tuple[tuple[Literal["segment_start", "segment_end"], int], ...] = (
            ("segment_start", segment.t0_ms),
            ("segment_end", segment.t1_ms),
        )
        for kind, requested in bounds:
            cues.append(_cue_timing(segment, None, kind, requested))
        for channel, channel_value in segment.channels.items():
            if channel_value.physical is not None:
                cues.extend(
                    _cue_timing(segment, channel, "cue", requested)
                    for requested in _step_cue_times(channel_value.physical)
                )
    return tuple(cues)


def _cue_timing(
    segment: FixtureSegment,
    channel: ChannelName | None,
    kind: Literal["segment_start", "segment_end", "cue"],
    requested_ms: int,
) -> CueTiming:
    return CueTiming(
        fixture_id=segment.fixture_id,
        segment_id=segment.segment_id,
        channel=channel,
        kind=kind,
        requested_ms=requested_ms,
        actual_ms=quantize_cue(requested_ms).actual_ms,
    )


def _step_cue_times(value: PhysicalValue) -> list[int]:
    if isinstance(value, ContinuousTrajectory):
        return [] if value.interpolation == "linear" else [point.t_ms for point in value.points]
    return [event.t_ms for event in value.events]


def encode_fixture_frames(
    segments: Sequence[FixtureSegment],
    capabilities: FixtureCapabilities,
    *,
    frame_times_ms: tuple[int, ...],
) -> tuple[EncodedFixtureFrame, ...]:
    """Encode one fixture's physical segments as complete frames at `frame_times_ms`.

    Each segment samples the frames in its quantized half-open span. Linear values are
    sampled exactly at the frame start; hold values and discrete states change on their
    quantized cue frame; after its last point a trajectory holds its terminal value.
    Channels no segment writes keep the profile's declared default byte.

    Raises:
        ValueError: If segments name more than one fixture, frame times are empty or
            not increasing grid frames, a segment is zero-length on the grid or samples
            none of the frames, or the profile lacks a default byte.
        PhysicalChannelError: If a channel holds no physical value, a value the
            profile cannot honor, a sample before its first point, cues that land on
            one frame or at or after the segment's end, or two segments write the same
            channel in one frame.
        PhysicalOutputError: If the footprint exceeds the DMX effect's 48 channels.
    """
    fixture_ids = {segment.fixture_id for segment in segments}
    if len(fixture_ids) != 1:
        raise ValueError(f"frames encode one fixture's segments; got {sorted(fixture_ids)}")
    (fixture_id,) = fixture_ids
    footprint = range(1, capabilities.footprint + 1)
    if capabilities.footprint > MAX_DMX_EFFECT_CHANNELS:
        raise PhysicalOutputError(
            MHDiagnostic(
                code="unsupported_backend_channel",
                severity="error",
                message=(
                    f"{fixture_id}: profile {capabilities.profile_id!r} footprint "
                    f"{capabilities.footprint} exceeds the DMX effect's "
                    f"{MAX_DMX_EFFECT_CHANNELS} channels"
                ),
                fixture_id=fixture_id,
                action="rejected",
            )
        )
    if missing := sorted(set(footprint) - capabilities.defaults.keys()):
        raise ValueError(
            f"profile {capabilities.profile_id!r} has no default byte for offsets {missing}"
        )
    if (
        not frame_times_ms
        or any(t < 0 or t % EFFECT_GRID_MS for t in frame_times_ms)
        or any(later <= earlier for earlier, later in pairwise(frame_times_ms))
    ):
        raise ValueError(
            f"frame times must be increasing {EFFECT_GRID_MS} ms grid frames; got {frame_times_ms}"
        )

    # The segments covering each frame, found once per segment by bisection.
    writes: list[tuple[str, dict[ChannelName, _Sampler]]] = []
    covering: list[list[int]] = [[] for _ in frame_times_ms]
    for segment in segments:
        start, end = segment_frame_span(segment)
        samplers: dict[ChannelName, _Sampler] = {}
        for channel, channel_value in segment.channels.items():
            value = channel_value.physical
            if value is None:
                raise PhysicalChannelError(
                    fixture_id=fixture_id,
                    channel=channel,
                    time_ms=segment.t0_ms,
                    reason="not a physical value; the physical encoder takes no legacy DMX",
                )
            check_physical_value(fixture_id, channel, value, capabilities)
            samplers[channel] = _sampler(fixture_id, channel, value, end)
        first, stop = bisect_left(frame_times_ms, start), bisect_left(frame_times_ms, end)
        if first == stop:
            raise ValueError(
                f"segment {segment.segment_id!r} of {fixture_id} ({start}-{end} ms) samples "
                "no frame of the requested frame times"
            )
        for index in range(first, stop):
            covering[index].append(len(writes))
        writes.append((segment.segment_id, samplers))

    defaults = {offset: capabilities.defaults[offset] for offset in footprint}
    frames: list[EncodedFixtureFrame] = []
    for time_ms, covered in zip(frame_times_ms, covering, strict=True):
        state = dict(defaults)
        writers: dict[ChannelName, str] = {}
        for write in covered:
            segment_id, samplers = writes[write]
            for channel, sampler in samplers.items():
                if channel in writers:
                    raise PhysicalChannelError(
                        fixture_id=fixture_id,
                        channel=channel,
                        time_ms=time_ms,
                        reason=(
                            f"segments {writers[channel]!r} and {segment_id!r} both write it "
                            "with equal priority and no explicit override"
                        ),
                    )
                writers[channel] = segment_id
                state.update(_encode(fixture_id, channel, sampler, time_ms, capabilities))
        frames.append(
            EncodedFixtureFrame(
                time_ms=time_ms, fixture_id=fixture_id, channels=tuple(sorted(state.items()))
            )
        )
    return tuple(frames)


def _sampler(
    fixture_id: str, channel: ChannelName, value: PhysicalValue, segment_end: int
) -> _Sampler:
    """Prepare a channel for lookups; refuse step cues that would never emit.

    Two cues landing on one frame would drop all but the last, and a cue landing at or
    after the segment's quantized end would never be sampled.
    """
    if isinstance(value, ContinuousTrajectory) and value.interpolation == "linear":
        return _Linear(
            times=[point.t_ms for point in value.points],
            values=[Fraction(point.value) for point in value.points],
            start_frame=quantize_cue(value.points[0].t_ms).actual_ms,
        )
    requested = _step_cue_times(value)
    landed = [quantize_cue(t).actual_ms for t in requested]

    def fail(time_ms: int, reason: str) -> PhysicalChannelError:
        return PhysicalChannelError(
            fixture_id=fixture_id, channel=channel, time_ms=time_ms, reason=reason
        )

    for (earlier, later), (earlier_frame, frame) in zip(
        pairwise(requested), pairwise(landed), strict=True
    ):
        if frame == earlier_frame:
            raise fail(later, f"cues at {earlier} and {later} ms land on the same frame {frame} ms")
    for cue_ms, frame in zip(requested, landed, strict=True):
        if frame >= segment_end:
            raise fail(
                cue_ms,
                f"cue lands on {frame} ms, at or after the segment's end frame {segment_end} ms",
            )
    if isinstance(value, ContinuousTrajectory):
        return _Steps(frames=landed, values=[point.value for point in value.points])
    return _Steps(frames=landed, values=[event.state for event in value.events])


def _sample(sampler: _Sampler, time_ms: int) -> Fraction | float | str | None:
    """The value at a frame start, or None before the channel's first cue."""
    if isinstance(sampler, _Steps):
        held = bisect_right(sampler.frames, time_ms)
        return sampler.values[held - 1] if held else None
    times, values = sampler.times, sampler.values
    if time_ms < sampler.start_frame:
        return None
    after = bisect_right(times, time_ms)
    if after == 0:
        return values[0]  # within the first point's quantization window
    if after == len(times):
        return values[-1]
    a, b = after - 1, after
    return values[a] + (values[b] - values[a]) * Fraction(time_ms - times[a], times[b] - times[a])


def _encode(
    fixture_id: str,
    channel: ChannelName,
    sampler: _Sampler,
    time_ms: int,
    capabilities: FixtureCapabilities,
) -> dict[int, int]:
    """Bytes by offset for one channel's value at a frame."""

    def fail(reason: str) -> PhysicalChannelError:
        return PhysicalChannelError(
            fixture_id=fixture_id, channel=channel, time_ms=time_ms, reason=reason
        )

    sample = _sample(sampler, time_ms)
    if sample is None:
        raise fail("sampled before its first point; its value there is unknown")
    if isinstance(sample, str):
        wheel = capabilities.discrete[DISCRETE_KEYS[channel]]
        return {wheel.offset: wheel.resolve(sample)}
    axis = capabilities.axes[AXIS_KEYS[channel]]
    try:
        word = axis.dmx_word(sample)
    except ValueError as error:
        raise fail(str(error)) from error
    if axis.fine_offset is None:
        return {axis.coarse_offset: word}
    return {axis.coarse_offset: word >> 8, axis.fine_offset: word & 0xFF}


def coalesce_frames(frames: Sequence[EncodedFixtureFrame]) -> tuple[FrameRun, ...]:
    """Merge each fixture's adjacent frames whose bytes are all identical.

    Runs are returned per fixture in order of first appearance, then by time. Frames
    separated by a gap are never merged.

    Raises:
        ValueError: If a frame is off the frame grid or a fixture's frames are not
            increasing.
    """
    runs: dict[str, list[FrameRun]] = {}
    for frame in frames:
        if frame.time_ms < 0 or frame.time_ms % EFFECT_GRID_MS:
            raise ValueError(
                f"{frame.fixture_id} frame at {frame.time_ms} ms is not on the "
                f"{EFFECT_GRID_MS} ms frame grid"
            )
        fixture_runs = runs.setdefault(frame.fixture_id, [])
        last = fixture_runs[-1] if fixture_runs else None
        if last is not None and frame.time_ms < last.end_ms:
            raise ValueError(
                f"{frame.fixture_id} frame at {frame.time_ms} ms overlaps the frame before it"
            )
        if (
            last is not None
            and frame.time_ms == last.end_ms
            and frame.channels == last.frame.channels
        ):
            fixture_runs[-1] = FrameRun(frame=last.frame, end_ms=frame.time_ms + EFFECT_GRID_MS)
        else:
            fixture_runs.append(FrameRun(frame=frame, end_ms=frame.time_ms + EFFECT_GRID_MS))
    return tuple(run for fixture_runs in runs.values() for run in fixture_runs)


def measure_output(runs: Sequence[FrameRun], serialized_xsq: bytes) -> OutputMeasure:
    """Count the effects the runs emit and the serialized `.xsq`'s exact bytes."""
    return OutputMeasure(effect_count=len(runs), xsq_bytes=len(serialized_xsq))


def check_output_budget(measure: OutputMeasure, policy: MHRenderPolicy) -> None:
    """Fail when physical output exceeds the job's budgets; never decimate to fit.

    Raises:
        PhysicalOutputError: With code `output_budget_exceeded` and the measure.
    """
    over = []
    if measure.effect_count > policy.max_effects:
        over.append(f"{measure.effect_count} effects exceed max_effects {policy.max_effects}")
    if measure.xsq_bytes > policy.max_xsq_bytes:
        over.append(f"{measure.xsq_bytes} bytes exceed max_xsq_bytes {policy.max_xsq_bytes}")
    if over:
        raise PhysicalOutputError(
            MHDiagnostic(
                code="output_budget_exceeded",
                severity="error",
                message=f"Physical output rejected: {'; '.join(over)}. No frames were dropped.",
                action="rejected",
            ),
            measure,
        )
