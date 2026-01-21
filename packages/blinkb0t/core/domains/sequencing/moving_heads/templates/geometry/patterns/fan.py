"""Fan geometry transform."""

from __future__ import annotations

import logging
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class FanTransform(GeometryTransform):
    """Fan/arc spread geometry.

    Spreads fixtures in a fan or arc formation with evenly distributed
    pan offsets. Similar to audience_scan but with more uniform distribution.

    Not explicitly in geometry_library.json but derived from similar patterns.

    Example:
        4 fixtures with 60° total spread:
        MH1: pan_offset=-30°
        MH2: pan_offset=-10°
        MH3: pan_offset=+10°
        MH4: pan_offset=+30°
    """

    geometry_type = "fan"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply fan geometry with distributed pan offsets.

        Args:
            targets: List of fixture names (left-to-right order)
            base_movement: Base movement specification
            params: Optional parameters:
                - total_spread_deg: Total fan spread angle (default: 60°)
                - center_offset_deg: Pan offset for center of fan (default: 0°)
                - tilt (or tilt_role): Tilt role for all fixtures (above_horizon/up/zero)

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}
        total_spread_deg = float(params.get("total_spread_deg", 60))
        center_offset_deg = float(params.get("center_offset_deg", 0))

        # Phase 0: Tilt role support
        tilt_role = self._get_tilt_role_from_params(params)

        num_fixtures = len(targets)
        if num_fixtures < 2:
            logger.warning(
                f"fan works best with 2+ fixtures, got {num_fixtures}. Returning base movement."
            )
            return {target: self._clone_movement(base_movement) for target in targets}

        # Calculate evenly distributed pan offsets across the fan spread
        result = {}
        for i, target in enumerate(targets):
            movement = self._clone_movement(base_movement)

            # Calculate position in fan: 0.0 (left) to 1.0 (right)
            if num_fixtures == 1:
                position = 0.5
            else:
                position = i / (num_fixtures - 1)

            # Convert to pan offset: -spread/2 to +spread/2
            pan_offset = (position - 0.5) * total_spread_deg + center_offset_deg

            # Add offset to movement
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + pan_offset

            # Phase 0: Assign tilt role if specified
            if tilt_role:
                self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"Applied fan: {num_fixtures} fixtures, "
            f"spread={total_spread_deg}°, center={center_offset_deg}°, tilt_role={tilt_role}"
        )
        return result
