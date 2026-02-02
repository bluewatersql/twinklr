"""Holistic evaluator pipeline stage.

Wraps HolisticEvaluator for pipeline execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from twinklr.core.agents.sequencer.group_planner.holistic import HolisticEvaluation
    from twinklr.core.pipeline.context import PipelineContext
    from twinklr.core.pipeline.result import StageResult

logger = logging.getLogger(__name__)


class HolisticEvaluatorStage:
    """Pipeline stage for holistic evaluation of GroupPlanSet.

    Evaluates the complete GroupPlanSet for cross-section coherence,
    energy arc, template variety, and MacroPlan alignment.

    Input: GroupPlanSet (from aggregator stage)
    Output: HolisticEvaluation

    Note: Retrieves display_graph, template_catalog, and macro_plan from
    context.state (stored by SectionContextBuilderStage).

    Example:
        >>> stage = HolisticEvaluatorStage()
        >>> result = await stage.execute(group_plan_set, context)
        >>> if result.success:
        ...     evaluation = result.output
        ...     print(f"Score: {evaluation.score}, Approved: {evaluation.is_approved}")
    """

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "holistic_evaluator"

    async def execute(
        self,
        input: Any,  # GroupPlanSet
        context: PipelineContext,
    ) -> StageResult[HolisticEvaluation]:
        """Run holistic evaluation on GroupPlanSet.

        Args:
            input: GroupPlanSet from aggregator stage
            context: Pipeline context with state (display_graph, template_catalog, macro_plan)

        Returns:
            StageResult containing HolisticEvaluation

        Side Effects:
            - Adds "holistic_score" to context.metrics
            - Adds "holistic_status" to context.metrics
            - Adds "holistic_issues_count" to context.metrics
        """
        from twinklr.core.agents.sequencer.group_planner.holistic import HolisticEvaluator
        from twinklr.core.pipeline.result import failure_result

        try:
            logger.debug(f"Running holistic evaluation on {len(input.section_plans)} sections")

            # Retrieve required context from state
            display_graph = context.get_state("display_graph")
            template_catalog = context.get_state("template_catalog")
            macro_plan = context.get_state("macro_plan")

            if display_graph is None:
                return failure_result(
                    "Missing 'display_graph' in context.state",
                    stage_name=self.name,
                )

            if template_catalog is None:
                return failure_result(
                    "Missing 'template_catalog' in context.state",
                    stage_name=self.name,
                )

            # Build macro_plan_summary for holistic judge
            macro_plan_summary: dict[str, Any] = {}
            if macro_plan is not None and hasattr(macro_plan, "global_story"):
                macro_plan_summary["global_story"] = (
                    macro_plan.global_story.model_dump() if macro_plan.global_story else None
                )

            # Create evaluator
            evaluator = HolisticEvaluator(
                provider=context.provider,
                llm_logger=context.llm_logger,
            )

            # Use execute_step for caching and metrics
            from twinklr.core.agents.sequencer.group_planner.holistic import HolisticEvaluation
            from twinklr.core.pipeline.execution import execute_step

            return await execute_step(
                stage_name=self.name,
                context=context,
                compute=lambda: evaluator.evaluate(
                    group_plan_set=input,
                    display_graph=display_graph,
                    template_catalog=template_catalog,
                    macro_plan_summary=macro_plan_summary,
                ),
                result_extractor=lambda r: r,  # Result is already HolisticEvaluation
                result_type=HolisticEvaluation,
                cache_key_fn=lambda: evaluator.get_cache_key(
                    group_plan_set=input,
                    display_graph=display_graph,
                    template_catalog=template_catalog,
                    macro_plan_summary=macro_plan_summary,
                ),
                cache_version="1",
                metrics_handler=self._handle_metrics,
            )

        except Exception as e:
            logger.exception("Holistic evaluation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    def _handle_metrics(self, result: Any, context: PipelineContext) -> None:
        """Track holistic evaluation metrics (extends defaults)."""
        from twinklr.core.agents.sequencer.group_planner.holistic import HolisticEvaluation

        if isinstance(result, HolisticEvaluation):
            context.add_metric("holistic_score", result.score)
            context.add_metric("holistic_status", result.status.value)
            context.add_metric("holistic_issues_count", len(result.cross_section_issues))
