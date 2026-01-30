"""Rainbow arc geometry handler - smooth arc formations."""

import math
from typing import Any

from twinklr.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class RainbowArcHandler:
    """Geometry handler for rainbow arc formation.

    Creates smooth arc formation resembling a rainbow, with optional
    vertical curve. Uses fixture roles to determine position along the arc.

    Attributes:
        handler_id: Unique identifier ("RAINBOW_ARC").

    Example:
        >>> handler = RainbowArcHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"pan_start_norm": 0.2, "pan_end_norm": 0.8, "arc_height_norm": 0.3},
        ...     calibration={},
        ... )
    """

    handler_id: str = "rainbow_arc"

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
        """Resolve rainbow arc position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_start_norm: Start of arc (normalized, default: 0.2)
                - pan_end_norm: End of arc (normalized, default: 0.8)
                - tilt_base_norm: Base tilt level (normalized, default: 0.3)
                - arc_height_norm: Height of arc curve (normalized, default: 0.2)
                - invert_arc: Invert arc (concave down), default: False
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with rainbow arc positions.
        """
        # Get params
        pan_start = params.get("pan_start_norm", 0.2)
        pan_end = params.get("pan_end_norm", 0.8)
        tilt_base = params.get("tilt_base_norm", 0.3)
        arc_height = params.get("arc_height_norm", 0.2)
        invert_arc = params.get("invert_arc", False)

        # Map role to position along arc [0, 1]
        position_norm = self._role_to_position(role)

        # Calculate horizontal pan position (linear interpolation)
        pan_norm = pan_start + position_norm * (pan_end - pan_start)

        # Calculate vertical tilt using parabolic arc
        # Arc is highest/lowest at center (position_norm = 0.5)
        # y = -4 * (x - 0.5)^2 + 1  (inverted parabola, peak at center)
        arc_factor = 1.0 - 4.0 * math.pow(position_norm - 0.5, 2)

        if invert_arc:
            # Concave down (U-shape)
            tilt_norm = tilt_base - (arc_factor * arc_height)
        else:
            # Concave up (rainbow shape)
            tilt_norm = tilt_base + (arc_factor * arc_height)

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
