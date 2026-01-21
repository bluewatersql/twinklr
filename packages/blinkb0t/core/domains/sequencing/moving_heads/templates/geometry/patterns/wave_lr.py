"""Wave left-right geometry transform."""

from __future__ import annotations

import logging
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class WaveLRTransform(GeometryTransform):
    """Traveling wave with progressive phase offsets.

    Creates a wave effect that travels across fixtures by applying
    progressive phase offsets. Typically used with sweep_lr or similar
    oscillating patterns.

    From geometry_library.json: "wave_lr"

    Example:
        4 fixtures create 90° phase spacing:
        MH1: phase_deg=0°
        MH2: phase_deg=90°
        MH3: phase_deg=180°
        MH4: phase_deg=270°
    """

    geometry_type = "wave_lr"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply wave geometry with progressive phase offsets.

        Args:
            targets: List of fixture names (left-to-right order)
            base_movement: Base movement specification
            params: Optional parameters:
                - phase_spacing: "auto" (360/n) or manual degrees between fixtures
                - direction: "forward" (L→R) or "reverse" (R→L)
                - tilt (or tilt_role): Tilt role for all fixtures (above_horizon/up/zero)

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}
        phase_spacing_param = params.get("phase_spacing", "auto")
        direction = params.get("direction", "forward")

        # Phase 0: Tilt role support
        tilt_role = self._get_tilt_role_from_params(params)

        num_fixtures = len(targets)
        if num_fixtures < 2:
            logger.warning(
                f"wave_lr works best with 2+ fixtures, got {num_fixtures}. Returning base movement."
            )
            return {target: self._clone_movement(base_movement) for target in targets}

        # Calculate phase spacing
        if phase_spacing_param == "auto":
            phase_spacing = 360.0 / num_fixtures
        else:
            try:
                phase_spacing = float(phase_spacing_param)
            except (TypeError, ValueError):
                logger.warning(f"Invalid phase_spacing '{phase_spacing_param}', using auto")
                phase_spacing = 360.0 / num_fixtures

        # Generate per-fixture movements with phase offsets
        result = {}
        for i, target in enumerate(targets):
            movement = self._clone_movement(base_movement)

            # Calculate phase offset for this fixture
            if direction == "reverse":
                phase_deg = (num_fixtures - 1 - i) * phase_spacing
            else:  # forward
                phase_deg = i * phase_spacing

            # Normalize to 0-360
            phase_deg = phase_deg % 360.0

            # Add phase to movement (or override existing)
            movement["phase_deg"] = phase_deg

            # Phase 0: Assign tilt role if specified
            if tilt_role:
                self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"Applied wave_lr: {num_fixtures} fixtures, "
            f"spacing={phase_spacing:.1f}°, direction={direction}, tilt_role={tilt_role}"
        )
        return result
