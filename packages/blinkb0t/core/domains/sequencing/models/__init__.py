"""Consolidated domain models for sequencing.

All models related to sequence generation live here for easy discovery
and to prevent circular dependencies.
"""

# Pose models
from blinkb0t.core.domains.sequencing.models.poses import (
    Pose,
    PoseConfig,
    PoseID,
)

# Template models
from blinkb0t.core.domains.sequencing.models.templates import (
    FixtureTarget,
    PatternStep,
    PatternStepTiming,
    Template,
    TransitionConfig,
)

# Timing models
from blinkb0t.core.domains.sequencing.models.timing import (
    MusicalTiming,
    QuantizeMode,
    TimingMode,
)

# Transition/Timeline models
from blinkb0t.core.domains.sequencing.models.transitions import (
    GapType,
    Timeline,
    TimelineEffect,
    TimelineGap,
)

__all__ = [
    # Templates
    "Template",
    "PatternStep",
    "PatternStepTiming",
    "TransitionConfig",
    "FixtureTarget",
    # Poses
    "Pose",
    "PoseID",
    "PoseConfig",
    # Timing
    "MusicalTiming",
    "TimingMode",
    "QuantizeMode",
    # Transitions
    "GapType",
    "TimelineGap",
    "TimelineEffect",
    "Timeline",
]
