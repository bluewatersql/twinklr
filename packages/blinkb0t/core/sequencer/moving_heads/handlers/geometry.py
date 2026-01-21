"""Geometry Handlers for the moving head sequencer.

This module implements geometry handlers that resolve static base poses
for fixtures. Geometry handlers determine WHERE the rig is positioned
in space (formation) but do NOT animate or change over time.

The primary handler is ROLE_POSE which maps role tokens to pan/tilt positions.
"""

from enum import Enum
from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class PanPose(str, Enum):
    """Standard pan pose positions.

    Defines normalized pan positions across the horizontal range.
    Values are ordered from left (0.0) to right (1.0).

    Attributes:
        WIDE_LEFT: Far left position (0.1).
        LEFT: Left position (0.3).
        CENTER: Center position (0.5).
        RIGHT: Right position (0.7).
        WIDE_RIGHT: Far right position (0.9).
    """

    WIDE_LEFT = "WIDE_LEFT"
    LEFT = "LEFT"
    CENTER = "CENTER"
    RIGHT = "RIGHT"
    WIDE_RIGHT = "WIDE_RIGHT"

    @property
    def norm_value(self) -> float:
        """Get normalized value for this pose."""
        values = {
            PanPose.WIDE_LEFT: 0.1,
            PanPose.LEFT: 0.3,
            PanPose.CENTER: 0.5,
            PanPose.RIGHT: 0.7,
            PanPose.WIDE_RIGHT: 0.9,
        }
        return values[self]


class TiltPose(str, Enum):
    """Standard tilt pose positions.

    Defines normalized tilt positions across the vertical range.
    Values are ordered from up/sky (high) to down/stage (low).

    Attributes:
        SKY: Pointing up (0.9).
        HORIZON: Level/horizontal (0.5).
        CROWD: Aimed at audience (0.3).
        STAGE: Pointing down at stage (0.1).
    """

    SKY = "SKY"
    HORIZON = "HORIZON"
    CROWD = "CROWD"
    STAGE = "STAGE"

    @property
    def norm_value(self) -> float:
        """Get normalized value for this pose."""
        values = {
            TiltPose.SKY: 0.9,
            TiltPose.HORIZON: 0.5,
            TiltPose.CROWD: 0.3,
            TiltPose.STAGE: 0.1,
        }
        return values[self]


class RolePoseHandler:
    """Geometry handler that maps role tokens to base poses.

    This handler resolves static base poses based on role assignments
    and pose tokens. It supports:

    - Explicit pan/tilt pose specification
    - Per-role pan pose mapping
    - Default poses when not specified

    The output is always a static normalized position - no animation.

    Attributes:
        handler_id: Unique identifier ("ROLE_POSE").

    Example:
        >>> handler = RolePoseHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="FRONT_LEFT",
        ...     params={
        ...         "pan_pose_by_role": {"FRONT_LEFT": "LEFT"},
        ...         "tilt_pose": "CROWD",
        ...     },
        ...     calibration={},
        ... )
        >>> result.pan_norm
        0.3
    """

    handler_id: str = "ROLE_POSE"

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve the base pose for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture (unused here).
            role: Role assigned to this fixture (e.g., "FRONT_LEFT").
            params: Handler parameters from template:
                - pan_pose: Explicit pan pose token (fallback)
                - pan_pose_by_role: Dict mapping role to pan pose
                - tilt_pose: Tilt pose token
            calibration: Fixture calibration data (unused in base impl).

        Returns:
            GeometryResult with normalized pan/tilt positions.

        Raises:
            ValueError: If an unknown pose token is specified.
        """
        # Resolve pan pose
        pan_norm = self._resolve_pan(role, params)

        # Resolve tilt pose
        tilt_norm = self._resolve_tilt(params)

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)

    def _resolve_pan(self, role: str, params: dict[str, Any]) -> float:
        """Resolve pan position from params.

        Priority:
        1. pan_pose_by_role[role] if role exists in mapping
        2. pan_pose explicit fallback
        3. CENTER default
        """
        pan_pose_by_role = params.get("pan_pose_by_role", {})

        # Check role mapping first
        if role in pan_pose_by_role:
            pose_name = pan_pose_by_role[role]
            return self._pan_pose_to_norm(pose_name)

        # Fallback to explicit pan_pose
        if "pan_pose" in params:
            return self._pan_pose_to_norm(params["pan_pose"])

        # Default to CENTER
        return PanPose.CENTER.norm_value

    def _resolve_tilt(self, params: dict[str, Any]) -> float:
        """Resolve tilt position from params.

        Uses tilt_pose if specified, otherwise defaults to HORIZON.
        """
        if "tilt_pose" in params:
            return self._tilt_pose_to_norm(params["tilt_pose"])

        # Default to HORIZON
        return TiltPose.HORIZON.norm_value

    def _pan_pose_to_norm(self, pose_name: str) -> float:
        """Convert pan pose name to normalized value.

        Args:
            pose_name: Name of the pan pose (e.g., "LEFT", "CENTER").

        Returns:
            Normalized pan value [0, 1].

        Raises:
            ValueError: If pose_name is not a valid PanPose.
        """
        try:
            pose = PanPose(pose_name)
            return pose.norm_value
        except ValueError as e:
            raise ValueError(f"Unknown pan pose: {pose_name}") from e

    def _tilt_pose_to_norm(self, pose_name: str) -> float:
        """Convert tilt pose name to normalized value.

        Args:
            pose_name: Name of the tilt pose (e.g., "HORIZON", "CROWD").

        Returns:
            Normalized tilt value [0, 1].

        Raises:
            ValueError: If pose_name is not a valid TiltPose.
        """
        try:
            pose = TiltPose(pose_name)
            return pose.norm_value
        except ValueError as e:
            raise ValueError(f"Unknown tilt pose: {pose_name}") from e
