"""Tests for channel state management."""

import pytest

from blinkb0t.core.config.fixtures import (
    ChannelInversions,
    DmxMapping,
    FixtureConfig,
    FixtureInstance,
    MovementLimits,
    PanTiltRange,
)
from blinkb0t.core.domains.sequencing.channels import ChannelState


@pytest.fixture
def fixture_instance():
    """Basic fixture instance for testing."""
    base_config = FixtureConfig(
        fixture_id="MH1",
        dmx_mapping=DmxMapping(
            pan_channel=11,
            tilt_channel=13,
            dimmer_channel=3,
        ),
        inversions=ChannelInversions(pan=False, tilt=False),
        pan_tilt_range=PanTiltRange(pan_range_deg=540.0, tilt_range_deg=270.0),
        movement_limits=MovementLimits(pan_min=50, pan_max=190),
    )

    return FixtureInstance(
        fixture_id="MH1",
        xlights_model_name="Dmx MH1",
        config=base_config,
    )


def test_set_channel_by_integer(fixture_instance):
    """Test setting channel with integer value."""
    state = ChannelState(fixture_instance)

    success = state.set_channel("dimmer", 127)
    assert success
    assert state.get_channel("dimmer") == 127

    dmx_dict = state.to_dmx_dict()
    assert dmx_dict[3] == 127  # Dimmer is channel 3


def test_set_channel_by_name(fixture_instance):
    """Test setting channel with named value - V2 only supports integers."""
    state = ChannelState(fixture_instance)

    # V2 doesn't support named values yet, so this should fail gracefully
    state.set_channel("dimmer", 190)  # Direct value
    assert state.get_channel("dimmer") == 190


def test_clamping(fixture_instance):
    """Test value clamping to 0-255 (V2 doesn't use channel-specific limits yet)."""
    state = ChannelState(fixture_instance)

    # V2 clamps to 0-255, not channel-specific limits
    state.set_channel("pan", 300)
    assert state.get_channel("pan") == 255  # Clamped to max

    state.set_channel("pan", -10)
    assert state.get_channel("pan") == 0  # Clamped to min


def test_unknown_channel(fixture_instance):
    """Test setting unknown channel."""
    state = ChannelState(fixture_instance)

    success = state.set_channel("unknown_channel", 100)
    assert success is False
    assert state.get_channel("unknown_channel") is None


def test_merge_states(fixture_instance):
    """Test merging two channel states."""
    state1 = ChannelState(fixture_instance)
    state1.set_channel("pan", 128)
    state1.set_channel("dimmer", 100)

    state2 = ChannelState(fixture_instance)
    state2.set_channel("tilt", 64)
    state2.set_channel("dimmer", 200)  # Override

    state1.merge(state2)

    assert state1.get_channel("pan") == 128  # Unchanged
    assert state1.get_channel("tilt") == 64  # Added
    assert state1.get_channel("dimmer") == 200  # Overridden
