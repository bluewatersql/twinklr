"""Scattered chaos geometry handler - randomized positions."""

import hashlib
from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class ScatteredChaosHandler:
    """Geometry handler for scattered/randomized positions.

    Applies controlled randomization to create scattered, chaotic patterns.
    Uses fixture_id and seed for deterministic pseudo-random positions.

    Attributes:
        handler_id: Unique identifier ("SCATTERED_CHAOS").

    Example:
        >>> handler = ScatteredChaosHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"seed": 5, "pan_center_dmx": 128, "pan_spread_dmx": 36},
        ...     calibration={},
        ... )
    """

    handler_id: str = "scattered_chaos"

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve scattered position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture.
            params: Handler parameters:
                - seed: Random seed for reproducibility (default: 0)
                - pan_center_dmx: Center pan position in DMX (default: 128)
                - pan_spread_dmx: Pan spread range in DMX (default: 36)
                - tilt_center_dmx: Center tilt position in DMX (default: 128)
                - tilt_spread_dmx: Tilt spread range in DMX (default: 18)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with randomized pan/tilt positions.
        """
        # Get params
        seed = params.get("seed", 0)
        pan_center_dmx = params.get("pan_center_dmx", 128)
        pan_spread_dmx = params.get("pan_spread_dmx", 36)
        tilt_center_dmx = params.get("tilt_center_dmx", 128)
        tilt_spread_dmx = params.get("tilt_spread_dmx", 18)

        # Convert DMX to normalized
        pan_center = pan_center_dmx / 255.0
        pan_spread = pan_spread_dmx / 255.0
        tilt_center = tilt_center_dmx / 255.0
        tilt_spread = tilt_spread_dmx / 255.0

        # Generate deterministic random offset based on fixture_id and seed
        # Use separate hashes for pan and tilt for independent randomization
        pan_hash_input = f"{fixture_id}_pan_{seed}"
        tilt_hash_input = f"{fixture_id}_tilt_{seed}"

        pan_hash = int(hashlib.md5(pan_hash_input.encode()).hexdigest(), 16)
        tilt_hash = int(hashlib.md5(tilt_hash_input.encode()).hexdigest(), 16)

        # Convert hash to offset in range [-spread/2, +spread/2]
        pan_offset = ((pan_hash % 1000) / 1000.0 - 0.5) * pan_spread
        tilt_offset = ((tilt_hash % 1000) / 1000.0 - 0.5) * tilt_spread

        # Apply offset to center
        pan_norm = pan_center + pan_offset
        tilt_norm = tilt_center + tilt_offset

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))
        tilt_norm = max(0.0, min(1.0, tilt_norm))

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)
