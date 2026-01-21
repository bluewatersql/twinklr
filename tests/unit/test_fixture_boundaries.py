"""Tests for fixture boundary calculation (per-fixture curves).

Phase 4: Per-Fixture Curves V2 Migration

Updated to test BoundaryEnforcer which replaced the old fixture_boundaries module.
"""

from __future__ import annotations

import pytest

from blinkb0t.core.config.fixtures import (
    ChannelInversions,
    DmxMapping,
    FixtureConfig,
    FixtureInstance,
    MovementLimits,
    Orientation,
    PanTiltRange,
)
from blinkb0t.core.domains.sequencing.moving_heads.boundary_enforcer import BoundaryEnforcer


@pytest.fixture
def standard_fixture() -> FixtureInstance:
    """Create a standard fixture with typical config."""
    config = FixtureConfig(
        fixture_id="MH1",
        name="Test MH",
        dmx_mapping=DmxMapping(
            pan_channel=1,
            tilt_channel=3,
            dimmer_channel=5,
            shutter_channel=7,
            color_channel=9,
            gobo_channel=11,
        ),
        inversions=ChannelInversions(),
        pan_tilt_range=PanTiltRange(pan_range_deg=540.0, tilt_range_deg=180.0),
        orientation=Orientation(pan_front_dmx=127, tilt_zero_dmx=127, tilt_up_dmx=170),
        limits=MovementLimits(
            pan_min=0,
            pan_max=255,
            tilt_min=50,
            tilt_max=200,
        ),
    )
    return FixtureInstance(
        fixture_id="MH1", config=config, start_channel=1, xlights_model_name="Test MH"
    )


class TestBoundaryEnforcer:
    """Test BoundaryEnforcer functionality."""

    def test_boundary_enforcer_initialization(self, standard_fixture):
        """Test that BoundaryEnforcer initializes with fixture."""
        enforcer = BoundaryEnforcer(standard_fixture)

        assert enforcer is not None
        assert enforcer.fixture == standard_fixture

    def test_pan_limits_respected(self, standard_fixture):
        """Test that pan limits are enforced."""
        enforcer = BoundaryEnforcer(standard_fixture)

        # Should clamp to limits
        assert enforcer.clamp_pan(300) <= standard_fixture.config.limits.pan_max
        assert enforcer.clamp_pan(-50) >= standard_fixture.config.limits.pan_min

    def test_tilt_limits_respected(self, standard_fixture):
        """Test that tilt limits are enforced."""
        enforcer = BoundaryEnforcer(standard_fixture)

        # Should clamp to limits
        assert enforcer.clamp_tilt(300) <= standard_fixture.config.limits.tilt_max
        assert enforcer.clamp_tilt(0) >= standard_fixture.config.limits.tilt_min

    def test_deg_to_pan_dmx(self, standard_fixture):
        """Test degree to pan DMX conversion."""
        enforcer = BoundaryEnforcer(standard_fixture)

        # 0 degrees should map to front position
        dmx_value = enforcer.deg_to_pan_dmx(0.0)
        assert 0 <= dmx_value <= 255

    def test_deg_to_tilt_dmx(self, standard_fixture):
        """Test degree to tilt DMX conversion."""
        enforcer = BoundaryEnforcer(standard_fixture)

        # 0 degrees should map to horizontal position
        dmx_value = enforcer.deg_to_tilt_dmx(0.0)
        assert 0 <= dmx_value <= 255

    def test_multiple_fixtures_have_different_boundaries(self):
        """Test that fixtures with different limits have different boundaries."""
        fixture1_config = FixtureConfig(
            fixture_id="MH1",
            name="Test MH 1",
            dmx_mapping=DmxMapping(pan_channel=1, tilt_channel=3, dimmer_channel=5),
            inversions=ChannelInversions(),
            pan_tilt_range=PanTiltRange(pan_range_deg=540.0, tilt_range_deg=180.0),
            orientation=Orientation(pan_front_dmx=127, tilt_zero_dmx=127, tilt_up_dmx=170),
            limits=MovementLimits(
                pan_min=0, pan_max=255, tilt_min=50, tilt_max=200, avoid_backward=False
            ),
        )
        fixture1 = FixtureInstance(
            fixture_id="MH1",
            config=fixture1_config,
            start_channel=1,
            xlights_model_name="Test MH 1",
        )

        fixture2_config = FixtureConfig(
            fixture_id="MH2",
            name="Test MH 2",
            dmx_mapping=DmxMapping(pan_channel=1, tilt_channel=3, dimmer_channel=5),
            inversions=ChannelInversions(),
            pan_tilt_range=PanTiltRange(pan_range_deg=540.0, tilt_range_deg=180.0),
            orientation=Orientation(pan_front_dmx=127, tilt_zero_dmx=127, tilt_up_dmx=170),
            limits=MovementLimits(
                pan_min=10, pan_max=245, tilt_min=60, tilt_max=190, avoid_backward=False
            ),
        )
        fixture2 = FixtureInstance(
            fixture_id="MH2",
            config=fixture2_config,
            start_channel=17,
            xlights_model_name="Test MH 2",
        )

        enforcer1 = BoundaryEnforcer(fixture1)
        enforcer2 = BoundaryEnforcer(fixture2)

        # Different limits should produce different boundaries
        assert enforcer1.pan_limits != enforcer2.pan_limits
        assert enforcer1.tilt_limits != enforcer2.tilt_limits
