"""Orchestrator for Lyrics agent.

Provides orchestration layer for lyrics analysis without iteration.
Single-shot agent with heuristic validation.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from pathlib import Path

from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.audio.models import SongBundle

logger = logging.getLogger(__name__)


class LyricsOrchestrator:
    """Orchestrates Lyrics agent execution.

    Single-shot orchestrator (no iteration) that wraps the lyrics runner
    to provide consistent interface with other orchestrators.

    Attributes:
        provider: LLM provider
        model: Model identifier
        temperature: Sampling temperature
        llm_logger: LLM call logger
        prompt_base_path: Optional prompt pack base path
        token_budget: Optional token budget
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        model: str = "gpt-5.2",
        temperature: float = 0.5,
        llm_logger: LLMCallLogger | None = None,
        prompt_base_path: str | Path | None = None,
        token_budget: int | None = None,
    ):
        """Initialize Lyrics orchestrator.

        Args:
            provider: LLM provider for agent execution
            model: Model identifier (default: gpt-5.2)
            temperature: Sampling temperature (default: 0.5, higher than AudioProfile)
            llm_logger: Optional LLM call logger (uses NullLLMCallLogger if None)
            prompt_base_path: Optional prompt pack base path
            token_budget: Optional token budget limit
        """
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.llm_logger = llm_logger or NullLLMCallLogger()
        self.prompt_base_path = prompt_base_path
        self.token_budget = token_budget

        logger.debug(f"LyricsOrchestrator initialized (model={model}, temperature={temperature})")

    async def get_cache_key(self, song_bundle: SongBundle) -> str:
        """Generate cache key for deterministic caching.

        Cache key includes all inputs that affect lyrics analysis output:
        - Song bundle (with lyrics text)
        - Model configuration
        - Temperature setting

        Args:
            song_bundle: Full SongBundle from AudioAnalyzer

        Returns:
            SHA256 hash of canonical inputs
        """
        key_data = {
            "song_bundle": song_bundle.model_dump(),
            "model": self.model,
            "temperature": self.temperature,
        }

        # Canonical JSON encoding for stable hashing
        canonical = json.dumps(
            key_data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def run(self, song_bundle: SongBundle) -> LyricContextModel:
        """Run Lyrics agent to generate narrative and thematic context.

        Single-shot execution (no iteration). Handles context shaping,
        agent execution, heuristic validation, and provenance injection.

        Args:
            song_bundle: Full SongBundle from AudioAnalyzer

        Returns:
            LyricContextModel with complete provenance

        Raises:
            Exception: If agent execution or validation fails
            ValueError: If lyrics not available in SongBundle
        """
        from twinklr.core.agents.async_runner import AgentResult, AsyncAgentRunner
        from twinklr.core.agents.audio.lyrics.context import shape_lyrics_context
        from twinklr.core.agents.audio.lyrics.models import Provenance
        from twinklr.core.agents.audio.lyrics.spec import get_lyrics_spec
        from twinklr.core.agents.audio.lyrics.validation import validate_lyrics

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
                model=self.model,
                temperature=self.temperature,
                token_budget=self.token_budget,
            )

            # Determine prompt base path
            prompt_base = self.prompt_base_path
            if prompt_base is None:
                prompt_base = Path(__file__).parent / "prompts"

            # Create runner
            runner = AsyncAgentRunner(
                provider=self.provider,
                llm_logger=self.llm_logger,
                prompt_base_path=prompt_base,
            )

            # Run agent
            logger.debug(
                f"Running Lyrics agent with model={self.model}, temperature={self.temperature}"
            )
            result: AgentResult = await runner.run(
                spec=spec,
                variables=shaped_context,
            )

            # Extract model from result
            if not result.success or result.data is None:
                raise Exception(
                    f"Lyrics agent failed: {result.error_message or 'No data returned'}"
                )

            # Parse result
            if isinstance(result.data, LyricContextModel):
                lyric_context = result.data
            else:
                lyric_context = LyricContextModel(**result.data)

            # Inject provenance
            lyric_context.provenance = Provenance(
                provider_id=self.provider.provider_type.value,
                model_id=self.model,
                prompt_pack="lyrics",
                prompt_pack_version="1.0",
                framework_version="twinklr-agents-2.0",
                seed=None,
                temperature=self.temperature,
                created_at=dt.datetime.now(dt.UTC).isoformat() + "Z",
            )

            # Heuristic validation
            logger.debug("Running heuristic validation")
            validation_errors = validate_lyrics(lyric_context, song_bundle)
            if validation_errors:
                error_strs = [
                    f"{issue.severity.value}: {issue.message}" for issue in validation_errors
                ]
                logger.warning(f"Validation warnings: {'; '.join(error_strs)}")

            logger.debug("Lyrics orchestration complete")
            return lyric_context

        except Exception:
            logger.exception("Lyrics orchestration failed")
            raise
