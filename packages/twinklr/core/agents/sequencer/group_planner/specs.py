"""Agent specifications for GroupPlanner section-level coordination.

Defines specs for:
- GroupPlanner: Generates SectionCoordinationPlan for each section
- SectionJudge: Evaluates section plans for quality and coherence
"""

from __future__ import annotations

from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict
from twinklr.core.config.models import AgentConfig, AgentOrchestrationConfig
from twinklr.core.sequencer.planning import SectionCoordinationPlan


def get_planner_spec(
    config: AgentConfig | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get GroupPlanner agent specification.

    The GroupPlanner is conversational and creative, generating section-level
    coordination plans that define how display groups work together
    for Christmas light shows.

    Args:
        config: Per-role model, sampling, and reasoning configuration.
        token_budget: Optional token budget

    Returns:
        GroupPlanner agent spec
    """
    resolved = _resolve_config(
        config or AgentOrchestrationConfig().plan_agent, model, temperature, reasoning_effort
    )
    return AgentSpec(
        name="group_planner",
        prompt_pack="sequencer/group_planner/prompts/planner",
        response_model=SectionCoordinationPlan,
        mode=AgentMode.CONVERSATIONAL,  # Maintains context for refinement
        model=resolved.model,
        temperature=resolved.temperature,
        reasoning_effort=resolved.reasoning_effort,
        max_tokens=resolved.max_tokens,
        timeout_seconds=resolved.timeout_seconds,
        max_schema_repair_attempts=3,
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},
    )


def get_section_judge_spec(
    config: AgentConfig | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get SectionJudge agent specification.

    The SectionJudge is stateless and analytical, evaluating section plans for:
    - Template appropriateness for section intent
    - Coordination mode coherence
    - Timing validity within section bounds
    - Group coverage completeness

    Uses the configured judge model because section-level evaluation is focused.

    Args:
        config: Per-role model, sampling, and reasoning configuration.
        token_budget: Optional token budget

    Returns:
        SectionJudge agent spec
    """
    resolved = _resolve_config(
        config or AgentOrchestrationConfig().judge_agent, model, temperature, reasoning_effort
    )
    return AgentSpec(
        name="section_judge",
        prompt_pack="sequencer/group_planner/prompts/section_judge",
        response_model=JudgeVerdict,
        mode=AgentMode.ONESHOT,  # Stateless per-section evaluation
        model=resolved.model,
        temperature=resolved.temperature,
        reasoning_effort=resolved.reasoning_effort,
        max_tokens=resolved.max_tokens,
        timeout_seconds=resolved.timeout_seconds,
        max_schema_repair_attempts=5,  # Increased for enum validation
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},
    )


def get_holistic_corrector_spec(
    config: AgentConfig | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get HolisticCorrector agent specification.

    The HolisticCorrector applies structured targeted actions from holistic
    evaluation to correct cross-section quality issues.  It returns only the
    modified sections (CorrectionResult) rather than the entire GroupPlanSet,
    keeping both input and output within feasible token budgets.

    Args:
        config: Per-role model, sampling, and reasoning configuration.
        token_budget: Optional token budget

    Returns:
        HolisticCorrector agent spec
    """
    from twinklr.core.sequencer.planning import CorrectionResult

    resolved = _resolve_config(
        config or AgentOrchestrationConfig().refinement_agent,
        model,
        temperature,
        reasoning_effort,
    )
    return AgentSpec(
        name="holistic_corrector",
        prompt_pack="sequencer/group_planner/prompts/holistic_corrector",
        response_model=CorrectionResult,
        mode=AgentMode.ONESHOT,
        model=resolved.model,
        temperature=resolved.temperature,
        reasoning_effort=resolved.reasoning_effort,
        max_tokens=resolved.max_tokens,
        timeout_seconds=resolved.timeout_seconds,
        max_schema_repair_attempts=3,
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},
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
GROUP_PLANNER_SPEC = get_planner_spec()
SECTION_JUDGE_SPEC = get_section_judge_spec()
HOLISTIC_CORRECTOR_SPEC = get_holistic_corrector_spec()
