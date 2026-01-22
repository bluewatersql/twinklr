"""None geometry handler - returns center position."""

from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class NoneGeometryHandler:
    """Geometry handler for center position (no specific geometry).

    Returns normalized center position (0.5, 0.5) for all fixtures.

    Attributes:
        handler_id: Unique identifier ("NONE").
    """

    handler_id: str = "NONE"

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve center position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture (unused).
            role: Role assigned to this fixture (unused).
            params: Handler parameters (unused).
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with center position (0.5, 0.5).
        """
        # Return center position for both pan and tilt
        return GeometryResult(pan_norm=0.5, tilt_norm=0.5)
