"""Holistic corrector pipeline stage.

Applies structured targeted actions from holistic evaluation to correct
cross-section quality issues in a GroupPlanSet.

The corrector uses a scoped LLM call: only affected sections are sent at
full detail and the LLM returns only the modified sections (CorrectionResult).
The stage splices corrected sections back into the original GroupPlanSet.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from twinklr.core.agents._paths import AGENTS_BASE_PATH
from twinklr.core.agents.issues import IssueSeverity
from twinklr.core.agents.logging import NullLLMCallLogger
from twinklr.core.agents.sequencer.group_planner.holistic import (
    HolisticEvaluation,
)
from twinklr.core.agents.spec import AgentSpec
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.pipeline.result import StageResult, success_result
from twinklr.core.sequencer.planning import CorrectionResult, GroupPlanSet
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph

logger = logging.getLogger(__name__)


class HolisticCorrectorStage:
    """Pipeline stage for applying holistic corrections to GroupPlanSet.

    Runs after HolisticEvaluatorStage. Gated on holistic status:
    - APPROVE: pass-through (no correction needed)
    - SOFT_FAIL / HARD_FAIL: run corrector agent

    The corrector receives only the affected sections at full detail and
    returns a CorrectionResult with only the modified sections.  The stage
    splices corrected sections back into the original GroupPlanSet and
    re-validates to prevent structural regression.

    Input: GroupPlanSet (with holistic_evaluation attached)
    Output: GroupPlanSet (corrected or original on validation failure)
    """

    def __init__(
        self,
        choreo_graph: ChoreographyGraph,
        template_catalog: TemplateCatalog,
        *,
        min_correction_severity: IssueSeverity = IssueSeverity.WARN,
        corrector_spec: AgentSpec | None = None,
    ) -> None:
        """Initialize holistic corrector stage.

        Args:
            choreo_graph: Choreography graph for target validation
            template_catalog: Template catalog for template validation
            min_correction_severity: Minimum severity to trigger correction
            corrector_spec: Optional corrector agent spec (uses default if None)
        """
        self.choreo_graph = choreo_graph
        self.template_catalog = template_catalog
        self.min_correction_severity = min_correction_severity
        self.corrector_spec = corrector_spec

    @property
    def name(self) -> str:
        """Stage name for logging."""
        return "holistic_corrector"

    async def execute(
        self,
        input: GroupPlanSet,
        context: PipelineContext,
    ) -> StageResult[GroupPlanSet]:
        """Apply holistic corrections to GroupPlanSet.

        Args:
            input: GroupPlanSet with holistic_evaluation attached
            context: Pipeline context

        Returns:
            StageResult with corrected GroupPlanSet
        """
        try:
            evaluation = input.holistic_evaluation

            if evaluation is None:
                logger.debug("No holistic evaluation found — passing through")
                return success_result(input, stage_name=self.name)

            # Deserialize if needed (from cache)
            if isinstance(evaluation, dict):
                evaluation = HolisticEvaluation(**evaluation)

            if evaluation.is_approved:
                logger.debug(
                    "Holistic evaluation APPROVED (score=%.1f) — no correction needed",
                    evaluation.score,
                )
                context.add_metric("holistic_corrector_applied", False)
                return success_result(input, stage_name=self.name)

            # Filter to actionable issues
            severity_order = {IssueSeverity.ERROR: 0, IssueSeverity.WARN: 1, IssueSeverity.NIT: 2}
            min_order = severity_order.get(self.min_correction_severity, 1)

            actionable_issues = [
                issue
                for issue in evaluation.cross_section_issues
                if severity_order.get(issue.severity, 2) <= min_order and issue.targeted_actions
            ]

            if not actionable_issues:
                logger.debug("No actionable issues above severity threshold — passing through")
                context.add_metric("holistic_corrector_applied", False)
                return success_result(input, stage_name=self.name)

            total_actions = sum(len(i.targeted_actions) for i in actionable_issues)

            # Determine affected section IDs for hallucination guard
            affected_section_ids: set[str] = set()
            for issue in actionable_issues:
                affected_section_ids.update(issue.affected_sections)
                for action in issue.targeted_actions:
                    affected_section_ids.add(action.section_id)

            logger.info(
                "Running holistic correction: %d issues, %d actions, "
                "%d affected sections (score=%.1f, status=%s)",
                len(actionable_issues),
                total_actions,
                len(affected_section_ids),
                evaluation.score,
                evaluation.status.value,
            )

            # Run corrector and reassemble
            corrected = await self._run_corrector(
                input, evaluation, actionable_issues, affected_section_ids, context
            )

            if corrected is None:
                logger.warning("Corrector failed — returning original plan")
                context.add_metric("holistic_corrector_applied", False)
                context.add_metric("holistic_corrector_validation_passed", False)
                return success_result(input, stage_name=self.name)

            # Validate corrected plan
            modified_sections = self._identify_modified_sections(input, corrected)

            if not self._validate_corrected_plan(corrected, modified_sections, context):
                logger.warning(
                    "Corrected plan failed heuristic validation — "
                    "returning original plan (safe fallback)"
                )
                context.add_metric("holistic_corrector_applied", False)
                context.add_metric("holistic_corrector_validation_passed", False)
                return success_result(input, stage_name=self.name)

            # Success
            context.add_metric("holistic_corrector_applied", True)
            context.add_metric("holistic_corrector_sections_modified", len(modified_sections))
            context.add_metric("holistic_corrector_actions_applied", total_actions)
            context.add_metric("holistic_corrector_validation_passed", True)

            self._write_correction_artifact(input, corrected, modified_sections, context)

            logger.info(
                "Holistic correction applied: %d sections modified",
                len(modified_sections),
            )

            return success_result(corrected, stage_name=self.name)

        except Exception as e:
            logger.exception("Holistic correction failed", exc_info=e)
            context.add_metric("holistic_corrector_applied", False)
            return success_result(input, stage_name=self.name)

    async def _run_corrector(
        self,
        plan_set: GroupPlanSet,
        evaluation: HolisticEvaluation,
        actionable_issues: list[Any],
        affected_section_ids: set[str],
        context: PipelineContext,
    ) -> GroupPlanSet | None:
        """Run the corrector agent and reassemble the GroupPlanSet.

        The corrector returns a CorrectionResult with only modified sections.
        This method splices them back into the original plan set.

        Args:
            plan_set: Original GroupPlanSet
            evaluation: Holistic evaluation with issues
            actionable_issues: Filtered issues with targeted actions
            affected_section_ids: Section IDs the corrector is allowed to modify
            context: Pipeline context

        Returns:
            Reassembled GroupPlanSet or None on failure
        """
        from twinklr.core.agents.async_runner import AsyncAgentRunner
        from twinklr.core.agents.sequencer.group_planner.context_shaping import (
            shape_holistic_corrector_context,
        )
        from twinklr.core.agents.sequencer.group_planner.specs import (
            get_holistic_corrector_spec,
        )

        spec = self.corrector_spec or get_holistic_corrector_spec()

        variables = shape_holistic_corrector_context(
            group_plan_set=plan_set,
            holistic_evaluation=evaluation,
            choreo_graph=self.choreo_graph,
            template_catalog=self.template_catalog,
        )

        runner = AsyncAgentRunner(
            provider=context.provider,
            prompt_base_path=AGENTS_BASE_PATH,
            llm_logger=context.llm_logger or NullLLMCallLogger(),
        )

        result = await runner.run(spec=spec, variables=variables)

        if not result.success or result.data is None:
            logger.error("Holistic corrector agent failed: %s", result.error_message)
            return None

        correction = result.data
        if not isinstance(correction, CorrectionResult):
            logger.error("Corrector returned unexpected type: %s", type(correction))
            return None

        context.add_metric("holistic_corrector_tokens", result.tokens_used or 0)

        # Splice corrected sections into the original plan set
        return self._reassemble_plan(plan_set, correction, affected_section_ids, evaluation)

    def _reassemble_plan(
        self,
        original: GroupPlanSet,
        correction: CorrectionResult,
        affected_section_ids: set[str],
        evaluation: HolisticEvaluation,
    ) -> GroupPlanSet | None:
        """Splice corrected sections back into the original GroupPlanSet.

        Guards against hallucinated section_ids that weren't in the
        affected set.  Preserves timing fields (start_ms, end_ms) from
        the original sections since the LLM doesn't produce them.

        Args:
            original: Original GroupPlanSet
            correction: CorrectionResult from the corrector LLM
            affected_section_ids: Allowed section IDs
            evaluation: Original holistic evaluation to re-attach

        Returns:
            Reassembled GroupPlanSet or None if a hallucinated section is detected
        """
        original_by_id = {s.section_id: s for s in original.section_plans}

        # Validate: reject any section_id not in the affected set
        corrected_by_id = {}
        for section in correction.corrected_sections:
            if section.section_id not in affected_section_ids:
                logger.error(
                    "Corrector returned section '%s' which is not in the affected set %s — "
                    "rejecting entire correction (hallucination guard)",
                    section.section_id,
                    sorted(affected_section_ids),
                )
                return None
            if section.section_id not in original_by_id:
                logger.error(
                    "Corrector returned unknown section_id '%s' — "
                    "rejecting entire correction",
                    section.section_id,
                )
                return None
            corrected_by_id[section.section_id] = section

        # Rebuild section_plans: use corrected version where available,
        # original otherwise. Preserve timing from originals.
        merged_sections = []
        for orig_section in original.section_plans:
            if orig_section.section_id in corrected_by_id:
                corrected_section = corrected_by_id[orig_section.section_id]
                # Restore timing fields the LLM doesn't produce
                corrected_section = corrected_section.model_copy(
                    update={
                        "start_ms": orig_section.start_ms,
                        "end_ms": orig_section.end_ms,
                    }
                )
                merged_sections.append(corrected_section)
            else:
                merged_sections.append(orig_section)

        return original.model_copy(
            update={
                "section_plans": merged_sections,
                "holistic_evaluation": evaluation,
            }
        )

    def _identify_modified_sections(
        self, original: GroupPlanSet, corrected: GroupPlanSet
    ) -> list[str]:
        """Identify which sections were modified by the corrector."""
        original_by_id = {s.section_id: s for s in original.section_plans}
        modified: list[str] = []

        for section in corrected.section_plans:
            original_section = original_by_id.get(section.section_id)
            if original_section is None:
                modified.append(section.section_id)
                continue

            orig_dump = original_section.model_dump(exclude={"start_ms", "end_ms"})
            corr_dump = section.model_dump(exclude={"start_ms", "end_ms"})
            if orig_dump != corr_dump:
                modified.append(section.section_id)

        return modified

    def _validate_corrected_plan(
        self,
        corrected: GroupPlanSet,
        modified_sections: list[str],
        context: PipelineContext,
    ) -> bool:
        """Validate corrected plan with heuristic checks.

        Catches structural regressions the corrector LLM may introduce:
        empty lane_plans, empty motif_ids, and coordination_plans with
        empty targets lists.

        Returns True if the plan passes basic structural validation.
        """
        if not corrected.section_plans:
            logger.error("Corrected plan has no section plans")
            return False

        for section in corrected.section_plans:
            if section.section_id not in modified_sections:
                continue

            if not section.lane_plans:
                logger.error("Modified section %s has no lane_plans", section.section_id)
                return False

            if not section.motif_ids:
                logger.error("Modified section %s has empty motif_ids", section.section_id)
                return False

            for lane_plan in section.lane_plans:
                for coord in lane_plan.coordination_plans:
                    if not coord.targets:
                        logger.error(
                            "Modified section %s lane %s has coordination_plan "
                            "with empty targets",
                            section.section_id,
                            lane_plan.lane,
                        )
                        return False

        return True

    def _write_correction_artifact(
        self,
        original: GroupPlanSet,
        corrected: GroupPlanSet,
        modified_sections: list[str],
        context: PipelineContext,
    ) -> None:
        """Write correction artifact to output directory."""
        output_dir = context.output_dir
        if output_dir is None:
            return

        artifact = {
            "sections_modified": modified_sections,
            "modification_count": len(modified_sections),
        }

        try:
            path = Path(output_dir) / "holistic_correction.json"
            path.write_text(json.dumps(artifact, indent=2, default=str))
        except Exception as e:
            logger.warning("Failed to write correction artifact: %s", e)
