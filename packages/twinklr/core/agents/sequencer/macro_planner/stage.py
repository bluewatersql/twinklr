"""Macro planner pipeline stage.

Wraps MacroPlannerOrchestrator for pipeline execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from twinklr.core.agents.sequencer.macro_planner.models import MacroSectionPlan
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult

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
            display_groups: List of display group configs with role_key, model_count, group_type
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
            - Adds "section_count" to context.metrics
        """
        from twinklr.core.agents.sequencer.macro_planner import (
            MacroPlannerOrchestrator,
            PlanningContext,
        )
        from twinklr.core.pipeline.result import failure_result, success_result

        try:
            logger.info("Generating macro plan")

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
                min_pass_score=7.0,
                llm_logger=context.llm_logger,
            )

            # Run orchestrator with agent context
            result = await orchestrator.run(planning_context=planning_context)

            if not result.success or result.plan is None:
                error_msg = result.context.termination_reason or "No plan generated"
                logger.error(f"Macro planning failed: {error_msg}")
                return failure_result(error_msg, stage_name=self.name)

            # Store full MacroPlan in state for downstream stages
            context.set_state("macro_plan", result.plan)

            # Log success
            logger.info(
                f"Macro plan complete: {len(result.plan.section_plans)} sections, "
                f"iterations={result.context.current_iteration}, "
                f"score={result.context.final_verdict.score if result.context.final_verdict else 'N/A'}"
            )

            # Track metrics in pipeline context
            context.add_metric("macro_plan_iterations", result.context.current_iteration)
            context.add_metric("macro_plan_tokens", result.context.total_tokens_used)
            context.add_metric("section_count", len(result.plan.section_plans))
            if result.context.final_verdict:
                context.add_metric("macro_plan_score", result.context.final_verdict.score)

            # Return section_plans list for direct FAN_OUT to GroupPlanner
            return success_result(result.plan.section_plans, stage_name=self.name)

        except KeyError as e:
            logger.error(f"Missing required input: {e}")
            return failure_result(f"Missing required input: {e}", stage_name=self.name)
        except Exception as e:
            logger.exception("Macro planning failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)
