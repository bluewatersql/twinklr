"""Extract channel values for analysis and plotting.

A physical render is read from the frames it encoded (`physical_channel_values`): what
the delivered sequence commands, in physical units. A legacy render is sampled from the
normalized curves of its FixtureSegment IR (`extract_curves_from_segments`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
from typing import TYPE_CHECKING, Any

from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import AXIS_KEYS

if TYPE_CHECKING:
    from twinklr.core.config.fixtures import AxisCapability, FixtureCapabilities
    from twinklr.core.sequencer.moving_heads.export.frame_encoder import EncodedFixtureFrame

logger = logging.getLogger(__name__)


def physical_channel_values(
    frames: Sequence[EncodedFixtureFrame],
    profiles: Mapping[str, FixtureCapabilities],
    window_ms: tuple[int, int],
) -> dict[str, dict[str, list[float]]]:
    """Each fixture's per-frame physical values over the frames starting in a window.

    The encoded bytes are read back through each fixture's profile
    (`AxisCapability.decode`): pan, tilt and zoom in degrees, for each axis the profile
    declares, and dimmer as the emitted intensity: the dimmer's normalized value (1
    without a dimmer axis), or 0 in a frame whose shutter is in a state the profile
    declares extinguishing. Values are as exact as the DMX word, not the trajectory.
    Channels are keyed by `ChannelName` value, as legacy curves are.

    Args:
        frames: A physical render's encoded frames (`RenderingPipeline.frames`).
        profiles: Each fixture's physical profile.
        window_ms: `(start_ms, end_ms)`; frames starting in `[start_ms, end_ms)` are read.

    Returns:
        fixture_id -> channel name -> one value per frame, in frame order.
    """
    start_ms, end_ms = window_ms
    values: dict[str, dict[str, list[float]]] = {}
    for frame in frames:
        if not start_ms <= frame.time_ms < end_ms:
            continue
        profile = profiles[frame.fixture_id]
        data = dict(frame.channels)
        channels = values.setdefault(frame.fixture_id, {})
        for channel in POSE_CHANNELS:
            axis = profile.axes.get(AXIS_KEYS[channel])
            if axis is not None:
                channels.setdefault(channel.value, []).append(_axis_value(axis, data))
        shutter = profile.discrete.get("shutter")
        dark = shutter is not None and any(
            state.range_min <= data[shutter.offset] <= state.range_max
            for name, state in shutter.states.items()
            if name in profile.visibility.extinguishing_shutter_states
        )
        dimmer = profile.axes.get("dimmer")
        intensity = 1.0 if dimmer is None else _axis_value(dimmer, data)
        channels.setdefault(ChannelName.DIMMER.value, []).append(0.0 if dark else intensity)
    return values


POSE_CHANNELS = (ChannelName.PAN, ChannelName.TILT, ChannelName.ZOOM)
"""The channels `physical_channel_values` reads in degrees, where the profile has them."""


def _axis_value(axis: AxisCapability, data: Mapping[int, int]) -> float:
    """The physical value the encoded bytes command on an axis."""
    return float(axis.decode(axis.default_word(data)))


def extract_curves_from_segments(
    segments: list[Any],
    section_window_ms: tuple[int, int],
    samples_per_bar: int,
    bar_duration_ms: float,
) -> dict[str, dict[str, list[float]]]:
    """Extract curve samples from segments within a time window.

    Samples curves at regular intervals across the section window,
    interpolating within segments and returning 0 for gaps.

    Args:
        segments: List of FixtureSegment IR objects
        section_window_ms: (start_ms, end_ms) time window
        samples_per_bar: Number of samples to take per bar
        bar_duration_ms: Duration of one bar in milliseconds

    Returns:
        Dict mapping fixture_id -> {channel_name -> [samples]}

    Example:
        >>> curves = extract_curves_from_segments(
        ...     segments=ir_segments,
        ...     section_window_ms=(0, 10000),
        ...     samples_per_bar=96,
        ...     bar_duration_ms=1875.0,
        ... )
        >>> "fixture_01" in curves
        True
        >>> "PAN" in curves["fixture_01"]
        True
    """
    start_ms, end_ms = section_window_ms
    duration_ms = end_ms - start_ms
    num_samples = int((duration_ms / bar_duration_ms) * samples_per_bar)

    logger.debug(
        f"Extracting curves: window={start_ms}-{end_ms}ms, "
        f"samples={num_samples}, "
        f"duration={duration_ms}ms"
    )

    # Initialize result structure
    curves: dict[str, dict[str, list[float]]] = {}

    # Group segments by fixture
    by_fixture: dict[str, list[Any]] = {}
    for seg in segments:
        # Skip segments outside window
        if seg.t0_ms >= end_ms or seg.t1_ms <= start_ms:
            continue
        by_fixture.setdefault(seg.fixture_id, []).append(seg)

    logger.debug(f"Found {len(by_fixture)} fixtures with segments in window")

    # Sample each fixture's curves
    for fixture_id, fixture_segments in by_fixture.items():
        fixture_curves = {}

        for channel in [ChannelName.PAN, ChannelName.TILT, ChannelName.DIMMER]:
            samples = _sample_channel_over_window(
                segments=fixture_segments,
                channel=channel,
                window_ms=(start_ms, end_ms),
                num_samples=num_samples,
            )
            fixture_curves[channel.value] = samples

        curves[fixture_id] = fixture_curves

    return curves


def _sample_channel_over_window(
    segments: list[Any],
    channel: ChannelName,
    window_ms: tuple[int, int],
    num_samples: int,
) -> list[float]:
    """Sample a single channel over a time window.

    Args:
        segments: Segments for this fixture
        channel: Channel to sample
        window_ms: (start_ms, end_ms)
        num_samples: Number of samples to take

    Returns:
        List of sampled values (normalized 0-1)
    """
    start_ms, end_ms = window_ms
    duration_ms = end_ms - start_ms

    if num_samples == 0 or duration_ms == 0:
        return []

    samples = []

    for i in range(num_samples):
        # Calculate sample time
        t_ms = start_ms + (i / num_samples) * duration_ms

        # Sample at this time
        value = _sample_at_time(segments, channel, t_ms)
        samples.append(value)

    return samples


def _sample_at_time(
    segments: list[Any],
    channel: ChannelName,
    t_ms: float,
) -> float:
    """Sample channel value at a specific time.

    Finds the active segment at t_ms and interpolates the curve value.
    Returns 0 if no segment is active.

    Args:
        segments: Segments to search
        channel: Channel to sample
        t_ms: Time in milliseconds

    Returns:
        Normalized value (0-1)
    """
    # Find segment containing t_ms
    for seg in segments:
        if seg.t0_ms <= t_ms < seg.t1_ms:
            channel_value = seg.channels.get(channel)
            if not channel_value:
                continue

            # Check for curve points
            if channel_value.value_points:
                # Interpolate within segment
                seg_duration = seg.t1_ms - seg.t0_ms
                t_norm = (t_ms - seg.t0_ms) / seg_duration if seg_duration > 0 else 0.0

                return _interpolate_curve_points(channel_value.value_points, t_norm)

            # Static value
            elif channel_value.static_dmx is not None:
                # Convert DMX to normalized
                return float(channel_value.static_dmx) / 255.0

    # No segment found - return 0
    return 0.0


def _interpolate_curve_points(points: list[Any], t_norm: float) -> float:
    """Linear interpolation in curve points.

    Args:
        points: List of CurvePoint objects with .t and .v attributes
        t_norm: Normalized time (0-1) within segment

    Returns:
        Interpolated value at t_norm
    """
    if not points:
        return 0.0

    # Handle edge cases
    if len(points) == 1:
        return float(points[0].v)

    # Find bracketing points
    for i in range(len(points) - 1):
        p0, p1 = points[i], points[i + 1]

        if p0.t <= t_norm <= p1.t:
            # Linear interpolation
            t_range = p1.t - p0.t
            if t_range > 0:
                alpha = (t_norm - p0.t) / t_range
                return float(p0.v + alpha * (p1.v - p0.v))
            else:
                return float(p0.v)

    # Outside range - use nearest
    if t_norm <= points[0].t:
        return float(points[0].v)
    return float(points[-1].v)
