"""Spotlight cluster geometry handler - converging beams to focal point."""

from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class SpotlightClusterHandler:
    """Geometry handler for converging spotlight cluster.

    Fixtures converge to create a tight focal point like a spotlight.
    Ideal for intimate moments and dramatic focus on specific areas.

    Attributes:
        handler_id: Unique identifier ("SPOTLIGHT_CLUSTER").

    Example:
        >>> handler = SpotlightClusterHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"focal_point_pan_norm": 0.5, "focal_point_tilt_norm": 0.3},
        ...     calibration={},
        ... )
    """

    handler_id: str = "spotlight_cluster"

    # Role ordering for determining fixture position
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
        """Resolve converging spotlight position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - focal_point_pan_norm: Pan position of focal point (normalized, default: 0.5)
                - focal_point_tilt_norm: Tilt position of focal point (normalized, default: 0.3)
                - convergence: Convergence factor [0, 1] (0=loose, 1=tight, default: 0.8)
                - pan_spread_norm: Base pan spread before convergence (normalized, default: 0.3)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with converging positions toward focal point.
        """
        # Get params
        focal_pan = params.get("focal_point_pan_norm", 0.5)
        focal_tilt = params.get("focal_point_tilt_norm", 0.3)
        convergence = params.get("convergence", 0.8)
        pan_spread = params.get("pan_spread_norm", 0.3)

        # Get fixture's base position (where it would be without convergence)
        position_norm = self._role_to_position(role)
        base_pan = focal_pan + (position_norm - 0.5) * pan_spread

        # Apply convergence: interpolate between base position and focal point
        # convergence=1.0 means all fixtures converge exactly at focal point
        # convergence=0.0 means fixtures stay at base spread positions
        pan_norm = base_pan * (1.0 - convergence) + focal_pan * convergence

        # Tilt: converge toward focal point with slight variation based on position
        # Outer fixtures need slightly different angles to converge
        distance_from_center = abs(position_norm - 0.5)
        tilt_adjustment = distance_from_center * 0.1 * (1.0 - convergence)
        tilt_norm = focal_tilt + tilt_adjustment

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
