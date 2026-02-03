"""Agent specifications for moving heads choreography.

V2 Framework: Uses shared JudgeVerdict model for judge evaluation.
"""

from __future__ import annotations

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.shared.judge.models import JudgeVerdict
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
        name="mh_planner",
        prompt_pack="agents/sequencer/moving_heads/prompts/planner",
        response_model=ChoreographyPlan,
        mode=AgentMode.CONVERSATIONAL,  # Maintains context across iterations
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=3,  # More attempts for complex plans
        token_budget=token_budget,
    )


def get_judge_spec(
    model: str = "gpt-5-mini",
    temperature: float = 0.3,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get judge agent specification.

    The judge is stateless, evaluating plans for technical correctness
    and creative quality, providing constructive feedback for refinement.

    Uses JudgeVerdict (V2 shared model) for consistent evaluation
    across all agents.

    Args:
        model: LLM model to use (default: gpt-5-mini for fast evaluation)
        temperature: Sampling temperature (default: 0.3 for consistent judgment)
        token_budget: Optional token budget

    Returns:
        Judge agent spec
    """
    return AgentSpec(
        name="mh_judge",
        prompt_pack="agents/sequencer/moving_heads/prompts/judge",
        response_model=JudgeVerdict,
        mode=AgentMode.ONESHOT,  # Stateless evaluation
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=3,  # Increased for enum validation
        token_budget=token_budget,
    )
