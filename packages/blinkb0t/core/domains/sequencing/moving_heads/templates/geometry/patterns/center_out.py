"""Center-out / Outside-in geometry transform."""

from __future__ import annotations

import logging
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class CenterOutTransform(GeometryTransform):
    """Center-out / Outside-in geometry.

    Expands outward from center or collapses inward to center to shape energy dynamics.
    Best rendered as phrase-based geometry change across multiple bars/steps.

    From geometry_library.json:
    - Cinematic, dynamic, tension/release vibes
    - Use discrete geometry steps over time (e.g., every bar) if steps > 1
    - center_out: start tight (near 0°) then expand to max_pan_spread_deg
    - outside_in: start wide then converge to 0° offsets at phrase boundary

    Example (n=4, center_out):
        Step 1 (start): pan_offsets = [0, 0, 0, 0]
        Step 3 (mid):   pan_offsets = [-35, -12, 12, 35]
        Step 6 (end):   pan_offsets = [-70, -25, 25, 70]
    """

    geometry_type = "center_out"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply center-out/outside-in geometry with pan offsets.

        Args:
            targets: List of fixture names (left-to-right order)
            base_movement: Base movement specification
            params: Optional parameters:
                - mode: "center_out" or "outside_in" (default: "center_out")
                - steps: Number of geometry positions (default: 6)
                - max_pan_spread_deg: Maximum outer spread (default: 70)
                - tilt_offset_deg: Shared tilt offset (default: 0)
                - step: Current step number (0 to steps-1, default: steps-1 for final position)
                - tilt (or tilt_role): Tilt role for all fixtures

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}
        mode = params.get("mode", "center_out")
        steps = int(params.get("steps", 6))
        max_pan_spread_deg = float(params.get("max_pan_spread_deg", 70))
        tilt_offset_deg = float(params.get("tilt_offset_deg", 0))
        current_step = int(params.get("step", steps - 1))  # Default to final position

        # Tilt role support
        tilt_role = self._get_tilt_role_from_params(params)

        num_fixtures = len(targets)
        if num_fixtures < 2:
            logger.warning(
                f"center_out works best with 2+ fixtures, got {num_fixtures}. "
                "Returning base movement."
            )
            return {target: self._clone_movement(base_movement) for target in targets}

        # Calculate progress fraction (0.0 = start, 1.0 = end)
        progress = current_step / max(1, steps - 1) if steps > 1 else 1.0

        # For outside_in, reverse the progress
        if mode == "outside_in":
            progress = 1.0 - progress

        # Calculate per-fixture offsets
        result = {}
        for i, target in enumerate(targets):
            movement = self._clone_movement(base_movement)

            # Calculate position: 0.0 (left) to 1.0 (right)
            if num_fixtures == 1:
                position = 0.5
            else:
                position = i / (num_fixtures - 1)

            # Calculate max offset for this fixture (outer fixtures get larger offsets)
            # Using the n4 variant as reference: [-70, -25, 25, 70]
            # The pattern is: outer fixtures at ±max, inner fixtures scaled proportionally
            max_offset = (position - 0.5) * max_pan_spread_deg * 2

            # Scale by progress
            pan_offset = max_offset * progress

            # Apply offsets
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + pan_offset
            movement["tilt_offset_deg"] = movement.get("tilt_offset_deg", 0) + tilt_offset_deg

            # Assign tilt role
            self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"center_out: mode={mode}, step={current_step}/{steps}, "
            f"spread={max_pan_spread_deg}°, progress={progress:.2f}"
        )

        return result
