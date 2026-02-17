"""Spatial vocabulary — categorical position enums for display groups.

Provides categorical spatial descriptions that the LLM can reason over.
Each axis has an ordering that the composition engine uses to sort groups
for spatial coordination (e.g., L2R sweeps use HorizontalZone ordering).
"""

from enum import Enum


class HorizontalZone(str, Enum):
    """Horizontal position in the display, ordered left-to-right.

    The composition engine uses ``sort_key()`` to order groups when a
    ``SpatialIntent`` like L2R or R2L is active.

    Attributes:
        FAR_LEFT: Far left edge of the display.
        LEFT: Left side.
        CENTER_LEFT: Between center and left.
        CENTER: Center of the display.
        CENTER_RIGHT: Between center and right.
        RIGHT: Right side.
        FAR_RIGHT: Far right edge of the display.
        FULL_WIDTH: Spans the entire horizontal extent.
    """

    FAR_LEFT = "FAR_LEFT"
    LEFT = "LEFT"
    CENTER_LEFT = "CENTER_LEFT"
    CENTER = "CENTER"
    CENTER_RIGHT = "CENTER_RIGHT"
    RIGHT = "RIGHT"
    FAR_RIGHT = "FAR_RIGHT"
    FULL_WIDTH = "FULL_WIDTH"

    def sort_key(self) -> int:
        """Return an integer for left-to-right ordering.

        ``FULL_WIDTH`` sorts at the center position (3) since it spans
        the entire display and has no distinct horizontal bias.

        Returns:
            Integer sort key (0 = far left, 6 = far right).
        """
        return _HORIZONTAL_SORT[self]


_HORIZONTAL_SORT: dict[HorizontalZone, int] = {
    HorizontalZone.FAR_LEFT: 0,
    HorizontalZone.LEFT: 1,
    HorizontalZone.CENTER_LEFT: 2,
    HorizontalZone.CENTER: 3,
    HorizontalZone.CENTER_RIGHT: 4,
    HorizontalZone.RIGHT: 5,
    HorizontalZone.FAR_RIGHT: 6,
    HorizontalZone.FULL_WIDTH: 3,
}


class VerticalZone(str, Enum):
    """Vertical position in the display, ordered bottom-to-top.

    Attributes:
        GROUND: Ground level.
        LOW: Low position.
        MID: Middle height.
        HIGH: High position.
        TOP: Top of the display.
        FULL_HEIGHT: Spans the entire vertical extent.
    """

    GROUND = "GROUND"
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"
    TOP = "TOP"
    FULL_HEIGHT = "FULL_HEIGHT"

    def sort_key(self) -> int:
        """Return an integer for bottom-to-top ordering.

        ``FULL_HEIGHT`` sorts at the middle position (2).

        Returns:
            Integer sort key (0 = ground, 4 = top).
        """
        return _VERTICAL_SORT[self]


_VERTICAL_SORT: dict[VerticalZone, int] = {
    VerticalZone.GROUND: 0,
    VerticalZone.LOW: 1,
    VerticalZone.MID: 2,
    VerticalZone.HIGH: 3,
    VerticalZone.TOP: 4,
    VerticalZone.FULL_HEIGHT: 2,
}


class DepthZone(str, Enum):
    """Depth position (front-to-back), ordered near-to-far.

    Relevant for 3-D layouts where elements are placed at different
    distances from the viewer.

    Attributes:
        NEAR: Closest to the viewer / street.
        MID: Middle depth.
        FAR: Farthest from the viewer (e.g., against the house).
    """

    NEAR = "NEAR"
    MID = "MID"
    FAR = "FAR"

    def sort_key(self) -> int:
        """Return an integer for near-to-far ordering.

        Returns:
            Integer sort key (0 = near, 2 = far).
        """
        return _DEPTH_SORT[self]


_DEPTH_SORT: dict[DepthZone, int] = {
    DepthZone.NEAR: 0,
    DepthZone.MID: 1,
    DepthZone.FAR: 2,
}


class DisplayZone(str, Enum):
    """Logical zone of the display.

    Groups the display into meaningful areas that the planner can
    reference for zone-level coordination and targeting.

    Attributes:
        HOUSE: Structure-mounted elements (rooflines, windows, eaves).
        ROOF: Roof-mounted elements (peak stars, ridge lines, icicles).
        YARD: Ground-level elements (arches, trees, candy canes).
        PERIMETER: Boundary/edge elements (fence lines, driveway borders).
        ACCENT: Focal / decorative elements (stars, hero props).
    """

    HOUSE = "HOUSE"
    ROOF = "ROOF"
    YARD = "YARD"
    PERIMETER = "PERIMETER"
    ACCENT = "ACCENT"


__all__ = [
    "DepthZone",
    "DisplayZone",
    "HorizontalZone",
    "VerticalZone",
]
