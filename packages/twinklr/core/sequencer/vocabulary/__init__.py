"""Sequencer vocabulary - controlled enums for the choreography system.

Single source of truth for all enums used across planning, templates,
and agents.
"""

from twinklr.core.sequencer.vocabulary.composition import (
    BlendMode,
    GPBlendMode,
    LaneKind,
    LayerRole,
)
from twinklr.core.sequencer.vocabulary.coordination import (
    CoordinationMode,
    SnapRule,
    SpatialIntent,
    SpillPolicy,
    StepUnit,
)
from twinklr.core.sequencer.vocabulary.duration import (
    DURATION_BEATS,
    EffectDuration,
    resolve_duration_beats,
)
from twinklr.core.sequencer.vocabulary.energy import (
    ChoreographyStyle,
    EnergyTarget,
    MotionDensity,
)
from twinklr.core.sequencer.vocabulary.intensity import (
    INTENSITY_MAP,
    IntensityLevel,
    resolve_intensity,
)
from twinklr.core.sequencer.vocabulary.motion import (
    MotionVerb,
)
from twinklr.core.sequencer.vocabulary.planning import (
    PlanningTimeRef,
    TimingHint,
)
from twinklr.core.sequencer.vocabulary.targets import (
    TargetRole,
)
from twinklr.core.sequencer.vocabulary.templates import (
    AssetSlotType,
    AssetTemplateType,
    BackgroundMode,
    GroupTemplateType,
    MatrixAspect,
    TemplateProjectionHint,
)
from twinklr.core.sequencer.vocabulary.timing import (
    GPTimingDriver,
    QuantizeMode,
    SnapMode,
    TimeRefKind,
    TimingDriver,
)
from twinklr.core.sequencer.vocabulary.visual import (
    ColorMode,
    GroupVisualIntent,
    ProjectionIntent,
    VisualDepth,
    WarpHint,
)

__all__ = [
    # Composition
    "BlendMode",
    "GPBlendMode",
    "LaneKind",
    "LayerRole",
    # Coordination
    "CoordinationMode",
    "SnapRule",
    "SpatialIntent",
    "SpillPolicy",
    "StepUnit",
    # Duration (categorical planning)
    "DURATION_BEATS",
    "EffectDuration",
    "resolve_duration_beats",
    # Energy
    "ChoreographyStyle",
    "EnergyTarget",
    "MotionDensity",
    # Intensity (categorical planning)
    "INTENSITY_MAP",
    "IntensityLevel",
    "resolve_intensity",
    # Motion
    "MotionVerb",
    # Planning (categorical timing)
    "PlanningTimeRef",
    "TimingHint",
    # Targets
    "TargetRole",
    # Templates
    "AssetSlotType",
    "AssetTemplateType",
    "BackgroundMode",
    "GroupTemplateType",
    "MatrixAspect",
    "TemplateProjectionHint",
    # Timing
    "GPTimingDriver",
    "QuantizeMode",
    "SnapMode",
    "TimeRefKind",
    "TimingDriver",
    # Visual
    "ColorMode",
    "GroupVisualIntent",
    "ProjectionIntent",
    "VisualDepth",
    "WarpHint",
]
