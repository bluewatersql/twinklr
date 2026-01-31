"""Agent specification for Lyrics agent."""

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.spec import AgentMode, AgentSpec


def get_lyrics_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.5,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get agent specification for Lyrics agent.

    Args:
        model: LLM model to use (default: gpt-5.2)
        temperature: LLM temperature (default: 0.5, higher than AudioProfile for creative interpretation)
        token_budget: Optional token limit for this agent

    Returns:
        AgentSpec for Lyrics agent
    """
    return AgentSpec(
        name="lyrics",
        prompt_pack="lyrics",
        response_model=LyricContextModel,
        mode=AgentMode.ONESHOT,
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=2,
        token_budget=token_budget,
        default_variables={},
    )
