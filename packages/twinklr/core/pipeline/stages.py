"""Example pipeline stages for Twinklr sequencer.

Demonstrates how to wrap existing components as pipeline stages.
These are reference implementations - adapt as needed.
"""

from __future__ import annotations

import logging
from typing import Any

from twinklr.core.agents.audio.lyrics.orchestrator import LyricsOrchestrator
from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.audio.profile.orchestrator import AudioProfileOrchestrator
from twinklr.core.agents.sequencer.macro_planner import (
    MacroPlannerOrchestrator,
    PlanningContext,
)
from twinklr.core.agents.sequencer.macro_planner.models import MacroPlan
from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.audio.models import SongBundle
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.result import StageResult, failure_result, success_result

logger = logging.getLogger(__name__)


class AudioAnalysisStage:
    """Stage: Audio analysis with caching.

    Input: str (audio file path)
    Output: SongBundle
    """

    @property
    def name(self) -> str:
        return "audio_analysis"

    async def execute(
        self,
        input: str,
        context: PipelineContext,
    ) -> StageResult[SongBundle]:
        """Analyze audio file.

        Args:
            input: Path to audio file
            context: Pipeline context

        Returns:
            StageResult containing SongBundle
        """
        try:
            logger.debug(f"Analyzing audio: {input}")

            analyzer = AudioAnalyzer(context.app_config, context.job_config)
            bundle = await analyzer.analyze(input, force_reprocess=False)

            # Store state for downstream stages
            context.set_state("has_lyrics", bundle.lyrics is not None and bundle.lyrics.text)
            context.add_metric("audio_duration_ms", bundle.timing.duration_ms)
            context.add_metric("tempo_bpm", bundle.features.get("tempo_bpm"))

            logger.debug(
                f"Audio analysis complete: {bundle.timing.duration_ms / 1000:.1f}s, "
                f"{bundle.features.get('tempo_bpm')} BPM"
            )

            return success_result(bundle, stage_name=self.name)

        except Exception as e:
            logger.exception("Audio analysis failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)


class AudioProfileStage:
    """Stage: Audio profile generation.

    Input: SongBundle
    Output: AudioProfileModel
    """

    @property
    def name(self) -> str:
        return "audio_profile"

    async def execute(
        self,
        input: SongBundle,
        context: PipelineContext,
    ) -> StageResult[AudioProfileModel]:
        """Generate audio profile.

        Args:
            input: SongBundle from audio analysis
            context: Pipeline context

        Returns:
            StageResult containing AudioProfileModel
        """
        try:
            logger.debug("Generating audio profile")

            orchestrator = AudioProfileOrchestrator(
                provider=context.provider,
                llm_logger=context.llm_logger,
                model=context.job_config.agent.plan_agent.model,
                temperature=0.3,
            )
            profile = await orchestrator.run(input)

            logger.debug(
                f"Audio profile complete: {profile.energy_profile.macro_energy}, "
                f"recommended layers: {profile.creative_guidance.recommended_layer_count}"
            )

            return success_result(profile, stage_name=self.name)

        except Exception as e:
            logger.exception("Audio profile generation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)


class LyricsStage:
    """Stage: Lyrics context generation.

    Input: SongBundle
    Output: LyricContext
    """

    @property
    def name(self) -> str:
        return "lyrics"

    async def execute(
        self,
        input: SongBundle,
        context: PipelineContext,
    ) -> StageResult[Any]:  # LyricContext type
        """Generate lyrics context.

        Args:
            input: SongBundle from audio analysis
            context: Pipeline context

        Returns:
            StageResult containing LyricContext
        """
        try:
            logger.debug("Generating lyrics context")

            orchestrator = LyricsOrchestrator(
                provider=context.provider,
                llm_logger=context.llm_logger,
                model=context.job_config.agent.plan_agent.model,
                temperature=0.5,
            )
            lyric_context = await orchestrator.run(input)

            logger.debug(
                f"Lyrics context complete: has_narrative={lyric_context.has_narrative}, "
                f"themes={len(lyric_context.themes)}"
            )

            return success_result(lyric_context, stage_name=self.name)

        except Exception as e:
            logger.exception("Lyrics context generation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)


class MacroPlannerStage:
    """Stage: Macro planning.

    Input: dict with keys "profile" (AudioProfileModel) and "lyrics" (LyricContext)
    Output: MacroPlan
    """

    def __init__(self, display_groups: list[dict[str, Any]]) -> None:
        """Initialize macro planner stage.

        Args:
            display_groups: List of display group configs
        """
        self.display_groups = display_groups

    @property
    def name(self) -> str:
        return "macro_planner"

    async def execute(
        self,
        input: dict[str, Any],
        context: PipelineContext,
    ) -> StageResult[MacroPlan]:
        """Generate macro plan.

        Args:
            input: Dict with "profile" and "lyrics" keys
            context: Pipeline context

        Returns:
            StageResult containing MacroPlan
        """
        try:
            logger.debug("Generating macro plan")

            audio_profile = input["profile"]
            lyric_context = input.get("lyrics")  # May be None

            # Create planning context
            planning_context = PlanningContext(
                audio_profile=audio_profile,
                lyric_context=lyric_context,
                display_groups=self.display_groups,
            )

            # Create orchestrator
            orchestrator = MacroPlannerOrchestrator(
                provider=context.provider,
                max_iterations=context.job_config.agent.max_iterations,
                min_pass_score=7.0,
                llm_logger=context.llm_logger,
            )

            # Execute
            result = await orchestrator.run(planning_context=planning_context)

            if not result.success or result.plan is None:
                return failure_result(
                    error=result.context.termination_reason or "No plan generated",
                    stage_name=self.name,
                )

            logger.debug(
                f"Macro plan complete: {len(result.plan.section_plans)} sections, "
                f"score={result.context.final_verdict.score if result.context.final_verdict else 'N/A'}"
            )

            # Store metrics
            context.add_metric("macro_plan_iterations", result.context.current_iteration)
            context.add_metric("macro_plan_tokens", result.context.total_tokens_used)

            return success_result(result.plan, stage_name=self.name)

        except Exception as e:
            logger.exception("Macro planning failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)


# NOTE: GroupPlannerStage removed - previous implementation was architecturally incorrect.
# See changes/archive/group_planner_v3_failed/ARCHIVE_NOTES.md for details.
# New implementation will iterate by section (not group) and produce cross-group coordination.
