"""Wall wash geometry transform."""

from __future__ import annotations

import logging
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class WallWashTransform(GeometryTransform):
    """Wall/Parallel beams geometry.

    Creates unified direction with parallel beams/wash for simple, powerful moments.
    All fixtures point in the same direction with optional small spacing offsets
    to avoid looking 'stuck' while staying unified.

    Based on geometry_library.json wall_wash definition (lines 332-398).

    Example:
        4 fixtures with 'tight' spacing (no variation):
        MH1: pan_offset=0°
        MH2: pan_offset=0°
        MH3: pan_offset=0°
        MH4: pan_offset=0°

        4 fixtures with 'medium' spacing (small variation):
        MH1: pan_offset=-3°
        MH2: pan_offset=-1°
        MH3: pan_offset=+1°
        MH4: pan_offset=+3°

        4 fixtures with 'wide' spacing (more variation):
        MH1: pan_offset=-8°
        MH2: pan_offset=-3°
        MH3: pan_offset=+3°
        MH4: pan_offset=+8°
    """

    geometry_type = "wall_wash"

    # Spacing presets from geometry library (n4 variant)
    SPACING_PRESETS: dict[str, list[float]] = {
        "tight": [0.0, 0.0, 0.0, 0.0],
        "medium": [-3.0, -1.0, 1.0, 3.0],
        "wide": [-8.0, -3.0, 3.0, 8.0],
    }

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply wall wash geometry with parallel beams and optional spacing.

        Args:
            targets: List of fixture names (left-to-right order)
            base_movement: Base movement specification
            params: Optional parameters:
                - pan_spread_deg: Total spread (for backward compat, maps to base_pan_offset_deg)
                - base_pan_offset_deg: Direction of wall relative to center (default: 0°)
                - spacing: 'tight', 'medium', or 'wide' (default: 'tight')
                - tilt (or tilt_role): Tilt role for all fixtures (above_horizon/up/zero)

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}

        # Support both pan_spread_deg (for templates) and base_pan_offset_deg (library spec)
        base_pan_offset_deg = float(params.get("base_pan_offset_deg", 0))
        if "pan_spread_deg" in params and params.get("pan_spread_deg") == 0:
            # If pan_spread_deg is explicitly 0, use it as the base offset
            base_pan_offset_deg = 0

        spacing = params.get("spacing", "tight")

        # Phase 0: Tilt role support (especially important for wall_wash)
        tilt_role = self._get_tilt_role_from_params(params)
        if spacing not in self.SPACING_PRESETS:
            logger.warning(
                f"Unknown spacing '{spacing}', using 'tight'. Valid: {list(self.SPACING_PRESETS.keys())}"
            )
            spacing = "tight"

        num_fixtures = len(targets)
        spacing_deltas = self.SPACING_PRESETS[spacing]

        # If we have fewer or more fixtures than the preset (n4=4), scale/interpolate
        if num_fixtures != len(spacing_deltas):
            spacing_deltas = self._scale_spacing(spacing_deltas, num_fixtures)

        result = {}
        for i, target in enumerate(targets):
            movement = self._clone_movement(base_movement)

            # Calculate final pan offset: base direction + spacing variation
            pan_offset = base_pan_offset_deg + spacing_deltas[i]

            # Add offset to movement
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + pan_offset

            # Phase 0: Assign tilt role if specified
            if tilt_role:
                self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"Applied wall_wash: {num_fixtures} fixtures, "
            f"base_offset={base_pan_offset_deg}°, spacing={spacing}, tilt_role={tilt_role}"
        )
        return result

    def _scale_spacing(self, preset_deltas: list[float], num_fixtures: int) -> list[float]:
        """Scale spacing deltas for different fixture counts.

        Args:
            preset_deltas: Original spacing deltas (for n=4)
            num_fixtures: Actual number of fixtures

        Returns:
            Scaled spacing deltas
        """
        if num_fixtures == 1:
            return [0.0]

        # For 2-3 fixtures, use subset of preset
        if num_fixtures < len(preset_deltas):
            # Take center subset (skip outermost values)
            start = (len(preset_deltas) - num_fixtures) // 2
            return preset_deltas[start : start + num_fixtures]

        # For more than 4 fixtures, interpolate
        # This maintains the min/max range but distributes evenly
        if num_fixtures > len(preset_deltas):
            min_delta = min(preset_deltas)
            max_delta = max(preset_deltas)

            scaled = []
            for i in range(num_fixtures):
                if num_fixtures == 1:
                    position = 0.5
                else:
                    position = i / (num_fixtures - 1)
                # Interpolate from min to max
                delta = min_delta + (max_delta - min_delta) * position
                scaled.append(delta)
            return scaled

        return preset_deltas
