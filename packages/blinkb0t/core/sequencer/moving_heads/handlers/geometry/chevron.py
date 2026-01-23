"""Chevron geometry handler - arranges fixtures in V-shape."""

from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class ChevronVHandler:
    """Geometry handler for chevron V-shape formation.

    Arranges fixtures in a V-shaped pattern.
    Left side goes left/down, right side goes right/down.
    Uses fixture roles to determine position within the formation.

    Attributes:
        handler_id: Unique identifier ("CHEVRON_V").

    Example:
        >>> handler = ChevronVHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"pan_start_dmx": 96, "pan_end_dmx": 176},
        ...     calibration={},
        ... )
    """

    handler_id: str = "chevron_v"

    # Left side roles (ordered outward)
    LEFT_ROLES = ["FAR_LEFT", "OUTER_LEFT", "INNER_LEFT", "CENTER_LEFT"]
    # Right side roles (ordered outward)
    RIGHT_ROLES = ["CENTER_RIGHT", "INNER_RIGHT", "OUTER_RIGHT", "FAR_RIGHT"]

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve chevron position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_start_dmx: Start pan position in DMX (default: 96)
                - pan_end_dmx: End pan position in DMX (default: 176)
                - tilt_base_dmx: Base tilt position in DMX (default: 128)
                - tilt_inner_bias_dmx: Tilt offset for inner fixtures (default: 18)
                - tilt_outer_bias_dmx: Tilt offset for outer fixtures (default: 0)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with chevron V-shape pan/tilt positions.
        """
        # Get params (convert DMX to normalized [0, 1])
        pan_start_dmx = params.get("pan_start_dmx", 96)
        pan_end_dmx = params.get("pan_end_dmx", 176)
        tilt_base_dmx = params.get("tilt_base_dmx", 128)
        tilt_inner_bias_dmx = params.get("tilt_inner_bias_dmx", 18)
        tilt_outer_bias_dmx = params.get("tilt_outer_bias_dmx", 0)

        # Convert DMX to normalized
        pan_start = pan_start_dmx / 255.0
        pan_end = pan_end_dmx / 255.0
        tilt_base = tilt_base_dmx / 255.0
        tilt_inner_bias = tilt_inner_bias_dmx / 255.0
        tilt_outer_bias = tilt_outer_bias_dmx / 255.0

        # Determine side and position
        if role in self.LEFT_ROLES:
            # Left side: position from center to left
            idx = self.LEFT_ROLES.index(role)
            position_norm = idx / (len(self.LEFT_ROLES) - 1) if len(self.LEFT_ROLES) > 1 else 0.0
            # Pan: interpolate from center to left (start)
            pan_norm = pan_start + position_norm * (0.5 * (pan_end - pan_start))
            # Tilt: bias based on position (inner higher, outer lower)
            tilt_bias = tilt_inner_bias if "INNER" in role or "CENTER" in role else tilt_outer_bias
            tilt_norm = tilt_base + tilt_bias
        elif role in self.RIGHT_ROLES:
            # Right side: position from center to right
            idx = self.RIGHT_ROLES.index(role)
            position_norm = idx / (len(self.RIGHT_ROLES) - 1) if len(self.RIGHT_ROLES) > 1 else 0.0
            # Pan: interpolate from center to right (end)
            pan_norm = 0.5 * (pan_start + pan_end) + position_norm * (0.5 * (pan_end - pan_start))
            # Tilt: bias based on position (inner higher, outer lower)
            tilt_bias = tilt_inner_bias if "INNER" in role or "CENTER" in role else tilt_outer_bias
            tilt_norm = tilt_base + tilt_bias
        elif role == "CENTER":
            # Center fixture gets mid-point
            pan_norm = (pan_start + pan_end) / 2.0
            tilt_norm = tilt_base + tilt_inner_bias
        else:
            # Unknown role: default to center
            pan_norm = (pan_start + pan_end) / 2.0
            tilt_norm = tilt_base

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))
        tilt_norm = max(0.0, min(1.0, tilt_norm))

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)
