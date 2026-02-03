"""Orchestrator for GroupPlanner with section-level iteration.

Coordinates GroupPlanner agent with heuristic validation and section-level
judge evaluation using the StandardIterationController.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
from twinklr.core.agents.sequencer.group_planner.models import SectionCoordinationPlan
from twinklr.core.agents.sequencer.group_planner.specs import (
    get_planner_spec,
    get_section_judge_spec,
)
from twinklr.core.agents.sequencer.group_planner.validators import (
    SectionPlanValidator,
    ValidationSeverity,
)
from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    IterationResult,
    StandardIterationController,
)
from twinklr.core.agents.shared.judge.feedback import FeedbackManager
from twinklr.core.agents.spec import AgentSpec

logger = logging.getLogger(__name__)


class GroupPlannerOrchestrator:
    """Orchestrates GroupPlanner with section-level iteration.

    Provides high-level interface for running the GroupPlanner with:
    - Heuristic validation (fast, deterministic quality checks)
    - Section-level judge evaluation (LLM-driven quality assessment)
    - Iterative refinement with feedback

    This orchestrator handles ONE SECTION at a time. For full song processing,
    use GroupPlannerStage with FAN_OUT pattern in the pipeline.

    Attributes:
        planner_spec: Planner agent specification
        section_judge_spec: Section judge agent specification
        provider: LLM provider
        llm_logger: LLM call logger
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        planner_spec: AgentSpec | None = None,
        section_judge_spec: AgentSpec | None = None,
        max_iterations: int = 3,
        min_pass_score: float = 7.0,
        token_budget: int | None = None,
        llm_logger: LLMCallLogger | None = None,
    ):
        """Initialize GroupPlanner orchestrator.

        Args:
            provider: LLM provider for agent execution
            planner_spec: Optional planner spec (uses default if None)
            section_judge_spec: Optional section judge spec (uses default if None)
            max_iterations: Maximum refinement iterations per section (default: 3)
            min_pass_score: Minimum score for section approval (default: 7.0)
            token_budget: Optional token budget limit per section
            llm_logger: Optional LLM call logger (uses NullLLMCallLogger if None)
        """
        self.planner_spec = planner_spec or get_planner_spec()
        self.section_judge_spec = section_judge_spec or get_section_judge_spec()
        self.provider = provider
        self.llm_logger = llm_logger or NullLLMCallLogger()

        # Create iteration config
        self.config = IterationConfig(
            max_iterations=max_iterations,
            approval_score_threshold=min_pass_score,
            token_budget=token_budget,
        )

        logger.debug(
            f"GroupPlannerOrchestrator initialized "
            f"(max_iterations={max_iterations}, min_pass_score={min_pass_score})"
        )

    async def get_cache_key(self, section_context: SectionPlanningContext) -> str:
        """Generate cache key for deterministic caching.

        Cache key includes all inputs that affect section plan output:
        - Section planning context (macro section plan, display graph, templates, timing, layer intents)
        - Max iterations
        - Min pass score
        - Model configuration

        Args:
            section_context: Section planning context for this run

        Returns:
            SHA256 hash of canonical inputs
        """
        key_data = {
            "section_context": section_context.model_dump(),
            "max_iterations": self.config.max_iterations,
            "min_pass_score": self.config.approval_score_threshold,
            "planner_model": self.planner_spec.model,
            "judge_model": self.section_judge_spec.model,
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

    async def run(
        self,
        section_context: SectionPlanningContext,
    ) -> IterationResult[SectionCoordinationPlan]:
        """Run GroupPlanner for a single section with iterative refinement.

        Executes the complete GroupPlanner workflow for one section:
        1. Generate initial section plan (planner agent)
        2. Validate plan (heuristic validator)
        3. Evaluate plan (section judge agent)
        4. Refine if needed (repeat with feedback)
        5. Return final plan or best attempt

        Args:
            section_context: Complete section planning context

        Returns:
            IterationResult containing the final SectionCoordinationPlan

        Raises:
            ValueError: If section context is invalid
        """
        if not section_context.primary_focus_targets:
            raise ValueError("Section must have at least one primary_focus_target")

        logger.debug(
            f"Starting GroupPlanner orchestration for section: {section_context.section_id}"
        )

        # Create feedback manager for this section
        feedback_manager = FeedbackManager()

        # Create controller for this section
        controller = StandardIterationController[SectionCoordinationPlan](
            config=self.config,
            feedback_manager=feedback_manager,
        )

        # Prepare initial variables for planner
        initial_variables = self._build_planner_variables(section_context)

        # Create validator function
        validator = self._build_validator(section_context)

        # Run iteration loop
        result = await controller.run(
            planner_spec=self.planner_spec,
            judge_spec=self.section_judge_spec,
            initial_variables=initial_variables,
            validator=validator,
            provider=self.provider,
            llm_logger=self.llm_logger,
        )

        if result.success:
            logger.debug(
                f"✅ Section {section_context.section_id} succeeded: "
                f"{result.context.current_iteration} iterations, "
                f"score {result.context.final_verdict.score:.1f}"
                if result.context.final_verdict
                else f"✅ Section {section_context.section_id} succeeded"
            )
        else:
            logger.warning(
                f"⚠️ Section {section_context.section_id} completed without approval: "
                f"{result.context.current_iteration} iterations, "
                f"termination: {result.context.termination_reason}"
            )

        return result

    def _build_planner_variables(
        self,
        section_context: SectionPlanningContext,
    ) -> dict[str, Any]:
        """Build variables for planner prompt.

        Args:
            section_context: Section planning context

        Returns:
            Variables dict for planner
        """
        from twinklr.core.agents.sequencer.group_planner.context_shaping import (
            shape_planner_context,
        )

        # Get shaped context (filtered/simplified for tokens)
        # Note: Taxonomy enums are injected automatically by async_runner via taxonomy_utils
        variables = shape_planner_context(section_context)

        return variables

    def _build_validator(
        self,
        section_context: SectionPlanningContext,
    ) -> Callable[[SectionCoordinationPlan], list[str]]:
        """Build validator function for section plans.

        Args:
            section_context: Section planning context

        Returns:
            Validator function that returns list of error messages
        """
        # Create deterministic validator
        validator = SectionPlanValidator(
            display_graph=section_context.display_graph,
            template_catalog=section_context.template_catalog,
            timing_context=section_context.timing_context,
        )

        def validate(plan: SectionCoordinationPlan) -> list[str]:
            """Validate plan and return list of error messages."""
            result = validator.validate(plan)

            # Return only ERROR severity issues as strings
            errors = [
                f"{issue.code}: {issue.message}"
                for issue in result.errors
                if issue.severity == ValidationSeverity.ERROR
            ]
            return errors

        return validate
