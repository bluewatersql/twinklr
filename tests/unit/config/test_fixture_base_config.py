"""Tests for Phase 2 base_config feature in FixtureGroup.

Tests the new simplified fixture configuration that eliminates duplication.
"""

import pytest

from blinkb0t.core.config.fixtures import (
    BaseFixtureConfig,
    DmxMapping,
    FixtureGroup,
    FixtureInstance,
    FixturePosition,
    SimplifiedFixtureInstance,
)


class TestBaseFixtureConfig:
    """Test BaseFixtureConfig model."""

    def test_base_config_creation(self):
        """Test creating a base config with minimal required fields."""
        dmx_mapping = DmxMapping(
            pan_channel=11,
            tilt_channel=13,
            dimmer_channel=3,
        )

        base_config = BaseFixtureConfig(dmx_mapping=dmx_mapping)

        assert base_config.dmx_universe == 1  # Default
        assert base_config.channel_count == 16  # Default
        assert base_config.dmx_mapping.pan_channel == 11

    def test_base_config_with_full_settings(self):
        """Test base config with all settings specified."""
        dmx_mapping = DmxMapping(
            pan_channel=11,
            tilt_channel=13,
            dimmer_channel=3,
            shutter_channel=2,
            color_channel=1,
            gobo_channel=7,
        )

        base_config = BaseFixtureConfig(
            dmx_universe=1,
            channel_count=48,
            dmx_mapping=dmx_mapping,
        )

        assert base_config.dmx_universe == 1
        assert base_config.channel_count == 48
        assert base_config.dmx_mapping.shutter_channel == 2


class TestSimplifiedFixtureInstance:
    """Test SimplifiedFixtureInstance model."""

    def test_simplified_fixture_minimal(self):
        """Test creating simplified fixture with minimal fields."""
        fixture = SimplifiedFixtureInstance(
            fixture_id="MH1",
            dmx_start_address=1,
            xlights_model_name="Dmx MH1",
        )

        assert fixture.fixture_id == "MH1"
        assert fixture.dmx_start_address == 1
        assert fixture.xlights_model_name == "Dmx MH1"
        assert fixture.position is None
        assert fixture.config_overrides == {}

    def test_simplified_fixture_with_position(self):
        """Test simplified fixture with position."""
        position = FixturePosition(
            position_index=1,
            pan_offset_deg=-30.0,
            tilt_offset_deg=-5.0,
        )

        fixture = SimplifiedFixtureInstance(
            fixture_id="MH1",
            dmx_start_address=1,
            xlights_model_name="Dmx MH1",
            position=position,
        )

        assert fixture.position.position_index == 1
        assert fixture.position.pan_offset_deg == -30.0

    def test_simplified_fixture_with_overrides(self):
        """Test simplified fixture with config overrides."""
        fixture = SimplifiedFixtureInstance(
            fixture_id="MH2",
            dmx_start_address=17,
            xlights_model_name="Dmx MH2",
            config_overrides={"dmx_universe": 2, "channel_count": 32},
        )

        assert fixture.config_overrides["dmx_universe"] == 2
        assert fixture.config_overrides["channel_count"] == 32


class TestFixtureGroupExpansion:
    """Test FixtureGroup.expand_fixtures() method."""

    @pytest.fixture
    def base_config(self) -> BaseFixtureConfig:
        """Create a base config for testing."""
        dmx_mapping = DmxMapping(
            pan_channel=11,
            tilt_channel=13,
            dimmer_channel=3,
        )
        return BaseFixtureConfig(
            dmx_universe=1,
            channel_count=48,
            dmx_mapping=dmx_mapping,
        )

    @pytest.fixture
    def simplified_fixtures(self) -> list[SimplifiedFixtureInstance]:
        """Create simplified fixtures for testing."""
        return [
            SimplifiedFixtureInstance(
                fixture_id="MH1",
                dmx_start_address=1,
                xlights_model_name="Dmx MH1",
                position=FixturePosition(
                    position_index=1,
                    pan_offset_deg=-30.0,
                    tilt_offset_deg=-5.0,
                ),
            ),
            SimplifiedFixtureInstance(
                fixture_id="MH2",
                dmx_start_address=17,
                xlights_model_name="Dmx MH2",
                position=FixturePosition(
                    position_index=2,
                    pan_offset_deg=-10.0,
                    tilt_offset_deg=-5.0,
                ),
            ),
        ]

    def test_expand_simplified_fixtures(
        self, base_config: BaseFixtureConfig, simplified_fixtures: list[SimplifiedFixtureInstance]
    ):
        """Test expanding simplified fixtures into full FixtureInstance objects."""
        group = FixtureGroup(
            group_id="MOVING_HEADS",
            base_config=base_config,
            fixtures=simplified_fixtures,
        )

        expanded = group.expand_fixtures()

        assert len(expanded) == 2
        assert all(isinstance(f, FixtureInstance) for f in expanded)

        # Check first fixture
        mh1 = expanded[0]
        assert mh1.fixture_id == "MH1"
        assert mh1.config.dmx_start_address == 1
        assert mh1.config.dmx_universe == 1  # From base_config
        assert mh1.config.channel_count == 48  # From base_config
        assert mh1.config.dmx_mapping.pan_channel == 11  # From base_config
        assert mh1.config.position.position_index == 1
        assert mh1.xlights_model_name == "Dmx MH1"

        # Check second fixture
        mh2 = expanded[1]
        assert mh2.fixture_id == "MH2"
        assert mh2.config.dmx_start_address == 17
        assert mh2.config.position.position_index == 2

    def test_expand_with_overrides(self, base_config: BaseFixtureConfig):
        """Test expanding fixtures with config overrides."""
        fixture_with_override = SimplifiedFixtureInstance(
            fixture_id="MH3",
            dmx_start_address=33,
            xlights_model_name="Dmx MH3",
            config_overrides={"dmx_universe": 2},  # Override universe
        )

        group = FixtureGroup(
            group_id="MOVING_HEADS",
            base_config=base_config,
            fixtures=[fixture_with_override],
        )

        expanded = group.expand_fixtures()

        assert len(expanded) == 1
        mh3 = expanded[0]
        assert mh3.config.dmx_universe == 2  # Overridden
        assert mh3.config.channel_count == 48  # From base_config

    def test_expand_without_base_config_raises_error(self):
        """Test that expanding simplified fixtures without base_config raises error."""
        fixture = SimplifiedFixtureInstance(
            fixture_id="MH1",
            dmx_start_address=1,
            xlights_model_name="Dmx MH1",
        )

        group = FixtureGroup(
            group_id="MOVING_HEADS",
            fixtures=[fixture],
            # No base_config!
        )

        with pytest.raises(ValueError, match="no base_config provided"):
            group.expand_fixtures()

    def test_expand_mixed_fixture_types(self, base_config: BaseFixtureConfig):
        """Test expanding a mix of FixtureInstance and SimplifiedFixtureInstance."""
        # Create a full FixtureInstance (old format)
        from blinkb0t.core.config.fixtures import FixtureConfig

        full_fixture = FixtureInstance(
            fixture_id="MH1",
            config=FixtureConfig(
                fixture_id="MH1",
                dmx_start_address=1,
                dmx_mapping=DmxMapping(
                    pan_channel=11,
                    tilt_channel=13,
                    dimmer_channel=3,
                ),
            ),
            xlights_model_name="Dmx MH1",
        )

        # Create a simplified fixture (new format)
        simplified_fixture = SimplifiedFixtureInstance(
            fixture_id="MH2",
            dmx_start_address=17,
            xlights_model_name="Dmx MH2",
        )

        group = FixtureGroup(
            group_id="MOVING_HEADS",
            base_config=base_config,
            fixtures=[full_fixture, simplified_fixture],
        )

        expanded = group.expand_fixtures()

        assert len(expanded) == 2
        assert all(isinstance(f, FixtureInstance) for f in expanded)
        assert expanded[0].fixture_id == "MH1"  # Full fixture unchanged
        assert expanded[1].fixture_id == "MH2"  # Simplified expanded

    def test_get_fixture_expands_automatically(
        self, base_config: BaseFixtureConfig, simplified_fixtures: list[SimplifiedFixtureInstance]
    ):
        """Test that get_fixture() automatically expands simplified fixtures."""
        group = FixtureGroup(
            group_id="MOVING_HEADS",
            base_config=base_config,
            fixtures=simplified_fixtures,
        )

        mh1 = group.get_fixture("MH1")

        assert mh1 is not None
        assert isinstance(mh1, FixtureInstance)
        assert mh1.fixture_id == "MH1"
        assert mh1.config.dmx_universe == 1  # From base_config


class TestBackwardCompatibility:
    """Test that old format (full FixtureInstance) still works."""

    def test_old_format_still_works(self):
        """Test that FixtureGroup works with old format (no base_config)."""
        from blinkb0t.core.config.fixtures import FixtureConfig

        fixture = FixtureInstance(
            fixture_id="MH1",
            config=FixtureConfig(
                fixture_id="MH1",
                dmx_start_address=1,
                dmx_mapping=DmxMapping(
                    pan_channel=11,
                    tilt_channel=13,
                    dimmer_channel=3,
                ),
            ),
            xlights_model_name="Dmx MH1",
        )

        group = FixtureGroup(
            group_id="MOVING_HEADS",
            fixtures=[fixture],
            # No base_config - old format
        )

        expanded = group.expand_fixtures()

        assert len(expanded) == 1
        assert expanded[0].fixture_id == "MH1"
        assert expanded[0].config.dmx_start_address == 1
