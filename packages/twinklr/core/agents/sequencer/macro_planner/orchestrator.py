"""Orchestrator for MacroPlanner with judge-based iteration.

This module provides a high-level orchestrator that coordinates the MacroPlanner
agent with heuristic validation and judge-based refinement using the
StandardIterationController.
"""

from __future__ import annotations

import logging

from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.sequencer.macro_planner.context import PlanningContext
from twinklr.core.agents.sequencer.macro_planner.heuristics import (
    MacroPlanHeuristicValidator,
)
from twinklr.core.agents.sequencer.macro_planner.models import MacroPlan
from twinklr.core.agents.sequencer.macro_planner.specs import (
    get_judge_spec,
    get_planner_spec,
)
from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    IterationResult,
    StandardIterationController,
)
from twinklr.core.agents.shared.judge.feedback import FeedbackManager
from twinklr.core.agents.spec import AgentSpec

logger = logging.getLogger(__name__)


class MacroPlannerOrchestrator:
    """Orchestrates MacroPlanner with judge-based iteration.

    Provides a high-level interface for running the MacroPlanner with:
    - Heuristic validation (fast, deterministic quality checks)
    - Judge-based evaluation (LLM-driven quality assessment)
    - Iterative refinement with feedback

    Attributes:
        planner_spec: Planner agent specification
        judge_spec: Judge agent specification
        heuristic_validator: Heuristic validator instance
        controller: StandardIterationController instance
        provider: LLM provider
        llm_logger: LLM call logger
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        planner_spec: AgentSpec | None = None,
        judge_spec: AgentSpec | None = None,
        heuristic_validator: MacroPlanHeuristicValidator | None = None,
        max_iterations: int = 3,
        min_pass_score: float = 7.0,
        token_budget: int | None = None,
        llm_logger: LLMCallLogger | None = None,
    ):
        """Initialize MacroPlanner orchestrator.

        Args:
            provider: LLM provider for agent execution
            planner_spec: Optional planner spec (uses default if None)
            judge_spec: Optional judge spec (uses default if None)
            heuristic_validator: Optional validator (creates default if None)
            max_iterations: Maximum refinement iterations (default: 3)
            min_pass_score: Minimum score for approval (default: 7.0)
            token_budget: Optional token budget limit
            llm_logger: Optional LLM call logger (uses NullLLMCallLogger if None)
        """
        self.planner_spec = planner_spec or get_planner_spec()
        self.judge_spec = judge_spec or get_judge_spec()
        self.heuristic_validator = heuristic_validator or MacroPlanHeuristicValidator()
        self.provider = provider
        self.llm_logger = llm_logger or NullLLMCallLogger()

        # Create iteration config
        config = IterationConfig(
            max_iterations=max_iterations,
            approval_score_threshold=min_pass_score,
            token_budget=token_budget,
        )

        # Create feedback manager
        feedback_manager = FeedbackManager()

        # Create controller
        self.controller = StandardIterationController[MacroPlan](
            config=config,
            feedback_manager=feedback_manager,
        )

        logger.debug(
            f"MacroPlannerOrchestrator initialized "
            f"(max_iterations={max_iterations}, min_pass_score={min_pass_score})"
        )

    async def run(
        self,
        planning_context: PlanningContext,
    ) -> IterationResult[MacroPlan]:
        """Run MacroPlanner with iterative refinement.

        Executes the complete MacroPlanner workflow:
        1. Generate initial plan (planner agent)
        2. Validate plan (heuristic validator)
        3. Evaluate plan (judge agent)
        4. Refine if needed (repeat with feedback)
        5. Return final plan or best attempt

        Args:
            planning_context: Complete planning context containing:
                - audio_profile: Musical analysis and creative guidance
                - lyric_context: Narrative and thematic analysis (optional)
                - display_groups: Available display groups with role keys

        Returns:
            IterationResult containing the final MacroPlan and metadata

        Raises:
            ValueError: If inputs are invalid
        """
        audio_profile = planning_context.audio_profile

        if not audio_profile.structure.sections:
            raise ValueError("AudioProfile must have at least one section")

        if not planning_context.display_groups:
            raise ValueError("At least one display group must be provided")

        logger.debug(
            f"Starting MacroPlanner orchestration: "
            f"{audio_profile.song_identity.title} by {audio_profile.song_identity.artist}"
        )
        if planning_context.has_lyrics:
            logger.debug("  ✅ Lyric context available (narrative + thematic analysis)")
        else:
            logger.debug("  ⏭️  No lyric context (musical analysis only)")

        # Prepare initial variables for planner
        initial_variables = {
            "audio_profile": audio_profile,
            "display_groups": planning_context.display_groups,
        }

        # Add lyric context if available
        if planning_context.lyric_context:
            initial_variables["lyric_context"] = planning_context.lyric_context

        # Define validator function (converts heuristic validator to callable)
        def validator(plan: MacroPlan) -> list[str]:
            """Validate plan and return list of error messages."""
            issues = self.heuristic_validator.validate(plan, audio_profile)

            # Return only ERROR severity issues as strings
            errors = [
                f"{issue.category.value}: {issue.message}"
                for issue in issues
                if issue.severity.name == "ERROR"
            ]
            return errors

        # Run iteration loop
        result = await self.controller.run(
            planner_spec=self.planner_spec,
            judge_spec=self.judge_spec,
            initial_variables=initial_variables,
            validator=validator,
            provider=self.provider,
            llm_logger=self.llm_logger,
        )

        if result.success:
            logger.debug(
                f"✅ MacroPlanner succeeded: {result.context.current_iteration} iterations, "
                f"score {result.context.final_verdict.score:.1f}"
                if result.context.final_verdict
                else f"✅ MacroPlanner succeeded: {result.context.current_iteration} iterations"
            )
        else:
            logger.warning(
                f"⚠️ MacroPlanner completed without approval: "
                f"{result.context.current_iteration} iterations, "
                f"termination: {result.context.termination_reason}"
            )

        return result
