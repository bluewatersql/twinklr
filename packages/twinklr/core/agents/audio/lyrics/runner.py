"""Lyrics agent runner - facade for AsyncAgentRunner."""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

from twinklr.core.agents.async_runner import AgentResult, AsyncAgentRunner
from twinklr.core.agents.audio.lyrics.context import shape_lyrics_context
from twinklr.core.agents.audio.lyrics.models import LyricContextModel, Provenance
from twinklr.core.agents.audio.lyrics.spec import get_lyrics_spec
from twinklr.core.agents.audio.lyrics.validation import validate_lyrics
from twinklr.core.agents.logging import LLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.audio.models import SongBundle

logger = logging.getLogger(__name__)


class LyricsRunError(Exception):
    """Raised when Lyrics agent execution fails."""

    pass


async def run_lyrics_async(
    song_bundle: SongBundle,
    provider: LLMProvider,
    llm_logger: LLMCallLogger,
    prompt_base_path: str | Path | None = None,
    model: str = "gpt-5.2",
    temperature: float = 0.5,
    token_budget: int | None = None,
) -> LyricContextModel:
    """Run Lyrics agent to generate lyric narrative and thematic context.

    This is the primary async entry point for running the Lyrics agent.
    It handles:
    1. Context shaping (SongBundle → shaped context)
    2. Agent execution (AsyncAgentRunner)
    3. Heuristic validation (fail-fast)
    4. Model instantiation
    5. Provenance injection (with correct runtime values)

    Args:
        song_bundle: Full SongBundle from AudioAnalyzer
        provider: LLM provider (OpenAI)
        llm_logger: LLM call logger for Phase 0 logging
        prompt_base_path: Base path for prompt packs (defaults to lyrics prompts)
        model: LLM model to use (default: gpt-5.2)
        temperature: Sampling temperature (default: 0.5, higher than AudioProfile)
        token_budget: Optional token budget

    Returns:
        LyricContextModel instance with injected provenance

    Raises:
        LyricsRunError: If agent execution or validation fails
        ValueError: If lyrics not available in SongBundle
    """
    try:
        # Validate lyrics available
        if song_bundle.lyrics is None or song_bundle.lyrics.text is None:
            raise ValueError("Lyrics not available in SongBundle")

        # Shape context
        logger.debug("Shaping context from SongBundle")
        shaped_context = shape_lyrics_context(song_bundle)

        if not shaped_context.get("has_lyrics"):
            raise ValueError("No lyrics available for analysis")

        # Get spec
        spec = get_lyrics_spec(
            model=model,
            temperature=temperature,
            token_budget=token_budget,
        )

        # Determine prompt base path
        if prompt_base_path is None:
            # Default to prompts directory (parent of lyrics pack)
            prompt_base_path = Path(__file__).parent / "prompts"

        # Create runner
        runner = AsyncAgentRunner(
            provider=provider,
            llm_logger=llm_logger,
            prompt_base_path=prompt_base_path,
        )

        # Run agent
        logger.debug(f"Running Lyrics agent with model={model}, temperature={temperature}")
        result: AgentResult = await runner.run(
            spec=spec,
            variables=shaped_context,
        )

        # Extract model from result
        if not result.success:
            raise LyricsRunError(f"Agent execution failed: {result.error_message}")

        lyric_context: LyricContextModel = result.data  # type: ignore[assignment]

        # Validate output
        logger.debug("Validating Lyrics agent output")
        validation_issues = validate_lyrics(lyric_context, song_bundle)
        if validation_issues:
            logger.warning(f"Lyrics validation found {len(validation_issues)} issue(s)")
            # Attach warnings to model
            lyric_context.warnings.extend(validation_issues)

        # Inject provenance with ACTUAL runtime values
        lyric_context.provenance = Provenance(
            provider_id=provider.provider_type.value,
            model_id=model,
            prompt_pack="lyrics",
            prompt_pack_version="2.0",
            framework_version="twinklr-agents-2.0",
            seed=None,
            temperature=temperature,
            created_at=dt.datetime.now(dt.UTC).isoformat(),
        )

        logger.debug("Lyrics agent completed successfully")
        return lyric_context

    except ValueError as e:
        # Validation or input errors
        logger.error(f"Lyrics agent validation error: {e}")
        raise

    except Exception as e:
        # Unexpected errors
        logger.error(f"Lyrics agent execution failed: {e}", exc_info=True)
        raise LyricsRunError(f"Lyrics agent failed: {e}") from e


def run_lyrics(
    song_bundle: SongBundle,
    provider: LLMProvider,
    llm_logger: LLMCallLogger,
    prompt_base_path: str | Path | None = None,
    model: str = "gpt-5.2",
    temperature: float = 0.5,
    token_budget: int | None = None,
) -> LyricContextModel:
    """Run Lyrics agent (sync wrapper).

    Synchronous wrapper around run_lyrics_async for compatibility.

    Args:
        song_bundle: Full SongBundle from AudioAnalyzer
        provider: LLM provider (OpenAI)
        llm_logger: LLM call logger for Phase 0 logging
        prompt_base_path: Base path for prompt packs (defaults to lyrics prompts)
        model: LLM model to use (default: gpt-5.2)
        temperature: Sampling temperature (default: 0.5)
        token_budget: Optional token budget

    Returns:
        LyricContextModel instance with injected provenance

    Raises:
        LyricsRunError: If agent execution or validation fails
        ValueError: If lyrics not available in SongBundle
    """
    import asyncio

    return asyncio.run(
        run_lyrics_async(
            song_bundle=song_bundle,
            provider=provider,
            llm_logger=llm_logger,
            prompt_base_path=prompt_base_path,
            model=model,
            temperature=temperature,
            token_budget=token_budget,
        )
    )
