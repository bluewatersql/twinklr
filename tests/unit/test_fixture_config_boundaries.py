"""Tests for FixtureConfig boundary and conversion helper methods."""

from __future__ import annotations

import pytest

from blinkb0t.core.config.fixtures import (
    ChannelInversions,
    DmxMapping,
    FixtureConfig,
    MovementLimits,
    Orientation,
    PanTiltRange,
)


@pytest.fixture
def basic_fixture_config() -> FixtureConfig:
    """Create a basic fixture config for testing."""
    return FixtureConfig(
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
        ),
    )


@pytest.fixture
def inverted_fixture_config() -> FixtureConfig:
    """Create a fixture config with inversions enabled."""
    return FixtureConfig(
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
            pan=True,
            tilt=True,
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
        ),
    )


class TestClampPan:
    """Tests for clamp_pan() method."""

    def test_clamp_pan_within_bounds(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that values within bounds are unchanged."""
        assert basic_fixture_config.clamp_pan(100) == 100
        assert basic_fixture_config.clamp_pan(50) == 50  # Min boundary
        assert basic_fixture_config.clamp_pan(190) == 190  # Max boundary

    def test_clamp_pan_below_min(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that values below min are clamped to min."""
        assert basic_fixture_config.clamp_pan(0) == 50
        assert basic_fixture_config.clamp_pan(25) == 50
        assert basic_fixture_config.clamp_pan(49) == 50

    def test_clamp_pan_above_max(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that values above max are clamped to max."""
        assert basic_fixture_config.clamp_pan(255) == 190
        assert basic_fixture_config.clamp_pan(200) == 190
        assert basic_fixture_config.clamp_pan(191) == 190

    def test_clamp_pan_edge_cases(self, basic_fixture_config: FixtureConfig) -> None:
        """Test edge cases."""
        assert basic_fixture_config.clamp_pan(-100) == 50  # Negative
        assert basic_fixture_config.clamp_pan(1000) == 190  # Way over


class TestClampTilt:
    """Tests for clamp_tilt() method."""

    def test_clamp_tilt_within_bounds(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that values within bounds are unchanged."""
        assert basic_fixture_config.clamp_tilt(50) == 50
        assert basic_fixture_config.clamp_tilt(5) == 5  # Min boundary
        assert basic_fixture_config.clamp_tilt(125) == 125  # Max boundary

    def test_clamp_tilt_below_min(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that values below min are clamped to min."""
        assert basic_fixture_config.clamp_tilt(0) == 5
        assert basic_fixture_config.clamp_tilt(3) == 5
        assert basic_fixture_config.clamp_tilt(4) == 5

    def test_clamp_tilt_above_max(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that values above max are clamped to max."""
        assert basic_fixture_config.clamp_tilt(255) == 125
        assert basic_fixture_config.clamp_tilt(150) == 125
        assert basic_fixture_config.clamp_tilt(126) == 125

    def test_clamp_tilt_edge_cases(self, basic_fixture_config: FixtureConfig) -> None:
        """Test edge cases."""
        assert basic_fixture_config.clamp_tilt(-50) == 5  # Negative
        assert basic_fixture_config.clamp_tilt(500) == 125  # Way over


class TestIsPanInBounds:
    """Tests for is_pan_in_bounds() method."""

    def test_is_pan_in_bounds_true(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that values within bounds return True."""
        assert basic_fixture_config.is_pan_in_bounds(100) is True
        assert basic_fixture_config.is_pan_in_bounds(50) is True  # Min
        assert basic_fixture_config.is_pan_in_bounds(190) is True  # Max
        assert basic_fixture_config.is_pan_in_bounds(120) is True

    def test_is_pan_in_bounds_false(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that values outside bounds return False."""
        assert basic_fixture_config.is_pan_in_bounds(0) is False
        assert basic_fixture_config.is_pan_in_bounds(49) is False
        assert basic_fixture_config.is_pan_in_bounds(191) is False
        assert basic_fixture_config.is_pan_in_bounds(255) is False
        assert basic_fixture_config.is_pan_in_bounds(-10) is False


class TestIsTiltInBounds:
    """Tests for is_tilt_in_bounds() method."""

    def test_is_tilt_in_bounds_true(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that values within bounds return True."""
        assert basic_fixture_config.is_tilt_in_bounds(50) is True
        assert basic_fixture_config.is_tilt_in_bounds(5) is True  # Min
        assert basic_fixture_config.is_tilt_in_bounds(125) is True  # Max
        assert basic_fixture_config.is_tilt_in_bounds(60) is True

    def test_is_tilt_in_bounds_false(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that values outside bounds return False."""
        assert basic_fixture_config.is_tilt_in_bounds(0) is False
        assert basic_fixture_config.is_tilt_in_bounds(4) is False
        assert basic_fixture_config.is_tilt_in_bounds(126) is False
        assert basic_fixture_config.is_tilt_in_bounds(255) is False
        assert basic_fixture_config.is_tilt_in_bounds(-5) is False


class TestDegToPanDmx:
    """Tests for deg_to_pan_dmx() method."""

    def test_deg_to_pan_dmx_center(self, basic_fixture_config: FixtureConfig) -> None:
        """Test conversion at center (0 degrees)."""
        # 0 degrees = front = pan_front_dmx
        dmx = basic_fixture_config.deg_to_pan_dmx(0.0)
        assert dmx == 128

    def test_deg_to_pan_dmx_positive(self, basic_fixture_config: FixtureConfig) -> None:
        """Test positive degrees (stage right)."""
        # Pan range is 540 degrees, so 255 DMX units / 540 deg = 0.472 DMX/deg
        # At 128 center, +45 degrees should be ~128 + 21 = 149
        dmx = basic_fixture_config.deg_to_pan_dmx(45.0)
        assert 148 <= dmx <= 150  # Allow small rounding variance

    def test_deg_to_pan_dmx_negative(self, basic_fixture_config: FixtureConfig) -> None:
        """Test negative degrees (stage left)."""
        # -45 degrees should be ~128 - 21 = 107
        dmx = basic_fixture_config.deg_to_pan_dmx(-45.0)
        assert 106 <= dmx <= 108

    def test_deg_to_pan_dmx_clamped(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that results are clamped to limits."""
        # Large positive should clamp to max (190)
        dmx = basic_fixture_config.deg_to_pan_dmx(1000.0)
        assert dmx == 190

        # Large negative should clamp to min (50)
        dmx = basic_fixture_config.deg_to_pan_dmx(-1000.0)
        assert dmx == 50

    def test_deg_to_pan_dmx_inverted(self, inverted_fixture_config: FixtureConfig) -> None:
        """Test with pan inversion enabled."""
        # With inversion, positive degrees become negative
        dmx_normal = inverted_fixture_config.deg_to_pan_dmx(45.0)
        # Should be less than center (inverted)
        assert dmx_normal < 128


class TestDegToTiltDmx:
    """Tests for deg_to_tilt_dmx() method."""

    def test_deg_to_tilt_dmx_zero(self, basic_fixture_config: FixtureConfig) -> None:
        """Test conversion at horizon (0 degrees)."""
        # 0 degrees = horizon = tilt_zero_dmx
        dmx = basic_fixture_config.deg_to_tilt_dmx(0.0)
        assert dmx == 22

    def test_deg_to_tilt_dmx_positive(self, basic_fixture_config: FixtureConfig) -> None:
        """Test positive degrees (up)."""
        # Tilt range is 270 degrees, so 255 DMX / 270 deg = 0.944 DMX/deg
        # +25 degrees from zero (22) should be ~22 + 24 = 46
        dmx = basic_fixture_config.deg_to_tilt_dmx(25.0)
        assert 45 <= dmx <= 47

    def test_deg_to_tilt_dmx_negative(self, basic_fixture_config: FixtureConfig) -> None:
        """Test negative degrees (down)."""
        # -10 degrees should be ~22 - 9 = 13
        dmx = basic_fixture_config.deg_to_tilt_dmx(-10.0)
        assert 12 <= dmx <= 14

    def test_deg_to_tilt_dmx_clamped(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that results are clamped to limits."""
        # Large positive should clamp to max (125)
        dmx = basic_fixture_config.deg_to_tilt_dmx(500.0)
        assert dmx == 125

        # Large negative should clamp to min (5)
        dmx = basic_fixture_config.deg_to_tilt_dmx(-500.0)
        assert dmx == 5

    def test_deg_to_tilt_dmx_inverted(self, inverted_fixture_config: FixtureConfig) -> None:
        """Test with tilt inversion enabled."""
        # With inversion, positive degrees become negative
        dmx = inverted_fixture_config.deg_to_tilt_dmx(25.0)
        # Should be less than zero position (inverted)
        assert dmx < 22


class TestPanDegToDmxDelta:
    """Tests for pan_deg_to_dmx_delta() method."""

    def test_pan_deg_to_dmx_delta_zero(self, basic_fixture_config: FixtureConfig) -> None:
        """Test zero delta."""
        assert basic_fixture_config.pan_deg_to_dmx_delta(0.0) == 0

    def test_pan_deg_to_dmx_delta_positive(self, basic_fixture_config: FixtureConfig) -> None:
        """Test positive delta."""
        # 45 degrees with 540 range: (45 / 540) * 255 = ~21
        delta = basic_fixture_config.pan_deg_to_dmx_delta(45.0)
        assert 20 <= delta <= 22

    def test_pan_deg_to_dmx_delta_negative(self, basic_fixture_config: FixtureConfig) -> None:
        """Test negative delta."""
        # -45 degrees should give ~-21
        delta = basic_fixture_config.pan_deg_to_dmx_delta(-45.0)
        assert -22 <= delta <= -20

    def test_pan_deg_to_dmx_delta_no_clamping(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that delta conversion doesn't clamp (just converts)."""
        # Large value should not be clamped, just converted
        delta = basic_fixture_config.pan_deg_to_dmx_delta(1000.0)
        # 1000 / 540 * 255 = ~472
        assert delta > 400  # Should be large, not clamped

    def test_pan_deg_to_dmx_delta_full_range(self, basic_fixture_config: FixtureConfig) -> None:
        """Test full range conversion."""
        # Full 540 degrees should give 255 DMX units
        delta = basic_fixture_config.pan_deg_to_dmx_delta(540.0)
        assert delta == 255


class TestTiltDegToDmxDelta:
    """Tests for tilt_deg_to_dmx_delta() method."""

    def test_tilt_deg_to_dmx_delta_zero(self, basic_fixture_config: FixtureConfig) -> None:
        """Test zero delta."""
        assert basic_fixture_config.tilt_deg_to_dmx_delta(0.0) == 0

    def test_tilt_deg_to_dmx_delta_positive(self, basic_fixture_config: FixtureConfig) -> None:
        """Test positive delta."""
        # 25 degrees with 270 range: (25 / 270) * 255 = ~24
        delta = basic_fixture_config.tilt_deg_to_dmx_delta(25.0)
        assert 23 <= delta <= 25

    def test_tilt_deg_to_dmx_delta_negative(self, basic_fixture_config: FixtureConfig) -> None:
        """Test negative delta."""
        # -25 degrees should give ~-24
        delta = basic_fixture_config.tilt_deg_to_dmx_delta(-25.0)
        assert -25 <= delta <= -23

    def test_tilt_deg_to_dmx_delta_no_clamping(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that delta conversion doesn't clamp."""
        # Large value should not be clamped
        delta = basic_fixture_config.tilt_deg_to_dmx_delta(500.0)
        # 500 / 270 * 255 = ~472
        assert delta > 400

    def test_tilt_deg_to_dmx_delta_full_range(self, basic_fixture_config: FixtureConfig) -> None:
        """Test full range conversion."""
        # Full 270 degrees should give 255 DMX units
        delta = basic_fixture_config.tilt_deg_to_dmx_delta(270.0)
        assert delta == 255


class TestIntegration:
    """Integration tests combining multiple methods."""

    def test_roundtrip_conversion(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that degree->DMX->degree roundtrip is consistent."""
        # Start with a known degree value
        original_pan_deg = 45.0
        original_tilt_deg = 25.0

        # Convert to DMX
        pan_dmx = basic_fixture_config.deg_to_pan_dmx(original_pan_deg)
        tilt_dmx = basic_fixture_config.deg_to_tilt_dmx(original_tilt_deg)

        # Convert back to degrees using existing method
        pose = basic_fixture_config.dmx_to_degrees(pan_dmx, tilt_dmx)

        # Should be close to original (within rounding error)
        assert abs(pose.pan_deg - original_pan_deg) < 1.0
        assert abs(pose.tilt_deg - original_tilt_deg) < 1.0

    def test_boundary_consistency(self, basic_fixture_config: FixtureConfig) -> None:
        """Test that clamp and is_in_bounds are consistent."""
        # Test a value that's out of bounds
        value_below = 30
        value_within = 100
        value_above = 200

        # Below min
        assert not basic_fixture_config.is_pan_in_bounds(value_below)
        assert basic_fixture_config.clamp_pan(value_below) == 50

        # Within bounds
        assert basic_fixture_config.is_pan_in_bounds(value_within)
        assert basic_fixture_config.clamp_pan(value_within) == value_within

        # Above max
        assert not basic_fixture_config.is_pan_in_bounds(value_above)
        assert basic_fixture_config.clamp_pan(value_above) == 190

    def test_delta_vs_absolute_conversion(self, basic_fixture_config: FixtureConfig) -> None:
        """Test relationship between delta and absolute conversions."""
        # Convert 45 degrees absolute
        abs_dmx = basic_fixture_config.deg_to_pan_dmx(45.0)

        # Convert 45 degrees as delta
        delta_dmx = basic_fixture_config.pan_deg_to_dmx_delta(45.0)

        # Absolute should equal center + delta (before clamping)
        expected = 128 + delta_dmx
        assert abs(abs_dmx - expected) <= 1  # Allow rounding difference

    def test_inverted_conversions_symmetric(self, inverted_fixture_config: FixtureConfig) -> None:
        """Test that inverted conversions are symmetric."""
        # +45 and -45 should be equidistant from center
        pos_dmx = inverted_fixture_config.deg_to_pan_dmx(45.0)
        neg_dmx = inverted_fixture_config.deg_to_pan_dmx(-45.0)

        center = 128
        pos_distance = abs(pos_dmx - center)
        neg_distance = abs(neg_dmx - center)

        # Distances should be equal (within rounding)
        assert abs(pos_distance - neg_distance) <= 1
