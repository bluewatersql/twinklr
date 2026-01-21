"""Left/Right mirror geometry transform."""

from __future__ import annotations

import logging
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class MirrorLRTransform(GeometryTransform):
    """Symmetric left/right mirror around center.

    Creates clean, powerful symmetric looks by mirroring fixtures
    around a center axis. Left fixtures get negative pan offsets,
    right fixtures get positive pan offsets.

    From geometry_library.json: "mirror_lr"

    Example:
        4 fixtures with 30° spread:
        MH1 (left outer):  pan_offset=-30°
        MH2 (left inner):  pan_offset=-10°
        MH3 (right inner): pan_offset=+10°
        MH4 (right outer): pan_offset=+30°
    """

    geometry_type = "mirror_lr"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply mirror geometry with symmetric left/right pan offsets.

        Args:
            targets: List of fixture names (assumed left-to-right order)
            base_movement: Base movement specification
            params: Optional parameters:
                - pan_spread_deg: Total mirror spread (default: 30°)
                - tilt_offset_deg: Shared tilt offset (default: 0°)
                - tilt (or tilt_role): Tilt role for all fixtures (above_horizon/up/zero)
                - tilt_spread_deg: Optional vertical spread (outer fixtures higher/lower)

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}
        pan_spread_deg = float(params.get("pan_spread_deg", 30))
        tilt_offset_deg = float(params.get("tilt_offset_deg", 0))
        tilt_spread_deg = float(params.get("tilt_spread_deg", 0))

        # Phase 0: Tilt role support
        tilt_role = self._get_tilt_role_from_params(params)

        num_fixtures = len(targets)
        if num_fixtures < 2:
            logger.warning(
                f"mirror_lr requires at least 2 fixtures, got {num_fixtures}. "
                f"Returning base movement."
            )
            return {target: self._clone_movement(base_movement) for target in targets}

        # Calculate symmetric offsets
        # For n=4: [-30, -10, +10, +30] with spread=30
        result = {}
        mid = num_fixtures / 2.0

        for i, target in enumerate(targets):
            movement = self._clone_movement(base_movement)

            # Calculate offset: negative for left half, positive for right half
            # Distance from center determines magnitude
            distance_from_center = (i + 0.5) - mid
            normalized_distance = distance_from_center / mid  # -1 to +1

            # Pan offset (symmetric mirror)
            pan_offset = normalized_distance * pan_spread_deg
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + pan_offset

            # Tilt offset (shared + optional spread)
            if tilt_offset_deg != 0 or tilt_spread_deg != 0:
                # Base tilt offset
                total_tilt_offset = tilt_offset_deg
                # Add spread (outer fixtures get more offset)
                if tilt_spread_deg != 0:
                    total_tilt_offset += abs(normalized_distance) * tilt_spread_deg
                movement["tilt_offset_deg"] = movement.get("tilt_offset_deg", 0) + total_tilt_offset

            # Phase 0: Assign tilt role if specified
            if tilt_role:
                self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"Applied mirror_lr: {num_fixtures} fixtures, "
            f"pan_spread={pan_spread_deg}°, tilt_role={tilt_role}"
        )
        return result
