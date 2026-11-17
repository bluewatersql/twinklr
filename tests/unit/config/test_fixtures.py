"""Tests for fixture configuration models."""

from __future__ import annotations

from twinklr.core.config.fixtures import (
    BaseFixtureConfig,
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureGroupBuilder,
    FixtureInstance,
    FixturePosition,
    SimplifiedFixtureInstance,
)
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group


class TestFixtureConfig:
    """Tests for FixtureConfig model."""

    def test_config_minimal(self) -> None:
        """Test fixture config with minimal required fields."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )

        assert config.fixture_id == "MH1"

    def test_config_full(self) -> None:
        """Test fixture config with all fields."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
            position=FixturePosition(position_index=3),
        )

        assert config.fixture_id == "MH1"
        assert config.position is not None
        assert config.position.position_index == 3


class TestFixtureInstance:
    """Tests for FixtureInstance model."""

    def test_instance_creation(self) -> None:
        """Test creating fixture instance."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )

        instance = FixtureInstance(fixture_id="MH1", config=config, xlights_model_name="Dmx MH1")

        assert instance.fixture_id == "MH1"
        assert instance.xlights_model_name == "Dmx MH1"
        assert instance.config.fixture_id == "MH1"

    def test_instance_id_sync(self) -> None:
        """Test that fixture_id syncs with config."""
        config = FixtureConfig(
            fixture_id="WRONG",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )

        instance = FixtureInstance(fixture_id="MH1", config=config, xlights_model_name="Dmx MH1")

        # Config fixture_id should be updated to match
        assert instance.config.fixture_id == "MH1"


class TestFixtureGroup:
    """Tests for FixtureGroup model."""

    def test_group_creation(self) -> None:
        """Test creating empty fixture group."""
        group = FixtureGroup(group_id="MOVING_HEADS", xlights_group="GROUP - MOVING HEADS")

        assert group.group_id == "MOVING_HEADS"
        assert group.xlights_group == "GROUP - MOVING HEADS"
        assert len(group) == 0
        assert group.is_semantic() is False

    def test_add_fixture(self) -> None:
        """Test adding fixture to group."""
        group = FixtureGroup(group_id="MOVING_HEADS")

        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )
        instance = FixtureInstance(fixture_id="MH1", config=config, xlights_model_name="Dmx MH1")

        group.add_fixture(instance)

        assert [fixture.fixture_id for fixture in group.expand_fixtures()] == ["MH1"]

    def test_iteration(self) -> None:
        """Test iterating over fixtures in group."""
        group = FixtureGroup(group_id="MOVING_HEADS")

        for i in [1, 2, 3]:
            config = FixtureConfig(
                fixture_id=f"MH{i}",
                dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
            )
            instance = FixtureInstance(
                fixture_id=f"MH{i}", config=config, xlights_model_name=f"Dmx MH{i}"
            )
            group.add_fixture(instance)

        fixture_ids = [f.fixture_id for f in group]
        assert fixture_ids == ["MH1", "MH2", "MH3"]

    def test_position_index_changes_rig_order(self) -> None:
        mapping = DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15)
        group = FixtureGroup(
            group_id="heads",
            fixtures=[
                FixtureInstance(
                    fixture_id="MH1",
                    config=FixtureConfig(
                        fixture_id="MH1",
                        dmx_mapping=mapping,
                        position=FixturePosition(position_index=2),
                    ),
                    xlights_model_name="Dmx MH1",
                ),
                FixtureInstance(
                    fixture_id="MH2",
                    config=FixtureConfig(
                        fixture_id="MH2",
                        dmx_mapping=mapping,
                        position=FixturePosition(position_index=1),
                    ),
                    xlights_model_name="Dmx MH2",
                ),
            ],
        )

        rig = rig_profile_from_fixture_group(group)

        assert [fixture.fixture_id for fixture in rig.fixtures] == ["MH2", "MH1"]

    def test_base_config_and_override_change_expanded_fixture_behavior(self) -> None:
        group = FixtureGroup(
            group_id="heads",
            base_config=BaseFixtureConfig(
                dmx_mapping=DmxMapping(
                    pan_channel=1,
                    tilt_channel=2,
                    dimmer_channel=3,
                    shutter_channel=6,
                    color_channel=7,
                    gobo_channel=8,
                ),
            ),
            fixtures=[
                SimplifiedFixtureInstance(
                    fixture_id="MH1",
                    xlights_model_name="Dmx MH1",
                    position=FixturePosition(position_index=2),
                    config_overrides={
                        "dmx_mapping": {"pan_channel": 11, "tilt_channel": 12, "dimmer_channel": 13}
                    },
                ),
                SimplifiedFixtureInstance(
                    fixture_id="MH2",
                    xlights_model_name="Dmx MH2",
                    position=FixturePosition(position_index=1),
                ),
            ],
        )

        overridden, inherited = group.expand_fixtures()
        rig = rig_profile_from_fixture_group(group)

        assert (overridden.config.dmx_mapping.pan, overridden.config.dmx_mapping.gobo) == (11, None)
        assert (inherited.config.dmx_mapping.pan, inherited.config.dmx_mapping.gobo) == (1, 8)
        assert rig.rig_id == "heads"
        assert [fixture.fixture_id for fixture in rig.fixtures] == ["MH2", "MH1"]


class TestFixtureGroupBuilder:
    """Tests for FixtureGroupBuilder."""

    def test_builder_creation(self) -> None:
        """Test creating fixture group builder."""
        base_config = FixtureConfig(
            fixture_id="BASE",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )

        builder = FixtureGroupBuilder(
            group_id="MOVING_HEADS",
            xlights_group="GROUP - MOVING HEADS",
            base_config=base_config,
        )

        assert builder.group_id == "MOVING_HEADS"

    def test_builder_build_group(self) -> None:
        """Test building fixture group with builder."""
        base_config = FixtureConfig(
            fixture_id="BASE",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )

        builder = FixtureGroupBuilder(
            group_id="MOVING_HEADS",
            xlights_group="GROUP - MOVING HEADS",
            base_config=base_config,
        )

        # Build group with 4 fixtures
        group = builder.build(
            [
                (
                    "MH1",
                    "Dmx MH1",
                    FixturePosition(position_index=1),
                ),
                (
                    "MH2",
                    "Dmx MH2",
                    FixturePosition(position_index=2),
                ),
                (
                    "MH3",
                    "Dmx MH3",
                    FixturePosition(position_index=3),
                ),
                (
                    "MH4",
                    "Dmx MH4",
                    FixturePosition(position_index=4),
                ),
            ]
        )

        assert len(group) == 4
        assert group.group_id == "MOVING_HEADS"

        # Check each fixture has the expected position.
        by_id = {fixture.fixture_id: fixture for fixture in group.expand_fixtures()}
        mh1 = by_id["MH1"]
        assert mh1.config.position is not None
        assert mh1.config.position.position_index == 1

        mh4 = by_id["MH4"]
        assert mh4.config.position is not None
        assert mh4.config.position.position_index == 4


class TestIntegrationScenarios:
    """Integration tests for complete workflows."""

    def test_complete_4_fixture_setup(self) -> None:
        """Test complete setup of 4-fixture rig."""
        # 1. Create base config
        base_config = FixtureConfig(
            fixture_id="BASE",
            dmx_mapping=DmxMapping(
                pan_channel=11,
                tilt_channel=13,
                dimmer_channel=15,
                shutter_channel=17,
                color_channel=18,
            ),
        )

        # 2. Build group
        builder = FixtureGroupBuilder(
            group_id="MOVING_HEADS",
            xlights_group="GROUP - MOVING HEADS",
            base_config=base_config,
        )

        group = builder.build(
            [
                (
                    "MH1",
                    "Dmx MH1",
                    FixturePosition(position_index=1),
                ),
                (
                    "MH2",
                    "Dmx MH2",
                    FixturePosition(position_index=2),
                ),
                (
                    "MH3",
                    "Dmx MH3",
                    FixturePosition(position_index=3),
                ),
                (
                    "MH4",
                    "Dmx MH4",
                    FixturePosition(position_index=4),
                ),
            ]
        )

        # 3. Every fixture carries the base mapping
        for fixture in group:
            assert (fixture.config.dmx_mapping.pan, fixture.config.dmx_mapping.color) == (11, 18)
