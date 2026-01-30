"""Adapter utilities for fixture configuration.

Provides helper functions to extract and aggregate fixture configuration data
for use in sequencing and effect generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import ChannelWithConfig, FixtureGroup


def _to_int(channel: int | ChannelWithConfig | None) -> int | None:
    """Extract integer channel number from channel config.

    Args:
        channel: Channel number or ChannelWithConfig object

    Returns:
        Integer channel number, or None if channel is None
    """
    if channel is None:
        return None
    if isinstance(channel, int):
        return channel
    # ChannelWithConfig has a .channel attribute
    return channel.channel


def get_inversion_map(fixtures: FixtureGroup) -> dict[int, int]:
    """Get DMX channel inversion map for all fixtures in group.

    Aggregates inversion flags from all fixtures, mapping DMX channel numbers
    to inversion flags (0 = not inverted, 1 = inverted).

    Args:
        fixtures: Fixture group to extract inversions from

    Returns:
        Dict mapping DMX channel number to inversion flag (0 or 1)

    Example:
        >>> inv_map = get_inversion_map(fixture_group)
        >>> inv_map[11]  # Pan channel
        1  # Inverted
        >>> inv_map[13]  # Tilt channel
        0  # Not inverted
    """
    inversion_map: dict[int, int] = {}

    # Expand fixtures to ensure we have full FixtureInstance objects
    expanded_fixtures = fixtures.expand_fixtures()

    for fixture in expanded_fixtures:
        dmx_mapping = fixture.config.dmx_mapping
        inversions = fixture.config.inversions

        # Map each channel type to its inversion flag
        channel_inversions = [
            (_to_int(dmx_mapping.pan_channel), inversions.pan),
            (_to_int(dmx_mapping.tilt_channel), inversions.tilt),
            (_to_int(dmx_mapping.dimmer_channel), inversions.dimmer),
            (_to_int(dmx_mapping.shutter_channel), inversions.shutter),
            (_to_int(dmx_mapping.color_channel), inversions.color),
            (_to_int(dmx_mapping.gobo_channel), inversions.gobo),
        ]

        for channel_num, is_inverted in channel_inversions:
            if channel_num is not None:
                inversion_map[channel_num] = 1 if is_inverted else 0

    return inversion_map


def get_max_channel(fixtures: FixtureGroup) -> int:
    """Get maximum DMX channel number used across all fixtures.

    Args:
        fixtures: Fixture group to analyze

    Returns:
        Maximum DMX channel number (1-512)

    Example:
        >>> max_ch = get_max_channel(fixture_group)
        >>> max_ch
        13  # Highest channel used is tilt at DMX 13
    """
    max_channel = 0

    # Expand fixtures to ensure we have full FixtureInstance objects
    expanded_fixtures = fixtures.expand_fixtures()

    for fixture in expanded_fixtures:
        dmx_mapping = fixture.config.dmx_mapping

        # Check all possible channels
        channels = [
            _to_int(dmx_mapping.pan_channel),
            _to_int(dmx_mapping.tilt_channel),
            _to_int(dmx_mapping.dimmer_channel),
            _to_int(dmx_mapping.pan_fine_channel),
            _to_int(dmx_mapping.tilt_fine_channel),
            _to_int(dmx_mapping.shutter_channel),
            _to_int(dmx_mapping.color_channel),
            _to_int(dmx_mapping.gobo_channel),
        ]

        for ch in channels:
            if ch is not None:
                max_channel = max(max_channel, ch)

    return max_channel
