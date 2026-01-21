"""Tests for pose models."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.domains.sequencing.models.poses import Pose, PoseConfig, PoseID


class TestPoseID:
    """Test PoseID enum."""

    def test_horizontal_poses(self):
        """Test horizontal reference poses."""
        assert PoseID.FORWARD == "FORWARD"
        assert PoseID.LEFT_45 == "LEFT_45"
        assert PoseID.RIGHT_45 == "RIGHT_45"
        assert PoseID.LEFT_90 == "LEFT_90"
        assert PoseID.RIGHT_90 == "RIGHT_90"

    def test_vertical_poses(self):
        """Test vertical reference poses."""
        assert PoseID.UP == "UP"
        assert PoseID.DOWN == "DOWN"
        assert PoseID.CEILING == "CEILING"

    def test_audience_poses(self):
        """Test audience reference poses."""
        assert PoseID.AUDIENCE_CENTER == "AUDIENCE_CENTER"
        assert PoseID.AUDIENCE_LEFT == "AUDIENCE_LEFT"
        assert PoseID.AUDIENCE_RIGHT == "AUDIENCE_RIGHT"


class TestPose:
    """Test Pose model."""

    def test_valid_pose(self):
        """Test creating valid pose."""
        pose = Pose(
            pose_id="FORWARD",
            name="Forward Horizon",
            description="Straight ahead",
            pan_deg=0.0,
            tilt_deg=0.0,
        )

        assert pose.pose_id == "FORWARD"
        assert pose.name == "Forward Horizon"
        assert pose.pan_deg == 0.0
        assert pose.tilt_deg == 0.0

    def test_pose_without_description(self):
        """Test pose with default empty description."""
        pose = Pose(pose_id="TEST", name="Test", pan_deg=0.0, tilt_deg=0.0)

        assert pose.description == ""

    def test_pan_range_validation(self):
        """Test pan angle range validation."""
        # Valid ranges
        Pose(pose_id="TEST", name="Test", pan_deg=-180.0, tilt_deg=0.0)
        Pose(pose_id="TEST", name="Test", pan_deg=180.0, tilt_deg=0.0)
        Pose(pose_id="TEST", name="Test", pan_deg=0.0, tilt_deg=0.0)

        # Invalid - too negative
        with pytest.raises(ValidationError):
            Pose(pose_id="TEST", name="Test", pan_deg=-181.0, tilt_deg=0.0)

        # Invalid - too positive
        with pytest.raises(ValidationError):
            Pose(pose_id="TEST", name="Test", pan_deg=181.0, tilt_deg=0.0)

    def test_tilt_range_validation(self):
        """Test tilt angle range validation."""
        # Valid ranges
        Pose(pose_id="TEST", name="Test", pan_deg=0.0, tilt_deg=-90.0)
        Pose(pose_id="TEST", name="Test", pan_deg=0.0, tilt_deg=90.0)
        Pose(pose_id="TEST", name="Test", pan_deg=0.0, tilt_deg=0.0)

        # Invalid - too negative
        with pytest.raises(ValidationError):
            Pose(pose_id="TEST", name="Test", pan_deg=0.0, tilt_deg=-91.0)

        # Invalid - too positive
        with pytest.raises(ValidationError):
            Pose(pose_id="TEST", name="Test", pan_deg=0.0, tilt_deg=91.0)

    def test_immutability(self):
        """Test that Pose is immutable."""
        pose = Pose(pose_id="TEST", name="Test", pan_deg=0.0, tilt_deg=0.0)

        with pytest.raises((ValidationError, AttributeError)):
            pose.pan_deg = 45.0


class TestPoseConfig:
    """Test PoseConfig model."""

    def test_default_pose_config(self):
        """Test default pose configuration."""
        config = PoseConfig()

        assert len(config.custom_poses) == 0
        assert len(config.pose_overrides) == 0

    def test_custom_poses(self):
        """Test adding custom poses."""
        config = PoseConfig(
            custom_poses={
                "CUSTOM_SPOT": Pose(
                    pose_id="CUSTOM_SPOT",
                    name="Custom Spotlight",
                    description="Venue-specific",
                    pan_deg=-15.0,
                    tilt_deg=25.0,
                )
            }
        )

        assert "CUSTOM_SPOT" in config.custom_poses
        assert config.custom_poses["CUSTOM_SPOT"].pan_deg == -15.0

    def test_pose_overrides(self):
        """Test overriding standard poses."""
        config = PoseConfig(
            pose_overrides={
                PoseID.FORWARD: Pose(
                    pose_id="FORWARD",
                    name="Forward (Adjusted)",
                    description="Adjusted for rig angle",
                    pan_deg=5.0,
                    tilt_deg=-2.0,
                )
            }
        )

        assert PoseID.FORWARD in config.pose_overrides
        assert config.pose_overrides[PoseID.FORWARD].pan_deg == 5.0

    def test_both_custom_and_overrides(self):
        """Test configuration with both custom poses and overrides."""
        config = PoseConfig(
            custom_poses={
                "VENUE_SPOT": Pose(
                    pose_id="VENUE_SPOT", name="Venue Spot", pan_deg=-12.0, tilt_deg=20.0
                )
            },
            pose_overrides={
                PoseID.DOWN: Pose(
                    pose_id="DOWN", name="Down (Low Rig)", pan_deg=0.0, tilt_deg=-35.0
                )
            },
        )

        assert len(config.custom_poses) == 1
        assert len(config.pose_overrides) == 1
