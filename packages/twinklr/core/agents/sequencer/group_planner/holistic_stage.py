"""Holistic evaluator pipeline stage.

Wraps HolisticEvaluator for pipeline execution.

The stage evaluates the complete GroupPlanSet for cross-section coherence,
stores the evaluation in context state and metrics, and passes the
GroupPlanSet through to downstream stages unchanged.
"""

from __future__ import annotations

import logging

from twinklr.core.agents.sequencer.group_planner.holistic import (
    HolisticEvaluation,
    HolisticEvaluator,
)
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.execution import execute_step
from twinklr.core.pipeline.result import StageResult, failure_result
from twinklr.core.sequencer.planning import GroupPlanSet
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph

logger = logging.getLogger(__name__)


class HolisticEvaluatorStage:
    """Pipeline stage for holistic evaluation of GroupPlanSet.

    Evaluates the complete GroupPlanSet for cross-section coherence,
    energy arc, template variety, and MacroPlan alignment.

    This is an informational pass-through stage: the evaluation is stored
    in context state (``holistic_evaluator_result``) and metrics, but the
    original GroupPlanSet is returned as output so downstream stages
    receive the plan unchanged.

    Input: GroupPlanSet (from aggregator stage)
    Output: GroupPlanSet (pass-through; evaluation in state/metrics)

    Example:
        >>> stage = HolisticEvaluatorStage(choreo_graph, template_catalog)
        >>> result = await stage.execute(group_plan_set, context)
        >>> if result.success:
        ...     plan = result.output  # GroupPlanSet (unchanged)
        ...     eval = context.get_state("holistic_evaluator_result")
        ...     print(f"Score: {eval.score}, Approved: {eval.is_approved}")
    """

    def __init__(
        self,
        choreo_graph: ChoreographyGraph,
        template_catalog: TemplateCatalog,
    ) -> None:
        """Initialize holistic evaluator stage.

        Args:
            choreo_graph: Choreography graph configuration
            template_catalog: Available templates
        """
        self.choreo_graph = choreo_graph
        self.template_catalog = template_catalog

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "holistic_evaluator"

    async def execute(
        self,
        input: GroupPlanSet,
        context: PipelineContext,
    ) -> StageResult[GroupPlanSet]:
        """Run holistic evaluation on GroupPlanSet.

        The evaluation is stored in context state and metrics. The
        original GroupPlanSet is returned as output (pass-through) so
        downstream stages (e.g. asset resolution) receive the plan
        unchanged.

        Args:
            input: GroupPlanSet from aggregator stage
            context: Pipeline context with state (macro_plan, etc.)

        Returns:
            StageResult containing the original GroupPlanSet

        Side Effects:
            - Stores HolisticEvaluation in context state as ``holistic_evaluator_result``
            - Adds ``holistic_score`` to context.metrics
            - Adds ``holistic_status`` to context.metrics
            - Adds ``holistic_issues_count`` to context.metrics
        """
        try:
            logger.debug("Running holistic evaluation on %d sections", len(input.section_plans))

            macro_plan = context.get_state("macro_plan")
            macro_plan_summary = _extract_macro_plan_summary(macro_plan)

            evaluator = HolisticEvaluator(
                provider=context.provider,
                llm_logger=context.llm_logger,
            )

            # Pass-through: evaluate() produces HolisticEvaluation (stored in
            # state by execute_step), but we return the original GroupPlanSet.
            return await execute_step(
                stage_name=self.name,
                context=context,
                compute=lambda: evaluator.evaluate(
                    group_plan_set=input,
                    choreo_graph=self.choreo_graph,
                    template_catalog=self.template_catalog,
                    macro_plan_summary=macro_plan_summary,
                ),
                result_extractor=lambda _: input,
                result_type=HolisticEvaluation,
                cache_key_fn=lambda: evaluator.get_cache_key(
                    group_plan_set=input,
                    choreo_graph=self.choreo_graph,
                    template_catalog=self.template_catalog,
                    macro_plan_summary=macro_plan_summary,
                ),
                cache_version="1",
                metrics_handler=self._handle_metrics,
            )

        except Exception as e:
            logger.exception("Holistic evaluation failed", exc_info=e)
            return failure_result(str(e), stage_name=self.name)

    def _handle_metrics(self, result: HolisticEvaluation, context: PipelineContext) -> None:
        """Track holistic evaluation metrics (extends defaults)."""
        context.add_metric("holistic_score", result.score)
        context.add_metric("holistic_status", result.status.value)
        context.add_metric("holistic_issues_count", len(result.cross_section_issues))


def _extract_macro_plan_summary(
    macro_plan: object | None,
) -> dict[str, object]:
    """Extract macro plan summary for holistic judge context.

    Handles both Pydantic model and dict (from cache deserialization).

    Extracts:
    - global_story: Theme, motifs, pacing notes
    - expected_section_ids: Ordered list of section IDs from MacroPlan
      so the holistic judge can verify completeness against the canonical
      section list rather than guessing.

    Args:
        macro_plan: MacroPlan from context state, or None

    Returns:
        Summary dict with global_story and expected_section_ids
    """
    if macro_plan is None:
        return {}

    summary: dict[str, object] = {}

    if isinstance(macro_plan, dict):
        global_story = macro_plan.get("global_story")
    else:
        global_story = getattr(macro_plan, "global_story", None)

    if global_story is not None:
        if isinstance(global_story, dict):
            summary["global_story"] = global_story
        else:
            summary["global_story"] = global_story.model_dump()

    # Extract expected section IDs from MacroPlan.section_plans
    expected_ids: list[str] = []
    if isinstance(macro_plan, dict):
        section_plans = macro_plan.get("section_plans", [])
        if section_plans:
            for sp in section_plans:
                if isinstance(sp, dict):
                    section = sp.get("section", {})
                    if isinstance(section, dict):
                        sid = section.get("section_id")
                        if sid:
                            expected_ids.append(sid)
    else:
        section_plans = getattr(macro_plan, "section_plans", None)
        if section_plans:
            for sp in section_plans:
                section = getattr(sp, "section", None)
                if section is not None:
                    sid = getattr(section, "section_id", None)
                    if sid:
                        expected_ids.append(sid)

    if expected_ids:
        summary["expected_section_ids"] = expected_ids

    return summary
