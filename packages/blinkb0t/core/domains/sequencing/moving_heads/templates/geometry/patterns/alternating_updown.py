"""Alternating Up/Down geometry transform for vertical contrast effects."""

from __future__ import annotations

import logging
from typing import Any

from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.base import GeometryTransform

logger = logging.getLogger(__name__)


class AlternatingUpDownTransform(GeometryTransform):
    """
    Alternates fixtures between up and horizon tilt positions.

    Creates vertical contrast by assigning different tilt roles to fixtures
    based on their position. Supports two patterns:
    - "every_other": Alternates each fixture (0,1,0,1,0,1...)
    - "pairs": Alternates in pairs (0,0,1,1,0,0...)

    Ideal for:
    - Drop sections with edgy vertical contrast
    - Breakdown moments with alternating patterns
    - Modern high-energy sections

    Parameters:
    - pattern: "every_other" or "pairs" (default: "every_other")
    - up_tilt_role: "up" (60-90°) or "above_horizon" (default: "up")
    - down_tilt_role: "above_horizon" (30-50°) or "zero" (default: "above_horizon")
    - tilt_offset_deg: Optional shared tilt offset for all fixtures (default: 0)

    Min fixtures: 2
    """

    geometry_type = "alternating_updown"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Apply alternating up/down tilt roles to fixtures.

        Args:
            targets: List of fixture names
            base_movement: Base movement specification
            params: Geometry parameters including pattern, up_tilt_role, down_tilt_role

        Returns:
            Dictionary mapping fixture names to their movement specifications
        """
        if params is None:
            params = {}

        if len(targets) < 2:
            logger.warning(
                f"alternating_updown requires at least 2 fixtures, got {len(targets)}. "
                "Using first fixture only."
            )
            return {targets[0]: base_movement.copy()}

        # Extract parameters
        pattern = params.get("pattern", "every_other")
        up_tilt_role = params.get("up_tilt_role", "up")
        down_tilt_role = params.get("down_tilt_role", "above_horizon")
        tilt_offset_deg = float(params.get("tilt_offset_deg", 0))

        # Validate pattern
        if pattern not in ["every_other", "pairs"]:
            logger.warning(
                f"Invalid pattern '{pattern}' for alternating_updown. Using 'every_other' instead."
            )
            pattern = "every_other"

        # Validate tilt roles
        valid_tilt_roles = ["up", "above_horizon", "zero"]
        if up_tilt_role not in valid_tilt_roles:
            logger.warning(f"Invalid up_tilt_role '{up_tilt_role}'. Using 'up' instead.")
            up_tilt_role = "up"
        if down_tilt_role not in valid_tilt_roles:
            logger.warning(
                f"Invalid down_tilt_role '{down_tilt_role}'. Using 'above_horizon' instead."
            )
            down_tilt_role = "above_horizon"

        result: dict[str, dict[str, Any]] = {}

        for idx, fixture_name in enumerate(targets):
            movement = base_movement.copy()

            # Determine which tilt role to use based on pattern
            if pattern == "every_other":
                # Alternate each fixture: 0,1,0,1,0,1...
                is_up = idx % 2 == 0
            else:  # pattern == "pairs"
                # Alternate in pairs: 0,0,1,1,0,0...
                is_up = (idx // 2) % 2 == 0

            # Assign tilt role
            tilt_role = up_tilt_role if is_up else down_tilt_role
            self._assign_tilt_role(movement, tilt_role)

            # Apply shared tilt offset if specified
            if tilt_offset_deg != 0:
                movement["tilt_offset_deg"] = movement.get("tilt_offset_deg", 0) + tilt_offset_deg

            result[fixture_name] = movement

        return result
