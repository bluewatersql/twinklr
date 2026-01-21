"""Chevron/V-shape geometry transform."""

from __future__ import annotations

import logging
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class ChevronVTransform(GeometryTransform):
    """V-shape / Chevron formation.

    Creates a V-shape formation where outer fixtures have larger pan
    offsets than inner fixtures, with optional tilt lift for the apex.

    From geometry_library.json: "chevron_v"

    Example:
        4 fixtures with tightness=0.65:
        MH1 (left outer):  pan_offset=-50°, tilt_offset=0°
        MH2 (left inner):  pan_offset=-18°, tilt_offset=+6°
        MH3 (right inner): pan_offset=+18°, tilt_offset=+6°
        MH4 (right outer): pan_offset=+50°, tilt_offset=0°
    """

    geometry_type = "chevron_v"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply chevron/V-shape geometry.

        Args:
            targets: List of fixture names (left-to-right order)
            base_movement: Base movement specification
            params: Optional parameters:
                - tightness: 0.0 (wide shallow V) to 1.0 (tight sharp V), default: 0.65
                - max_outer_pan_deg: Max pan offset for outer fixtures, default: 60°
                - inner_tilt_lift_deg: Tilt lift for apex/inner fixtures, default: 6°
                - orientation: "upward_V" or "downward_V", default: "upward_V"
                - tilt (or tilt_role): Tilt role for all fixtures (above_horizon/up/zero)

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}
        tightness = float(params.get("tightness", 0.65))
        max_outer_pan_deg = float(params.get("max_outer_pan_deg", 60))
        inner_tilt_lift_deg = float(params.get("inner_tilt_lift_deg", 6))
        orientation = params.get("orientation", "upward_V")

        # Phase 0: Tilt role support
        tilt_role = self._get_tilt_role_from_params(params)

        # Clamp tightness to 0-1
        tightness = max(0.0, min(1.0, tightness))

        num_fixtures = len(targets)
        if num_fixtures < 3:
            logger.warning(
                f"chevron_v works best with 3+ fixtures, got {num_fixtures}. "
                f"Returning base movement."
            )
            return {target: self._clone_movement(base_movement) for target in targets}

        # Define pan offsets at tightness extremes (for n=4)
        # Interpolate based on tightness parameter
        # Wide (tightness=0): [-35, -12, 12, 35]
        # Tight (tightness=1): [-60, -25, 25, 60]

        result = {}
        mid = num_fixtures / 2.0

        for i, target in enumerate(targets):
            movement = self._clone_movement(base_movement)

            # Calculate distance from center (0.5 to 1.0 for outer, 0.0 to 0.5 for inner)
            distance_from_center = abs((i + 0.5) - mid) / mid

            # Interpolate pan offset based on tightness
            # At tightness=0: use ~0.6 * max_outer_pan_deg
            # At tightness=1: use full max_outer_pan_deg
            min_factor = 0.35  # Shallow V factor
            max_factor = 1.0  # Sharp V factor
            spread_factor = min_factor + tightness * (max_factor - min_factor)

            # Calculate pan offset (negative for left, positive for right)
            side = 1 if (i + 0.5) > mid else -1
            pan_offset = side * distance_from_center * max_outer_pan_deg * spread_factor

            # Add pan offset
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + pan_offset

            # Add tilt lift for inner/apex fixtures
            # Inner fixtures have smaller distance_from_center
            is_inner = distance_from_center < 0.6
            if is_inner and inner_tilt_lift_deg != 0:
                tilt_offset = inner_tilt_lift_deg
                if orientation == "downward_V":
                    tilt_offset = -tilt_offset
                movement["tilt_offset_deg"] = movement.get("tilt_offset_deg", 0) + tilt_offset

            # Phase 0: Assign tilt role if specified
            if tilt_role:
                self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"Applied chevron_v: {num_fixtures} fixtures, "
            f"tightness={tightness:.2f}, max_outer={max_outer_pan_deg}°"
        )
        return result
