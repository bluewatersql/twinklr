"""Tests for ROLE_POSE Geometry Handler.

Tests the geometry handler that maps role tokens to base poses.
Validates pose resolution, calibration handling, and edge cases.
"""

import pytest

from blinkb0t.core.sequencer.moving_heads.handlers.geometry import (
    PanPose,
    RolePoseHandler,
    TiltPose,
)
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class TestPanPoseEnum:
    """Tests for PanPose enum values."""

    def test_pan_poses_have_normalized_values(self) -> None:
        """Test all PanPose values are normalized [0, 1]."""
        for pose in PanPose:
            assert 0.0 <= pose.norm_value <= 1.0

    def test_pan_pose_ordering(self) -> None:
        """Test pan poses are ordered left to right."""
        assert PanPose.WIDE_LEFT.norm_value < PanPose.LEFT.norm_value
        assert PanPose.LEFT.norm_value < PanPose.CENTER.norm_value
        assert PanPose.CENTER.norm_value < PanPose.RIGHT.norm_value
        assert PanPose.RIGHT.norm_value < PanPose.WIDE_RIGHT.norm_value

    def test_center_is_midpoint(self) -> None:
        """Test CENTER is at 0.5."""
        assert PanPose.CENTER.norm_value == 0.5


class TestTiltPoseEnum:
    """Tests for TiltPose enum values."""

    def test_tilt_poses_have_normalized_values(self) -> None:
        """Test all TiltPose values are normalized [0, 1]."""
        for pose in TiltPose:
            assert 0.0 <= pose.norm_value <= 1.0

    def test_tilt_pose_ordering(self) -> None:
        """Test tilt poses are ordered sky to stage."""
        # Logic SKY (up) > HORIZON > CROWD > STAGE (down)
        assert TiltPose.SKY.norm_value > TiltPose.HORIZON.norm_value
        assert TiltPose.HORIZON.norm_value > TiltPose.CROWD.norm_value
        assert TiltPose.CROWD.norm_value > TiltPose.STAGE.norm_value


class TestRolePoseHandler:
    """Tests for RolePoseHandler."""

    def test_handler_has_correct_id(self) -> None:
        """Test handler has correct handler_id."""
        handler = RolePoseHandler()
        assert handler.handler_id == "ROLE_POSE"

    def test_resolve_with_explicit_poses(self) -> None:
        """Test resolve with explicit pan and tilt poses."""
        handler = RolePoseHandler()
        result = handler.resolve(
            fixture_id="fx1",
            role="FRONT_LEFT",
            params={
                "pan_pose": "LEFT",
                "tilt_pose": "HORIZON",
            },
            calibration={},
        )

        assert isinstance(result, GeometryResult)
        assert result.pan_norm == PanPose.LEFT.norm_value
        assert result.tilt_norm == TiltPose.HORIZON.norm_value

    def test_resolve_with_role_mapping(self) -> None:
        """Test resolve with pan_pose_by_role mapping."""
        handler = RolePoseHandler()
        result = handler.resolve(
            fixture_id="fx1",
            role="FRONT_LEFT",
            params={
                "pan_pose_by_role": {
                    "FRONT_LEFT": "LEFT",
                    "FRONT_RIGHT": "RIGHT",
                },
                "tilt_pose": "CROWD",
            },
            calibration={},
        )

        # FRONT_LEFT role should map to LEFT pan pose
        assert result.pan_norm == PanPose.LEFT.norm_value
        assert result.tilt_norm == TiltPose.CROWD.norm_value

    def test_resolve_role_mapping_overrides_explicit(self) -> None:
        """Test role mapping overrides explicit pan_pose."""
        handler = RolePoseHandler()
        result = handler.resolve(
            fixture_id="fx1",
            role="FRONT_LEFT",
            params={
                "pan_pose": "CENTER",  # This should be overridden
                "pan_pose_by_role": {
                    "FRONT_LEFT": "WIDE_LEFT",
                },
                "tilt_pose": "HORIZON",
            },
            calibration={},
        )

        # Role mapping should override explicit pose
        assert result.pan_norm == PanPose.WIDE_LEFT.norm_value

    def test_resolve_defaults_to_center(self) -> None:
        """Test resolve defaults to CENTER/HORIZON when no params."""
        handler = RolePoseHandler()
        result = handler.resolve(
            fixture_id="fx1",
            role="UNKNOWN",
            params={},
            calibration={},
        )

        assert result.pan_norm == PanPose.CENTER.norm_value
        assert result.tilt_norm == TiltPose.HORIZON.norm_value

    def test_resolve_with_all_pan_poses(self) -> None:
        """Test resolve works with all pan pose values."""
        handler = RolePoseHandler()

        for pose in PanPose:
            result = handler.resolve(
                fixture_id="fx1",
                role="TEST",
                params={"pan_pose": pose.value, "tilt_pose": "HORIZON"},
                calibration={},
            )
            assert result.pan_norm == pose.norm_value

    def test_resolve_with_all_tilt_poses(self) -> None:
        """Test resolve works with all tilt pose values."""
        handler = RolePoseHandler()

        for pose in TiltPose:
            result = handler.resolve(
                fixture_id="fx1",
                role="TEST",
                params={"pan_pose": "CENTER", "tilt_pose": pose.value},
                calibration={},
            )
            assert result.tilt_norm == pose.norm_value


class TestRolePoseHandlerEdgeCases:
    """Tests for edge cases."""

    def test_role_not_in_mapping_uses_default(self) -> None:
        """Test role not in mapping falls back to explicit or default."""
        handler = RolePoseHandler()
        result = handler.resolve(
            fixture_id="fx1",
            role="UNKNOWN_ROLE",
            params={
                "pan_pose_by_role": {
                    "FRONT_LEFT": "LEFT",
                },
                "pan_pose": "CENTER",  # Fallback
                "tilt_pose": "HORIZON",
            },
            calibration={},
        )

        # Role not in mapping, should use pan_pose fallback
        assert result.pan_norm == PanPose.CENTER.norm_value

    def test_invalid_pan_pose_raises_error(self) -> None:
        """Test invalid pan pose raises ValueError."""
        handler = RolePoseHandler()
        with pytest.raises(ValueError, match="Unknown pan pose"):
            handler.resolve(
                fixture_id="fx1",
                role="TEST",
                params={"pan_pose": "INVALID_POSE", "tilt_pose": "HORIZON"},
                calibration={},
            )

    def test_invalid_tilt_pose_raises_error(self) -> None:
        """Test invalid tilt pose raises ValueError."""
        handler = RolePoseHandler()
        with pytest.raises(ValueError, match="Unknown tilt pose"):
            handler.resolve(
                fixture_id="fx1",
                role="TEST",
                params={"pan_pose": "CENTER", "tilt_pose": "INVALID_POSE"},
                calibration={},
            )

    def test_empty_role_mapping_uses_fallback(self) -> None:
        """Test empty role mapping uses fallback."""
        handler = RolePoseHandler()
        result = handler.resolve(
            fixture_id="fx1",
            role="FRONT_LEFT",
            params={
                "pan_pose_by_role": {},  # Empty mapping
                "pan_pose": "RIGHT",
                "tilt_pose": "CROWD",
            },
            calibration={},
        )

        # Empty mapping, should use fallback
        assert result.pan_norm == PanPose.RIGHT.norm_value


class TestRolePoseHandlerDeterminism:
    """Tests for handler determinism."""

    def test_same_input_same_output(self) -> None:
        """Test handler produces same output for same input."""
        handler = RolePoseHandler()
        params = {
            "pan_pose_by_role": {"FRONT_LEFT": "LEFT"},
            "tilt_pose": "CROWD",
        }
        calibration: dict[str, object] = {}

        result1 = handler.resolve("fx1", "FRONT_LEFT", params, calibration)
        result2 = handler.resolve("fx1", "FRONT_LEFT", params, calibration)

        assert result1.pan_norm == result2.pan_norm
        assert result1.tilt_norm == result2.tilt_norm

    def test_different_fixtures_same_role_same_result(self) -> None:
        """Test different fixtures with same role get same result."""
        handler = RolePoseHandler()
        params = {
            "pan_pose": "LEFT",
            "tilt_pose": "HORIZON",
        }
        calibration: dict[str, object] = {}

        result1 = handler.resolve("fx1", "FRONT_LEFT", params, calibration)
        result2 = handler.resolve("fx2", "FRONT_LEFT", params, calibration)

        assert result1.pan_norm == result2.pan_norm
        assert result1.tilt_norm == result2.tilt_norm
