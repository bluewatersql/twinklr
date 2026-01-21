"""Scattered / Controlled Chaos geometry transform."""

from __future__ import annotations

import logging
import random
from typing import Any

from ..base import GeometryTransform

logger = logging.getLogger(__name__)


class ScatteredChaosTransform(GeometryTransform):
    """Scattered / Controlled Chaos geometry.

    Randomized offsets within constraints for short bursts of modern disorder.
    Best for breakdown, drop, transition sections - use briefly (2-8 bars).

    From geometry_library.json:
    - Chaotic, modern, glitchy vibes
    - Random per-fixture offsets within ranges
    - Static mode: generate once
    - Dynamic mode: re-randomize every N bars

    Example (n=4, pan_range=60, tilt_range=15):
        MH1: pan=+45°, tilt=-8°
        MH2: pan=-22°, tilt=+12°
        MH3: pan=-55°, tilt=+3°
        MH4: pan=+38°, tilt=-14°
    """

    geometry_type = "scattered_chaos"

    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply scattered_chaos geometry with randomized offsets.

        Args:
            targets: List of fixture names
            base_movement: Base movement specification
            params: Optional parameters:
                - pan_range_deg: Random pan offsets in [-range, +range] (default: 60)
                - tilt_range_deg: Random tilt offsets (default: 15)
                - update_mode: "static" or "dynamic" (default: "static")
                - reseed_every_bars: Re-randomize interval for dynamic mode (default: 2)
                - seed: Random seed for determinism (default: based on target names)
                - tilt (or tilt_role): Base tilt role (default: above_horizon)

        Returns:
            Dict mapping fixture name to transformed movement spec
        """
        params = params or {}
        pan_range_deg = float(params.get("pan_range_deg", 60))
        tilt_range_deg = float(params.get("tilt_range_deg", 15))
        update_mode = params.get("update_mode", "static")
        seed = params.get("seed")

        # Tilt role support
        tilt_role = self._get_tilt_role_from_params(params)

        num_fixtures = len(targets)
        if num_fixtures < 2:
            logger.warning(
                f"scattered_chaos works best with 2+ fixtures, got {num_fixtures}. "
                "Returning base movement."
            )
            return {target: self._clone_movement(base_movement) for target in targets}

        # Create deterministic random seed if not provided
        if seed is None:
            # Use fixture names for deterministic but unique-per-group seed
            seed = hash("".join(sorted(targets))) % 10000

        rng = random.Random(seed)

        # Generate random offsets per fixture
        result = {}
        for target in targets:
            movement = self._clone_movement(base_movement)

            # Generate random offsets within ranges
            pan_offset = rng.uniform(-pan_range_deg, pan_range_deg)
            tilt_offset = rng.uniform(-tilt_range_deg, tilt_range_deg)

            # Apply offsets
            movement["pan_offset_deg"] = movement.get("pan_offset_deg", 0) + pan_offset
            movement["tilt_offset_deg"] = movement.get("tilt_offset_deg", 0) + tilt_offset

            # Assign tilt role
            self._assign_tilt_role(movement, tilt_role)

            result[target] = movement

        logger.debug(
            f"scattered_chaos: pan_range=±{pan_range_deg}°, tilt_range=±{tilt_range_deg}°, "
            f"mode={update_mode}, seed={seed}, fixtures={num_fixtures}"
        )

        return result
