"""AudioProfile agent specification."""

from __future__ import annotations

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.spec import AgentMode, AgentSpec


def get_audio_profile_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.4,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get AudioProfile agent specification.

    The AudioProfile agent is a oneshot, fact-based analyzer that transforms
    raw audio analysis into a canonical song intent profile. It uses moderate
    temperature (0.4) to balance factual accuracy with creative interpretation.

    Args:
        model: LLM model to use (default: gpt-5.2 for high-quality analysis)
        temperature: Sampling temperature (default: 0.4 for balanced output)
        token_budget: Optional token budget for this agent

    Returns:
        AudioProfile agent specification
    """
    return AgentSpec(
        name="audio_profile",
        prompt_pack="audio_profile",
        response_model=AudioProfileModel,
        mode=AgentMode.ONESHOT,  # No iteration, no judge
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=2,
        token_budget=token_budget,
    )
