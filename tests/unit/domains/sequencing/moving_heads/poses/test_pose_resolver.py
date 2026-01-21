"""Tests for pose system."""

import pytest

from blinkb0t.core.domains.sequencing.models.poses import Pose, PoseConfig, PoseID
from blinkb0t.core.domains.sequencing.poses import (
    STANDARD_POSES,
    PoseResolver,
    get_pose_by_name,
    get_standard_pose,
    list_standard_poses,
)


class TestStandardPoses:
    """Test standard pose definitions."""

    def test_all_pose_ids_defined(self):
        """Test that all PoseID enum values are in STANDARD_POSES."""
        for pose_id in PoseID:
            assert pose_id in STANDARD_POSES

    def test_get_standard_pose(self):
        """Test getting standard pose by ID."""
        pose = get_standard_pose(PoseID.FORWARD)
        assert pose.pose_id == "FORWARD"
        assert pose.pan_deg == 0.0
        assert pose.tilt_deg == 0.0

    def test_list_standard_poses(self):
        """Test listing all standard poses."""
        poses = list_standard_poses()
        assert len(poses) > 0
        assert PoseID.FORWARD in poses
        assert PoseID.UP in poses

    def test_get_pose_by_name(self):
        """Test getting pose by human-readable name."""
        pose = get_pose_by_name("Forward Horizon")
        assert pose is not None
        assert pose.pose_id == "FORWARD"

        # Case insensitive
        pose = get_pose_by_name("forward horizon")
        assert pose is not None
        assert pose.pose_id == "FORWARD"

    def test_get_pose_by_name_not_found(self):
        """Test getting non-existent pose by name."""
        pose = get_pose_by_name("Nonexistent Pose")
        assert pose is None


class TestPoseResolver:
    """Test pose resolver."""

    @pytest.fixture
    def resolver(self) -> PoseResolver:
        """Create pose resolver."""
        return PoseResolver()

    def test_resolver_initialization(self, resolver: PoseResolver):
        """Test resolver initializes with standard poses."""
        assert len(resolver.poses) >= len(STANDARD_POSES)

    def test_resolve_standard_pose(self, resolver: PoseResolver):
        """Test resolving standard pose."""
        pan, tilt = resolver.resolve_pose(PoseID.FORWARD)
        assert pan == 0.0
        assert tilt == 0.0

    def test_resolve_pose_by_string(self, resolver: PoseResolver):
        """Test resolving pose by string ID."""
        pan, tilt = resolver.resolve_pose("FORWARD")
        assert pan == 0.0
        assert tilt == 0.0

    def test_resolve_pose_with_offset(self, resolver: PoseResolver):
        """Test resolving pose with geometry offset."""
        pan, tilt = resolver.resolve_pose_with_offset(
            PoseID.FORWARD, pan_offset_deg=15.0, tilt_offset_deg=10.0
        )
        assert pan == 15.0
        assert tilt == 10.0

    def test_resolve_pose_not_found(self, resolver: PoseResolver):
        """Test resolving non-existent pose raises KeyError."""
        with pytest.raises(KeyError):
            resolver.resolve_pose("NONEXISTENT")

    def test_get_pose(self, resolver: PoseResolver):
        """Test getting raw pose definition."""
        pose = resolver.get_pose(PoseID.FORWARD)
        assert pose.pose_id == "FORWARD"
        assert pose.pan_deg == 0.0

    def test_list_poses(self, resolver: PoseResolver):
        """Test listing available poses."""
        poses = resolver.list_poses()
        assert len(poses) >= len(STANDARD_POSES)
        assert "FORWARD" in poses

    def test_range_clamping(self):
        """Test that resolver clamps poses to specified range."""
        # Create resolver with limited range
        resolver = PoseResolver(pan_range_deg=180.0, tilt_range_deg=90.0)

        # Try to resolve pose that's out of range
        pan, _tilt = resolver.resolve_pose_with_offset(PoseID.FORWARD, pan_offset_deg=200.0)

        # Should be clamped to ±90° for pan
        assert pan == 90.0  # Clamped from 200°

    def test_pose_overrides(self):
        """Test pose overrides."""
        # Create custom FORWARD pose
        custom_forward = Pose(
            pose_id="FORWARD",
            name="Custom Forward",
            description="Custom",
            pan_deg=10.0,
            tilt_deg=5.0,
        )

        pose_config = PoseConfig(pose_overrides={PoseID.FORWARD: custom_forward})
        resolver = PoseResolver(pose_config)

        pan, tilt = resolver.resolve_pose(PoseID.FORWARD)
        assert pan == 10.0
        assert tilt == 5.0

    def test_custom_poses(self):
        """Test custom user-defined poses."""
        custom_pose = Pose(
            pose_id="MY_CUSTOM_POSE",
            name="My Custom Pose",
            description="A custom pose",
            pan_deg=25.0,
            tilt_deg=15.0,
        )

        pose_config = PoseConfig(custom_poses={"MY_CUSTOM_POSE": custom_pose})
        resolver = PoseResolver(pose_config)

        pan, tilt = resolver.resolve_pose("MY_CUSTOM_POSE")
        assert pan == 25.0
        assert tilt == 15.0
