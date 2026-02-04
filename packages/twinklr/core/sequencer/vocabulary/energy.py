"""Energy enums - energy and style vocabulary.

Defines energy targets, motion density, and choreography styles.
"""

from enum import Enum


class EnergyTarget(str, Enum):
    """Target energy level for a section.

    Defines the overall energy character of a section.

    Attributes:
        LOW: Subdued, ambient.
        MED: Moderate energy.
        HIGH: High energy, driving.
        BUILD: Rising energy.
        RELEASE: Falling energy.
        PEAK: Maximum energy moment.
    """

    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
    BUILD = "BUILD"
    RELEASE = "RELEASE"
    PEAK = "PEAK"


class MotionDensity(str, Enum):
    """Overall activity level in a section.

    Defines how busy/active the choreography should be.

    Attributes:
        SPARSE: Minimal activity, spacious.
        MED: Moderate activity.
        BUSY: High activity, dense choreography.
    """

    SPARSE = "SPARSE"
    MED = "MED"
    BUSY = "BUSY"


class ChoreographyStyle(str, Enum):
    """Visual approach for choreography.

    Defines the overall visual style strategy.

    Attributes:
        IMAGERY: Picture/gif-based, representational.
        ABSTRACT: Pure light patterns, non-representational.
        HYBRID: Mix of imagery and abstract.
    """

    IMAGERY = "IMAGERY"
    ABSTRACT = "ABSTRACT"
    HYBRID = "HYBRID"
