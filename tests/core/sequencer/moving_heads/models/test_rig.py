"""Tests for Rig Profile Models.

Tests ChaseOrder, AimZone, FixtureCalibration, FixtureDefinition,
SemanticGroup, and RigProfile models.
All 12 test cases per implementation plan Task 0.5.
"""

import json

from pydantic import ValidationError
import pytest

from blinkb0t.core.sequencer.moving_heads.models.rig import (
    AimZone,
    ChaseOrder,
    FixtureCalibration,
    FixtureDefinition,
    RigProfile,
    SemanticGroup,
)


class TestEnums:
    """Tests for ChaseOrder and AimZone enums."""

    def test_chase_order_values(self) -> None:
        """Test ChaseOrder enum values."""
        assert ChaseOrder.LEFT_TO_RIGHT.value == "LEFT_TO_RIGHT"
        assert ChaseOrder.RIGHT_TO_LEFT.value == "RIGHT_TO_LEFT"
        assert ChaseOrder.OUTSIDE_IN.value == "OUTSIDE_IN"
        assert ChaseOrder.INSIDE_OUT.value == "INSIDE_OUT"

    def test_aim_zone_values(self) -> None:
        """Test AimZone enum values."""
        assert AimZone.SKY.value == "SKY"
        assert AimZone.HORIZON.value == "HORIZON"
        assert AimZone.CROWD.value == "CROWD"
        assert AimZone.STAGE.value == "STAGE"


class TestRigProfile:
    """Tests for RigProfile model."""

    def test_minimal_valid_rig_profile(self) -> None:
        """Test minimal valid RigProfile."""
        profile = RigProfile(
            rig_id="test_rig",
            fixtures=[
                FixtureDefinition(
                    fixture_id="fix1",
                    universe=1,
                    start_address=1,
                )
            ],
        )
        assert profile.rig_id == "test_rig"
        assert len(profile.fixtures) == 1
        assert profile.groups == []

    def test_empty_fixture_list_raises_error(self) -> None:
        """Test empty fixture list raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            RigProfile(
                rig_id="test_rig",
                fixtures=[],
            )
        assert "fixtures" in str(exc_info.value).lower() or "min" in str(exc_info.value).lower()


class TestFixtureCalibration:
    """Tests for FixtureCalibration model."""

    def test_fixture_calibration_with_defaults(self) -> None:
        """Test FixtureCalibration with defaults."""
        cal = FixtureCalibration()
        assert cal.pan_min_dmx == 0
        assert cal.pan_max_dmx == 255
        assert cal.tilt_min_dmx == 0
        assert cal.tilt_max_dmx == 255
        assert cal.pan_inverted is False
        assert cal.tilt_inverted is False
        assert cal.dimmer_floor_dmx == 0
        assert cal.dimmer_ceiling_dmx == 255

    def test_fixture_calibration_with_custom_ranges(self) -> None:
        """Test FixtureCalibration with custom ranges."""
        cal = FixtureCalibration(
            pan_min_dmx=10,
            pan_max_dmx=245,
            tilt_min_dmx=20,
            tilt_max_dmx=235,
            pan_inverted=True,
            tilt_inverted=True,
            dimmer_floor_dmx=60,
            dimmer_ceiling_dmx=200,
        )
        assert cal.pan_min_dmx == 10
        assert cal.pan_max_dmx == 245
        assert cal.pan_inverted is True
        assert cal.dimmer_floor_dmx == 60
        assert cal.dimmer_ceiling_dmx == 200

    def test_dimmer_ceiling_less_than_floor_raises_error(self) -> None:
        """Test dimmer_ceiling < dimmer_floor raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            FixtureCalibration(
                dimmer_floor_dmx=200,
                dimmer_ceiling_dmx=100,
            )
        assert "dimmer" in str(exc_info.value).lower()


class TestSemanticGroup:
    """Tests for SemanticGroup model."""

    def test_group_references_non_existent_fixture_raises_error(self) -> None:
        """Test group references non-existent fixture raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            RigProfile(
                rig_id="test_rig",
                fixtures=[FixtureDefinition(fixture_id="fix1", universe=1, start_address=1)],
                groups=[
                    SemanticGroup(
                        group_id="group1",
                        fixture_ids=["fix1", "fix_nonexistent"],
                    )
                ],
            )
        assert "fix_nonexistent" in str(exc_info.value)

    def test_group_with_valid_fixture_ids(self) -> None:
        """Test group with valid fixture IDs (passes)."""
        profile = RigProfile(
            rig_id="test_rig",
            fixtures=[
                FixtureDefinition(fixture_id="fix1", universe=1, start_address=1),
                FixtureDefinition(fixture_id="fix2", universe=1, start_address=17),
            ],
            groups=[
                SemanticGroup(
                    group_id="all_fixtures",
                    fixture_ids=["fix1", "fix2"],
                    order=ChaseOrder.LEFT_TO_RIGHT,
                )
            ],
        )
        assert len(profile.groups) == 1
        assert profile.groups[0].fixture_ids == ["fix1", "fix2"]


class TestFixtureDefinition:
    """Tests for FixtureDefinition model."""

    def test_pan_tilt_inversion_flags(self) -> None:
        """Test pan/tilt inversion flags in calibration."""
        fixture = FixtureDefinition(
            fixture_id="fix1",
            universe=1,
            start_address=1,
            calibration=FixtureCalibration(
                pan_inverted=True,
                tilt_inverted=True,
            ),
        )
        assert fixture.calibration.pan_inverted is True
        assert fixture.calibration.tilt_inverted is True

    def test_universe_address_bounds(self) -> None:
        """Test universe/address bounds (1-512)."""
        # Valid bounds
        fixture = FixtureDefinition(
            fixture_id="fix1",
            universe=1,
            start_address=1,
        )
        assert fixture.universe == 1
        assert fixture.start_address == 1

        # Max valid values
        fixture2 = FixtureDefinition(
            fixture_id="fix2",
            universe=512,
            start_address=512,
        )
        assert fixture2.universe == 512
        assert fixture2.start_address == 512

        # Below bounds - universe
        with pytest.raises(ValidationError):
            FixtureDefinition(
                fixture_id="fix_bad",
                universe=0,
                start_address=1,
            )

        # Above bounds - universe
        with pytest.raises(ValidationError):
            FixtureDefinition(
                fixture_id="fix_bad",
                universe=513,
                start_address=1,
            )

        # Below bounds - start_address
        with pytest.raises(ValidationError):
            FixtureDefinition(
                fixture_id="fix_bad",
                universe=1,
                start_address=0,
            )


class TestMultipleGroups:
    """Tests for multiple groups."""

    def test_multiple_groups(self) -> None:
        """Test multiple groups in rig profile."""
        profile = RigProfile(
            rig_id="test_rig",
            fixtures=[
                FixtureDefinition(fixture_id="left1", universe=1, start_address=1),
                FixtureDefinition(fixture_id="left2", universe=1, start_address=17),
                FixtureDefinition(fixture_id="right1", universe=1, start_address=33),
                FixtureDefinition(fixture_id="right2", universe=1, start_address=49),
            ],
            groups=[
                SemanticGroup(
                    group_id="left",
                    fixture_ids=["left1", "left2"],
                    order=ChaseOrder.LEFT_TO_RIGHT,
                ),
                SemanticGroup(
                    group_id="right",
                    fixture_ids=["right1", "right2"],
                    order=ChaseOrder.RIGHT_TO_LEFT,
                ),
                SemanticGroup(
                    group_id="all",
                    fixture_ids=["left1", "left2", "right1", "right2"],
                    order=ChaseOrder.OUTSIDE_IN,
                ),
            ],
        )
        assert len(profile.groups) == 3


class TestSpatialPosition:
    """Tests for spatial position."""

    def test_spatial_position_for_ordering(self) -> None:
        """Test spatial_position for ordering."""
        fixture = FixtureDefinition(
            fixture_id="fix1",
            universe=1,
            start_address=1,
            spatial_position=(-1.0, 0.5),
        )
        assert fixture.spatial_position == (-1.0, 0.5)

        # Without spatial position
        fixture2 = FixtureDefinition(
            fixture_id="fix2",
            universe=1,
            start_address=17,
        )
        assert fixture2.spatial_position is None


class TestJsonSerialization:
    """Tests for JSON serialization."""

    def test_json_serialization_roundtrip(self) -> None:
        """Test JSON serialization roundtrip."""
        original = RigProfile(
            rig_id="test_rig",
            fixtures=[
                FixtureDefinition(
                    fixture_id="fix1",
                    universe=1,
                    start_address=1,
                    role="FRONT_LEFT",
                    spatial_position=(-1.0, 0.0),
                    calibration=FixtureCalibration(
                        pan_min_dmx=10,
                        pan_max_dmx=245,
                        dimmer_floor_dmx=60,
                        dimmer_ceiling_dmx=200,
                    ),
                ),
                FixtureDefinition(
                    fixture_id="fix2",
                    universe=1,
                    start_address=17,
                    role="FRONT_RIGHT",
                    spatial_position=(1.0, 0.0),
                ),
            ],
            groups=[
                SemanticGroup(
                    group_id="fronts",
                    fixture_ids=["fix1", "fix2"],
                    order=ChaseOrder.LEFT_TO_RIGHT,
                )
            ],
            default_dimmer_floor_dmx=60,
            default_dimmer_ceiling_dmx=255,
        )
        json_str = original.model_dump_json()
        restored = RigProfile.model_validate_json(json_str)

        assert restored.rig_id == original.rig_id
        assert len(restored.fixtures) == 2
        assert len(restored.groups) == 1
        assert restored.fixtures[0].calibration.pan_min_dmx == 10
        assert restored.groups[0].order == ChaseOrder.LEFT_TO_RIGHT

        # Verify JSON structure
        parsed = json.loads(json_str)
        assert parsed["rig_id"] == "test_rig"
        assert len(parsed["fixtures"]) == 2


class TestDefaultDimmerValues:
    """Tests for default dimmer values."""

    def test_default_dimmer_values(self) -> None:
        """Test default dimmer floor/ceiling values."""
        profile = RigProfile(
            rig_id="test_rig",
            fixtures=[FixtureDefinition(fixture_id="fix1", universe=1, start_address=1)],
        )
        assert profile.default_dimmer_floor_dmx == 60
        assert profile.default_dimmer_ceiling_dmx == 255


class TestExampleFixture:
    """Tests for example fixture file."""

    def test_example_fixture_validates(self) -> None:
        """Test example rig fixture file validates correctly."""
        import pathlib

        # tests/core/sequencer/moving_heads/models/test_rig.py -> tests/fixtures/
        fixture_path = (
            pathlib.Path(__file__).parent.parent.parent.parent.parent
            / "fixtures"
            / "example_rig_4fixtures.json"
        )
        profile = RigProfile.model_validate_json(fixture_path.read_text())

        assert profile.rig_id == "example_4fixture_rig"
        assert len(profile.fixtures) == 4
        assert len(profile.groups) == 5

        # Verify fixture IDs
        fixture_ids = {f.fixture_id for f in profile.fixtures}
        assert fixture_ids == {"front_left", "front_right", "back_left", "back_right"}

        # Verify groups reference valid fixtures
        for group in profile.groups:
            for fid in group.fixture_ids:
                assert fid in fixture_ids
