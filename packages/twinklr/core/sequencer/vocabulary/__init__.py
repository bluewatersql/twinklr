"""Sequencer vocabulary - controlled enums for the choreography system.

Single source of truth for all enums used across planning, templates,
and agents.
"""

from twinklr.core.sequencer.vocabulary.choreography import (
    ChoreoTag,
    SplitDimension,
    TargetType,
)
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
from twinklr.core.sequencer.vocabulary.display import (
    DetailCapability,
    DisplayElementKind,
    DisplayProminence,
    GroupArrangement,
    PixelDensity,
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
from twinklr.core.sequencer.vocabulary.spatial import (
    DepthZone,
    DisplayZone,
    HorizontalZone,
    VerticalZone,
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
    # Duration (categorical planning)
    "DURATION_BEATS",
    # Intensity (categorical planning)
    "INTENSITY_MAP",
    # Templates
    "AssetSlotType",
    "AssetTemplateType",
    "BackgroundMode",
    # Composition
    "BlendMode",
    # Choreographic tags & splits
    "ChoreoTag",
    # Energy
    "ChoreographyStyle",
    # Visual
    "ColorMode",
    # Coordination
    "CoordinationMode",
    # Spatial (categorical position)
    "DepthZone",
    # Display (physical metadata)
    "DetailCapability",
    "DisplayElementKind",
    "DisplayProminence",
    "DisplayZone",
    "EffectDuration",
    "EnergyTarget",
    "GPBlendMode",
    # Timing
    "GPTimingDriver",
    "GroupArrangement",
    "GroupTemplateType",
    "GroupVisualIntent",
    "HorizontalZone",
    "IntensityLevel",
    "LaneKind",
    "LayerRole",
    "MatrixAspect",
    "MotionDensity",
    # Motion
    "MotionVerb",
    "PixelDensity",
    # Planning (categorical timing)
    "PlanningTimeRef",
    "ProjectionIntent",
    "QuantizeMode",
    "SnapMode",
    "SnapRule",
    "SpatialIntent",
    "SpillPolicy",
    "SplitDimension",
    "StepUnit",
    # Targets
    "TargetRole",
    "TargetType",
    "TemplateProjectionHint",
    "TimeRefKind",
    "TimingDriver",
    "TimingHint",
    "VerticalZone",
    "VisualDepth",
    "WarpHint",
    "resolve_duration_beats",
    "resolve_intensity",
]
