"""Tilt bias by group geometry handler - constant pan with group tilt offsets."""

from typing import Any

from twinklr.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class TiltBiasByGroupHandler:
    """Geometry handler for constant pan with per-group tilt offsets.

    Maintains constant pan position while applying different tilt offsets
    to each group. Useful for layered looks with vertical separation.

    Attributes:
        handler_id: Unique identifier ("TILT_BIAS_BY_GROUP").

    Example:
        >>> handler = TiltBiasByGroupHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"pan_center_norm": 0.5, "tilt_base_norm": 0.4},
        ...     calibration={},
        ... )
    """

    handler_id: str = "tilt_bias_by_group"

    # Group assignments for tilt bias (3 groups: inner, middle, outer)
    INNER_ROLES = ["CENTER", "CENTER_LEFT", "CENTER_RIGHT"]
    MIDDLE_ROLES = ["INNER_LEFT", "INNER_RIGHT"]
    OUTER_ROLES = ["OUTER_LEFT", "OUTER_RIGHT", "FAR_LEFT", "FAR_RIGHT"]

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve constant pan with group-based tilt for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_center_norm: Constant pan position (normalized, default: 0.5)
                - tilt_base_norm: Base tilt position (normalized, default: 0.4)
                - inner_tilt_offset_norm: Tilt offset for inner group (normalized, default: 0.15)
                - middle_tilt_offset_norm: Tilt offset for middle group (normalized, default: 0.0)
                - outer_tilt_offset_norm: Tilt offset for outer group (normalized, default: -0.15)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with constant pan and group-based tilt positions.
        """
        # Get params
        pan_center = params.get("pan_center_norm", 0.5)
        tilt_base = params.get("tilt_base_norm", 0.4)
        inner_tilt_offset = params.get("inner_tilt_offset_norm", 0.15)
        middle_tilt_offset = params.get("middle_tilt_offset_norm", 0.0)
        outer_tilt_offset = params.get("outer_tilt_offset_norm", -0.15)

        # All fixtures use constant pan
        pan_norm = pan_center

        # Apply tilt offset based on group membership
        if role in self.INNER_ROLES:
            tilt_norm = tilt_base + inner_tilt_offset
        elif role in self.MIDDLE_ROLES:
            tilt_norm = tilt_base + middle_tilt_offset
        elif role in self.OUTER_ROLES:
            tilt_norm = tilt_base + outer_tilt_offset
        else:
            # Unknown role: use base tilt
            tilt_norm = tilt_base

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))
        tilt_norm = max(0.0, min(1.0, tilt_norm))

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)
