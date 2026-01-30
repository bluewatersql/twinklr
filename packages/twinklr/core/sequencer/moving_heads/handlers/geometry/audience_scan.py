"""Audience scan geometry handlers - spreads fixtures across audience."""

from typing import Any

from twinklr.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class AudienceScanHandler:
    """Geometry handler for symmetric audience scan.

    Evenly distributes fixtures across audience width.
    Uses fixture roles to determine position in the spread.

    Attributes:
        handler_id: Unique identifier ("AUDIENCE_SCAN").
    """

    handler_id: str = "audience_scan"

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
        """Resolve audience scan position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_start_norm: Start of scan range (normalized, default: 0.1)
                - pan_end_norm: End of scan range (normalized, default: 0.9)
                - tilt_norm: Audience-facing tilt (normalized, default: 0.3)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with audience-spread pan/tilt positions.
        """
        # Get ranges from params
        pan_start = params.get("pan_start_norm", 0.1)
        pan_end = params.get("pan_end_norm", 0.9)
        tilt_norm = params.get("tilt_norm", 0.3)

        # Map role to position in scan
        position_norm = self._role_to_position(role)

        # Spread across audience width
        pan_norm = pan_start + position_norm * (pan_end - pan_start)

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

        # Fallback: center for unknown roles
        return 0.5


class AudienceScanAsymHandler:
    """Geometry handler for asymmetric audience scan.

    Creates an asymmetric audience scan by biasing positions to one side.
    Uses fixture roles to determine base position, then applies bias.

    Attributes:
        handler_id: Unique identifier ("AUDIENCE_SCAN_ASYM").
    """

    handler_id: str = "audience_scan_asym"

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
        """Resolve asymmetric audience scan position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (e.g., "OUTER_LEFT").
            params: Handler parameters:
                - pan_start_norm: Start of scan range (normalized, default: 0.1)
                - pan_end_norm: End of scan range (normalized, default: 0.9)
                - bias: Pan bias direction ("left" or "right", default: "left")
                - bias_amount: How much to bias [0, 1] (default: 0.3)
                - tilt_norm: Audience-facing tilt (normalized, default: 0.3)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with asymmetrically-spread pan/tilt positions.
        """
        # Get params
        pan_start = params.get("pan_start_norm", 0.1)
        pan_end = params.get("pan_end_norm", 0.9)
        bias = params.get("bias", "left")
        bias_amount = params.get("bias_amount", 0.3)
        tilt_norm = params.get("tilt_norm", 0.3)

        # Map role to base position
        position_norm = self._role_to_position(role)

        # Calculate base pan spread
        base_pan = pan_start + position_norm * (pan_end - pan_start)

        # Apply asymmetric bias
        if bias == "left":
            # Compress range toward left
            pan_norm = pan_start + (base_pan - pan_start) * (1.0 - bias_amount)
        else:
            # Compress range toward right
            pan_norm = base_pan * (1.0 - bias_amount) + pan_end * bias_amount

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))

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

        # Fallback: center for unknown roles
        return 0.5
