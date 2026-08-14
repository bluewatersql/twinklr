"""Agent specifications for MacroPlanner choreography."""

from __future__ import annotations

from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict, get_theming_ids
from twinklr.core.config.models import AgentConfig, AgentOrchestrationConfig
from twinklr.core.sequencer.planning import MacroPlan


def get_planner_spec(
    config: AgentConfig | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get MacroPlanner agent specification.

    The MacroPlanner is conversational and strategic, generating high-level
    choreography plans focusing on global story, section energy, and layering
    architecture for Christmas light shows.

    Args:
        config: Per-role model, sampling, and reasoning configuration.
        token_budget: Optional token budget

    Returns:
        MacroPlanner agent spec
    """
    resolved = _resolve_config(
        config or AgentOrchestrationConfig().plan_agent, model, temperature, reasoning_effort
    )
    return AgentSpec(
        name="macro_planner",
        prompt_pack="sequencer/macro_planner/prompts/planner",
        response_model=MacroPlan,
        mode=AgentMode.CONVERSATIONAL,  # Maintains context across iterations
        model=resolved.model,
        temperature=resolved.temperature,
        reasoning_effort=resolved.reasoning_effort,
        max_tokens=resolved.max_tokens,
        timeout_seconds=resolved.timeout_seconds,
        max_schema_repair_attempts=1,
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},  # Auto-inject taxonomy
    )


def get_judge_spec(
    config: AgentConfig | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get MacroPlanner judge agent specification.

    The judge is stateless and analytical, evaluating MacroPlans for
    strategic coherence, section appropriateness, layer architecture clarity,
    and bold impactful design suitable for Christmas light shows.

    Args:
        config: Per-role model, sampling, and reasoning configuration.
        token_budget: Optional token budget

    Returns:
        MacroPlanner judge spec
    """
    resolved = _resolve_config(
        config or AgentOrchestrationConfig().judge_agent, model, temperature, reasoning_effort
    )
    return AgentSpec(
        name="macro_judge",
        prompt_pack="sequencer/macro_planner/prompts/judge",
        response_model=JudgeVerdict,
        mode=AgentMode.ONESHOT,  # Stateless evaluation
        model=resolved.model,
        temperature=resolved.temperature,
        reasoning_effort=resolved.reasoning_effort,
        max_tokens=resolved.max_tokens,
        timeout_seconds=resolved.timeout_seconds,
        max_schema_repair_attempts=1,
        token_budget=token_budget,
        default_variables={
            "taxonomy": get_taxonomy_dict(),
            "theming_ids": get_theming_ids(),  # For theme/tag/palette validation
        },
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


# Convenience constants for default specs
MACRO_PLANNER_SPEC = get_planner_spec()
MACRO_JUDGE_SPEC = get_judge_spec()
