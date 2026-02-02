"""Lyrics context pipeline stage.

Wraps lyrics agent for pipeline execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from twinklr.core.agents.audio.lyrics.models import LyricContextModel
    from twinklr.core.audio.models import SongBundle
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult

logger = logging.getLogger(__name__)


class LyricsStage:
    """Pipeline stage for lyrics context generation.

    Generates narrative and thematic analysis using the Lyrics agent.
    Only executes if lyrics are available in the SongBundle.

    Input: SongBundle (from audio analysis)
    Output: LyricContextModel

    Example:
        >>> stage = LyricsStage()
        >>> # Typically used with CONDITIONAL pattern
        >>> result = await stage.execute(song_bundle, context)
        >>> if result.success:
        ...     lyrics = result.output
        ...     print(f"Themes: {', '.join(lyrics.themes)}")
    """

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "lyrics"

    async def execute(
        self,
        input: SongBundle,
        context: PipelineContext,
    ) -> StageResult[LyricContextModel]:
        """Generate lyrics context with caching.

        Args:
            input: SongBundle from audio analysis
            context: Pipeline context with provider and config

        Returns:
            StageResult containing LyricContextModel

        Side Effects:
            - Stores "lyrics_result" in context.state (full result)
            - Stores "lyric_context" in context.state (for backward compatibility)
            - Adds "lyrics_from_cache" to context.metrics
        """
        from twinklr.core.agents.audio.lyrics.models import LyricContextModel
        from twinklr.core.agents.audio.lyrics.orchestrator import LyricsOrchestrator
        from twinklr.core.pipeline.execution import execute_step
        from twinklr.core.pipeline.result import failure_result

        try:
            # Check if lyrics are available
            if input.lyrics is None or input.lyrics.text is None:
                logger.warning("Lyrics stage called but no lyrics available in bundle")
                return failure_result(
                    "No lyrics available in audio bundle",
                    stage_name=self.name,
                )

            model = context.job_config.agent.plan_agent.model
            temperature = 0.5

            # Create orchestrator
            orchestrator = LyricsOrchestrator(
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
                result_extractor=lambda r: r,  # Result is already LyricContextModel
                result_type=LyricContextModel,
                cache_key_fn=lambda: orchestrator.get_cache_key(input),
                cache_version="1",
                state_handler=self._handle_state,
            )

        except Exception as e:
            logger.exception("Lyrics context generation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    def _handle_state(self, result: LyricContextModel, context: PipelineContext) -> None:
        """Store lyrics context in state (backward compatibility)."""
        context.set_state("lyric_context", result)
