"""Tests for BoundaryEnforcer using FixtureInstance."""

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
def basic_fixture() -> FixtureInstance:
    """Create a basic fixture instance for testing."""
    config = FixtureConfig(
        fixture_id="TEST_MH1",
        dmx_universe=1,
        dmx_start_address=1,
        channel_count=16,
        dmx_mapping=DmxMapping(
            pan_channel=1,
            tilt_channel=2,
            dimmer_channel=3,
        ),
        inversions=ChannelInversions(
            pan=False,
            tilt=False,
        ),
        pan_tilt_range=PanTiltRange(
            pan_range_deg=540.0,
            tilt_range_deg=270.0,
        ),
        orientation=Orientation(
            pan_front_dmx=128,
            tilt_zero_dmx=22,
            tilt_up_dmx=112,
        ),
        limits=MovementLimits(
            pan_min=50,
            pan_max=190,
            tilt_min=5,
            tilt_max=125,
            avoid_backward=True,
        ),
    )
    return FixtureInstance(
        fixture_id="TEST_MH1",
        config=config,
        xlights_model_name="Dmx MH1",
    )


@pytest.fixture
def fixture_no_avoid_backward() -> FixtureInstance:
    """Create fixture with avoid_backward disabled."""
    config = FixtureConfig(
        fixture_id="TEST_MH2",
        dmx_universe=1,
        dmx_start_address=17,
        channel_count=16,
        dmx_mapping=DmxMapping(
            pan_channel=17,
            tilt_channel=18,
            dimmer_channel=19,
        ),
        inversions=ChannelInversions(
            pan=False,
            tilt=False,
        ),
        pan_tilt_range=PanTiltRange(
            pan_range_deg=540.0,
            tilt_range_deg=270.0,
        ),
        orientation=Orientation(
            pan_front_dmx=128,
            tilt_zero_dmx=22,
            tilt_up_dmx=112,
        ),
        limits=MovementLimits(
            pan_min=50,
            pan_max=190,
            tilt_min=5,
            tilt_max=125,
            avoid_backward=False,
        ),
    )
    return FixtureInstance(
        fixture_id="TEST_MH2",
        config=config,
        xlights_model_name="Dmx MH2",
    )


class TestBoundaryEnforcerInit:
    """Tests for BoundaryEnforcer initialization."""

    def test_init_with_fixture(self, basic_fixture: FixtureInstance) -> None:
        """Test initialization with FixtureInstance."""
        enforcer = BoundaryEnforcer(basic_fixture)
        assert enforcer.fixture == basic_fixture

    def test_init_calculates_avoid_backward(self, basic_fixture: FixtureInstance) -> None:
        """Test that avoid_backward limits are calculated."""
        enforcer = BoundaryEnforcer(basic_fixture)

        # With avoid_backward=True and 540° range, ±90° = ±42 DMX units from center (128)
        # So effective limits should be narrower than hardware limits
        pan_min, pan_max = enforcer.pan_limits

        # Effective limits should be narrower due to avoid_backward
        assert pan_min >= basic_fixture.config.limits.pan_min
        assert pan_max <= basic_fixture.config.limits.pan_max

    def test_init_without_avoid_backward(self, fixture_no_avoid_backward: FixtureInstance) -> None:
        """Test initialization without avoid_backward constraint."""
        enforcer = BoundaryEnforcer(fixture_no_avoid_backward)
        pan_min, pan_max = enforcer.pan_limits

        # Without avoid_backward, should use hardware limits directly
        assert pan_min == fixture_no_avoid_backward.config.limits.pan_min
        assert pan_max == fixture_no_avoid_backward.config.limits.pan_max


class TestClampPan:
    """Tests for clamp_pan() method."""

    def test_clamp_pan_delegates_to_fixture(self, basic_fixture: FixtureInstance) -> None:
        """Test that clamp_pan uses effective limits (with avoid_backward)."""
        enforcer = BoundaryEnforcer(basic_fixture)

        # Test with value that needs clamping
        # BoundaryEnforcer uses effective limits (with avoid_backward constraint)
        result = enforcer.clamp_pan(200)

        # Should be clamped to effective max, not hardware max
        _pan_min, pan_max = enforcer.pan_limits
        assert result == pan_max
        assert result <= basic_fixture.config.limits.pan_max  # Within hardware limits

    def test_clamp_pan_with_geometry(self, basic_fixture: FixtureInstance) -> None:
        """Test clamp_pan with geometry constraints."""
        # Set geometry constraints
        enforcer = BoundaryEnforcer(
            basic_fixture,
            geometry_pan_min=80,
            geometry_pan_max=150,
        )

        # Geometry constraints intersect with effective limits (which include avoid_backward)
        # Effective limits are ~86-170 (due to avoid_backward), geometry is 80-150
        # Intersection: max(86, 80) = 86, min(170, 150) = 150
        pan_min, pan_max = enforcer.pan_limits
        expected_min = max(pan_min, 80)
        expected_max = min(pan_max, 150)

        assert enforcer.clamp_pan(60, respect_geometry=True) == expected_min
        assert enforcer.clamp_pan(160, respect_geometry=True) == expected_max
        assert enforcer.clamp_pan(100, respect_geometry=True) == 100

    def test_clamp_pan_ignore_geometry_when_not_requested(
        self, basic_fixture: FixtureInstance
    ) -> None:
        """Test that geometry is ignored when respect_geometry=False."""
        enforcer = BoundaryEnforcer(
            basic_fixture,
            geometry_pan_min=80,
            geometry_pan_max=150,
        )

        # Without respect_geometry, should use effective limits (not geometry)
        # Value of 60 should be clamped to effective min (not geometry min of 80)
        result = enforcer.clamp_pan(60, respect_geometry=False)
        pan_min, _ = enforcer.pan_limits
        assert result == pan_min  # Should use effective limit, not geometry


class TestClampTilt:
    """Tests for clamp_tilt() method."""

    def test_clamp_tilt_delegates_to_fixture(self, basic_fixture: FixtureInstance) -> None:
        """Test that clamp_tilt delegates to FixtureConfig."""
        enforcer = BoundaryEnforcer(basic_fixture)

        result = enforcer.clamp_tilt(200)
        expected = basic_fixture.config.clamp_tilt(200)
        assert result == expected

    def test_clamp_tilt_with_geometry(self, basic_fixture: FixtureInstance) -> None:
        """Test clamp_tilt with geometry constraints."""
        enforcer = BoundaryEnforcer(
            basic_fixture,
            geometry_tilt_min=20,
            geometry_tilt_max=100,
        )

        assert enforcer.clamp_tilt(10, respect_geometry=True) == 20
        assert enforcer.clamp_tilt(110, respect_geometry=True) == 100
        assert enforcer.clamp_tilt(50, respect_geometry=True) == 50


class TestDegreeConversion:
    """Tests for degree to DMX conversion methods."""

    def test_deg_to_pan_dmx_delegates(self, basic_fixture: FixtureInstance) -> None:
        """Test deg_to_pan_dmx delegates to FixtureConfig."""
        enforcer = BoundaryEnforcer(basic_fixture)

        result = enforcer.deg_to_pan_dmx(45.0)
        expected = basic_fixture.config.deg_to_pan_dmx(45.0)
        assert result == expected

    def test_deg_to_tilt_dmx_delegates(self, basic_fixture: FixtureInstance) -> None:
        """Test deg_to_tilt_dmx delegates to FixtureConfig."""
        enforcer = BoundaryEnforcer(basic_fixture)

        result = enforcer.deg_to_tilt_dmx(25.0)
        expected = basic_fixture.config.deg_to_tilt_dmx(25.0)
        assert result == expected

    def test_pan_deg_to_dmx_delta_delegates(self, basic_fixture: FixtureInstance) -> None:
        """Test pan_deg_to_dmx_delta delegates to FixtureConfig."""
        enforcer = BoundaryEnforcer(basic_fixture)

        result = enforcer.pan_deg_to_dmx_delta(45.0)
        expected = basic_fixture.config.pan_deg_to_dmx_delta(45.0)
        assert result == expected

    def test_tilt_deg_to_dmx_delta_delegates(self, basic_fixture: FixtureInstance) -> None:
        """Test tilt_deg_to_dmx_delta delegates to FixtureConfig."""
        enforcer = BoundaryEnforcer(basic_fixture)

        result = enforcer.tilt_deg_to_dmx_delta(25.0)
        expected = basic_fixture.config.tilt_deg_to_dmx_delta(25.0)
        assert result == expected


class TestChannelClamping:
    """Tests for channel clamping methods."""

    def test_clamp_channel_dimmer(self, basic_fixture: FixtureInstance) -> None:
        """Test clamping dimmer channel."""
        enforcer = BoundaryEnforcer(basic_fixture)

        # Dimmer should be 0-255
        assert enforcer.clamp_channel("dimmer", 300) == 255
        assert enforcer.clamp_channel("dimmer", -10) == 0
        assert enforcer.clamp_channel("dimmer", 128) == 128

    def test_clamp_channel_unknown_defaults(self, basic_fixture: FixtureInstance) -> None:
        """Test clamping unknown channel defaults to 0-255."""
        enforcer = BoundaryEnforcer(basic_fixture)

        # Unknown channels should default to full range
        assert enforcer.clamp_channel("unknown", 300) == 255
        assert enforcer.clamp_channel("unknown", -10) == 0


class TestProperties:
    """Tests for property methods."""

    def test_pan_limits_property(self, basic_fixture: FixtureInstance) -> None:
        """Test pan_limits property returns effective limits."""
        enforcer = BoundaryEnforcer(basic_fixture)
        pan_min, pan_max = enforcer.pan_limits

        # Should return effective limits (considering avoid_backward)
        assert isinstance(pan_min, int)
        assert isinstance(pan_max, int)
        assert pan_min < pan_max

    def test_tilt_limits_property(self, basic_fixture: FixtureInstance) -> None:
        """Test tilt_limits property."""
        enforcer = BoundaryEnforcer(basic_fixture)
        tilt_min, tilt_max = enforcer.tilt_limits

        assert tilt_min == basic_fixture.config.limits.tilt_min
        assert tilt_max == basic_fixture.config.limits.tilt_max


class TestValueCurveClamping:
    """Tests for value curve parameter clamping."""

    def test_clamp_value_curve_params_sine(self, basic_fixture: FixtureInstance) -> None:
        """Test clamping sine curve parameters."""
        from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType

        enforcer = BoundaryEnforcer(basic_fixture)

        # Sine curve: P2=amplitude, P4=center
        # If amplitude is too large, should be reduced
        _p1, p2, _p3, p4 = enforcer.clamp_value_curve_params(
            curve_type=NativeCurveType.SINE,
            p1=0.0,  # phase
            p2=100.0,  # amplitude (too large)
            p3=1.0,  # cycles
            p4=128.0,  # center
            min_limit=50,
            max_limit=190,
            channel_name="pan",
        )

        # Amplitude should be reduced to fit within limits
        assert p2 is not None
        assert p2 <= 70.0  # (190-50)/2 = 70
        assert p4 is not None

    def test_clamp_value_curve_params_ramp(self, basic_fixture: FixtureInstance) -> None:
        """Test clamping ramp curve parameters."""
        from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType

        enforcer = BoundaryEnforcer(basic_fixture)

        # Ramp: P1=start, P2=end
        p1, p2, _p3, _p4 = enforcer.clamp_value_curve_params(
            curve_type=NativeCurveType.RAMP,
            p1=0.0,  # start (below limit)
            p2=300.0,  # end (above limit)
            p3=None,
            p4=None,
            min_limit=50,
            max_limit=190,
            channel_name="pan",
        )

        # Values should be clamped to limits
        assert p1 == 50.0
        assert p2 == 190.0


class TestGeometryConstraints:
    """Tests for geometry constraint handling."""

    def test_geometry_constraints_intersection(self, basic_fixture: FixtureInstance) -> None:
        """Test that geometry constraints intersect with fixture limits."""
        # Geometry constraints narrower than fixture limits
        enforcer = BoundaryEnforcer(
            basic_fixture,
            geometry_pan_min=80,
            geometry_pan_max=150,
        )

        # When respecting geometry, should use intersection of effective and geometry limits
        pan_min, pan_max = enforcer.pan_limits
        expected_min = max(pan_min, 80)
        expected_max = min(pan_max, 150)

        assert enforcer.clamp_pan(60, respect_geometry=True) == expected_min
        assert enforcer.clamp_pan(160, respect_geometry=True) == expected_max

    def test_geometry_constraints_wider_than_fixture(self, basic_fixture: FixtureInstance) -> None:
        """Test geometry constraints wider than fixture limits are capped."""
        # Geometry constraints wider than fixture limits (50-190)
        enforcer = BoundaryEnforcer(
            basic_fixture,
            geometry_pan_min=20,  # Below fixture min (50)
            geometry_pan_max=200,  # Above fixture max (190)
        )

        # Fixture limits should still be respected
        assert enforcer.clamp_pan(30, respect_geometry=True) >= 50
        assert enforcer.clamp_pan(195, respect_geometry=True) <= 190


class TestPercentageConversion:
    """Tests for percentage to DMX conversion."""

    def test_pct_to_dmx(self, basic_fixture: FixtureInstance) -> None:
        """Test percentage to DMX conversion."""
        enforcer = BoundaryEnforcer(basic_fixture)

        assert enforcer.pct_to_dmx(0.0) == 0
        assert enforcer.pct_to_dmx(100.0) == 255
        assert enforcer.pct_to_dmx(50.0) == 128  # Approximately

    def test_pct_to_dmx_clamped(self, basic_fixture: FixtureInstance) -> None:
        """Test percentage conversion is clamped."""
        enforcer = BoundaryEnforcer(basic_fixture)

        assert enforcer.pct_to_dmx(-10.0) == 0
        assert enforcer.pct_to_dmx(150.0) == 255


class TestIntegration:
    """Integration tests for BoundaryEnforcer."""

    def test_enforcer_consistency_with_fixture(self, basic_fixture: FixtureInstance) -> None:
        """Test that enforcer respects avoid_backward constraints."""
        enforcer = BoundaryEnforcer(basic_fixture)

        # Enforcer uses effective limits (with avoid_backward)
        # FixtureConfig uses hardware limits
        # So they may differ
        test_value = 200
        enforcer_result = enforcer.clamp_pan(test_value)
        fixture_result = basic_fixture.config.clamp_pan(test_value)

        # Enforcer result should be more restrictive (or equal)
        assert enforcer_result <= fixture_result

        # Tilt should match (no avoid_backward for tilt)
        assert enforcer.clamp_tilt(test_value) == basic_fixture.config.clamp_tilt(test_value)

    def test_enforcer_with_all_geometry_constraints(self, basic_fixture: FixtureInstance) -> None:
        """Test enforcer with all geometry constraints set."""
        enforcer = BoundaryEnforcer(
            basic_fixture,
            geometry_pan_min=80,
            geometry_pan_max=150,
            geometry_tilt_min=20,
            geometry_tilt_max=100,
        )

        # Pan constraints intersect with effective limits (which include avoid_backward)
        pan_min, pan_max = enforcer.pan_limits
        expected_pan_min = max(pan_min, 80)
        expected_pan_max = min(pan_max, 150)

        # All constraints should be applied when requested
        assert enforcer.clamp_pan(60, respect_geometry=True) == expected_pan_min
        assert enforcer.clamp_pan(160, respect_geometry=True) == expected_pan_max
        assert enforcer.clamp_tilt(10, respect_geometry=True) == 20
        assert enforcer.clamp_tilt(110, respect_geometry=True) == 100

        # Without respect_geometry, geometry constraints are ignored
        # Value below effective limits
        assert enforcer.clamp_pan(60, respect_geometry=False) == pan_min
        # Value below fixture limits (but within geometry)
        assert (
            enforcer.clamp_tilt(1, respect_geometry=False) == basic_fixture.config.limits.tilt_min
        )
