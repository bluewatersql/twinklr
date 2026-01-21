"""X-cross / Criss-cross geometry transform."""

from __future__ import annotations

import logging
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class XCrossTransform(GeometryTransform):
    """X-cross / Criss-cross geometry.

    Two groups cross diagonally through center for high-energy, readable motion.
    Best for chorus, drop, build sections with haze.

    From geometry_library.json:
    - Dynamic, aggressive, diagonal energy vibes
    - Works best with LEFT/RIGHT or ODD/EVEN grouping
    - Alternating diagonal endpoints per group
    - Swap directions every N bars for phrase-aligned motion

    Example (n=4, swap_phase=0):
        Group A (fixtures 0,1): diagonal down-left to up-right
        Group B (fixtures 2,3): diagonal up-right to down-left
    """

    geometry_type = "x_cross"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply x_cross geometry with diagonal crossing patterns.

        Args:
            targets: List of fixture names (left-to-right order)
            base_movement: Base movement specification
            params: Optional parameters:
                - pan_spread_deg: Diagonal corner horizontal reach (default: 45)
                - tilt_delta_deg: Vertical diagonal separation (default: 15)
                - swap_every_bars: Phrase-aligned direction reversal (default: 4)
                - swap_phase: Current phase (0 or 1, default: 0)
                - tilt (or tilt_role): Base tilt role (default: above_horizon)

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}
        pan_spread_deg = float(params.get("pan_spread_deg", 45))
        tilt_delta_deg = float(params.get("tilt_delta_deg", 15))
        swap_phase = int(params.get("swap_phase", 0)) % 2  # 0 or 1

        # Tilt role support (base tilt, offsets applied on top)
        tilt_role = self._get_tilt_role_from_params(params)

        num_fixtures = len(targets)
        if num_fixtures < 2:
            logger.warning(
                f"x_cross works best with 2+ fixtures, got {num_fixtures}. Returning base movement."
            )
            return {target: self._clone_movement(base_movement) for target in targets}

        # Divide fixtures into two groups (A and B)
        # Group A: first half, Group B: second half
        mid_point = num_fixtures // 2
        group_a_indices = list(range(mid_point))
        group_b_indices = list(range(mid_point, num_fixtures))

        # Define diagonal endpoints based on swap_phase
        # From metadata variant n4:
        # diagonal A starts: {pan: [-45, -25], tilt: [15, 10]}
        # diagonal A ends:   {pan: [45, 25], tilt: [-15, -10]}
        # diagonal B starts: {pan: [45, 25], tilt: [15, 10]}
        # diagonal B ends:   {pan: [-45, -25], tilt: [-15, -10]}

        result = {}
        for i, target in enumerate(targets):
            movement = self._clone_movement(base_movement)

            is_group_a = i in group_a_indices
            group_size = len(group_a_indices) if is_group_a else len(group_b_indices)
            group_index = group_a_indices.index(i) if is_group_a else group_b_indices.index(i)

            # Calculate position within group (0.0 to 1.0, outer to inner)
            if group_size == 1:
                position = 0.5
            else:
                position = group_index / (group_size - 1)

            # Calculate base offsets (proportional to position in group)
            # Outer fixtures get full spread, inner fixtures get scaled
            pan_scale = 1.0 - (position * 0.45)  # Outer: 1.0, Inner: ~0.55
            tilt_scale = 1.0 - (position * 0.33)  # Outer: 1.0, Inner: ~0.67

            # Apply diagonal patterns based on group and swap phase
            if is_group_a:
                # Group A crosses from left-high to right-low (or reversed)
                if swap_phase == 0:
                    pan_offset = -pan_spread_deg * pan_scale
                    tilt_offset = tilt_delta_deg * tilt_scale
                else:
                    pan_offset = pan_spread_deg * pan_scale
                    tilt_offset = -tilt_delta_deg * tilt_scale
            else:
                # Group B crosses from right-high to left-low (or reversed)
                if swap_phase == 0:
                    pan_offset = pan_spread_deg * pan_scale
                    tilt_offset = tilt_delta_deg * tilt_scale
                else:
                    pan_offset = -pan_spread_deg * pan_scale
                    tilt_offset = -tilt_delta_deg * tilt_scale

            # Apply offsets
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + pan_offset
            movement["tilt_offset_deg"] = movement.get("tilt_offset_deg", 0) + tilt_offset

            # Assign tilt role
            self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"x_cross: pan_spread={pan_spread_deg}°, tilt_delta={tilt_delta_deg}°, "
            f"swap_phase={swap_phase}, groups=({len(group_a_indices)}, {len(group_b_indices)})"
        )

        return result
