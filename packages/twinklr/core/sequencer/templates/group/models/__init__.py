"""Group template models package.

Re-exports all models for backward compatibility with existing imports from
`twinklr.core.sequencer.templates.group.models`.

Models are organized into submodules by concern:
- template: Template definition models (GroupPlanTemplate, LayerRecipe, etc.)
- display: Display graph models (DisplayGraph, DisplayGroup, GroupPosition)
- coordination: Coordination models (GroupPlacement, CoordinationPlan, etc.)

Planning output models (SectionCoordinationPlan, GroupPlanSet, etc.) should be
imported from `twinklr.core.sequencer.planning`.
"""

from twinklr.core.sequencer.templates.assets.models import AssetRequest
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    GroupPlacement,
    PlacementWindow,
    PlanTarget,
)
from twinklr.core.sequencer.templates.group.models.display import (
    DisplayGraph,
    DisplayGroup,
    ElementType,
    GroupPosition,
)
from twinklr.core.sequencer.templates.group.models.template import (
    AssetSlot,
    AssetSlotDefaults,
    GroupConstraints,
    GroupPlanTemplate,
    LayerRecipe,
    ProjectionParams,
    ProjectionSpec,
    TimingHints,
)
from twinklr.core.sequencer.theming import (
    ColorStop,
    PaletteDefinition,
    TagDefinition,
    ThemeDefinition,
    ThemeRef,
)
from twinklr.core.sequencer.timing import TimeRef
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    GPBlendMode,
    GPTimingDriver,
    LaneKind,
    SnapRule,
    SpatialIntent,
    SpillPolicy,
    StepUnit,
)
from twinklr.core.sequencer.vocabulary.timing import TimeRefKind

__all__ = [
    # Re-exported from assets
    "AssetRequest",
    # Template models
    "AssetSlot",
    "AssetSlotDefaults",
    # Choreography models
    "ChoreoGroup",
    "ChoreographyGraph",
    # Theming models
    "ColorStop",
    # Coordination models
    "CoordinationConfig",
    # Enums (re-exported for convenience)
    "CoordinationMode",
    "CoordinationPlan",
    # Display models (legacy — being replaced by ChoreographyGraph)
    "DisplayGraph",
    "DisplayGroup",
    "ElementType",
    "GPBlendMode",
    "GPTimingDriver",
    "GroupConstraints",
    "GroupPlacement",
    "GroupPlanTemplate",
    "GroupPosition",
    "LaneKind",
    "LayerRecipe",
    "PaletteDefinition",
    "PlacementWindow",
    "PlanTarget",
    "ProjectionParams",
    "ProjectionSpec",
    "SnapRule",
    "SpatialIntent",
    "SpillPolicy",
    "StepUnit",
    "TagDefinition",
    "ThemeDefinition",
    "ThemeRef",
    "TimeRef",
    "TimeRefKind",
    "TimingHints",
]
