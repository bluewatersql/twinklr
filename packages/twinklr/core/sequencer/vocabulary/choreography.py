"""Choreographic grouping vocabulary — tags and splits for display coordination.

Provides closed enums for choreographic grouping:

- **ChoreoTag**: Zone membership tags (which logical area a group belongs to).
  Used for zone-level targeting (e.g., "apply to all HOUSE groups").
- **SplitDimension**: Partition values for cross-group and within-group
  splitting.  Used for split-level targeting (e.g., "left half", "odd models").
- **TargetType**: Discriminator for typed plan targets (group, zone, split).

Using enums (not free-form strings) enables deterministic bidirectional
resolution between the choreography model and xLights mapping.
"""

from enum import Enum


class ChoreoTag(str, Enum):
    """Zone membership tags for choreographic grouping.

    Tags describe which logical zone of the display a group belongs to.
    Used for zone-level targeting (e.g., "apply to all HOUSE groups").

    A group may belong to multiple zones (e.g., roofline icicles
    are both HOUSE and ROOF).

    Attributes:
        HOUSE: Structure-mounted elements (rooflines, windows, eaves).
        YARD: Ground-level elements (arches, trees, candy canes).
        ROOF: Roof-mounted elements (roofline, ridge, peak star).
        PERIMETER: Boundary/edge elements (fence lines, driveway borders).
    """

    HOUSE = "HOUSE"
    YARD = "YARD"
    ROOF = "ROOF"
    PERIMETER = "PERIMETER"


class SplitDimension(str, Enum):
    """Partition values for display group splitting.

    Each value names one side/slice of a partition.  Groups declare
    which split values they belong to via ``ChoreoGroup.split_membership``.

    The composition engine resolves split targets to concrete group IDs
    at render time using this membership data.

    **Cross-group partitions** (spatial halves/thirds):

    Attributes:
        HALVES_LEFT: Left half of the display or group.
        HALVES_RIGHT: Right half of the display or group.
        THIRDS_LEFT: Left third of the display.
        THIRDS_CENTER: Center third of the display.
        THIRDS_RIGHT: Right third of the display.

    **Within-group partitions** (model-level alternation):

    Attributes:
        ODD: Odd-numbered models within a group (1, 3, 5, ...).
        EVEN: Even-numbered models within a group (2, 4, 6, ...).
    """

    # Spatial halves (cross-group)
    HALVES_LEFT = "HALVES_LEFT"
    HALVES_RIGHT = "HALVES_RIGHT"

    # Spatial thirds (cross-group)
    THIRDS_LEFT = "THIRDS_LEFT"
    THIRDS_CENTER = "THIRDS_CENTER"
    THIRDS_RIGHT = "THIRDS_RIGHT"

    # Model-level alternation (within-group)
    ODD = "ODD"
    EVEN = "EVEN"


class TargetType(str, Enum):
    """Type discriminator for choreography plan targets.

    Used in :class:`PlanTarget` to unambiguously specify whether a
    target refers to an individual group, a display zone, or a
    split partition.

    Attributes:
        GROUP: A single concrete ChoreoGroup by id.
        ZONE: All groups in a display zone (via ChoreoTag value).
        SPLIT: A partition slice (via SplitDimension value).
    """

    GROUP = "group"
    ZONE = "zone"
    SPLIT = "split"


__all__ = [
    "ChoreoTag",
    "SplitDimension",
    "TargetType",
]
