from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult
from blinkb0t.core.sequencer.moving_heads.models.base import PanPose, TiltPose


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
