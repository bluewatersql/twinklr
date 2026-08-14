"""Tests for `config/adapter.py::get_max_channel` (P1P-T6).

`get_max_channel` had zero callers before this task wired it into
`DmxSettingsBuilder` as the emitted-window authority, replacing the exporter's old
floor-16/round-to-16 heuristic. The spec's own risk note says to unit-test it
directly against the P1P-T2 rigs -- including fine channels and absent optional
channels -- before trusting it in the export path; this module is that test.
"""

from __future__ import annotations

from twinklr.core.config.adapter import get_max_channel
from twinklr.core.config.fixtures import DmxMapping


def test_pan_tilt_dimmer_only() -> None:
    """`mh4_minimal`-shaped mapping: no shutter/colour/gobo, no fine channels."""
    mapping = DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15)
    assert get_max_channel(mapping) == 15


def test_shutter_in_window_still_governs_the_max() -> None:
    """`mh4_shutter_in_window`-shaped mapping: shutter/colour/gobo below dimmer."""
    mapping = DmxMapping(
        pan_channel=11,
        tilt_channel=13,
        dimmer_channel=15,
        shutter_channel=6,
        color_channel=7,
        gobo_channel=8,
    )
    assert get_max_channel(mapping) == 15


def test_shutter_above_the_old_floor_widens_the_window() -> None:
    """`mh4_shutter_out_of_window`-shaped mapping: shutter/colour above 16.

    This is exactly the case the old floor-16/round-to-16 heuristic could not see:
    shutter was mapped but the emitted window never reached it.
    """
    mapping = DmxMapping(
        pan_channel=11,
        tilt_channel=13,
        dimmer_channel=15,
        shutter_channel=17,
        color_channel=18,
    )
    assert get_max_channel(mapping) == 18


def test_absent_optional_channels_do_not_contribute() -> None:
    """Channels the fixture does not map (None) are excluded from the max."""
    mapping = DmxMapping(pan_channel=1, tilt_channel=2, dimmer_channel=3)
    assert mapping.shutter_channel is None
    assert mapping.color_channel is None
    assert mapping.gobo_channel is None
    assert get_max_channel(mapping) == 3


def test_fine_channels_contribute_to_the_max() -> None:
    """16-bit pan/tilt fine channels count toward the window even though the
    exporter currently has no declared default for them (P1P-T6 scope: only
    shutter/colour/gobo gain declared defaults)."""
    mapping = DmxMapping(
        pan_channel=11,
        tilt_channel=13,
        dimmer_channel=15,
        pan_fine_channel=20,
        tilt_fine_channel=21,
        use_16bit_pan_tilt=True,
    )
    assert get_max_channel(mapping) == 21


def test_channel_with_config_objects_resolve_to_their_channel_number() -> None:
    """A channel may be declared as `ChannelWithConfig` rather than a bare int."""
    from twinklr.core.config.fixtures import ChannelWithConfig

    mapping = DmxMapping(
        pan_channel=ChannelWithConfig(channel=11),
        tilt_channel=13,
        dimmer_channel=15,
        shutter_channel=ChannelWithConfig(channel=20),
    )
    assert get_max_channel(mapping) == 20
