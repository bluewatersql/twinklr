"""Chevron geometry handler - arranges fixtures in V-shape."""

from typing import Any

from blinkb0t.core.config.poses import STANDARD_POSES, PoseLibrary
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
                - pan_start_deg: Start pan position in degrees (default: -120°, WIDE_LEFT)
                - pan_end_deg: End pan position in degrees (default: 120°, WIDE_RIGHT)
                - tilt_base_deg: Base tilt position in degrees (default: 80°, CEILING)
                - tilt_inner_bias_deg: Tilt bias for inner fixtures in degrees (default: 5°)
                - tilt_outer_bias_deg: Tilt bias for outer fixtures in degrees (default: 0°)
            calibration: Fixture calibration data with 'fixture_config' for degree->DMX conversion.

        Returns:
            GeometryResult with chevron V-shape pan/tilt positions.
        """
        # Get fixture config for degree->DMX conversion
        fixture_config = calibration.get("fixture_config")
        if not fixture_config:
            raise ValueError(
                f"Missing fixture_config in calibration for {fixture_id}. "
                "Geometry handlers require FixtureConfig for degree->DMX conversion."
            )

        # Get params in degrees (using STANDARD_POSES defaults)
        pan_start_deg = params.get("pan_start_deg", STANDARD_POSES[PoseLibrary.WIDE_LEFT].pan_deg)
        pan_end_deg = params.get("pan_end_deg", STANDARD_POSES[PoseLibrary.WIDE_RIGHT].pan_deg)
        tilt_base_deg = params.get("tilt_base_deg", STANDARD_POSES[PoseLibrary.CEILING].tilt_deg)

        # Bias values are already in DMX from templates, not degrees
        tilt_inner_bias_dmx = params.get("tilt_inner_bias_dmx", 18)
        tilt_outer_bias_dmx = params.get("tilt_outer_bias_dmx", 0)

        # Convert degrees to DMX using fixture config
        pan_start_dmx = fixture_config.deg_to_pan_dmx(pan_start_deg)
        pan_end_dmx = fixture_config.deg_to_pan_dmx(pan_end_deg)
        tilt_base_dmx = fixture_config.deg_to_tilt_dmx(tilt_base_deg)

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
