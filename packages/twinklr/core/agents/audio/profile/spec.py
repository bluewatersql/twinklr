"""AudioProfile agent specification."""

from __future__ import annotations

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.config.models import AgentConfig, AgentOrchestrationConfig


def get_audio_profile_spec(
    config: AgentConfig | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get AudioProfile agent specification.

    The AudioProfile agent is a oneshot, fact-based analyzer that transforms
    raw audio analysis into a canonical song intent profile. It uses moderate
    temperature (0.4) to balance factual accuracy with creative interpretation.

    Args:
        config: Per-role model, sampling, and reasoning configuration.
        model: Optional compatibility override for ``config.model``.
        temperature: Optional compatibility override for ``config.temperature``.
        reasoning_effort: Optional compatibility override for ``config.reasoning_effort``.
        token_budget: Optional token budget for this agent

    Returns:
        AudioProfile agent specification
    """
    resolved = config or AgentOrchestrationConfig().profile_agent
    if model is not None or temperature is not None or reasoning_effort is not None:
        resolved = resolved.model_copy(
            update={
                "model": model if model is not None else resolved.model,
                "temperature": temperature if temperature is not None else resolved.temperature,
                "reasoning_effort": (
                    reasoning_effort if reasoning_effort is not None else resolved.reasoning_effort
                ),
            }
        )
    return AgentSpec(
        name="audio_profile",
        prompt_pack="audio_profile",
        response_model=AudioProfileModel,
        mode=AgentMode.ONESHOT,  # No iteration, no judge
        model=resolved.model,
        temperature=resolved.temperature,
        reasoning_effort=resolved.reasoning_effort,
        max_tokens=resolved.max_tokens,
        timeout_seconds=resolved.timeout_seconds,
        max_schema_repair_attempts=1,
        token_budget=token_budget,
    )
