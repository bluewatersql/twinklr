"""Tests for refactored ChannelState using FixtureInstance."""

from __future__ import annotations

import pytest

from blinkb0t.core.config.fixtures import (
    ChannelInversions,
    DmxMapping,
    FixtureConfig,
    FixtureInstance,
)
from blinkb0t.core.domains.sequencing.channels.state import ChannelState
from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec


@pytest.fixture
def basic_fixture() -> FixtureInstance:
    """Create a basic fixture for testing."""
    config = FixtureConfig(
        fixture_id="MH1",
        name="Test Moving Head",
        manufacturer="Test",
        model="TH-100",
        dmx_mapping=DmxMapping(
            pan_channel=1,
            tilt_channel=3,
            dimmer_channel=5,
            shutter_channel=6,
            color_channel=7,
            gobo_channel=8,
        ),
        inversions=ChannelInversions(pan=False, tilt=True, dimmer=False),
    )
    return FixtureInstance(
        fixture_id="MH1",
        config=config,
        xlights_model_name="Dmx MH1",
    )


def test_set_channel_basic(basic_fixture: FixtureInstance) -> None:
    """Test basic channel setting."""
    state = ChannelState(basic_fixture)

    # Set pan to 127
    success = state.set_channel("pan", 127)
    assert success is True

    # Verify value is stored
    dmx_dict = state.to_dmx_dict()
    assert dmx_dict[1] == 127  # Pan channel


def test_set_channel_with_inversion(basic_fixture: FixtureInstance) -> None:
    """Test channel setting with inversion."""
    state = ChannelState(basic_fixture)

    # Set tilt to 100 (tilt is inverted)
    state.set_channel("tilt", 100)

    # Should be inverted: 255 - 100 = 155
    dmx_dict = state.to_dmx_dict()
    assert dmx_dict[3] == 155


def test_set_channel_clamping(basic_fixture: FixtureInstance) -> None:
    """Test that values are clamped to 0-255."""
    state = ChannelState(basic_fixture)

    # Try to set out-of-range values
    state.set_channel("pan", 300)
    state.set_channel("tilt", -50)

    dmx_dict = state.to_dmx_dict()
    assert dmx_dict[1] == 255  # Clamped to max
    assert dmx_dict[3] == 255 - 0  # Inverted and clamped to min (255 - 0 = 255)


def test_set_channel_nonexistent(basic_fixture: FixtureInstance) -> None:
    """Test setting a channel that doesn't exist."""
    state = ChannelState(basic_fixture)

    # Try to set a channel not in DMX mapping
    success = state.set_channel("prism", 50)
    assert success is False

    # Should not be in DMX dict
    dmx_dict = state.to_dmx_dict()
    assert "prism" not in dmx_dict


def test_get_channel(basic_fixture: FixtureInstance) -> None:
    """Test getting channel values."""
    state = ChannelState(basic_fixture)

    state.set_channel("pan", 100)
    value = state.get_channel("pan")
    assert value == 100


def test_get_channel_nonexistent(basic_fixture: FixtureInstance) -> None:
    """Test getting a nonexistent channel."""
    state = ChannelState(basic_fixture)

    value = state.get_channel("prism")
    assert value is None


def test_value_curves(basic_fixture: FixtureInstance) -> None:
    """Test value curve support."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType

    state = ChannelState(basic_fixture)

    curve = ValueCurveSpec(type=NativeCurveType.RAMP, p1=0, p2=255)
    state.set_channel("pan", 127, value_curve=curve)

    # When value curve is set, base value should NOT be set
    dmx_dict = state.to_dmx_dict()
    assert 1 not in dmx_dict  # Pan channel should not have base value

    # But value curve should be stored
    curves_dict = state.to_value_curves_dict()
    assert 1 in curves_dict
    assert curves_dict[1] == curve


def test_to_dmx_dict(basic_fixture: FixtureInstance) -> None:
    """Test converting to DMX dict."""
    state = ChannelState(basic_fixture)

    state.set_channel("pan", 50)
    state.set_channel("tilt", 100)
    state.set_channel("dimmer", 200)

    dmx_dict = state.to_dmx_dict()
    assert dmx_dict[1] == 50  # Pan
    assert dmx_dict[3] == 155  # Tilt (inverted: 255 - 100)
    assert dmx_dict[5] == 200  # Dimmer


def test_merge_states(basic_fixture: FixtureInstance) -> None:
    """Test merging two channel states."""
    state1 = ChannelState(basic_fixture)
    state2 = ChannelState(basic_fixture)

    state1.set_channel("pan", 50)
    state2.set_channel("tilt", 100)
    state2.set_channel("dimmer", 200)

    state1.merge(state2)

    dmx_dict = state1.to_dmx_dict()
    assert dmx_dict[1] == 50  # From state1
    assert dmx_dict[3] == 155  # From state2 (inverted)
    assert dmx_dict[5] == 200  # From state2


def test_multiple_fixtures_different_mappings() -> None:
    """Test that different fixtures can have different channel mappings."""
    fixture1 = FixtureInstance(
        fixture_id="MH1",
        config=FixtureConfig(
            fixture_id="MH1",
            name="Fixture 1",
            manufacturer="Test",
            model="TH-100",
            dmx_mapping=DmxMapping(pan_channel=1, tilt_channel=3, dimmer_channel=5),
        ),
        xlights_model_name="Dmx MH1",
    )

    fixture2 = FixtureInstance(
        fixture_id="MH2",
        config=FixtureConfig(
            fixture_id="MH2",
            name="Fixture 2",
            manufacturer="Test",
            model="TH-200",
            dmx_mapping=DmxMapping(pan_channel=10, tilt_channel=12, dimmer_channel=14),
        ),
        xlights_model_name="Dmx MH2",
    )

    state1 = ChannelState(fixture1)
    state2 = ChannelState(fixture2)

    state1.set_channel("pan", 100)
    state2.set_channel("pan", 150)

    dmx1 = state1.to_dmx_dict()
    dmx2 = state2.to_dmx_dict()

    assert dmx1[1] == 100  # MH1 pan on channel 1
    assert dmx2[10] == 150  # MH2 pan on channel 10
