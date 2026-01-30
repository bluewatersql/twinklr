"""AudioProfile agent runner - facade for AsyncAgentRunner."""

from __future__ import annotations

import logging
from pathlib import Path

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.audio.profile.context import shape_context
from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.audio.profile.spec import get_audio_profile_spec
from twinklr.core.agents.audio.profile.validation import validate_audio_profile
from twinklr.core.agents.logging import LLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.audio.models import SongBundle

logger = logging.getLogger(__name__)


class AudioProfileRunError(Exception):
    """Raised when AudioProfile agent execution fails."""

    pass


async def run_audio_profile(
    song_bundle: SongBundle,
    provider: LLMProvider,
    llm_logger: LLMCallLogger,
    prompt_base_path: str | Path | None = None,
    model: str = "gpt-5.2",
    temperature: float = 0.2,
    token_budget: int | None = None,
) -> AudioProfileModel:
    """Run AudioProfile agent to generate song intent profile.

    This is the primary entry point for running the AudioProfile agent.
    It handles:
    1. Context shaping (SongBundle → shaped context)
    2. Agent execution (AsyncAgentRunner)
    3. Heuristic validation (fail-fast)
    4. Model instantiation

    Args:
        song_bundle: Full SongBundle from AudioAnalyzer
        provider: LLM provider (OpenAI)
        llm_logger: LLM call logger for Phase 0 logging
        prompt_base_path: Base path for prompt packs (defaults to audio_profile prompts)
        model: LLM model to use (default: gpt-5.2)
        temperature: Sampling temperature (default: 0.2)
        token_budget: Optional token budget

    Returns:
        AudioProfileModel instance

    Raises:
        AudioProfileRunError: If agent execution or validation fails
    """
    try:
        # Shape context
        logger.debug("Shaping context from SongBundle")
        shaped_context = shape_context(song_bundle)

        # Get spec
        spec = get_audio_profile_spec(
            model=model,
            temperature=temperature,
            token_budget=token_budget,
        )

        # Determine prompt base path
        if prompt_base_path is None:
            # Default to prompts directory (parent of audio_profile pack)
            prompt_base_path = Path(__file__).parent / "prompts"

        # Create runner
        runner = AsyncAgentRunner(
            provider=provider,
            prompt_base_path=prompt_base_path,
            llm_logger=llm_logger,
        )

        # Run agent
        logger.info(f"Running AudioProfile agent (model={model}, temp={temperature})")
        result = await runner.run(
            spec=spec,
            variables={"shaped_context": shaped_context},
        )

        # Check for failure
        if not result.success:
            raise AudioProfileRunError(f"Agent execution failed: {result.error_message}")

        # Parse output
        logger.debug("Parsing AudioProfileModel from agent output")
        if result.data is None:
            raise AudioProfileRunError("Agent returned no data")

        # AsyncAgentRunner already returns the parsed model, not a dict
        if isinstance(result.data, AudioProfileModel):
            profile = result.data
        else:
            # Fallback if it's a dict (shouldn't happen with current implementation)
            profile = AudioProfileModel(**result.data)

        # Heuristic validation
        logger.debug("Running heuristic validation")
        validation_errors = validate_audio_profile(profile)
        if validation_errors:
            error_msg = f"Heuristic validation failed: {'; '.join(validation_errors)}"
            logger.error(error_msg)
            raise AudioProfileRunError(error_msg)

        logger.info("AudioProfile agent completed successfully")
        return profile

    except Exception as e:
        if isinstance(e, AudioProfileRunError):
            raise
        logger.exception("Unexpected error in AudioProfile agent")
        raise AudioProfileRunError(f"Unexpected error: {e}") from e
