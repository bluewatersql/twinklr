"""Agent specifications for MacroPlanner choreography."""

from __future__ import annotations

from twinklr.core.agents.sequencer.macro_planner.models import MacroPlan
from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.agents.spec import AgentMode, AgentSpec


def get_planner_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.7,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get MacroPlanner agent specification.

    The planner is conversational and strategic, generating high-level
    choreography plans that bridge musical understanding and execution.

    Args:
        model: LLM model to use (default: gpt-5.2 for strategic planning)
        temperature: Sampling temperature (default: 0.7 for creativity)
        token_budget: Optional token budget

    Returns:
        Planner agent spec
    """
    return AgentSpec(
        name="macro_planner",
        prompt_pack="sequencer/macro_planner/prompts/planner",
        response_model=MacroPlan,
        mode=AgentMode.ONESHOT,  # StandardIterationController handles feedback via prompt vars
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=3,  # More attempts for complex plans
        token_budget=token_budget,
    )


def get_judge_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.3,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get MacroPlanner judge agent specification.

    The judge is stateless but evaluative, assessing plans across four
    dimensions with a weighted rubric and providing constructive feedback.

    Args:
        model: LLM model to use (default: gpt-5.2 for nuanced evaluation)
        temperature: Sampling temperature (default: 0.3 for consistent judgment)
        token_budget: Optional token budget

    Returns:
        Judge agent spec
    """
    return AgentSpec(
        name="macro_planner_judge",
        prompt_pack="sequencer/macro_planner/prompts/judge",
        response_model=JudgeVerdict,
        mode=AgentMode.ONESHOT,  # Stateless evaluation
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=2,
        token_budget=token_budget,
    )
