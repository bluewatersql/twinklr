"""Holistic evaluation for GroupPlanSet.

Provides models and evaluator for cross-section quality assessment.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from twinklr.core.agents._paths import AGENTS_BASE_PATH
from twinklr.core.agents.issues import (
    Issue,
    IssueCategory,
    IssueLocation,
)
from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.prompts import spec_prompt_hash
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.shared.judge.models import VerdictStatus
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.taxonomy_utils import get_taxonomy_dict
from twinklr.core.config.models import AgentConfig, AgentOrchestrationConfig
from twinklr.core.sequencer.planning import GroupPlanSet
from twinklr.core.sequencer.planning.holistic_models import (
    CrossSectionIssue,
    HolisticEvaluation,
)
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph

logger = logging.getLogger(__name__)


def get_holistic_judge_spec(
    config: AgentConfig | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    token_budget: int | None = None,
) -> AgentSpec:
    """Get HolisticJudge agent specification.

    The HolisticJudge evaluates the complete GroupPlanSet for:
    - Cross-section coherence and energy arc
    - Template variety across sections
    - Group utilization balance
    - Alignment with MacroPlan global story

    Uses the configured judge model for nuanced cross-section evaluation where
    scoring consistency is critical for downstream pipeline decisions.

    Args:
        config: Per-role model, sampling, and reasoning configuration.
        token_budget: Optional token budget

    Returns:
        HolisticJudge agent spec
    """
    resolved = config or AgentOrchestrationConfig().judge_agent
    if model is not None or temperature is not None or reasoning_effort is not None:
        resolved = resolved.model_copy(
            update={
                "model": model if model is not None else resolved.model,
                "temperature": temperature if temperature is not None else resolved.temperature,
                "reasoning_effort": (
                    reasoning_effort if reasoning_effort is not None else resolved.reasoning_effort
                ),
            }
        )
    return AgentSpec(
        name="holistic_judge",
        prompt_pack="sequencer/group_planner/prompts/holistic_judge",
        response_model=HolisticEvaluation,
        mode=AgentMode.ONESHOT,
        model=resolved.model,
        temperature=resolved.temperature,
        reasoning_effort=resolved.reasoning_effort,
        max_tokens=resolved.max_tokens,
        timeout_seconds=resolved.timeout_seconds,
        max_schema_repair_attempts=1,
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
        choreo_graph: ChoreographyGraph,
        template_catalog: TemplateCatalog,
        macro_plan_summary: dict[str, Any] | None = None,
        lyric_context: Any | None = None,
    ) -> str:
        """Generate cache key for deterministic caching.

        Cache key includes all inputs that affect holistic evaluation:
        - Group plan set (all section plans)
        - Choreography graph configuration
        - Template catalog
        - Macro plan summary
        - Lyric context (narrative calibration)
        - Model configuration
        - Holistic-judge prompt-pack content

        Args:
            group_plan_set: Complete set of section plans
            choreo_graph: Choreography graph configuration
            template_catalog: Available templates
            macro_plan_summary: Optional MacroPlan summary
            lyric_context: Optional LyricContextModel for narrative calibration

        Returns:
            SHA256 hash of canonical inputs
        """
        from twinklr.core.agents.sequencer.group_planner.context_shaping import (
            _shape_lyric_context_summary,
        )

        key_data = {
            "group_plan_set": group_plan_set.model_dump(),
            "choreo_graph": choreo_graph.model_dump(),
            "template_catalog": template_catalog.model_dump(),
            "macro_plan_summary": macro_plan_summary or {},
            "lyric_context": _shape_lyric_context_summary(lyric_context),
            "model": self.holistic_judge_spec.model,
            "reasoning_effort": self.holistic_judge_spec.reasoning_effort,
            "temperature": self.holistic_judge_spec.temperature,
            "prompt_packs": spec_prompt_hash(AGENTS_BASE_PATH, self.holistic_judge_spec),
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
        choreo_graph: ChoreographyGraph,
        template_catalog: TemplateCatalog,
        macro_plan_summary: dict[str, Any] | None = None,
        lyric_context: Any | None = None,
        run_id: str | None = None,
    ) -> HolisticEvaluation:
        """Evaluate GroupPlanSet for cross-section quality.

        Args:
            group_plan_set: Complete set of section plans to evaluate
            choreo_graph: Choreography graph configuration
            template_catalog: Available templates
            macro_plan_summary: Optional typed summary from MacroPlan
            lyric_context: Optional LyricContextModel for narrative calibration

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
            choreo_graph=choreo_graph,
            template_catalog=template_catalog,
            macro_plan_summary=macro_plan_summary,
            lyric_context=lyric_context,
            run_id=run_id,
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
        choreo_graph: ChoreographyGraph,
        template_catalog: TemplateCatalog,
        macro_plan_summary: dict[str, Any] | None,
        lyric_context: Any | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Build variables for holistic judge prompt.

        Args:
            group_plan_set: Plans to evaluate
            choreo_graph: Choreography graph configuration
            template_catalog: Available templates
            macro_plan_summary: Optional MacroPlan summary
            lyric_context: Optional LyricContextModel for narrative calibration

        Returns:
            Variables dict for judge prompt
        """
        from twinklr.core.agents.sequencer.group_planner.context_shaping import (
            shape_holistic_judge_context,
        )

        variables = shape_holistic_judge_context(
            group_plan_set=group_plan_set,
            choreo_graph=choreo_graph,
            template_catalog=template_catalog,
            macro_plan_summary=macro_plan_summary,
            lyric_context=lyric_context,
        )

        # Always set learning_context (empty if no data) to avoid template errors
        # Note: Holistic judge doesn't use IterationController, so we set it manually
        if "learning_context" not in variables:
            variables["learning_context"] = ""
        if run_id:
            variables["run_id"] = run_id

        return variables


def cross_section_issues_to_issues(
    cross_section_issues: list[CrossSectionIssue],
) -> list[Issue]:
    """Convert CrossSectionIssues to Issue models for IssueRepository.

    Creates one Issue per CrossSectionIssue, mapping the first affected
    section to IssueLocation.section_id. The cross-section nature is
    preserved via the issue_id and message fields.

    Args:
        cross_section_issues: Holistic evaluation issues

    Returns:
        List of Issue models compatible with IssueRepository
    """
    issues: list[Issue] = []
    for csi in cross_section_issues:
        location = IssueLocation(
            section_id=csi.affected_sections[0] if csi.affected_sections else None,
            group_id=None,
            effect_id=None,
            bar_start=None,
            bar_end=None,
            field_path=None,
        )

        issue = Issue(
            issue_id=csi.issue_id,
            category=_infer_category(csi.issue_id),
            severity=csi.severity,
            location=location,
            rule=f"DON'T allow {csi.issue_id.replace('_', ' ')} across sections",
            message=f"{csi.description} (affects: {', '.join(csi.affected_sections)})",
            fix_hint=csi.recommendation,
            acceptance_test=f"Issue {csi.issue_id} is resolved across affected sections",
            generic_example=None,
            targeted_actions=list(csi.targeted_actions),
        )
        issues.append(issue)

    return issues


def _infer_category(issue_id: str) -> IssueCategory:
    """Infer IssueCategory from holistic issue_id pattern."""
    issue_lower = issue_id.lower()
    if "energy" in issue_lower or "arc" in issue_lower:
        return IssueCategory.CONTRAST_DYNAMICS
    if "variety" in issue_lower or "repetit" in issue_lower or "monoton" in issue_lower:
        return IssueCategory.VARIETY
    if "palette" in issue_lower or "color" in issue_lower:
        return IssueCategory.PALETTE
    if "motif" in issue_lower or "cohes" in issue_lower:
        return IssueCategory.MOTIF_COHESION
    if "layer" in issue_lower or "lane" in issue_lower or "reuse" in issue_lower:
        return IssueCategory.LAYERING
    if "transition" in issue_lower:
        return IssueCategory.COORDINATION
    if "coverage" in issue_lower or "utiliz" in issue_lower:
        return IssueCategory.COVERAGE
    if "theme" in issue_lower or "story" in issue_lower:
        return IssueCategory.STYLE
    return IssueCategory.COORDINATION
