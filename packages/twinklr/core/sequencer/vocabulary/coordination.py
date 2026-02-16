"""Coordination enums - cross-group choreography vocabulary.

Defines coordination modes, spatial intents, and timing rules
for cross-group choreography.
"""

from enum import Enum


class CoordinationMode(str, Enum):
    """Coordination mode for cross-group choreography.

    Defines how multiple groups work together.

    Attributes:
        UNIFIED: Same behavior across groups simultaneously.
        COMPLEMENTARY: Different behaviors, designed to harmonize.
        SEQUENCED: Ordered progression across groups.
        CALL_RESPONSE: Alternating sets (A responds to B).
        RIPPLE: Propagation across ordered set with overlap.
    """

    UNIFIED = "UNIFIED"
    COMPLEMENTARY = "COMPLEMENTARY"
    SEQUENCED = "SEQUENCED"
    CALL_RESPONSE = "CALL_RESPONSE"
    RIPPLE = "RIPPLE"


class StepUnit(str, Enum):
    """Step unit for sequenced coordination.

    Defines the time unit for sequential steps.

    Attributes:
        BEAT: Single beat steps.
        BAR: Full bar steps.
        PHRASE: Musical phrase steps.
    """

    BEAT = "BEAT"
    BAR = "BAR"
    PHRASE = "PHRASE"


class SpillPolicy(str, Enum):
    """Policy for handling placements that spill outside section bounds.

    Attributes:
        TRUNCATE: Clip to section end.
        DROP: Omit if extends past section.
        WRAP: Wrap to next occurrence (if applicable).
    """

    TRUNCATE = "TRUNCATE"
    DROP = "DROP"
    WRAP = "WRAP"


class SnapRule(str, Enum):
    """Snap rule for time alignment.

    Defines how placements snap to musical boundaries.

    Attributes:
        BAR: Snap to bar boundaries.
        BEAT: Snap to beat boundaries.
        PHRASE: Snap to phrase boundaries.
        NONE: No snapping.
    """

    BAR = "BAR"
    BEAT = "BEAT"
    PHRASE = "PHRASE"
    NONE = "NONE"


class SpatialIntent(str, Enum):
    """Spatial direction intent for coordination.

    Defines the spatial pattern for cross-group effects.

    Attributes:
        NONE: No spatial pattern.
        L2R: Left to right (horizontal).
        R2L: Right to left (horizontal).
        C2O: Center to outer (horizontal).
        O2C: Outer to center (horizontal).
        B2T: Bottom to top (vertical).
        T2B: Top to bottom (vertical).
        F2B: Front to back (depth).
        B2F: Back to front (depth).
        RANDOM: Random order.
    """

    NONE = "NONE"
    L2R = "L2R"
    R2L = "R2L"
    C2O = "C2O"
    O2C = "O2C"
    B2T = "B2T"
    T2B = "T2B"
    F2B = "F2B"
    B2F = "B2F"
    RANDOM = "RANDOM"
