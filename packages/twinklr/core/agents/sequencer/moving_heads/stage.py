"""Moving head planner pipeline stage.

Wraps MovingHeadPlannerOrchestrator for pipeline execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult

logger = logging.getLogger(__name__)


class MovingHeadStage:
    """Pipeline stage for moving head choreography planning.

    Generates choreography using the MovingHead planner agent with V2 orchestrator.
    Takes audio bundle, audio profile, macro plan, and optional lyrics context to create
    a choreography plan that coordinates with the overall show strategy.

    Input: dict with keys:
        - "audio": SongBundle (from AudioAnalysisStage, for BeatGrid)
        - "profile": AudioProfileModel (from AudioProfileStage)
        - "lyrics": LyricContextModel | None (from LyricsStage, optional)
        - "macro": list[MacroSectionPlan] (from MacroPlannerStage)
    Output: ChoreographyPlan

    State stored:
        - "choreography_plan": ChoreographyPlan (for downstream rendering)
        - "beat_grid": BeatGrid (for downstream rendering)
        - "mh_planning_context": MovingHeadPlanningContext (for debugging)

    Example:
        >>> stage = MovingHeadStage(
        ...     fixture_count=4,
        ...     available_templates=["sweep_lr_fan_pulse", "circle_fan_hold"],
        ... )
        >>> input = {
        ...     "audio": song_bundle,  # from AudioAnalysisStage
        ...     "profile": audio_profile,
        ...     "lyrics": lyric_context,  # optional, may be None
        ...     "macro": macro_section_plans,  # from MacroPlannerStage
        ... }
        >>> result = await stage.execute(input, context)
        >>> if result.success:
        ...     plan = result.output  # ChoreographyPlan
    """

    def __init__(
        self,
        fixture_count: int,
        available_templates: list[str],
        fixture_groups: list[dict[str, Any]] | None = None,
        max_iterations: int = 3,
        min_pass_score: float = 7.0,
    ) -> None:
        """Initialize moving head planner stage.

        Args:
            fixture_count: Number of moving head fixtures
            available_templates: List of valid template IDs
            fixture_groups: Optional fixture group configurations
            max_iterations: Maximum refinement iterations (default: 3)
            min_pass_score: Minimum score for approval (default: 7.0)
        """
        self.fixture_count = fixture_count
        self.available_templates = available_templates
        self.fixture_groups = fixture_groups or []
        self.max_iterations = max_iterations
        self.min_pass_score = min_pass_score

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "moving_head_planner"

    async def execute(
        self,
        input: dict[str, Any],
        context: PipelineContext,
    ) -> StageResult[ChoreographyPlan]:
        """Generate choreography plan for moving heads.

        Args:
            input: Dict with keys:
                - "audio": SongBundle (from AudioAnalysisStage)
                - "profile": AudioProfileModel (from AudioProfileStage)
                - "lyrics": LyricContextModel | None (from LyricsStage, optional)
                - "macro": list[MacroSectionPlan] | None (from MacroPlannerStage)
            context: Pipeline context with provider and config

        Returns:
            StageResult containing ChoreographyPlan

        Side Effects:
            - Stores "choreography_plan" in context.state
            - Stores "beat_grid" in context.state (for downstream rendering)
            - Stores "mh_planning_context" in context.state
            - Adds "mh_iterations" to context.metrics
            - Adds "mh_tokens" to context.metrics
            - Adds "mh_score" to context.metrics (if available)
            - Adds "mh_from_cache" to context.metrics
            - Adds "mh_section_count" to context.metrics
        """
        from twinklr.core.agents.sequencer.moving_heads.context import (
            FixtureContext,
            MovingHeadPlanningContext,
        )
        from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
        from twinklr.core.agents.sequencer.moving_heads.orchestrator import (
            MovingHeadPlannerOrchestrator,
        )
        from twinklr.core.agents.shared.judge.controller import IterationResult
        from twinklr.core.pipeline.execution import execute_step
        from twinklr.core.pipeline.result import failure_result

        try:
            # Extract inputs per pipeline stage contract
            # inputs=["audio", "profile", "lyrics", "macro"]
            audio_bundle = input["audio"]  # SongBundle from AudioAnalysisStage
            audio_profile = input["profile"]
            lyric_context = input.get("lyrics")  # May be None (conditional stage)
            macro_plan = input.get("macro")  # list[MacroSectionPlan] from MacroPlannerStage

            # Build BeatGrid from audio bundle for downstream rendering
            from twinklr.core.sequencer.timing.beat_grid import BeatGrid

            beat_grid = BeatGrid.from_song_features(audio_bundle.features)
            context.set_state("beat_grid", beat_grid)
            logger.debug(
                f"Built beat_grid: tempo={beat_grid.tempo_bpm} BPM, "
                f"total_bars={beat_grid.total_bars}"
            )

            # Build fixture context
            fixture_context = FixtureContext(
                count=self.fixture_count,
                groups=self.fixture_groups,
            )

            # Build planning context with macro plan coordination
            planning_context = MovingHeadPlanningContext(
                audio_profile=audio_profile,
                lyric_context=lyric_context,
                fixtures=fixture_context,
                available_templates=self.available_templates,
                macro_plan=macro_plan,  # Coordinate with overall show strategy
            )

            # Store planning context for debugging
            context.set_state("mh_planning_context", planning_context)

            # Get max_iterations from job config if available
            max_iterations = self.max_iterations
            if hasattr(context, "job_config") and context.job_config:
                max_iterations = getattr(
                    context.job_config.agent, "max_iterations", self.max_iterations
                )

            # Create orchestrator with pipeline context dependencies
            orchestrator = MovingHeadPlannerOrchestrator(
                provider=context.provider,
                max_iterations=max_iterations,
                min_pass_score=self.min_pass_score,
                llm_logger=context.llm_logger,
            )

            def extract_plan(r: Any) -> ChoreographyPlan:
                """Extract choreography plan from IterationResult."""
                from twinklr.core.agents.shared.judge.controller import IterationResult

                normalized_result = IterationResult.model_validate(r) if isinstance(r, dict) else r
                plan = normalized_result.plan
                if plan is None:
                    raise ValueError("IterationResult.plan is None")

                return ChoreographyPlan.model_validate(plan)

            # Execute with caching and automatic metrics/state handling
            return await execute_step(
                stage_name=self.name,
                context=context,
                compute=lambda: orchestrator.run(planning_context),
                result_extractor=extract_plan,
                result_type=IterationResult,
                cache_key_fn=lambda: orchestrator.get_cache_key(planning_context),
                cache_version="1",
                state_handler=self._handle_state,
                metrics_handler=self._handle_metrics,
            )

        except KeyError as e:
            logger.error(f"Missing required input: {e}")
            return failure_result(f"Missing required input: {e}", stage_name=self.name)
        except Exception as e:
            logger.exception("Moving head planning failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    def _handle_state(self, result: Any, context: PipelineContext) -> None:
        """Store choreography plan in state for downstream stages."""
        from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan

        if isinstance(result, dict):
            plan = result.get("plan")
        else:
            plan = getattr(result, "plan", None)
        if plan:
            context.set_state("choreography_plan", ChoreographyPlan.model_validate(plan))

    def _handle_metrics(self, result: Any, context: PipelineContext) -> None:
        """Track iteration metrics (extends defaults from execute_step)."""
        from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan

        if isinstance(result, dict):
            plan = result.get("plan")
            ctx = result.get("context", {})
        else:
            plan = getattr(result, "plan", None)
            ctx = getattr(result, "context", None)

        # Track section count
        if plan:
            sections = ChoreographyPlan.model_validate(plan).sections
            context.add_metric("mh_section_count", len(sections))

        # Track iteration details
        if ctx:
            if isinstance(ctx, dict):
                iterations = ctx.get("current_iteration", 0)
                tokens = ctx.get("total_tokens_used", 0)
                final_verdict = ctx.get("final_verdict")
            else:
                iterations = getattr(ctx, "current_iteration", 0)
                tokens = getattr(ctx, "total_tokens_used", 0)
                final_verdict = getattr(ctx, "final_verdict", None)

            context.add_metric("mh_iterations", iterations)
            context.add_metric("mh_tokens", tokens)

            # Track final score if available
            if final_verdict:
                if isinstance(final_verdict, dict):
                    score = final_verdict.get("score")
                else:
                    score = getattr(final_verdict, "score", None)
                if score is not None:
                    context.add_metric("mh_score", score)
