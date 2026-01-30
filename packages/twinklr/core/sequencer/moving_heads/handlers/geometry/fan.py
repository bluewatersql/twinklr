"""Fan geometry handler - spreads fixtures in a fan pattern."""

from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class FanHandler:
    """Geometry handler for fan spread formation.

    Spreads fixtures out in a fan pattern from a central point.
    Uses fixture roles to determine position in the spread.

    Attributes:
        handler_id: Unique identifier ("FAN").

    Example:
        >>> handler = FanHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"pan_start_norm": 0.2, "pan_end_norm": 0.8},
        ...     calibration={},
        ... )
    """

    handler_id: str = "fan"

    # Role ordering from left to right
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

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve fan position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_start_norm: Start of fan spread (normalized, default: 0.2)
                - pan_end_norm: End of fan spread (normalized, default: 0.8)
                - tilt_start_norm: Start tilt position (normalized, default: 0.3)
                - tilt_end_norm: End tilt position (normalized, default: 0.7)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with fan-spread pan/tilt positions.
        """
        # Get pan/tilt ranges from params (normalized)
        pan_start = params.get("pan_start_norm", 0.2)
        pan_end = params.get("pan_end_norm", 0.8)
        tilt_start = params.get("tilt_start_norm", 0.3)
        tilt_end = params.get("tilt_end_norm", 0.7)

        # Map role to position in fan spread
        position_norm = self._role_to_position(role)

        # Calculate pan/tilt in fan spread
        pan_norm = pan_start + position_norm * (pan_end - pan_start)
        tilt_norm = tilt_start + position_norm * (tilt_end - tilt_start)

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)

    def _role_to_position(self, role: str) -> float:
        """Map role to normalized position [0, 1] in left-to-right order.

        Args:
            role: Fixture role (e.g., "OUTER_LEFT", "CENTER").

        Returns:
            Normalized position [0, 1] where 0 is leftmost, 1 is rightmost.
        """
        # Try to find role in ordered list
        if role in self.ROLE_ORDER:
            idx = self.ROLE_ORDER.index(role)
            return idx / (len(self.ROLE_ORDER) - 1)

        # Fallback: center position for unknown roles
        return 0.5
