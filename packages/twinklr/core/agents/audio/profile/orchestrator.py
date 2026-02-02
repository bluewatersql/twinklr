"""Orchestrator for AudioProfile agent.

Provides orchestration layer for audio profile generation without iteration.
Unlike MacroPlanner/GroupPlanner, this is a single-shot agent with heuristic validation.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from pathlib import Path

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.audio.models import SongBundle

logger = logging.getLogger(__name__)


class AudioProfileOrchestrator:
    """Orchestrates AudioProfile agent execution.

    Single-shot orchestrator (no iteration) that wraps the audio profile runner
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
        temperature: float = 0.2,
        llm_logger: LLMCallLogger | None = None,
        prompt_base_path: str | Path | None = None,
        token_budget: int | None = None,
    ):
        """Initialize AudioProfile orchestrator.

        Args:
            provider: LLM provider for agent execution
            model: Model identifier (default: gpt-5.2)
            temperature: Sampling temperature (default: 0.2)
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

        logger.debug(
            f"AudioProfileOrchestrator initialized (model={model}, temperature={temperature})"
        )

    async def get_cache_key(self, song_bundle: SongBundle) -> str:
        """Generate cache key for deterministic caching.

        Cache key includes all inputs that affect audio profile output:
        - Song bundle (audio analysis results)
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

    async def run(self, song_bundle: SongBundle) -> AudioProfileModel:
        """Run AudioProfile agent to generate song intent profile.

        Single-shot execution (no iteration). Handles context shaping,
        agent execution, heuristic validation, and provenance injection.

        Args:
            song_bundle: Full SongBundle from AudioAnalyzer

        Returns:
            AudioProfileModel with complete provenance

        Raises:
            Exception: If agent execution or validation fails
        """
        from twinklr.core.agents.async_runner import AsyncAgentRunner
        from twinklr.core.agents.audio.profile.context import shape_context
        from twinklr.core.agents.audio.profile.models import Provenance
        from twinklr.core.agents.audio.profile.spec import get_audio_profile_spec
        from twinklr.core.agents.audio.profile.validation import validate_audio_profile

        try:
            # Shape context
            logger.debug("Shaping context from SongBundle")
            shaped_context = shape_context(song_bundle)

            # Get spec
            spec = get_audio_profile_spec(
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
                prompt_base_path=prompt_base,
                llm_logger=self.llm_logger,
            )

            # Run agent
            logger.debug(
                f"Running AudioProfile agent (model={self.model}, temp={self.temperature})"
            )
            result = await runner.run(
                spec=spec,
                variables={"shaped_context": shaped_context},
            )

            # Check for failure
            if not result.success:
                raise Exception(f"Agent execution failed: {result.error_message}")

            # Parse output
            logger.debug("Parsing AudioProfileModel from agent output")
            if result.data is None:
                raise Exception("Agent returned no data")

            # AsyncAgentRunner already returns the parsed model
            if isinstance(result.data, AudioProfileModel):
                profile = result.data
            else:
                profile = AudioProfileModel(**result.data)

            # Inject provenance with actual runtime values
            profile.provenance = Provenance(
                provider_id=self.provider.provider_type.value,
                model_id=self.model,
                prompt_pack="audio_profile",
                prompt_pack_version="2.0",
                framework_version="twinklr-agents-2.0",
                seed=None,
                temperature=self.temperature,
                created_at=dt.datetime.now(dt.UTC).isoformat() + "Z",
            )

            # Heuristic validation
            logger.debug("Running heuristic validation")
            validation_errors = validate_audio_profile(profile)
            if validation_errors:
                error_msg = f"Heuristic validation failed: {'; '.join(validation_errors)}"
                logger.error(error_msg)
                raise Exception(error_msg)

            logger.debug("AudioProfile orchestration complete")
            return profile

        except Exception:
            logger.exception("AudioProfile orchestration failed")
            raise
