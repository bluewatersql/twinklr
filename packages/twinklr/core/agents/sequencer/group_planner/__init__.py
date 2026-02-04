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
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateCatalogEntry,
)
from twinklr.core.sequencer.templates.group.models import (
    AssetRequest,
    CoordinationConfig,
    CoordinationMode,
    CoordinationPlan,
    Deviation,
    DisplayGraph,
    DisplayGroup,
    GPBlendMode,
    GPTimingDriver,
    GroupPlacement,
    GroupPlanSet,
    GroupPosition,
    LaneKind,
    LanePlan,
    PlacementWindow,
    SectionCoordinationPlan,
    SnapRule,
    SpatialIntent,
    SpillPolicy,
    StepUnit,
    TimeRef,
    TimeRefKind,
)

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
    "TemplateCatalogEntry",
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
