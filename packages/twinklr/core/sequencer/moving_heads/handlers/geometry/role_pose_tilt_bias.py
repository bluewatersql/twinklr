"""Role pose with tilt bias geometry handler - role-based pan with group tilt offsets."""

from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class RolePoseTiltBiasHandler:
    """Geometry handler for role-based pan with per-group tilt bias.

    Uses role-based pan positioning (similar to ROLE_POSE) while applying
    group-specific tilt bias to create vertical contrast between fixture groups.

    Attributes:
        handler_id: Unique identifier ("ROLE_POSE_TILT_BIAS").

    Example:
        >>> handler = RolePoseTiltBiasHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"tilt_base_norm": 0.4, "group_tilt_bias_norm": 0.1},
        ...     calibration={},
        ... )
    """

    handler_id: str = "role_pose_tilt_bias"

    # Role ordering from left to right for pan positioning
    ROLE_ORDER = [
        "FAR_LEFT",
        "OUTER_LEFT",
        "INNER_LEFT",
        "CENTER_LEFT",
        "CENTER",
        "CENTER_RIGHT",
        "INNER_RIGHT",
        "OUTER_RIGHT",
        "FAR_RIGHT",
    ]

    # Group assignments for tilt bias (inner vs outer)
    INNER_ROLES = ["INNER_LEFT", "CENTER_LEFT", "CENTER", "CENTER_RIGHT", "INNER_RIGHT"]
    OUTER_ROLES = ["FAR_LEFT", "OUTER_LEFT", "OUTER_RIGHT", "FAR_RIGHT"]

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve role-based position with tilt bias for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_start_norm: Start of pan range (normalized, default: 0.2)
                - pan_end_norm: End of pan range (normalized, default: 0.8)
                - tilt_base_norm: Base tilt position (normalized, default: 0.4)
                - inner_tilt_bias_norm: Tilt offset for inner group (normalized, default: 0.1)
                - outer_tilt_bias_norm: Tilt offset for outer group (normalized, default: -0.1)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with role-based pan and group-biased tilt positions.
        """
        # Get params
        pan_start = params.get("pan_start_norm", 0.2)
        pan_end = params.get("pan_end_norm", 0.8)
        tilt_base = params.get("tilt_base_norm", 0.4)
        inner_tilt_bias = params.get("inner_tilt_bias_norm", 0.1)
        outer_tilt_bias = params.get("outer_tilt_bias_norm", -0.1)

        # Calculate pan based on role position (left to right)
        position_norm = self._role_to_position(role)
        pan_norm = pan_start + position_norm * (pan_end - pan_start)

        # Apply tilt bias based on group membership
        if role in self.INNER_ROLES:
            tilt_norm = tilt_base + inner_tilt_bias
        elif role in self.OUTER_ROLES:
            tilt_norm = tilt_base + outer_tilt_bias
        else:
            # Unknown role: use base tilt
            tilt_norm = tilt_base

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))
        tilt_norm = max(0.0, min(1.0, tilt_norm))

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)

    def _role_to_position(self, role: str) -> float:
        """Map role to normalized position [0, 1] in left-to-right order.

        Args:
            role: Fixture role (e.g., "OUTER_LEFT", "CENTER").

        Returns:
            Normalized position [0, 1] where 0 is leftmost, 1 is rightmost.
        """
        if role in self.ROLE_ORDER:
            idx = self.ROLE_ORDER.index(role)
            return idx / (len(self.ROLE_ORDER) - 1)

        # Fallback: center position
        return 0.5
