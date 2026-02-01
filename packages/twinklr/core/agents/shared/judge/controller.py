"""Iteration controller for judge-based refinement loops.

This module provides a reusable iteration controller that manages judge-based
refinement loops across all agents.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.logging import LLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.result import AgentResult
from twinklr.core.agents.shared.judge.feedback import FeedbackManager
from twinklr.core.agents.shared.judge.models import (
    IterationState,
    JudgeVerdict,
    RevisionPriority,
    RevisionRequest,
    VerdictStatus,
)
from twinklr.core.agents.spec import AgentSpec
from twinklr.core.agents.state import AgentState

# Generic plan type (ChoreographyPlan, MacroPlan, etc.)
TPlan = TypeVar("TPlan")


class IterationConfig(BaseModel):
    """Configuration for iteration controller.

    Controls iteration behavior, termination conditions, and feedback.

    Attributes:
        max_iterations: Maximum iterations (1-10)
        token_budget: Optional token budget (cumulative)
        max_feedback_entries: Max feedback entries to keep (1-50)
        include_feedback_in_prompt: Include feedback in planner prompt
        approval_score_threshold: Min score for APPROVE (0-10)
        soft_fail_score_threshold: Min score for SOFT_FAIL (0-10)
    """

    max_iterations: int = Field(ge=1, le=10, default=3, description="Maximum iterations")
    token_budget: int | None = Field(default=None, description="Optional token budget (cumulative)")

    # Feedback management
    max_feedback_entries: int = Field(
        ge=1, le=50, default=25, description="Max feedback entries to keep"
    )
    include_feedback_in_prompt: bool = Field(
        default=True, description="Include feedback in planner prompt"
    )

    # Quality thresholds
    approval_score_threshold: float = Field(
        ge=0.0, le=10.0, default=7.0, description="Min score for APPROVE"
    )
    soft_fail_score_threshold: float = Field(
        ge=0.0, le=10.0, default=5.0, description="Min score for SOFT_FAIL"
    )

    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)


class IterationContext(BaseModel):
    """Runtime context for iteration loop.

    Tracks state, feedback, and progress across iterations.
    Mutable (not frozen) to allow state updates.

    Attributes:
        current_iteration: Current iteration number (0-based)
        state: Current iteration state
        verdicts: List of judge verdicts from all iterations
        revision_requests: List of revision requests from all iterations
        total_tokens_used: Cumulative token usage
        termination_reason: Reason for termination (if terminated)
        final_verdict: Final judge verdict (if any)
    """

    # State
    current_iteration: int = Field(ge=0, default=0)
    state: IterationState = Field(default=IterationState.NOT_STARTED)

    # History
    verdicts: list[JudgeVerdict] = Field(default_factory=list)
    revision_requests: list[RevisionRequest] = Field(default_factory=list)

    # Tracking
    total_tokens_used: int = Field(ge=0, default=0)

    # Termination
    termination_reason: str | None = Field(default=None)
    final_verdict: JudgeVerdict | None = Field(default=None)

    model_config = ConfigDict(extra="forbid")

    def update_state(self, new_state: IterationState) -> None:
        """Update iteration state.

        Args:
            new_state: New iteration state
        """
        self.state = new_state

    def add_verdict(self, verdict: JudgeVerdict) -> None:
        """Add judge verdict to history.

        Args:
            verdict: Judge verdict to add
        """
        self.verdicts.append(verdict)
        self.final_verdict = verdict

    def add_revision_request(self, request: RevisionRequest) -> None:
        """Add revision request to history.

        Args:
            request: Revision request to add
        """
        self.revision_requests.append(request)

    def increment_iteration(self) -> None:
        """Increment iteration counter."""
        self.current_iteration += 1

    def add_tokens(self, tokens: int) -> None:
        """Add to token usage.

        Args:
            tokens: Number of tokens to add
        """
        self.total_tokens_used += tokens

    @property
    def is_complete(self) -> bool:
        """Check if iteration loop is complete.

        Returns:
            True if state is terminal
        """
        return self.state.is_terminal

    @property
    def was_successful(self) -> bool:
        """Check if iteration loop succeeded.

        Returns:
            True if state is COMPLETE
        """
        return self.state == IterationState.COMPLETE


class IterationResult(BaseModel, Generic[TPlan]):
    """Result of iteration loop.

    Contains final plan, context, and success status.

    Attributes:
        success: Whether iteration loop succeeded
        plan: Final plan (if successful)
        context: Iteration context with history
        error_message: Error message (if failed)
    """

    success: bool = Field(description="Whether iteration loop succeeded")
    plan: TPlan | None = Field(default=None, description="Final plan (if successful)")
    context: IterationContext = Field(description="Iteration context with history")
    error_message: str | None = Field(default=None, description="Error message (if failed)")

    model_config = ConfigDict(frozen=True, extra="forbid")


class StandardIterationController(Generic[TPlan]):
    """Standard implementation of iteration controller.

    Manages judge-based refinement loop with feedback and validation.

    Attributes:
        config: Iteration configuration
        feedback: Feedback manager instance
        logger: Logger instance
    """

    def __init__(
        self,
        config: IterationConfig,
        feedback_manager: FeedbackManager,
    ):
        """Initialize iteration controller.

        Args:
            config: Iteration configuration
            feedback_manager: Feedback manager instance
        """
        self.config = config
        self.feedback = feedback_manager
        self.logger = logging.getLogger(__name__)

    async def run(
        self,
        planner_spec: AgentSpec,
        judge_spec: AgentSpec,
        initial_variables: dict[str, Any],
        validator: Callable[[TPlan], list[str]],
        provider: LLMProvider,
        llm_logger: LLMCallLogger,
        prompt_base_path: Path | str = Path("packages/twinklr/core/agents"),
    ) -> IterationResult[TPlan]:
        """Run iteration loop until approval or termination.

        Args:
            planner_spec: Planner agent specification
            judge_spec: Judge agent specification
            initial_variables: Initial variables for planner prompt
            validator: Heuristic validator function (returns list of errors)
            provider: LLM provider
            llm_logger: LLM call logger
            prompt_base_path: Base path for prompt packs (default: packages/twinklr/core/agents)

        Returns:
            IterationResult with final plan and metadata
        """
        context = IterationContext()
        runner = AsyncAgentRunner(
            provider=provider,
            prompt_base_path=Path(prompt_base_path),
            llm_logger=llm_logger,
        )

        # Create agent state for conversational planner (if needed)
        planner_state: AgentState | None = None
        if planner_spec.mode.value == "conversational":
            planner_state = AgentState(name=planner_spec.name)

        context.update_state(IterationState.PLANNING)

        plan: TPlan | None = None
        for iteration in range(self.config.max_iterations):
            context.increment_iteration()

            # === PLANNING STAGE ===
            self.logger.debug(f"Iteration {iteration + 1}/{self.config.max_iterations}: Planning")

            # Prepare planner variables (include feedback if enabled)
            planner_vars = self._prepare_planner_variables(initial_variables, context, iteration)

            # Run planner
            plan_result = await runner.run(
                spec=planner_spec, variables=planner_vars, state=planner_state
            )
            context.add_tokens(plan_result.tokens_used or 0)

            if not plan_result.success:
                return self._handle_planner_failure(context, plan_result)

            plan = cast(TPlan, plan_result.data)
            assert plan is not None, "Planner succeeded but returned None data"

            # === VALIDATION STAGE ===
            context.update_state(IterationState.VALIDATING)
            self.logger.debug("Validating plan (heuristics)")

            validation_errors = validator(plan)

            if validation_errors:
                context.update_state(IterationState.VALIDATION_FAILED)
                self.feedback.add_validation_failure(
                    message="; ".join(validation_errors),
                    iteration=iteration,
                )

                # Check if last iteration
                if iteration >= self.config.max_iterations - 1:
                    return self._handle_max_iterations(context, plan)

                # Build revision request and continue
                revision = RevisionRequest(
                    priority=RevisionPriority.CRITICAL,
                    focus_areas=["Schema Validation"],
                    specific_fixes=validation_errors,
                    avoid=[],
                    context_for_planner="Fix validation errors before judging",
                )
                context.add_revision_request(revision)
                continue

            # === JUDGING STAGE ===
            context.update_state(IterationState.JUDGING)
            self.logger.debug("Judging plan")

            # Prepare judge variables
            judge_vars = self._prepare_judge_variables(plan, initial_variables, iteration)

            # Run judge
            judge_result = await runner.run(spec=judge_spec, variables=judge_vars)
            context.add_tokens(judge_result.tokens_used or 0)

            if not judge_result.success:
                return self._handle_judge_failure(context, plan, judge_result)

            verdict = cast(JudgeVerdict, judge_result.data)
            assert isinstance(verdict, JudgeVerdict), "Judge succeeded but returned invalid data"
            context.add_verdict(verdict)

            # === DECISION STAGE ===
            if verdict.status == VerdictStatus.APPROVE:
                context.update_state(IterationState.JUDGE_APPROVED)
                context.update_state(IterationState.COMPLETE)
                self.logger.debug(f"✅ Plan approved (score: {verdict.score:.1f})")

                return IterationResult(
                    success=True,
                    plan=plan,
                    context=context,
                )

            # === REVISION STAGE ===
            if verdict.status == VerdictStatus.SOFT_FAIL:
                context.update_state(IterationState.JUDGE_SOFT_FAIL)
            elif verdict.status == VerdictStatus.HARD_FAIL:
                context.update_state(IterationState.JUDGE_HARD_FAIL)

            # Check termination conditions
            if iteration >= self.config.max_iterations - 1:
                return self._handle_max_iterations(context, plan)

            if self.config.token_budget and context.total_tokens_used >= self.config.token_budget:
                return self._handle_token_budget_exceeded(context, plan)

            # Build revision request
            revision = RevisionRequest.from_verdict(verdict)
            context.add_revision_request(revision)

            self.logger.debug(
                f"Refinement needed (score: {verdict.score:.1f}, status: {verdict.status.value})"
            )

        # Should never reach here (loop should exit via termination)
        # Assert plan exists (loop runs at least once due to max_iterations >= 1)
        assert plan is not None, "Plan should exist after at least one iteration"
        return self._handle_max_iterations(context, plan)

    def _prepare_planner_variables(
        self, initial_vars: dict[str, Any], context: IterationContext, iteration: int
    ) -> dict[str, Any]:
        """Prepare variables for planner prompt.

        Args:
            initial_vars: Initial variables
            context: Iteration context
            iteration: Current iteration number

        Returns:
            Variables dict for planner
        """
        variables = initial_vars.copy()

        if self.config.include_feedback_in_prompt and iteration > 0:
            variables["feedback"] = self.feedback.format_for_prompt()
            variables["iteration"] = iteration
            variables["revision_request"] = (
                context.revision_requests[-1] if context.revision_requests else None
            )

        return variables

    def _prepare_judge_variables(
        self, plan: TPlan, initial_vars: dict[str, Any], iteration: int
    ) -> dict[str, Any]:
        """Prepare variables for judge prompt.

        Args:
            plan: Plan to judge
            initial_vars: Initial variables
            iteration: Current iteration number

        Returns:
            Variables dict for judge
        """
        # Start with initial vars (includes context like audio_profile, etc.)
        variables = initial_vars.copy()

        # Add/override with judge-specific vars
        variables.update(
            {
                "plan": plan,
                "iteration": iteration,
            }
        )
        
        # Only alias macro_plan = plan for MacroPlanner judge
        # For other judges, macro_plan should come from initial_vars if present
        if "macro_plan" not in variables:
            variables["macro_plan"] = plan  # Fallback for MacroPlanner judge

        return variables

    def _handle_planner_failure(
        self, context: IterationContext, result: AgentResult
    ) -> IterationResult[TPlan]:
        """Handle planner failure.

        Args:
            context: Iteration context
            result: Failed agent result

        Returns:
            IterationResult with failure
        """
        context.update_state(IterationState.FAILED)
        context.termination_reason = f"Planner failed: {result.error_message}"

        return IterationResult(
            success=False,
            plan=None,
            context=context,
            error_message=context.termination_reason,
        )

    def _handle_judge_failure(
        self, context: IterationContext, plan: TPlan, result: AgentResult
    ) -> IterationResult[TPlan]:
        """Handle judge failure.

        Args:
            context: Iteration context
            plan: Plan that was being judged
            result: Failed agent result

        Returns:
            IterationResult with failure
        """
        context.update_state(IterationState.FAILED)
        context.termination_reason = f"Judge failed: {result.error_message}"

        return IterationResult(
            success=False,
            plan=plan,
            context=context,
            error_message=context.termination_reason,
        )

    def _handle_max_iterations(
        self, context: IterationContext, plan: TPlan
    ) -> IterationResult[TPlan]:
        """Handle max iterations reached.

        Args:
            context: Iteration context
            plan: Last plan generated

        Returns:
            IterationResult with failure
        """
        context.update_state(IterationState.MAX_ITERATIONS_REACHED)
        context.termination_reason = (
            f"Max iterations ({self.config.max_iterations}) reached without approval"
        )

        return IterationResult(
            success=False,
            plan=plan,
            context=context,
            error_message=context.termination_reason,
        )

    def _handle_token_budget_exceeded(
        self, context: IterationContext, plan: TPlan
    ) -> IterationResult[TPlan]:
        """Handle token budget exceeded.

        Args:
            context: Iteration context
            plan: Last plan generated

        Returns:
            IterationResult with failure
        """
        context.update_state(IterationState.TOKEN_BUDGET_EXCEEDED)
        context.termination_reason = (
            f"Token budget ({self.config.token_budget}) exceeded "
            f"(used: {context.total_tokens_used})"
        )

        return IterationResult(
            success=False,
            plan=plan,
            context=context,
            error_message=context.termination_reason,
        )
