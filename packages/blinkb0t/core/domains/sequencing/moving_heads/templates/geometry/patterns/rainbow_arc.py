"""Rainbow arc geometry transform."""

from __future__ import annotations

import logging
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class RainbowArcTransform(GeometryTransform):
    """Rainbow arc / spectrum spread geometry.

    Creates a horizontal arc formation spanning a wide angle. Optionally
    applies a vertical curve (parabola) where center fixtures are lifted
    higher for a true arc silhouette.

    Perfect for uplifting moments, choruses, and festival-style wide spreads.
    The "rainbow" name refers to the visual arc shape, not colors (this is
    a pan/tilt geometry only).

    Example with 4 fixtures, 120° arc width, curved mode:
        MH1 (left):   pan_offset = -60°, tilt_offset = 0° (edge)
        MH2 (c-left): pan_offset = -20°, tilt_offset = +7° (lifted)
        MH3 (c-right): pan_offset = +20°, tilt_offset = +7° (lifted)
        MH4 (right):  pan_offset = +60°, tilt_offset = 0° (edge)

    This creates a wide, photogenic arc that reads as "designed" and uplifting.
    """

    geometry_type = "rainbow_arc"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply rainbow arc geometry with horizontal spread and optional vertical curve.

        Args:
            targets: List of fixture names (left-to-right order)
            base_movement: Base movement specification
            params: Optional parameters:
                - arc_width_deg: Total horizontal spread across fixtures (default: 120°, range: 30-160)
                - arc_height: "flat" or "curved" (default: "curved")
                  * "flat" = all fixtures at same tilt offset (0°)
                  * "curved" = center fixtures lifted higher (parabolic curve)
                - center_tilt_lift_deg: Maximum tilt lift for center fixtures when curved (default: 7°, range: 0-15)
                - tilt (or tilt_role): Base tilt role for all fixtures (above_horizon/up/zero, default: above_horizon)

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}
        arc_width_deg = float(params.get("arc_width_deg", 120.0))
        arc_height = params.get("arc_height", "curved")
        center_tilt_lift_deg = float(params.get("center_tilt_lift_deg", 7.0))

        # Clamp parameters to valid ranges
        arc_width_deg = max(30.0, min(160.0, arc_width_deg))
        center_tilt_lift_deg = max(0.0, min(15.0, center_tilt_lift_deg))

        # Phase 0: Tilt role support - default to "above_horizon" for arc effects
        tilt_role = self._get_tilt_role_from_params(params, default="above_horizon")

        num_fixtures = len(targets)
        if num_fixtures < 3:
            logger.warning(
                f"rainbow_arc works best with 3+ fixtures, got {num_fixtures}. "
                f"Falling back to simple fan spread."
            )
            # For < 3 fixtures, just do a simple fan spread
            arc_height = "flat"

        # Calculate pan offsets: evenly distributed across arc
        result = {}
        for i, target in enumerate(targets):
            movement = self._clone_movement(base_movement)

            # Calculate normalized position: 0.0 (left) to 1.0 (right)
            if num_fixtures == 1:
                position = 0.5
            else:
                position = i / (num_fixtures - 1)

            # Convert to pan offset: -arc_width/2 to +arc_width/2
            pan_offset = (position - 0.5) * arc_width_deg
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + pan_offset

            # Calculate tilt offset based on arc_height mode
            if arc_height == "curved" and center_tilt_lift_deg > 0:
                # Parabolic curve: center is highest, edges are at 0
                # Use forumla lift * (1 - 4*(position - 0.5)^2)
                # This creates a smooth parabola with max at center
                distance_from_center = abs(position - 0.5) * 2.0  # 0.0 at center, 1.0 at edges
                tilt_offset = center_tilt_lift_deg * (1.0 - distance_from_center**2)
            else:
                # Flat mode: no tilt variation
                tilt_offset = 0.0

            movement["tilt_offset_deg"] = movement.get("tilt_offset_deg", 0) + tilt_offset

            # Phase 0: Assign tilt role if specified
            if tilt_role:
                self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"Applied rainbow_arc: {num_fixtures} fixtures, "
            f"arc_width={arc_width_deg}°, height={arc_height}, "
            f"center_lift={center_tilt_lift_deg if arc_height == 'curved' else 0}°, "
            f"tilt_role={tilt_role}"
        )
        return result
