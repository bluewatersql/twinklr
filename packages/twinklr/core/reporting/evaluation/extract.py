"""Extract channel values for analysis and plotting.

A render is read from the frames it encoded (`physical_channel_values`): what the
delivered sequence commands, in physical units.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
from typing import TYPE_CHECKING

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
    Channels are keyed by `ChannelName` value.

    Args:
        frames: A render's encoded frames (`RenderingPipeline.frames`).
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
