"""Wall wash geometry handler - unified parallel beams."""

from typing import Any

from blinkb0t.core.sequencer.moving_heads.handlers.protocols import GeometryResult


class WallWashHandler:
    """Geometry handler for wall wash unified direction.

    All fixtures aim in the same direction creating parallel beams.
    Simple, powerful look for unified directional emphasis.

    Attributes:
        handler_id: Unique identifier ("WALL_WASH").

    Example:
        >>> handler = WallWashHandler()
        >>> result = handler.resolve(
        ...     fixture_id="fx1",
        ...     role="OUTER_LEFT",
        ...     params={"pan_direction_norm": 0.5, "tilt_direction_norm": 0.4},
        ...     calibration={},
        ... )
    """

    handler_id: str = "wall_wash"

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult:
        """Resolve wall wash position for a fixture.

        Args:
            fixture_id: Unique identifier for the fixture.
            role: Role assigned to this fixture (unused - all fixtures unified).
            params: Handler parameters:
                - pan_direction_norm: Pan direction (normalized, default: 0.5)
                - tilt_direction_norm: Tilt direction (normalized, default: 0.4)
            calibration: Fixture calibration data (unused).

        Returns:
            GeometryResult with unified pan/tilt direction for all fixtures.
        """
        # Get params - all fixtures use the same position
        pan_norm = params.get("pan_direction_norm", 0.5)
        tilt_norm = params.get("tilt_direction_norm", 0.4)

        # Clamp to valid range
        pan_norm = max(0.0, min(1.0, pan_norm))
        tilt_norm = max(0.0, min(1.0, tilt_norm))

        return GeometryResult(pan_norm=pan_norm, tilt_norm=tilt_norm)
