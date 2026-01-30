"""Center-outward geometry handler - radiating from center."""

from typing import Any

from twinklr.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class CenterOutHandler:
    """Geometry handler for center-outward radiating pattern.

    Positions fixtures radiating outward from a center point, creating
    expanding or converging visual effects. Uses fixture roles to
    determine distance from center.

    Attributes:
        handler_id: Unique identifier ("CENTER_OUT").

    Example:
        >>> handler = CenterOutHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"pan_center_norm": 0.5, "tilt_center_norm": 0.4},
        ...     calibration={},
        ... )
    """

    handler_id: str = "center_out"

    # Center roles (innermost)
    CENTER_ROLES = ["CENTER", "CENTER_LEFT", "CENTER_RIGHT"]
    # Inner roles (middle distance)
    INNER_ROLES = ["INNER_LEFT", "INNER_RIGHT"]
    # Outer roles (furthest from center)
    OUTER_ROLES = ["OUTER_LEFT", "OUTER_RIGHT", "FAR_LEFT", "FAR_RIGHT"]

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve center-outward position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_center_norm: Center pan position (normalized, default: 0.5)
                - tilt_center_norm: Center tilt position (normalized, default: 0.4)
                - pan_spread_norm: Maximum pan spread from center (normalized, default: 0.3)
                - tilt_spread_norm: Maximum tilt spread from center (normalized, default: 0.2)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with center-outward radiating positions.
        """
        # Get params
        pan_center = params.get("pan_center_norm", 0.5)
        tilt_center = params.get("tilt_center_norm", 0.4)
        pan_spread = params.get("pan_spread_norm", 0.3)
        tilt_spread = params.get("tilt_spread_norm", 0.2)

        # Determine distance from center based on role
        if role in self.CENTER_ROLES:
            distance = 0.0  # At center
        elif role in self.INNER_ROLES:
            distance = 0.5  # Halfway out
        elif role in self.OUTER_ROLES:
            distance = 1.0  # Full spread
        else:
            distance = 0.5  # Unknown role: mid-range

        # Calculate direction based on role (left vs right)
        direction = self._role_to_direction(role)

        # Calculate position: center + (distance * spread * direction)
        pan_norm = pan_center + (distance * pan_spread * direction)

        # Tilt: radiate outward (up and down based on left/right)
        # Left side: tilt down slightly, right side: tilt up slightly
        tilt_offset = distance * tilt_spread * (0.5 if direction < 0 else -0.5)
        tilt_norm = tilt_center + tilt_offset

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))
        tilt_norm = max(0.0, min(1.0, tilt_norm))

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)

    def _role_to_direction(self, role: str) -> float:
        """Map role to direction (-1 for left, +1 for right, 0 for center).

        Args:
            role: Fixture role (e.g., "OUTER_LEFT", "CENTER").

        Returns:
            Direction multiplier: -1 (left), 0 (center), +1 (right).
        """
        left_roles = ["FAR_LEFT", "OUTER_LEFT", "INNER_LEFT", "CENTER_LEFT"]
        right_roles = ["CENTER_RIGHT", "INNER_RIGHT", "OUTER_RIGHT", "FAR_RIGHT"]

        if role in left_roles:
            return -1.0
        elif role in right_roles:
            return 1.0
        else:
            return 0.0  # CENTER or unknown
