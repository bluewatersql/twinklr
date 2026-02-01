"""Tests for fixture configuration models."""

from __future__ import annotations

import pytest

from twinklr.core.config.fixtures import (
    ChannelInversions,
    DmxMapping,
    FixtureConfig,
    FixtureGroup,
    FixtureGroupBuilder,
    FixtureInstance,
    FixturePosition,
    MovementLimits,
    PanTiltRange,
    Pose,
)


class TestPose:
    """Tests for Pose model."""

    def test_pose_pan_normalization(self) -> None:
        """Test pan angle normalization to [-180, 180)."""
        # 270° becomes -90°
        pose = Pose(pan_deg=270.0, tilt_deg=0.0)
        assert pose.pan_deg == -90.0

        # 360° becomes 0°
        pose = Pose(pan_deg=360.0, tilt_deg=0.0)
        assert pose.pan_deg == 0.0

        # -180° stays -180°
        pose = Pose(pan_deg=-180.0, tilt_deg=0.0)
        assert pose.pan_deg == -180.0

        # 540° becomes -180° (540 % 360 = 180, then 180 >= 180 so 180 - 360 = -180)
        pose = Pose(pan_deg=540.0, tilt_deg=0.0)
        assert pose.pan_deg == -180.0


class TestPoseLibraryIntegration:
    """Tests for PoseLibrary integration with FixtureConfig."""

    def test_invalid_pose_id(self) -> None:
        """Test that invalid pose ID raises error."""
        config = FixtureConfig(
            fixture_id="test",
            pan_range_deg=540.0,
            tilt_range_deg=270.0,
            dmx_mapping=DmxMapping(pan_channel=1, tilt_channel=3, dimmer_channel=5),
        )
        with pytest.raises(ValueError, match="Unknown pose ID"):
            config.get_standard_pose("INVALID_POSE")


class TestShutterMap:
    """Tests for ShutterMap model."""

    # Skip trivial dataclass tests - Pydantic validates these


class TestDmxMapping:
    """Tests for DmxMapping model."""


class TestMovementLimits:
    """Tests for MovementLimits model."""


class TestFixturePosition:
    """Tests for FixturePosition model."""

    def test_remove_offset(self) -> None:
        """Test removing position offset from a pose."""
        position = FixturePosition(pan_offset_deg=30.0, tilt_offset_deg=-5.0)
        actual = Pose(pan_deg=30.0, tilt_deg=-5.0)  # Fixture's actual pose

        relative = position.remove_offset(actual)

        # Relative to "forward"
        assert relative.pan_deg == 0.0
        assert relative.tilt_deg == 0.0


class TestFixtureConfig:
    """Tests for FixtureConfig model."""

    def test_config_minimal(self) -> None:
        """Test fixture config with minimal required fields."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )

        assert config.fixture_id == "MH1"
        assert config.dmx_universe == 1  # Default
        assert config.dmx_start_address == 1  # Default
        assert config.channel_count == 16  # Default

    def test_config_full(self) -> None:
        """Test fixture config with all fields."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_universe=2,
            dmx_start_address=17,
            channel_count=18,
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
            inversions=ChannelInversions(pan=True, tilt=False),
            pan_tilt_range=PanTiltRange(pan_range_deg=540.0, tilt_range_deg=270.0),
            position=FixturePosition(pan_offset_deg=30.0),
        )

        assert config.fixture_id == "MH1"
        assert config.dmx_universe == 2
        assert config.dmx_start_address == 17
        assert config.channel_count == 18
        assert config.inversions.pan is True
        assert config.position is not None
        assert config.position.pan_offset_deg == 30.0

    def test_get_standard_pose(self) -> None:
        """Test getting standard pose from config."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )

        center = config.get_standard_pose("center")
        assert center.pan_deg == 0.0
        assert center.tilt_deg == 0.0

        sky = config.get_standard_pose("sky")
        assert sky.tilt_deg == 80.0

    def test_dmx_to_degrees(self) -> None:
        """Test DMX to degrees conversion."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )

        # Center position (128, 22) should be (0, 0) in degrees
        pose = config.dmx_to_degrees(pan_dmx=128, tilt_dmx=22)
        assert abs(pose.pan_deg) < 0.1  # Nearly 0
        assert abs(pose.tilt_deg) < 0.1  # Nearly 0

    def test_degrees_to_dmx(self) -> None:
        """Test degrees to DMX conversion."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )

        # Forward (0, 0) should be near (128, 22) in DMX
        forward = Pose(pan_deg=0.0, tilt_deg=0.0)
        pan_dmx, tilt_dmx = config.degrees_to_dmx(forward)

        # Should be close to center values
        assert 120 <= pan_dmx <= 136  # Near 128
        assert 18 <= tilt_dmx <= 26  # Near 22

    def test_dmx_to_degrees_with_inversion(self) -> None:
        """Test DMX to degrees conversion with channel inversion."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
            inversions=ChannelInversions(pan=True),
        )

        # With pan inverted, positive DMX offset = negative degrees
        pose = config.dmx_to_degrees(pan_dmx=148, tilt_dmx=22)  # 20 DMX above center
        assert pose.pan_deg < 0  # Should be negative

    def test_is_pose_safe(self) -> None:
        """Test pose safety checking."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
            limits=MovementLimits(avoid_backward=True),
        )

        # Forward is safe
        forward = Pose(pan_deg=0.0, tilt_deg=0.0)
        assert config.is_pose_safe(forward) is True

        # Looking backward is unsafe (avoid_backward=True)
        backward = Pose(pan_deg=150.0, tilt_deg=0.0)
        assert config.is_pose_safe(backward) is False


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

        assert len(group) == 1
        assert group.get_fixture("MH1") is not None

    def test_get_fixture(self) -> None:
        """Test getting fixture by ID."""
        group = FixtureGroup(group_id="MOVING_HEADS")

        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
        )
        instance = FixtureInstance(fixture_id="MH1", config=config, xlights_model_name="Dmx MH1")
        group.add_fixture(instance)

        fixture = group.get_fixture("MH1")
        assert fixture is not None
        assert fixture.fixture_id == "MH1"

        missing = group.get_fixture("MH99")
        assert missing is None

    def test_get_xlights_mapping(self) -> None:
        """Test generating xLights mapping."""
        group = FixtureGroup(group_id="MOVING_HEADS", xlights_group="GROUP - MOVING HEADS")

        # Add two fixtures
        for i in [1, 2]:
            config = FixtureConfig(
                fixture_id=f"MH{i}",
                dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
            )
            instance = FixtureInstance(
                fixture_id=f"MH{i}", config=config, xlights_model_name=f"Dmx MH{i}"
            )
            group.add_fixture(instance)

        mapping = group.get_xlights_mapping()

        assert mapping["ALL"] == "GROUP - MOVING HEADS"
        assert mapping["MH1"] == "Dmx MH1"
        assert mapping["MH2"] == "Dmx MH2"

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
                    1,
                    "Dmx MH1",
                    FixturePosition(position_index=1, pan_offset_deg=-30.0),
                ),
                (
                    "MH2",
                    17,
                    "Dmx MH2",
                    FixturePosition(position_index=2, pan_offset_deg=-10.0),
                ),
                (
                    "MH3",
                    33,
                    "Dmx MH3",
                    FixturePosition(position_index=3, pan_offset_deg=10.0),
                ),
                (
                    "MH4",
                    49,
                    "Dmx MH4",
                    FixturePosition(position_index=4, pan_offset_deg=30.0),
                ),
            ]
        )

        assert len(group) == 4
        assert group.group_id == "MOVING_HEADS"

        # Check each fixture has correct DMX address and position
        mh1 = group.get_fixture("MH1")
        assert mh1 is not None
        assert mh1.config.dmx_start_address == 1
        assert mh1.config.position is not None
        assert mh1.config.position.pan_offset_deg == -30.0

        mh4 = group.get_fixture("MH4")
        assert mh4 is not None
        assert mh4.config.dmx_start_address == 49
        assert mh4.config.position is not None
        assert mh4.config.position.pan_offset_deg == 30.0


class TestIntegrationScenarios:
    """Integration tests for complete workflows."""

    def test_complete_4_fixture_setup(self) -> None:
        """Test complete setup of 4-fixture rig."""
        # 1. Create base config
        base_config = FixtureConfig(
            fixture_id="BASE",
            dmx_universe=1,
            dmx_start_address=1,
            channel_count=16,
            dmx_mapping=DmxMapping(
                pan_channel=11,
                tilt_channel=13,
                dimmer_channel=15,
                shutter_channel=17,
                color_channel=18,
            ),
            pan_tilt_range=PanTiltRange(pan_range_deg=540.0, tilt_range_deg=270.0),
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
                    1,
                    "Dmx MH1",
                    FixturePosition(position_index=1, pan_offset_deg=-30.0, tilt_offset_deg=-5.0),
                ),
                (
                    "MH2",
                    17,
                    "Dmx MH2",
                    FixturePosition(position_index=2, pan_offset_deg=-10.0, tilt_offset_deg=-5.0),
                ),
                (
                    "MH3",
                    33,
                    "Dmx MH3",
                    FixturePosition(position_index=3, pan_offset_deg=10.0, tilt_offset_deg=-5.0),
                ),
                (
                    "MH4",
                    49,
                    "Dmx MH4",
                    FixturePosition(position_index=4, pan_offset_deg=30.0, tilt_offset_deg=-5.0),
                ),
            ]
        )

        # 3. Test xLights mapping
        mapping = group.get_xlights_mapping()
        assert len(mapping) == 5  # ALL + 4 fixtures

        # 4. Test standard poses for all fixtures
        for fixture in group:
            center_pose = fixture.config.get_standard_pose("center")
            assert center_pose.pan_deg == 0.0

            # Apply position offset
            if fixture.config.position:
                actual = fixture.config.position.apply_offset(center_pose)
                dmx = fixture.config.degrees_to_dmx(actual)

                # Should get different DMX values due to offsets
                assert isinstance(dmx[0], int)
                assert isinstance(dmx[1], int)

    def test_pose_workflow(self) -> None:
        """Test complete pose conversion workflow."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
            position=FixturePosition(pan_offset_deg=30.0),
        )

        # 1. Get standard pose
        center = config.get_standard_pose("center")

        # 2. Apply position offset (where fixture actually needs to be)
        actual_pose = config.position.apply_offset(center)  # type: ignore[union-attr]
        assert actual_pose.pan_deg == 30.0

        # 3. Convert to DMX
        pan_dmx, tilt_dmx = config.degrees_to_dmx(actual_pose)

        # 4. Convert back to degrees
        reconstructed = config.dmx_to_degrees(pan_dmx, tilt_dmx)

        # 5. Remove offset to get relative aim
        relative = config.position.remove_offset(reconstructed)  # type: ignore[union-attr]

        # Should be close to original forward pose
        assert abs(relative.pan_deg) < 5.0  # Allow some DMX quantization error

    def test_safety_limits_workflow(self) -> None:
        """Test safety checking workflow."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
            limits=MovementLimits(
                pan_min=50, pan_max=190, tilt_min=5, tilt_max=125, avoid_backward=True
            ),
        )

        # Safe poses
        assert config.is_pose_safe(Pose(pan_deg=0.0, tilt_deg=0.0)) is True
        assert config.is_pose_safe(Pose(pan_deg=45.0, tilt_deg=30.0)) is True

        assert config.is_pose_safe(Pose(pan_deg=120.0, tilt_deg=0.0)) is False

        assert config.is_pose_safe(Pose(pan_deg=180.0, tilt_deg=100.0)) is False
