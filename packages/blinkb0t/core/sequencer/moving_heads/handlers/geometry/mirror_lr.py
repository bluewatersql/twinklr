"""Left/Right mirror geometry handler - symmetric formations."""

from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class MirrorLRHandler:
    """Geometry handler for left/right mirrored symmetry.

    Creates perfect symmetry with left and right sides mirroring each other.
    Uses fixture roles to determine mirror positioning.

    Attributes:
        handler_id: Unique identifier ("MIRROR_LR").

    Example:
        >>> handler = MirrorLRHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"pan_center_norm": 0.5, "pan_spread_norm": 0.3},
        ...     calibration={},
        ... )
    """

    handler_id: str = "mirror_lr"

    # Left side roles (with mirror pairs)
    LEFT_ROLES = {
        "FAR_LEFT": 1.0,  # Furthest from center
        "OUTER_LEFT": 0.75,  # Outer position
        "INNER_LEFT": 0.5,  # Inner position
        "CENTER_LEFT": 0.25,  # Near center
    }

    # Right side roles (mirrors of left)
    RIGHT_ROLES = {
        "FAR_RIGHT": 1.0,
        "OUTER_RIGHT": 0.75,
        "INNER_RIGHT": 0.5,
        "CENTER_RIGHT": 0.25,
    }

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve mirrored position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_center_norm: Center mirror axis (normalized, default: 0.5)
                - pan_spread_norm: Distance from center to edges (normalized, default: 0.3)
                - tilt_norm: Mirrored tilt position (normalized, default: 0.4)
                - tilt_bias_norm: Optional tilt bias for left vs right (normalized, default: 0.0)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with mirrored left/right positions.
        """
        # Get params
        pan_center = params.get("pan_center_norm", 0.5)
        pan_spread = params.get("pan_spread_norm", 0.3)
        tilt_base = params.get("tilt_norm", 0.4)
        tilt_bias = params.get("tilt_bias_norm", 0.0)

        # Determine mirror position based on role
        if role in self.LEFT_ROLES:
            # Left side: subtract from center
            distance = self.LEFT_ROLES[role]
            pan_norm = pan_center - (distance * pan_spread)
            tilt_norm = tilt_base - tilt_bias  # Optional left tilt bias
        elif role in self.RIGHT_ROLES:
            # Right side: add to center (mirror of left)
            distance = self.RIGHT_ROLES[role]
            pan_norm = pan_center + (distance * pan_spread)
            tilt_norm = tilt_base + tilt_bias  # Optional right tilt bias
        elif role == "CENTER":
            # Center fixture stays centered
            pan_norm = pan_center
            tilt_norm = tilt_base
        else:
            # Unknown role: default to center
            pan_norm = pan_center
            tilt_norm = tilt_base

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))
        tilt_norm = max(0.0, min(1.0, tilt_norm))

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)
