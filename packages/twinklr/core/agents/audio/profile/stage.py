"""Audio profile pipeline stage.

Wraps audio profile agent for pipeline execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from twinklr.core.agents.audio.profile.models import AudioProfileModel
    from twinklr.core.audio.models import SongBundle
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult

logger = logging.getLogger(__name__)


class AudioProfileStage:
    """Pipeline stage for audio profile generation.

    Generates musical analysis and creative guidance using the AudioProfile agent.
    Analyzes energy, structure, and provides choreography recommendations.

    Input: SongBundle (from audio analysis)
    Output: AudioProfileModel

    Example:
        >>> stage = AudioProfileStage()
        >>> result = await stage.execute(song_bundle, context)
        >>> if result.success:
        ...     profile = result.output
        ...     print(f"Energy: {profile.energy_profile.macro_energy}")
    """

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "audio_profile"

    async def execute(
        self,
        input: SongBundle,
        context: PipelineContext,
    ) -> StageResult[AudioProfileModel]:
        """Generate audio profile with caching.

        Args:
            input: SongBundle from audio analysis
            context: Pipeline context with provider and config

        Returns:
            StageResult containing AudioProfileModel

        Side Effects:
            - Stores "audio_profile_result" in context.state (full result)
            - Stores "audio_profile" in context.state (for backward compatibility)
            - Adds "audio_profile_from_cache" to context.metrics
        """
        from twinklr.core.agents.audio.profile.models import AudioProfileModel
        from twinklr.core.agents.audio.profile.orchestrator import AudioProfileOrchestrator
        from twinklr.core.pipeline.execution import execute_step
        from twinklr.core.pipeline.result import failure_result

        try:
            model = context.job_config.agent.plan_agent.model
            temperature = 0.3

            # Create orchestrator
            orchestrator = AudioProfileOrchestrator(
                provider=context.provider,
                model=model,
                temperature=temperature,
                llm_logger=context.llm_logger,
            )

            # Use execute_step for caching and metrics
            return await execute_step(
                stage_name=self.name,
                context=context,
                compute=lambda: orchestrator.run(input),
                result_extractor=lambda r: r,  # Result is already AudioProfileModel
                result_type=AudioProfileModel,
                cache_key_fn=lambda: orchestrator.get_cache_key(input),
                cache_version="1",
                state_handler=self._handle_state,
            )

        except Exception as e:
            logger.exception("Audio profile generation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    def _handle_state(self, result: AudioProfileModel, context: PipelineContext) -> None:
        """Store audio profile in state (backward compatibility)."""
        context.set_state("audio_profile", result)
