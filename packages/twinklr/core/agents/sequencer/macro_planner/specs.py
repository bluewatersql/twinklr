"""Agent specifications for MacroPlanner choreography."""

from __future__ import annotations

from twinklr.core.agents.sequencer.macro_planner.models import MacroPlan
from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict


def get_planner_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.7,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get MacroPlanner agent specification.

    The MacroPlanner is conversational and strategic, generating high-level
    choreography plans focusing on global story, section energy, and layering
    architecture for Christmas light shows.

    Args:
        model: LLM model to use (default: gpt-5.2 for strategic creative work)
        temperature: Sampling temperature (default: 0.7 for balanced creativity)
        token_budget: Optional token budget

    Returns:
        MacroPlanner agent spec
    """
    return AgentSpec(
        name="macro_planner",
        prompt_pack="sequencer/macro_planner/prompts/planner",
        response_model=MacroPlan,
        mode=AgentMode.CONVERSATIONAL,  # Maintains context across iterations
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=3,  # More attempts for complex plans
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},  # Auto-inject taxonomy
    )


def get_judge_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.3,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get MacroPlanner judge agent specification.

    The judge is stateless and analytical, evaluating MacroPlans for
    strategic coherence, section appropriateness, layer architecture clarity,
    and bold impactful design suitable for Christmas light shows.

    Args:
        model: LLM model to use (default: gpt-5.2 for nuanced evaluation)
        temperature: Sampling temperature (default: 0.3 for consistent judgment)
        token_budget: Optional token budget

    Returns:
        MacroPlanner judge spec
    """
    return AgentSpec(
        name="macro_judge",
        prompt_pack="sequencer/macro_planner/prompts/judge",
        response_model=JudgeVerdict,
        mode=AgentMode.ONESHOT,  # Stateless evaluation
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=5,  # Increased for enum validation issues
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},  # Auto-inject taxonomy
    )


# Convenience constants for default specs
MACRO_PLANNER_SPEC = get_planner_spec()
MACRO_JUDGE_SPEC = get_judge_spec()
