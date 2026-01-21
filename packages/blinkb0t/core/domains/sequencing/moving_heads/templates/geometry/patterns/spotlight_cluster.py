"""Spotlight cluster geometry transform."""

from __future__ import annotations

import logging
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class SpotlightClusterTransform(GeometryTransform):
    """Spotlight cluster/converging beam geometry.

    Creates a converging focal point where multiple fixtures point toward
    the same target area. Perfect for intimate moments, solos, and dramatic
    attention focus. Supports variable convergence tightness.

    The geometry calculates pan offsets to make fixtures converge on a target
    point, with optional spread to create a "cluster" rather than perfect overlap.

    Example with 4 fixtures, target at center (0°), tight convergence (spread=0.1):
        MH1 (left):   pan_offset = -3°  (converging right toward center)
        MH2 (c-left): pan_offset = -1°
        MH3 (c-right): pan_offset = +1°
        MH4 (right):  pan_offset = +3°  (converging left toward center)
    """

    geometry_type = "spotlight_cluster"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply spotlight cluster geometry with converging beams.

        Args:
            targets: List of fixture names (left-to-right order)
            base_movement: Base movement specification
            params: Optional parameters:
                - target_pan_offset_deg: Pan position of focal point (default: 0°, range: -90 to +90)
                - spread: Convergence tightness (default: 0.2, range: 0.0-1.0)
                  * 0.0 = perfect overlap (all fixtures aim at exact same point)
                  * 0.5 = moderate cluster (small spread around focal point)
                  * 1.0 = wider cluster (fixtures still converge but with noticeable spread)
                - tilt (or tilt_role): Tilt role for all fixtures (above_horizon/up/zero, default: above_horizon)

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}
        target_pan_offset_deg = float(params.get("target_pan_offset_deg", 0.0))
        spread = float(params.get("spread", 0.2))

        # Clamp spread to valid range
        spread = max(0.0, min(1.0, spread))

        # Phase 0: Tilt role support - default to "above_horizon" for spotlight effects
        tilt_role = self._get_tilt_role_from_params(params, default="above_horizon")

        num_fixtures = len(targets)
        if num_fixtures < 1:
            logger.warning("spotlight_cluster requires at least 1 fixture. Returning empty result.")
            return {}

        # Special case: single fixture just aims at target
        if num_fixtures == 1:
            movement = self._clone_movement(base_movement)
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + target_pan_offset_deg
            if tilt_role:
                self._assign_tilt_role(movement, tilt_role)
            logger.debug(
                f"Applied spotlight_cluster (single fixture): "
                f"target={target_pan_offset_deg}°, tilt_role={tilt_role}"
            )
            return {targets[0]: movement}

        # Calculate converging offsets for multiple fixtures
        result = {}
        # Maximum base offset from center (before convergence)
        max_base_offset = 30.0  # degrees (reasonable physical spacing assumption)

        for i, target in enumerate(targets):
            movement = self._clone_movement(base_movement)

            # Calculate fixture's normalized position: -1.0 (left) to +1.0 (right)
            if num_fixtures == 1:
                position = 0.0
            else:
                position = (2.0 * i / (num_fixtures - 1)) - 1.0

            # Base offset: where fixture would naturally be without convergence
            # Fixtures on left have negative offsets, right have positive
            base_offset = position * max_base_offset

            # Convergence: calculate how much to adjust toward target
            # Spread controls how tight the cluster is:
            #   - spread=0.0: full convergence (offset = target_pan_offset_deg)
            #   - spread=1.0: no convergence (offset = base_offset)
            converged_offset = (spread * base_offset) + target_pan_offset_deg

            # Add offset to movement
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + converged_offset

            # Phase 0: Assign tilt role if specified
            if tilt_role:
                self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"Applied spotlight_cluster: {num_fixtures} fixtures, "
            f"target={target_pan_offset_deg}°, spread={spread:.2f}, tilt_role={tilt_role}"
        )
        return result
