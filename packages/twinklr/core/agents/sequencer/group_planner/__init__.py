"""GroupPlanner agent for section-level cross-group coordination.

GroupPlanner transforms MacroPlan section intent into coordinated
choreography plans across display groups.
"""

from twinklr.core.agents.sequencer.group_planner.context import (
    MacroSectionPlanningInput,
    SectionPlanningContext,
    project_macro_section,
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
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    GroupPlacement,
    PlacementWindow,
)
from twinklr.core.sequencer.templates.group.models.position import GroupPosition
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
    # Specs
    "GROUP_PLANNER_SPEC",
    "HOLISTIC_JUDGE_SPEC",
    "SECTION_JUDGE_SPEC",
    # Models - Plans
    "AssetRequest",
    # Timing
    "BarInfo",
    # Models - Display / Choreography
    "ChoreoGroup",
    "ChoreographyGraph",
    # Models - Placements
    "CoordinationConfig",
    # Models - Enums
    "CoordinationMode",
    "CoordinationPlan",
    # Holistic Evaluation
    "CrossSectionIssue",
    "Deviation",
    "GPBlendMode",
    "GPTimingDriver",
    "GroupPlacement",
    # Pipeline Stages
    "GroupPlanAggregatorStage",
    "GroupPlanSet",
    # Orchestrator
    "GroupPlannerOrchestrator",
    "GroupPlannerStage",
    "GroupPosition",
    "HolisticEvaluation",
    "HolisticEvaluator",
    "HolisticEvaluatorStage",
    "LaneKind",
    "LanePlan",
    # Context
    "MacroSectionPlanningInput",
    "PlacementWindow",
    "SectionBounds",
    "SectionCoordinationPlan",
    # Validators
    "SectionPlanValidator",
    "SectionPlanningContext",
    "SnapRule",
    "SpatialIntent",
    "SpillPolicy",
    "StepUnit",
    # Models - Templates
    "TemplateCatalog",
    "TemplateInfo",
    # Models - TimeRef
    "TimeRef",
    "TimeRefKind",
    "TimingContext",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    "get_holistic_judge_spec",
    "get_planner_spec",
    "get_section_judge_spec",
    "project_macro_section",
]
