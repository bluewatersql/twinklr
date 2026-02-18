"""Macro planner pipeline stage.

Wraps MacroPlannerOrchestrator for pipeline execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult
    from twinklr.core.sequencer.planning import MacroSectionPlan

logger = logging.getLogger(__name__)


class MacroPlannerStage:
    """Pipeline stage for macro planning.

    Generates high-level choreography strategy using the MacroPlanner agent.
    Takes audio profile, optional lyrics context, and display groups to create
    a strategic plan for the entire song.

    Input: dict with keys:
        - "profile": AudioProfileModel
        - "lyrics": LyricContextModel | None
    Output: list[MacroSectionPlan] (for direct FAN_OUT to GroupPlanner)

    State stored:
        - "macro_plan": Full MacroPlan (for global_story, layering_plan access)
        - "audio_profile": AudioProfileModel (for GroupPlannerStage)
        - "lyric_context": LyricContextModel | None (for GroupPlannerStage)

    Example:
        >>> stage = MacroPlannerStage(display_groups=[...])
        >>> input = {"profile": audio_profile, "lyrics": lyric_context}
        >>> result = await stage.execute(input, context)
        >>> if result.success:
        ...     sections = result.output  # list[MacroSectionPlan] for FAN_OUT
    """

    def __init__(self, display_groups: list[dict[str, Any]]) -> None:
        """Initialize macro planner stage.

        Args:
            display_groups: List of display group configs with concrete id, model_count, group_type
        """
        self.display_groups = display_groups

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "macro_planner"

    async def execute(
        self,
        input: dict[str, Any],
        context: PipelineContext,
    ) -> StageResult[list[MacroSectionPlan]]:
        """Generate macro plan and return section list for FAN_OUT.

        Args:
            input: Dict with "profile" (AudioProfileModel) and "lyrics" (LyricContextModel | None)
            context: Pipeline context with provider and config

        Returns:
            StageResult containing list[MacroSectionPlan] for direct FAN_OUT

        Side Effects:
            - Stores "macro_plan" in context.state (full MacroPlan for downstream)
            - Adds "macro_plan_iterations" to context.metrics
            - Adds "macro_plan_tokens" to context.metrics
            - Adds "macro_plan_score" to context.metrics (if available)
            - Adds "macro_plan_from_cache" to context.metrics
            - Adds "section_count" to context.metrics
        """
        from twinklr.core.agents.sequencer.macro_planner import (
            MacroPlannerOrchestrator,
            PlanningContext,
        )
        from twinklr.core.agents.shared.judge.controller import IterationResult
        from twinklr.core.pipeline.execution import execute_step
        from twinklr.core.pipeline.result import failure_result

        try:
            # Extract inputs
            audio_profile = input["profile"]
            lyric_context = input.get("lyrics")  # May be None

            # Build agent-specific context
            planning_context = PlanningContext(
                audio_profile=audio_profile,
                lyric_context=lyric_context,
                display_groups=self.display_groups,
            )

            # Create orchestrator with pipeline context dependencies
            orchestrator = MacroPlannerOrchestrator(
                provider=context.provider,
                max_iterations=context.job_config.agent.max_iterations,
                min_pass_score=context.job_config.agent.success_threshold / 10.0,
                llm_logger=context.llm_logger,
            )

            def extract_sections(r: Any) -> list[MacroSectionPlan]:
                """Extract section plans from IterationResult."""
                from twinklr.core.agents.shared.judge.controller import IterationResult
                from twinklr.core.sequencer.planning import MacroPlan

                normalized_result = IterationResult.model_validate(r) if isinstance(r, dict) else r
                plan = normalized_result.plan
                if plan is None:
                    raise ValueError("IterationResult.plan is None")

                normalized_plan = MacroPlan.model_validate(plan)
                result: list[MacroSectionPlan] = normalized_plan.section_plans
                return result

            # Execute with caching and automatic metrics/state handling
            return await execute_step(
                stage_name=self.name,
                context=context,
                compute=lambda: orchestrator.run(planning_context),
                result_extractor=extract_sections,
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
            logger.exception("Macro planning failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    def _handle_state(self, result: Any, context: PipelineContext) -> None:
        """Store macro plan in state for downstream stages."""
        from twinklr.core.agents.shared.judge.controller import IterationResult
        from twinklr.core.sequencer.planning import MacroPlan

        normalized_result = (
            IterationResult.model_validate(result) if isinstance(result, dict) else result
        )
        plan = normalized_result.plan
        if plan:
            context.set_state("macro_plan", MacroPlan.model_validate(plan))

    def _handle_metrics(self, result: Any, context: PipelineContext) -> None:
        """Track section count metric (extends defaults)."""
        from twinklr.core.agents.shared.judge.controller import IterationResult
        from twinklr.core.sequencer.planning import MacroPlan

        normalized_result = (
            IterationResult.model_validate(result) if isinstance(result, dict) else result
        )
        plan = normalized_result.plan
        if plan:
            normalized_plan = MacroPlan.model_validate(plan)
            context.add_metric("section_count", len(normalized_plan.section_plans))
