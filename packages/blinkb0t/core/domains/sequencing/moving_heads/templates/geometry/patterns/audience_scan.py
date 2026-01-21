"""Audience scan geometry transform."""

from __future__ import annotations

import logging
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class AudienceScanTransform(GeometryTransform):
    """Audience scan / crowd spread geometry.

    Spreads fixtures across audience width for inclusive, communal
    moments. Uses preset coverage widths (narrow, medium, wide, full).

    From geometry_library.json: "audience_scan"

    Example:
        4 fixtures with coverage="wide":
        MH1: pan_offset=-60°
        MH2: pan_offset=-20°
        MH3: pan_offset=+20°
        MH4: pan_offset=+60°
    """

    geometry_type = "audience_scan"

    # Coverage presets from geometry_library.json (n=4)
    COVERAGE_PRESETS = {
        "narrow": [-25, -8, 8, 25],
        "medium": [-40, -15, 15, 40],
        "wide": [-60, -20, 20, 60],
        "full": [-80, -30, 30, 80],
    }

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply audience scan geometry with preset coverage widths.

        Args:
            targets: List of fixture names (left-to-right order)
            base_movement: Base movement specification
            params: Optional parameters:
                - coverage_width: "narrow", "medium", "wide", or "full" (default: "wide")
                - tilt (or tilt_role): Tilt role for fixtures (above_horizon/up/zero)

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}
        coverage_width = params.get("coverage_width", "wide")

        # Phase 0: Tilt role support (use helper for consistency)
        tilt_role = self._get_tilt_role_from_params(params)

        num_fixtures = len(targets)
        if num_fixtures < 3:
            logger.warning(
                f"audience_scan works best with 3+ fixtures, got {num_fixtures}. "
                f"Returning base movement."
            )
            return {target: self._clone_movement(base_movement) for target in targets}

        # Get coverage preset or default to "wide"
        if coverage_width not in self.COVERAGE_PRESETS:
            logger.warning(
                f"Unknown coverage_width '{coverage_width}', using 'wide'. "
                f"Available: {list(self.COVERAGE_PRESETS.keys())}"
            )
            coverage_width = "wide"

        # Get offsets for n=4 fixture preset
        preset_offsets = self.COVERAGE_PRESETS[coverage_width]

        # Scale/interpolate for different fixture counts
        result = {}
        for i, target in enumerate(targets):
            movement = self._clone_movement(base_movement)

            # Interpolate from preset (designed for n=4)
            if num_fixtures == 4:
                # Exact match
                pan_offset: float = float(preset_offsets[i])
            else:
                # Interpolate: map fixture position to preset positions
                # Position in range [0, num_fixtures-1] → [0, 3]
                preset_position = (i / max(1, num_fixtures - 1)) * 3

                # Linear interpolation between preset values
                preset_idx = int(preset_position)
                if preset_idx >= 3:
                    pan_offset = float(preset_offsets[3])
                else:
                    frac = preset_position - preset_idx
                    pan_offset = (
                        float(preset_offsets[preset_idx]) * (1 - frac)
                        + float(preset_offsets[preset_idx + 1]) * frac
                    )

            # Add pan offset
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + pan_offset

            # Phase 0: Assign tilt role (now properly integrated with sequencer)
            if tilt_role:
                self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"Applied audience_scan: {num_fixtures} fixtures, "
            f"coverage={coverage_width}, tilt={tilt_role}"
        )
        return result
