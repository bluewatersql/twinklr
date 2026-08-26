"""Tests for fixture configuration models."""

from __future__ import annotations

import pytest

from twinklr.core.config.fixtures import (
    BaseFixtureConfig,
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
    ShutterMap,
    SimplifiedFixtureInstance,
)
from twinklr.core.config.fixtures.physical import Orientation
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.moving_heads.export.dmx_settings_builder import DmxSettingsBuilder
from twinklr.core.sequencer.moving_heads.handlers.wheels import (
    DefaultColorHandler,
    DefaultGoboHandler,
    DefaultShutterHandler,
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

    @pytest.mark.parametrize("source", ["base-config", "fixture-instance"])
    def test_avoid_backward_changes_public_pose_safety(self, source: str) -> None:
        """Both public fixture schema paths must enforce the safety toggle."""

        def configured_fixture(avoid_backward: bool) -> FixtureConfig:
            limits = MovementLimits(avoid_backward=avoid_backward)
            mapping = DmxMapping(pan_channel=1, tilt_channel=2, dimmer_channel=3)
            if source == "base-config":
                group = FixtureGroup(
                    group_id="heads",
                    base_config=BaseFixtureConfig(dmx_mapping=mapping, limits=limits),
                    fixtures=[
                        SimplifiedFixtureInstance(
                            fixture_id="MH1",
                            xlights_model_name="Dmx MH1",
                        )
                    ],
                )
                return group.expand_fixtures()[0].config
            group = FixtureGroup(
                group_id="heads",
                fixtures=[
                    FixtureInstance(
                        fixture_id="MH1",
                        xlights_model_name="Dmx MH1",
                        config=FixtureConfig(
                            fixture_id="MH1",
                            dmx_mapping=mapping,
                            limits=limits,
                        ),
                    )
                ],
            )
            return group.expand_fixtures()[0].config

        backward_pose = Pose(pan_deg=120.0, tilt_deg=0.0)

        assert configured_fixture(True).is_pose_safe(backward_pose) is False
        assert configured_fixture(False).is_pose_safe(backward_pose) is True


class TestFixturePosition:
    """Tests for FixturePosition model."""

    @pytest.mark.parametrize(
        ("source", "pan_offset", "tilt_offset", "expected"),
        [
            ("fixture-instance", 15.0, 0.0, Pose(pan_deg=25.0, tilt_deg=20.0)),
            ("fixture-instance", 0.0, -5.0, Pose(pan_deg=10.0, tilt_deg=15.0)),
            ("simplified-fixture", 15.0, 0.0, Pose(pan_deg=25.0, tilt_deg=20.0)),
            ("simplified-fixture", 0.0, -5.0, Pose(pan_deg=10.0, tilt_deg=15.0)),
        ],
        ids=[
            "fixture-instance-pan-offset",
            "fixture-instance-tilt-offset",
            "simplified-fixture-pan-offset",
            "simplified-fixture-tilt-offset",
        ],
    )
    def test_offsets_change_public_pose_conversion(
        self,
        source: str,
        pan_offset: float,
        tilt_offset: float,
        expected: Pose,
    ) -> None:
        position = FixturePosition(
            pan_offset_deg=pan_offset,
            tilt_offset_deg=tilt_offset,
        )
        mapping = DmxMapping(pan_channel=1, tilt_channel=2, dimmer_channel=3)
        if source == "fixture-instance":
            group = FixtureGroup(
                group_id="heads",
                fixtures=[
                    FixtureInstance(
                        fixture_id="MH1",
                        xlights_model_name="Dmx MH1",
                        config=FixtureConfig(
                            fixture_id="MH1",
                            dmx_mapping=mapping,
                            position=position,
                        ),
                    )
                ],
            )
        else:
            group = FixtureGroup(
                group_id="heads",
                base_config=BaseFixtureConfig(dmx_mapping=mapping),
                fixtures=[
                    SimplifiedFixtureInstance(
                        fixture_id="MH1",
                        xlights_model_name="Dmx MH1",
                        position=position,
                    )
                ],
            )
        effective_position = group.expand_fixtures()[0].config.position
        assert effective_position is not None
        target = Pose(pan_deg=10.0, tilt_deg=20.0)

        actual = effective_position.apply_offset(target)

        assert actual == expected
        assert effective_position.remove_offset(actual) == target


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
            inversions=ChannelInversions(pan=True, tilt=False),
            pan_tilt_range=PanTiltRange(pan_range_deg=540.0, tilt_range_deg=270.0),
            position=FixturePosition(position_index=3),
        )

        assert config.fixture_id == "MH1"
        assert config.inversions.pan is True
        assert config.position is not None
        assert config.position.position_index == 3

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

    def test_calibration_fields_change_output_dmx(self) -> None:
        mapping = DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15)
        default = FixtureConfig(fixture_id="default", dmx_mapping=mapping)
        calibrated = FixtureConfig(
            fixture_id="calibrated",
            dmx_mapping=mapping,
            pan_tilt_range=PanTiltRange(pan_range_deg=360.0, tilt_range_deg=180.0),
            orientation=Orientation(pan_front_dmx=100, tilt_zero_dmx=40),
            limits=MovementLimits(pan_min=60, pan_max=170, tilt_min=10, tilt_max=120),
        )

        pose = Pose(pan_deg=90.0, tilt_deg=45.0)
        assert default.degrees_to_dmx(pose) != calibrated.degrees_to_dmx(pose)
        assert calibrated.degrees_to_dmx(Pose(pan_deg=170.0, tilt_deg=90.0)) == (170, 120)

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
                    pan_fine_channel=4,
                    tilt_fine_channel=5,
                    use_16bit_pan_tilt=True,
                    shutter_channel=6,
                    shutter_default=211,
                    shutter_map=ShutterMap(
                        closed=10,
                        open=200,
                        strobe_slow=61,
                        strobe_medium=121,
                        strobe_fast=181,
                    ),
                    color_channel=7,
                    color_map={"open": 9, "red": 19},
                    gobo_channel=8,
                    gobo_map={"open": 11, "circles": 21},
                ),
                inversions=ChannelInversions(
                    pan=True,
                    tilt=True,
                    dimmer=True,
                    shutter=True,
                    color=True,
                    gobo=True,
                ),
                pan_tilt_range=PanTiltRange(pan_range_deg=360.0, tilt_range_deg=180.0),
                orientation=Orientation(pan_front_dmx=100, tilt_zero_dmx=40),
                limits=MovementLimits(pan_min=60, pan_max=170, tilt_min=10, tilt_max=120),
            ),
            fixtures=[
                SimplifiedFixtureInstance(
                    fixture_id="MH1",
                    xlights_model_name="Dmx MH1",
                    position=FixturePosition(position_index=2),
                    config_overrides={"inversions": {"pan": True}},
                ),
                SimplifiedFixtureInstance(
                    fixture_id="MH2",
                    xlights_model_name="Dmx MH2",
                    position=FixturePosition(position_index=1),
                ),
            ],
        )

        expanded, inherited = group.expand_fixtures()
        rig = rig_profile_from_fixture_group(group)
        segment = FixtureSegment(
            section_id="s",
            segment_id="seg",
            step_id="step",
            template_id="tmpl",
            fixture_id="MH1",
            t0_ms=0,
            t1_ms=1000,
            channels={
                ChannelName.PAN: ChannelValue(channel=ChannelName.PAN, static_dmx=100),
                ChannelName.TILT: ChannelValue(channel=ChannelName.TILT, static_dmx=100),
                ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200),
            },
        )
        settings = DmxSettingsBuilder(inherited).build_settings_string(segment)
        calibration = {"fixture_config": inherited.config}

        assert expanded.config.dmx_to_degrees(pan_dmx=148, tilt_dmx=22).pan_deg < 0
        assert inherited.config.degrees_to_dmx(Pose(pan_deg=-170.0, tilt_deg=-90.0)) == (170, 120)
        assert rig.rig_id == "heads"
        assert [fixture.fixture_id for fixture in rig.fixtures] == ["MH2", "MH1"]
        assert group.get_xlights_mapping()["MH1"] == "Dmx MH1"
        assert all(f"E_CHECKBOX_INVDMX{channel}=1" in settings for channel in range(1, 9))
        assert "E_SLIDER_DMX6=211" in settings
        assert "E_SLIDER_DMX7=9" in settings
        assert "E_SLIDER_DMX8=11" in settings
        assert (
            DefaultColorHandler()
            .generate({"preset": "red", "calibration": calibration}, 4)
            .static_dmx
            == 19
        )
        assert (
            DefaultGoboHandler()
            .generate({"pattern": "circles", "calibration": calibration}, 4)
            .static_dmx
            == 21
        )
        assert (
            DefaultShutterHandler()
            .generate({"pattern": "strobe_medium", "calibration": calibration}, 4)
            .static_dmx
            == 121
        )


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
        mh1 = group.get_fixture("MH1")
        assert mh1 is not None
        assert mh1.config.position is not None
        assert mh1.config.position.position_index == 1

        mh4 = group.get_fixture("MH4")
        assert mh4 is not None
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

        # 3. Test xLights mapping
        mapping = group.get_xlights_mapping()
        assert len(mapping) == 5  # ALL + 4 fixtures

        # 4. Test standard poses for all fixtures
        for fixture in group:
            center_pose = fixture.config.get_standard_pose("center")
            assert center_pose.pan_deg == 0.0

    def test_safety_limits_workflow(self) -> None:
        """Test safety checking workflow."""
        config = FixtureConfig(
            fixture_id="MH1",
            dmx_mapping=DmxMapping(pan_channel=11, tilt_channel=13, dimmer_channel=15),
            limits=MovementLimits(pan_min=50, pan_max=190, tilt_min=5, tilt_max=125),
        )

        assert config.degrees_to_dmx(Pose(pan_deg=-180.0, tilt_deg=-90.0)) == (50, 5)
        assert config.degrees_to_dmx(Pose(pan_deg=170.0, tilt_deg=90.0)) == (190, 107)
