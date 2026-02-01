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
        """Generate lyrics context.

        Args:
            input: SongBundle from audio analysis
            context: Pipeline context with provider and config

        Returns:
            StageResult containing LyricContextModel

        Side Effects:
            - Adds "lyrics_tokens" to context.metrics
        """
        from twinklr.core.agents.audio.lyrics import run_lyrics_async
        from twinklr.core.pipeline.result import failure_result, success_result

        try:
            # Check if lyrics are available
            if input.lyrics is None or input.lyrics.text is None:
                logger.warning("Lyrics stage called but no lyrics available in bundle")
                return failure_result(
                    "No lyrics available in audio bundle",
                    stage_name=self.name,
                )

            logger.info("Generating lyrics context")

            # Run lyrics agent
            lyric_context = await run_lyrics_async(
                song_bundle=input,
                provider=context.provider,
                llm_logger=context.llm_logger,
                model=context.job_config.agent.plan_agent.model,
                temperature=0.5,
            )

            logger.info(
                f"Lyrics context complete: has_narrative={lyric_context.has_narrative}, "
                f"themes={len(lyric_context.themes)}, "
                f"key_phrases={len(lyric_context.key_phrases)}"
            )

            # Store in state for downstream stages (GroupPlannerStage)
            context.set_state("lyric_context", lyric_context)

            return success_result(lyric_context, stage_name=self.name)

        except Exception as e:
            logger.exception("Lyrics context generation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)
