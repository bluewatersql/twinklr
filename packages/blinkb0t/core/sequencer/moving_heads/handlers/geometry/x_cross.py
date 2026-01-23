"""X-cross geometry handler - diagonal crossing pattern."""

from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class XCrossHandler:
    """Geometry handler for X-cross diagonal pattern.

    Groups cross diagonally creating an X pattern. Left fixtures aim right,
    right fixtures aim left, creating high-energy readable motion.

    Attributes:
        handler_id: Unique identifier ("X_CROSS").

    Example:
        >>> handler = XCrossHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"pan_start_norm": 0.2, "pan_end_norm": 0.8},
        ...     calibration={},
        ... )
    """

    handler_id: str = "x_cross"

    # Left side roles (will aim right/down)
    LEFT_ROLES = ["FAR_LEFT", "OUTER_LEFT", "INNER_LEFT", "CENTER_LEFT"]
    # Right side roles (will aim left/down)
    RIGHT_ROLES = ["CENTER_RIGHT", "INNER_RIGHT", "OUTER_RIGHT", "FAR_RIGHT"]

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve X-cross position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_start_norm: Left edge position (normalized, default: 0.2)
                - pan_end_norm: Right edge position (normalized, default: 0.8)
                - tilt_high_norm: High tilt position (normalized, default: 0.6)
                - tilt_low_norm: Low tilt position (normalized, default: 0.2)
                - cross_factor: How much to cross [0, 1] (0=no cross, 1=full cross, default: 1.0)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with X-cross diagonal positions.
        """
        # Get params
        pan_start = params.get("pan_start_norm", 0.2)
        pan_end = params.get("pan_end_norm", 0.8)
        tilt_high = params.get("tilt_high_norm", 0.6)
        tilt_low = params.get("tilt_low_norm", 0.2)
        cross_factor = params.get("cross_factor", 1.0)

        # Determine side and position within that side
        if role in self.LEFT_ROLES:
            # Left fixtures aim right/down (diagonal down-right)
            side = "left"
            idx = self.LEFT_ROLES.index(role)
            position_in_group = (
                idx / (len(self.LEFT_ROLES) - 1) if len(self.LEFT_ROLES) > 1 else 0.0
            )
        elif role in self.RIGHT_ROLES:
            # Right fixtures aim left/down (diagonal down-left)
            side = "right"
            idx = self.RIGHT_ROLES.index(role)
            position_in_group = (
                idx / (len(self.RIGHT_ROLES) - 1) if len(self.RIGHT_ROLES) > 1 else 0.0
            )
        elif role == "CENTER":
            # Center fixture stays centered
            side = "center"
            position_in_group = 0.5
        else:
            # Unknown role: default to center
            side = "center"
            position_in_group = 0.5

        # Calculate pan and tilt based on side
        if side == "left":
            # Left fixtures: cross toward right
            # Start at left, progress to right as position increases
            base_pan = pan_start
            target_pan = pan_end
            pan_norm = base_pan + (target_pan - base_pan) * position_in_group * cross_factor

            # Tilt: start high, go down
            tilt_norm = tilt_high - (tilt_high - tilt_low) * position_in_group

        elif side == "right":
            # Right fixtures: cross toward left
            # Start at right, progress to left as position increases
            base_pan = pan_end
            target_pan = pan_start
            pan_norm = base_pan + (target_pan - base_pan) * position_in_group * cross_factor

            # Tilt: start high, go down
            tilt_norm = tilt_high - (tilt_high - tilt_low) * position_in_group

        else:
            # Center fixture
            pan_norm = (pan_start + pan_end) / 2.0
            tilt_norm = (tilt_high + tilt_low) / 2.0

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))
        tilt_norm = max(0.0, min(1.0, tilt_norm))

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)
