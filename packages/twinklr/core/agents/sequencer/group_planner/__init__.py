"""GroupPlanner agent for section-level cross-group coordination.

GroupPlanner transforms MacroPlan section intent into coordinated
choreography plans across display groups.
"""

from twinklr.core.agents.sequencer.group_planner.context import (
    GroupPlanningContext,
    SectionPlanningContext,
)
from twinklr.core.agents.sequencer.group_planner.holistic import (
    HOLISTIC_JUDGE_SPEC,
    CrossSectionIssue,
    HolisticEvaluation,
    HolisticEvaluator,
    get_holistic_judge_spec,
)
from twinklr.core.agents.sequencer.group_planner.holistic_stage import (
    HolisticEvaluatorStage,
)
from twinklr.core.agents.sequencer.group_planner.orchestrator import (
    GroupPlannerOrchestrator,
)
from twinklr.core.agents.sequencer.group_planner.specs import (
    GROUP_PLANNER_SPEC,
    SECTION_JUDGE_SPEC,
    get_planner_spec,
    get_section_judge_spec,
)
from twinklr.core.agents.sequencer.group_planner.stage import (
    GroupPlanAggregatorStage,
    GroupPlannerStage,
)
from twinklr.core.agents.sequencer.group_planner.timing import (
    BarInfo,
    SectionBounds,
    TimingContext,
)
from twinklr.core.agents.sequencer.group_planner.validators import (
    SectionPlanValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from twinklr.core.sequencer.planning import (
    Deviation,
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.templates.assets.models import AssetRequest
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateInfo,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    GroupPlacement,
    PlacementWindow,
)
from twinklr.core.sequencer.templates.group.models.display import (
    DisplayGraph,
    DisplayGroup,
    GroupPosition,
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
    # Models - Enums
    "CoordinationMode",
    "GPBlendMode",
    "GPTimingDriver",
    "LaneKind",
    "SnapRule",
    "SpatialIntent",
    "SpillPolicy",
    "StepUnit",
    "TimeRefKind",
    # Models - TimeRef
    "TimeRef",
    # Models - Display
    "DisplayGraph",
    "DisplayGroup",
    "GroupPosition",
    # Models - Templates
    "TemplateCatalog",
    "TemplateInfo",
    # Models - Placements
    "CoordinationConfig",
    "CoordinationPlan",
    "GroupPlacement",
    "PlacementWindow",
    # Models - Plans
    "AssetRequest",
    "Deviation",
    "GroupPlanSet",
    "LanePlan",
    "SectionCoordinationPlan",
    # Context
    "GroupPlanningContext",
    "SectionPlanningContext",
    # Timing
    "BarInfo",
    "SectionBounds",
    "TimingContext",
    # Validators
    "SectionPlanValidator",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    # Orchestrator
    "GroupPlannerOrchestrator",
    # Specs
    "GROUP_PLANNER_SPEC",
    "SECTION_JUDGE_SPEC",
    "get_planner_spec",
    "get_section_judge_spec",
    # Pipeline Stages
    "GroupPlanAggregatorStage",
    "GroupPlannerStage",
    "HolisticEvaluatorStage",
    # Holistic Evaluation
    "CrossSectionIssue",
    "HolisticEvaluation",
    "HolisticEvaluator",
    "HOLISTIC_JUDGE_SPEC",
    "get_holistic_judge_spec",
]
