"""Tunnel/cone geometry handler - circular overhead pattern."""

import math
from typing import Any

from twinklr.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class TunnelConeHandler:
    """Geometry handler for tunnel/cone formation.

    Creates circular pattern overhead forming a cone or tunnel effect.
    Immersive volumetric look for high-impact moments.

    Attributes:
        handler_id: Unique identifier ("TUNNEL_CONE").

    Example:
        >>> handler = TunnelConeHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"circle_radius_norm": 0.3, "tilt_angle_norm": 0.7},
        ...     calibration={},
        ... )
    """

    handler_id: str = "tunnel_cone"

    # Role ordering for circular positioning (clockwise from left)
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
        """Resolve circular tunnel/cone position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_center_norm: Center of circle (normalized, default: 0.5)
                - circle_radius_norm: Radius of circle in pan space (normalized, default: 0.3)
                - tilt_angle_norm: Tilt angle for cone (normalized, default: 0.7 for overhead)
                - rotation_offset: Starting angle offset in degrees (default: 0)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with circular cone/tunnel positions.
        """
        # Get params
        pan_center = params.get("pan_center_norm", 0.5)
        circle_radius = params.get("circle_radius_norm", 0.3)
        tilt_angle = params.get("tilt_angle_norm", 0.7)
        rotation_offset = params.get("rotation_offset", 0.0)

        # Map role to angular position around circle [0, 2π)
        position_norm = self._role_to_position(role)
        angle_rad = (position_norm * 2.0 * math.pi) + math.radians(rotation_offset)

        # Calculate pan position using circular projection
        # x = center + radius * cos(angle)
        pan_norm = pan_center + circle_radius * math.cos(angle_rad)

        # Tilt is mostly constant (overhead) but can vary slightly for 3D effect
        # Add slight tilt variation based on position for depth
        tilt_variation = circle_radius * 0.1 * math.sin(angle_rad)
        tilt_norm = tilt_angle + tilt_variation

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))
        tilt_norm = max(0.0, min(1.0, tilt_norm))

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)

    def _role_to_position(self, role: str) -> float:
        """Map role to normalized angular position [0, 1] around circle.

        Args:
            role: Fixture role (e.g., "OUTER_LEFT", "CENTER").

        Returns:
            Normalized angular position [0, 1] where 0 and 1 meet at left.
        """
        if role in self.ROLE_ORDER:
            idx = self.ROLE_ORDER.index(role)
            return idx / len(self.ROLE_ORDER)  # Divide by length (not length-1) for circular wrap

        # Fallback: 0 degrees position
        return 0.0
