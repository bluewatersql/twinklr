"""Wave left-right geometry handler - progressive wave pattern."""

import math
from typing import Any

from twinklr.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class WaveLRHandler:
    """Geometry handler for left-right wave progression.

    Creates wave-like progression across fixtures from left to right.
    Flowing, organic movement pattern with sinusoidal tilt variation.

    Attributes:
        handler_id: Unique identifier ("WAVE_LR").

    Example:
        >>> handler = WaveLRHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"wave_amplitude_norm": 0.2, "wave_cycles": 1.0},
        ...     calibration={},
        ... )
    """

    handler_id: str = "wave_lr"

    # Role ordering from left to right
    ROLE_ORDER = [
        "FAR_LEFT",
        "OUTER_LEFT",
        "INNER_LEFT",
        "CENTER_LEFT",
        "CENTER",
        "CENTER_RIGHT",
        "INNER_RIGHT",
        "OUTER_RIGHT",
        "FAR_RIGHT",
    ]

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve wave progression position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_start_norm: Start of wave range (normalized, default: 0.2)
                - pan_end_norm: End of wave range (normalized, default: 0.8)
                - tilt_center_norm: Center tilt position (normalized, default: 0.4)
                - wave_amplitude_norm: Wave amplitude in tilt (normalized, default: 0.2)
                - wave_cycles: Number of wave cycles across fixtures (default: 1.0)
                - phase_offset: Phase offset in degrees (default: 0.0)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with wave-progression positions.
        """
        # Get params
        pan_start = params.get("pan_start_norm", 0.2)
        pan_end = params.get("pan_end_norm", 0.8)
        tilt_center = params.get("tilt_center_norm", 0.4)
        wave_amplitude = params.get("wave_amplitude_norm", 0.2)
        wave_cycles = params.get("wave_cycles", 1.0)
        phase_offset = params.get("phase_offset", 0.0)

        # Map role to position [0, 1] left to right
        position_norm = self._role_to_position(role)

        # Calculate pan based on position (linear interpolation)
        pan_norm = pan_start + position_norm * (pan_end - pan_start)

        # Calculate tilt using sinusoidal wave
        # wave = amplitude * sin(2π * cycles * position + phase)
        wave_angle = (2.0 * math.pi * wave_cycles * position_norm) + math.radians(phase_offset)
        wave_offset = wave_amplitude * math.sin(wave_angle)
        tilt_norm = tilt_center + wave_offset

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))
        tilt_norm = max(0.0, min(1.0, tilt_norm))

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)

    def _role_to_position(self, role: str) -> float:
        """Map role to normalized position [0, 1] in left-to-right order.

        Args:
            role: Fixture role (e.g., "OUTER_LEFT", "CENTER").

        Returns:
            Normalized position [0, 1] where 0 is leftmost, 1 is rightmost.
        """
        if role in self.ROLE_ORDER:
            idx = self.ROLE_ORDER.index(role)
            return idx / (len(self.ROLE_ORDER) - 1)

        # Fallback: center position
        return 0.5
