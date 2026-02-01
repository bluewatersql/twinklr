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
        """Generate audio profile.

        Args:
            input: SongBundle from audio analysis
            context: Pipeline context with provider and config

        Returns:
            StageResult containing AudioProfileModel

        Side Effects:
            - Adds "audio_profile_tokens" to context.metrics
        """
        from twinklr.core.agents.audio.profile import run_audio_profile
        from twinklr.core.pipeline.result import failure_result, success_result

        try:
            logger.info("Generating audio profile")

            # Run audio profile agent
            profile = await run_audio_profile(
                song_bundle=input,
                provider=context.provider,
                llm_logger=context.llm_logger,
                model=context.job_config.agent.plan_agent.model,
                temperature=0.3,
            )

            logger.info(
                f"Audio profile complete: {profile.energy_profile.macro_energy}, "
                f"recommended layers: {profile.creative_guidance.recommended_layer_count}"
            )

            # Store in state for downstream stages (GroupPlannerStage)
            context.set_state("audio_profile", profile)

            return success_result(profile, stage_name=self.name)

        except Exception as e:
            logger.exception("Audio profile generation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)
