"""Shared fixtures for channel tests."""

from unittest.mock import Mock

import pytest

from blinkb0t.core.config.fixtures import DmxMapping, FixtureConfig, FixtureInstance


def _create_mock_fixture():
    """Helper to create a mock fixture."""
    from blinkb0t.core.config.fixtures import ChannelInversions

    fixture = Mock(spec=FixtureInstance)
    fixture.fixture_id = "MH1"
    fixture.xlights_model_name = "Dmx MH1"  # xLights model name for this fixture
    fixture.config = Mock(spec=FixtureConfig)
    fixture.config.dmx_mapping = Mock(spec=DmxMapping)

    # Mock channel properties (both old and new attribute names for compatibility)
    fixture.config.dmx_mapping.pan = 1
    fixture.config.dmx_mapping.pan_channel = 1
    fixture.config.dmx_mapping.tilt = 2
    fixture.config.dmx_mapping.tilt_channel = 2
    fixture.config.dmx_mapping.dimmer = 3
    fixture.config.dmx_mapping.dimmer_channel = 3
    fixture.config.dmx_mapping.shutter = 4
    fixture.config.dmx_mapping.color = 5
    fixture.config.dmx_mapping.gobo = 6
    fixture.config.dmx_mapping.pan_fine_channel = None
    fixture.config.dmx_mapping.tilt_fine_channel = None
    fixture.config.dmx_mapping.use_16bit_pan_tilt = False

    # Mock inversions (no inversions by default)
    fixture.config.inversions = ChannelInversions()

    # Mock limits
    from blinkb0t.core.config.fixtures import MovementLimits

    fixture.config.limits = MovementLimits()

    # Mock degrees_to_dmx method (returns tuple of (pan_dmx, tilt_dmx))
    # For test purposes, simple conversion: degrees * 255 / 540 for pan, degrees * 255 / 270 for tilt
    def degrees_to_dmx(pose):
        pan_dmx = int((pose.pan_deg + 270) * 255 / 540)  # Normalize -270 to 270 -> 0 to 255
        tilt_dmx = int((pose.tilt_deg + 135) * 255 / 270)  # Normalize -135 to 135 -> 0 to 255
        return (pan_dmx, tilt_dmx)

    fixture.config.degrees_to_dmx = Mock(side_effect=degrees_to_dmx)

    return fixture


@pytest.fixture
def mock_fixture():
    """Create a mock fixture for testing."""
    return _create_mock_fixture()


@pytest.fixture
def mock_channel_state():
    """Create a mock ChannelState for testing."""
    from blinkb0t.core.domains.sequencing.channels.state import ChannelState

    fixture = _create_mock_fixture()
    state = ChannelState(fixture=fixture)
    # Set some values
    state.set_channel("pan", 128)
    state.set_channel("tilt", 64)
    return state
