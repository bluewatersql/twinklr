"""Agent specification for Lyrics agent."""

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.config.models import AgentConfig, AgentOrchestrationConfig


def get_lyrics_spec(
    config: AgentConfig | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get agent specification for Lyrics agent.

    Args:
        config: Per-role model, sampling, and reasoning configuration.
        model: Optional compatibility override for ``config.model``.
        temperature: Optional compatibility override for ``config.temperature``.
        reasoning_effort: Optional compatibility override for ``config.reasoning_effort``.
        token_budget: Optional token limit for this agent

    Returns:
        AgentSpec for Lyrics agent
    """
    resolved = config or AgentOrchestrationConfig().lyrics_agent
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
        name="lyrics",
        prompt_pack="lyrics",
        response_model=LyricContextModel,
        mode=AgentMode.ONESHOT,
        model=resolved.model,
        temperature=resolved.temperature,
        reasoning_effort=resolved.reasoning_effort,
        max_tokens=resolved.max_tokens,
        timeout_seconds=resolved.timeout_seconds,
        max_schema_repair_attempts=2,
        token_budget=token_budget,
        default_variables={},
    )
