"""Agent specifications for moving heads choreography.

V2 Framework: Uses shared JudgeVerdict model for judge evaluation.
"""

from __future__ import annotations

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.config.models import AgentConfig, AgentOrchestrationConfig


def get_planner_spec(
    config: AgentConfig | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get planner agent specification.

    The planner is conversational and creative, generating choreography
    plans that match the music's structure and energy.

    Args:
        config: Per-role model, sampling, and reasoning configuration.
        token_budget: Optional token budget

    Returns:
        Planner agent spec
    """
    resolved = _resolve_config(
        config or AgentOrchestrationConfig().plan_agent, model, temperature, reasoning_effort
    )
    return AgentSpec(
        name="mh_planner",
        prompt_pack="agents/sequencer/moving_heads/prompts/planner",
        response_model=ChoreographyPlan,
        mode=AgentMode.CONVERSATIONAL,  # Maintains context across iterations
        model=resolved.model,
        temperature=resolved.temperature,
        reasoning_effort=resolved.reasoning_effort,
        max_tokens=resolved.max_tokens,
        timeout_seconds=resolved.timeout_seconds,
        max_schema_repair_attempts=3,  # More attempts for complex plans
        token_budget=token_budget,
    )


def get_judge_spec(
    config: AgentConfig | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get judge agent specification.

    The judge is stateless, evaluating plans for technical correctness
    and creative quality, providing constructive feedback for refinement.

    Uses JudgeVerdict (V2 shared model) for consistent evaluation
    across all agents.

    Args:
        config: Per-role model, sampling, and reasoning configuration.
        token_budget: Optional token budget

    Returns:
        Judge agent spec
    """
    resolved = _resolve_config(
        config or AgentOrchestrationConfig().judge_agent, model, temperature, reasoning_effort
    )
    return AgentSpec(
        name="mh_judge",
        prompt_pack="agents/sequencer/moving_heads/prompts/judge",
        response_model=JudgeVerdict,
        mode=AgentMode.ONESHOT,  # Stateless evaluation
        model=resolved.model,
        temperature=resolved.temperature,
        reasoning_effort=resolved.reasoning_effort,
        max_tokens=resolved.max_tokens,
        timeout_seconds=resolved.timeout_seconds,
        max_schema_repair_attempts=3,  # Increased for enum validation
        token_budget=token_budget,
    )


def _resolve_config(
    config: AgentConfig,
    model: str | None,
    temperature: float | None,
    reasoning_effort: str | None,
) -> AgentConfig:
    """Resolve an explicit role config while retaining public override compatibility."""
    resolved = config
    if model is None and temperature is None and reasoning_effort is None:
        return resolved
    return resolved.model_copy(
        update={
            "model": model if model is not None else resolved.model,
            "temperature": temperature if temperature is not None else resolved.temperature,
            "reasoning_effort": (
                reasoning_effort if reasoning_effort is not None else resolved.reasoning_effort
            ),
        }
    )
