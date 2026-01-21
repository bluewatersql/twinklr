"""Tunnel/Cone geometry transform for overhead volumetric effects."""

from __future__ import annotations

import logging
import math
from typing import Any

from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.base import GeometryTransform

logger = logging.getLogger(__name__)


class TunnelConeTransform(GeometryTransform):
    """
    Distributes fixtures in circular pattern overhead, creating cone/tunnel effect.

    Each fixture is positioned at a different angle around a circle, all pointing
    inward or outward to create a volumetric cone or tunnel effect. Best viewed
    with haze for maximum impact.

    Ideal for:
    - Climax moments with dramatic overhead effects
    - Drop sections with epic ceiling beams
    - Cinematic volumetric moments

    Parameters:
    - radius: 0.0-1.0 (cone tightness; 0=tight center, 1=wide cone) (default: 0.5)
    - tilt: "above_horizon" or "up" (default: "above_horizon")
    - pan_spread_deg: Circular distribution angle (60-120°) (default: 90)
    - center_pan_deg: Center point of circular pattern (default: 0)
    - tilt_offset_deg: Optional shared tilt adjustment (default: 0)

    Min fixtures: 4 (optimal: 6+)
    """

    geometry_type = "tunnel_cone"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Apply tunnel/cone circular distribution to fixtures.

        Args:
            targets: List of fixture names
            base_movement: Base movement specification
            params: Geometry parameters including radius, tilt, pan_spread_deg

        Returns:
            Dictionary mapping fixture names to their movement specifications
        """
        if params is None:
            params = {}

        num_fixtures = len(targets)

        if num_fixtures < 4:
            logger.warning(
                f"tunnel_cone optimal with 4+ fixtures (got {num_fixtures}). "
                "Effect may be less dramatic."
            )

        # Extract parameters
        radius = float(params.get("radius", 0.5))
        tilt_role = self._get_tilt_role_from_params(params, default="above_horizon")
        pan_spread_deg = float(params.get("pan_spread_deg", 90.0))
        center_pan_deg = float(params.get("center_pan_deg", 0.0))
        tilt_offset_deg = float(params.get("tilt_offset_deg", 0.0))

        # Clamp radius to valid range
        radius = max(0.0, min(1.0, radius))

        # Validate pan_spread_deg
        if pan_spread_deg < 60 or pan_spread_deg > 120:
            logger.warning(
                f"pan_spread_deg={pan_spread_deg} outside recommended range (60-120°). "
                "Using clamped value."
            )
            pan_spread_deg = max(60.0, min(120.0, pan_spread_deg))

        result: dict[str, dict[str, Any]] = {}

        # Calculate angular spacing for circular distribution
        angle_step = 360.0 / num_fixtures if num_fixtures > 1 else 0.0

        for idx, fixture_name in enumerate(targets):
            movement = base_movement.copy()

            # Calculate angle for this fixture (in degrees, 0° = front center)
            angle_deg = idx * angle_step

            # Convert to radians for trig calculations
            angle_rad = math.radians(angle_deg)

            # Calculate pan offset based on circular position
            # Map circular position to pan spread range
            # cos(angle) gives x-coordinate on unit circle (-1 to +1)
            pan_position = math.cos(angle_rad)  # -1 (left) to +1 (right)
            pan_offset = center_pan_deg + (pan_position * pan_spread_deg / 2.0)

            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + pan_offset

            # Calculate tilt variation based on radius
            # Larger radius = more outward tilt variation (wider cone)
            # sin(angle) gives y-coordinate on unit circle (-1 to +1)
            # This creates subtle tilt variations around the circle
            tilt_variation = math.sin(angle_rad) * radius * 10.0  # Scale factor for visible effect

            # Assign base tilt role
            if tilt_role:
                self._assign_tilt_role(movement, tilt_role)

            # Apply tilt variations
            total_tilt_offset = tilt_offset_deg + tilt_variation
            if total_tilt_offset != 0:
                movement["tilt_offset_deg"] = movement.get("tilt_offset_deg", 0) + total_tilt_offset

            result[fixture_name] = movement

            # Log first fixture for debugging
            if idx == 0:
                logger.debug(
                    f"tunnel_cone: fixture[0] angle={angle_deg:.1f}° "
                    f"pan_offset={pan_offset:.1f}° tilt_variation={tilt_variation:.1f}°"
                )

        return result
