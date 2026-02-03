"""Moving heads choreography agent integration.

V2 Pipeline Framework implementation for moving head choreography.
"""

from twinklr.core.agents.sequencer.moving_heads.context import (
    FixtureContext,
    MovingHeadPlanningContext,
)
from twinklr.core.agents.sequencer.moving_heads.heuristic_validator import (
    HeuristicValidationResult,
    HeuristicValidator,
    create_validator_function,
)
from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    PlanSection,
)
from twinklr.core.agents.sequencer.moving_heads.orchestrator_v2 import (
    MovingHeadPlannerOrchestrator,
    build_judge_variables,
    build_planner_variables,
)
from twinklr.core.agents.sequencer.moving_heads.rendering_stage import (
    MovingHeadRenderingStage,
)
from twinklr.core.agents.sequencer.moving_heads.specs import (
    get_judge_spec,
    get_planner_spec,
)
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage

__all__ = [
    # Context
    "MovingHeadPlanningContext",
    "FixtureContext",
    # Models
    "PlanSection",
    "ChoreographyPlan",
    # Specs
    "get_planner_spec",
    "get_judge_spec",
    # Validator
    "HeuristicValidator",
    "HeuristicValidationResult",
    "create_validator_function",
    # Orchestrator
    "MovingHeadPlannerOrchestrator",
    "build_planner_variables",
    "build_judge_variables",
    # Pipeline Stages
    "MovingHeadStage",
    "MovingHeadRenderingStage",
]
