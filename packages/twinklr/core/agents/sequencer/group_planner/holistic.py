"""Holistic evaluation for GroupPlanSet.

Provides models and evaluator for cross-section quality assessment.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.agents._paths import AGENTS_BASE_PATH
from twinklr.core.agents.issues import IssueSeverity
from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.shared.judge.models import VerdictStatus
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict
from twinklr.core.sequencer.planning import GroupPlanSet
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.models import DisplayGraph

logger = logging.getLogger(__name__)


class CrossSectionIssue(BaseModel):
    """Issue spanning multiple sections.

    Captures problems that only become visible when viewing
    the complete GroupPlanSet (e.g., monotony, energy arc issues).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_id: str = Field(description="Stable issue identifier")
    severity: IssueSeverity = Field(description="Issue severity")
    affected_sections: list[str] = Field(
        min_length=1,
        description="Section IDs affected by this issue",
    )
    description: str = Field(description="Clear description of the issue")
    recommendation: str = Field(description="High-level recommendation summary")
    targeted_actions: list[str] = Field(
        default_factory=list,
        description=(
            "Specific, directly actionable changes referencing concrete "
            "section_ids, group_ids, template_ids, palette_ids, and/or lanes. "
            "Each action should be a single instruction that can be applied to "
            "a specific group plan without further interpretation."
        ),
    )


class HolisticEvaluation(BaseModel):
    """Result of holistic evaluation across all sections.

    Captures the quality assessment of the complete GroupPlanSet,
    focusing on cross-section coherence, energy arc, and variety.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: VerdictStatus = Field(description="APPROVE, SOFT_FAIL, or HARD_FAIL")
    score: float = Field(ge=0.0, le=10.0, description="Overall quality score")
    score_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown of score by dimension (e.g., story_coherence, energy_arc)",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in evaluation")

    summary: str = Field(description="Brief summary of evaluation")
    strengths: list[str] = Field(description="Notable strengths of the plan")
    cross_section_issues: list[CrossSectionIssue] = Field(
        default_factory=list,
        description="Issues spanning multiple sections",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="High-level recommendations for improvement",
    )

    @property
    def is_approved(self) -> bool:
        """Check if evaluation resulted in approval."""
        return self.status == VerdictStatus.APPROVE


def get_holistic_judge_spec(
    model: str = "gpt-5.2",
    temperature: float = 0.3,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get HolisticJudge agent specification.

    The HolisticJudge evaluates the complete GroupPlanSet for:
    - Cross-section coherence and energy arc
    - Template variety across sections
    - Group utilization balance
    - Alignment with MacroPlan global story

    Args:
        model: LLM model to use (default: gpt-5.2 for nuanced evaluation)
        temperature: Sampling temperature (default: 0.3 for consistent judgment)
        token_budget: Optional token budget

    Returns:
        HolisticJudge agent spec
    """
    return AgentSpec(
        name="holistic_judge",
        prompt_pack="sequencer/group_planner/prompts/holistic_judge",
        response_model=HolisticEvaluation,
        mode=AgentMode.ONESHOT,
        model=model,
        temperature=temperature,
        max_schema_repair_attempts=5,
        token_budget=token_budget,
        default_variables={"taxonomy": get_taxonomy_dict()},
    )


# Convenience constant
HOLISTIC_JUDGE_SPEC = get_holistic_judge_spec()


class HolisticEvaluator:
    """Evaluates GroupPlanSet for cross-section quality.

    Runs the holistic judge to assess the complete coordination plan
    across all sections, checking for coherence, variety, and alignment
    with MacroPlan intent.

    This evaluator does NOT iterate - it's a single-pass evaluation
    after section-level iteration is complete.
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        holistic_judge_spec: AgentSpec | None = None,
        llm_logger: LLMCallLogger | None = None,
    ):
        """Initialize holistic evaluator.

        Args:
            provider: LLM provider for judge execution
            holistic_judge_spec: Optional spec (uses default if None)
            llm_logger: Optional LLM call logger
        """
        self.provider = provider
        self.holistic_judge_spec = holistic_judge_spec or get_holistic_judge_spec()
        self.llm_logger = llm_logger or NullLLMCallLogger()

        logger.debug("HolisticEvaluator initialized")

    async def get_cache_key(
        self,
        group_plan_set: GroupPlanSet,
        display_graph: DisplayGraph,
        template_catalog: TemplateCatalog,
        macro_plan_summary: dict[str, Any] | None = None,
    ) -> str:
        """Generate cache key for deterministic caching.

        Cache key includes all inputs that affect holistic evaluation:
        - Group plan set (all section plans)
        - Display graph configuration
        - Template catalog
        - Macro plan summary
        - Model configuration

        Args:
            group_plan_set: Complete set of section plans
            display_graph: Display configuration
            template_catalog: Available templates
            macro_plan_summary: Optional MacroPlan summary

        Returns:
            SHA256 hash of canonical inputs
        """
        key_data = {
            "group_plan_set": group_plan_set.model_dump(),
            "display_graph": display_graph.model_dump(),
            "template_catalog": template_catalog.model_dump(),
            "macro_plan_summary": macro_plan_summary or {},
            "model": self.holistic_judge_spec.model,
        }

        # Canonical JSON encoding for stable hashing
        canonical = json.dumps(
            key_data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def evaluate(
        self,
        group_plan_set: GroupPlanSet,
        display_graph: DisplayGraph,
        template_catalog: TemplateCatalog,
        macro_plan_summary: dict[str, Any] | None = None,
    ) -> HolisticEvaluation:
        """Evaluate GroupPlanSet for cross-section quality.

        Args:
            group_plan_set: Complete set of section plans to evaluate
            display_graph: Display configuration
            template_catalog: Available templates
            macro_plan_summary: Optional summary from MacroPlan (global_story, etc.)

        Returns:
            HolisticEvaluation with score and issues

        Raises:
            ValueError: If group_plan_set is empty
        """

        from twinklr.core.agents.async_runner import AsyncAgentRunner

        if not group_plan_set.section_plans:
            raise ValueError("GroupPlanSet must have at least one section plan")

        logger.debug(f"Running holistic evaluation on {len(group_plan_set.section_plans)} sections")

        # Build variables for judge
        variables = self._build_judge_variables(
            group_plan_set=group_plan_set,
            display_graph=display_graph,
            template_catalog=template_catalog,
            macro_plan_summary=macro_plan_summary,
        )

        # Create runner and execute
        runner = AsyncAgentRunner(
            provider=self.provider,
            prompt_base_path=AGENTS_BASE_PATH,
            llm_logger=self.llm_logger,
        )

        result = await runner.run(spec=self.holistic_judge_spec, variables=variables)

        if not result.success or result.data is None:
            logger.error(f"Holistic judge failed: {result.error_message}")
            # Return a hard fail evaluation
            return HolisticEvaluation(
                status=VerdictStatus.HARD_FAIL,
                score=0.0,
                confidence=0.0,
                summary=f"Holistic evaluation failed: {result.error_message}",
                strengths=[],
                cross_section_issues=[],
                recommendations=["Fix evaluation errors and retry"],
            )

        evaluation = result.data
        assert isinstance(evaluation, HolisticEvaluation)

        logger.debug(
            f"Holistic evaluation complete: "
            f"status={evaluation.status.value}, score={evaluation.score:.1f}"
        )

        return evaluation

    def _build_judge_variables(
        self,
        group_plan_set: GroupPlanSet,
        display_graph: DisplayGraph,
        template_catalog: TemplateCatalog,
        macro_plan_summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build variables for holistic judge prompt.

        Args:
            group_plan_set: Plans to evaluate
            display_graph: Display configuration
            template_catalog: Available templates
            macro_plan_summary: Optional MacroPlan summary

        Returns:
            Variables dict for judge prompt
        """
        from twinklr.core.agents.sequencer.group_planner.context_shaping import (
            shape_holistic_judge_context,
        )

        variables = shape_holistic_judge_context(
            group_plan_set=group_plan_set,
            display_graph=display_graph,
            template_catalog=template_catalog,
            macro_plan_summary=macro_plan_summary,
        )

        # Always set learning_context (empty if no data) to avoid template errors
        # Note: Holistic judge doesn't use IterationController, so we set it manually
        if "learning_context" not in variables:
            variables["learning_context"] = ""

        return variables
