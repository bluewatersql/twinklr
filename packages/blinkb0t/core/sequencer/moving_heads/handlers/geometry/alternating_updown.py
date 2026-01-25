"""Alternating up/down geometry handler - vertical contrast pattern."""

from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class AlternatingUpDownHandler:
    """Geometry handler for alternating up/down tilt positions.

    Creates vertical contrast by alternating fixtures between upward and
    horizon tilt positions. Uses fixture roles to determine alternation pattern.

    Attributes:
        handler_id: Unique identifier ("ALTERNATING_UPDOWN").
    """

    handler_id: str = "alternating_updown"

    # Roles that tilt UP
    UP_ROLES = ["FAR_LEFT", "INNER_LEFT", "CENTER", "INNER_RIGHT", "FAR_RIGHT"]
    # Roles that stay at HORIZON (alternates with UP roles)
    HORIZON_ROLES = ["OUTER_LEFT", "CENTER_LEFT", "CENTER_RIGHT", "OUTER_RIGHT"]

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve alternating up/down position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_center_norm: Center pan position (normalized, default: 0.5)
                - tilt_up_norm: Upward tilt position (normalized, default: 0.7)
                - tilt_horizon_norm: Horizon tilt position (normalized, default: 0.3)
                - pan_spread_norm: Pan spread from center (normalized, default: 0.2)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with alternating up/down tilt positions.
        """
        # Get params
        pan_center = params.get("pan_center_norm", 0.5)
        pan_spread = params.get("pan_spread_norm", 0.2)
        tilt_up = params.get("tilt_up_norm", 0.7)
        tilt_horizon = params.get("tilt_horizon_norm", 0.3)

        # Determine tilt based on role
        if role in self.UP_ROLES:
            tilt_norm = tilt_up
        elif role in self.HORIZON_ROLES:
            tilt_norm = tilt_horizon
        else:
            # Unknown role: alternate based on fixture_id hash
            tilt_norm = tilt_up if hash(fixture_id) % 2 == 0 else tilt_horizon

        # Pan: spread fixtures around center based on role position
        position_norm = self._role_to_position(role)
        pan_norm = pan_center + (position_norm - 0.5) * pan_spread

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
        role_order = [
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

        if role in role_order:
            idx = role_order.index(role)
            return idx / (len(role_order) - 1)

        # Fallback: center position
        return 0.5
