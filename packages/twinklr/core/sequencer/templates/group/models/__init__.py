"""Group template models package.

Re-exports all models for backward compatibility with existing imports from
`twinklr.core.sequencer.templates.group.models`.

Models are organized into submodules by concern:
- template: Template definition models (GroupPlanTemplate, LayerRecipe, etc.)
- display: Display graph models (DisplayGraph, DisplayGroup, GroupPosition)
- coordination: Coordination and planning models (GroupPlacement, LanePlan, etc.)
- theming: Theme, tag, and palette models (ThemeDefinition, PaletteDefinition, etc.)
"""

from twinklr.core.sequencer.templates.assets.models import AssetRequest
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    Deviation,
    GroupPlacement,
    GroupPlanSet,
    LanePlan,
    PlacementWindow,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.templates.group.models.display import (
    DisplayGraph,
    DisplayGroup,
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
    # Template models
    "AssetSlot",
    "AssetSlotDefaults",
    "GroupConstraints",
    "GroupPlanTemplate",
    "LayerRecipe",
    "ProjectionParams",
    "ProjectionSpec",
    "TimingHints",
    # Display models
    "DisplayGraph",
    "DisplayGroup",
    "GroupPosition",
    # Coordination models
    "CoordinationConfig",
    "CoordinationPlan",
    "Deviation",
    "GroupPlacement",
    "GroupPlanSet",
    "LanePlan",
    "PlacementWindow",
    "SectionCoordinationPlan",
    "ThemeRef",
    "TimeRef",
    "TimeRefKind",
    # Enums (re-exported for convenience)
    "CoordinationMode",
    "GPBlendMode",
    "GPTimingDriver",
    "LaneKind",
    "SnapRule",
    "SpatialIntent",
    "SpillPolicy",
    "StepUnit",
    # Theming models
    "ColorStop",
    "PaletteDefinition",
    "TagDefinition",
    "ThemeDefinition",
    # Re-exported from assets
    "AssetRequest",
]
