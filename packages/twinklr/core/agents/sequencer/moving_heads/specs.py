"""Agent specifications for moving heads choreography."""

from __future__ import annotations

from twinklr.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    JudgeResponse,
)
from twinklr.core.agents.spec import AgentMode, AgentSpec


def get_planner_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.8,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get planner agent specification.

    The planner is conversational and creative, generating choreography
    plans that match the music's structure and energy.

    Args:
        model: LLM model to use (default: gpt-5.2 for creative work)
        temperature: Sampling temperature (default: 0.8 for creativity)
        token_budget: Optional token budget

    Returns:
        Planner agent spec
    """
    return AgentSpec(
        name="planner",
        prompt_pack="planner",
        response_model=ChoreographyPlan,
        mode=AgentMode.CONVERSATIONAL,  # Maintains context across iterations
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=3,  # More attempts for complex plans
        token_budget=token_budget,
    )


def get_judge_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.5,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get judge agent specification.

    The judge is stateless but creative, performing technical validation
    first, then evaluating plans for creative quality and providing
    constructive feedback.

    Args:
        model: LLM model to use (default: gpt-5.2 for nuanced evaluation)
        temperature: Sampling temperature (default: 0.5 for balanced judgment)
        token_budget: Optional token budget

    Returns:
        Judge agent spec
    """
    return AgentSpec(
        name="judge",
        prompt_pack="judge",
        response_model=JudgeResponse,
        mode=AgentMode.ONESHOT,  # Stateless evaluation
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=2,
        token_budget=token_budget,
    )
