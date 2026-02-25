"""Agent specifications for GroupPlanner section-level coordination.

Defines specs for:
- GroupPlanner: Generates SectionCoordinationPlan for each section
- SectionJudge: Evaluates section plans for quality and coherence
"""

from __future__ import annotations

from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict
from twinklr.core.sequencer.planning import SectionCoordinationPlan


def get_planner_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.7,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get GroupPlanner agent specification.

    The GroupPlanner is conversational and creative, generating section-level
    coordination plans that define how display groups work together
    for Christmas light shows.

    Args:
        model: LLM model to use (default: gpt-5.2 for creative coordination)
        temperature: Sampling temperature (default: 0.7 for balanced creativity)
        token_budget: Optional token budget

    Returns:
        GroupPlanner agent spec
    """
    return AgentSpec(
        name="group_planner",
        prompt_pack="sequencer/group_planner/prompts/planner",
        response_model=SectionCoordinationPlan,
        mode=AgentMode.CONVERSATIONAL,  # Maintains context for refinement
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=3,
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},
    )


def get_section_judge_spec(
    model: str = "gpt-5-mini",
    temperature: float = 0.3,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get SectionJudge agent specification.

    The SectionJudge is stateless and analytical, evaluating section plans for:
    - Template appropriateness for section intent
    - Coordination mode coherence
    - Timing validity within section bounds
    - Group coverage completeness

    Uses lighter model (gpt-5-mini) since section-level evaluation is focused.

    Args:
        model: LLM model to use (default: gpt-5-mini for fast evaluation)
        temperature: Sampling temperature (default: 0.3 for consistent judgment)
        token_budget: Optional token budget

    Returns:
        SectionJudge agent spec
    """
    return AgentSpec(
        name="section_judge",
        prompt_pack="sequencer/group_planner/prompts/section_judge",
        response_model=JudgeVerdict,
        mode=AgentMode.ONESHOT,  # Stateless per-section evaluation
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=5,  # Increased for enum validation
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},
    )


def get_holistic_corrector_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.3,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get HolisticCorrector agent specification.

    The HolisticCorrector applies structured targeted actions from holistic
    evaluation to correct cross-section quality issues.  It returns only the
    modified sections (CorrectionResult) rather than the entire GroupPlanSet,
    keeping both input and output within feasible token budgets.

    Args:
        model: LLM model to use (default: gpt-5.2 for complex plan modification)
        temperature: Sampling temperature (default: 0.3 for precise corrections)
        token_budget: Optional token budget

    Returns:
        HolisticCorrector agent spec
    """
    from twinklr.core.sequencer.planning import CorrectionResult

    return AgentSpec(
        name="holistic_corrector",
        prompt_pack="sequencer/group_planner/prompts/holistic_corrector",
        response_model=CorrectionResult,
        mode=AgentMode.ONESHOT,
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=3,
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},
    )


# Convenience constants for default specs
GROUP_PLANNER_SPEC = get_planner_spec()
SECTION_JUDGE_SPEC = get_section_judge_spec()
HOLISTIC_CORRECTOR_SPEC = get_holistic_corrector_spec()
