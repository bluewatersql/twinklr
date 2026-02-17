"""Choreographic grouping vocabulary — well-defined tags for display coordination.

Provides a closed enum of choreographic tags that describe how display groups
relate to each other spatially and what sub-group coordination patterns they
support.  Using an enum (not free-form strings) enables deterministic
bidirectional resolution between the choreography model and xLights mapping.

Two categories of tags:

- **Zone / spatial membership** (cross-group): which part of the display
  this group belongs to.  Used to coordinate groups that share a zone.
- **Pattern availability** (within-group): what sub-group splitting patterns
  are available for this group.  The mapping layer uses these to resolve
  a group into sub-sets of individual models.
"""

from enum import Enum


class ChoreoTag(str, Enum):
    """Well-defined choreographic grouping tags.

    Tags are attached to :class:`ChoreoGroup` instances to express spatial
    membership and available coordination patterns.

    **Zone / spatial membership (cross-group):**

    Attributes:
        HOUSE: Structure-mounted elements (rooflines, windows, eaves).
        YARD: Ground-level elements (arches, trees, candy canes).
        ROOF: Roof-mounted elements (roofline, ridge, peak star).
        PERIMETER: Boundary/edge elements (fence lines, driveway borders).
        LEFT_HALF: Left half of the display.
        RIGHT_HALF: Right half of the display.
        LEFT_THIRD: Left third of the display.
        CENTER_THIRD: Center third of the display.
        RIGHT_THIRD: Right third of the display.

    **Pattern availability (within-group):**

    Attributes:
        ODD_EVEN: Group supports odd/even alternation pattern.
        LEFT_RIGHT: Group supports left/right splitting.
        HORIZONTAL: Group has horizontal orientation.
        VERTICAL: Group has vertical orientation.
    """

    # Zone / spatial membership (cross-group coordination)
    HOUSE = "HOUSE"
    YARD = "YARD"
    ROOF = "ROOF"
    PERIMETER = "PERIMETER"

    # Spatial partitions (cross-group coordination)
    LEFT_HALF = "LEFT_HALF"
    RIGHT_HALF = "RIGHT_HALF"
    LEFT_THIRD = "LEFT_THIRD"
    CENTER_THIRD = "CENTER_THIRD"
    RIGHT_THIRD = "RIGHT_THIRD"

    # Sub-group pattern availability (within-group splitting)
    ODD_EVEN = "ODD_EVEN"
    LEFT_RIGHT = "LEFT_RIGHT"
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"


__all__ = [
    "ChoreoTag",
]
