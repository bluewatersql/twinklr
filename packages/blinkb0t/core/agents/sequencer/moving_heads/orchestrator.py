"""Orchestrator for moving heads choreography generation.

Coordinates the multi-agent pipeline: Planner -> Validator -> Judge with iteration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from blinkb0t.core.agents.feedback import FeedbackManager
from blinkb0t.core.agents.providers.base import LLMProvider
from blinkb0t.core.agents.runner import AgentRunner
from blinkb0t.core.agents.sequencer.moving_heads.context_shaper import (
    MovingHeadContextShaper,
)
from blinkb0t.core.agents.sequencer.moving_heads.heuristic_validator import (
    HeuristicValidator,
)
from blinkb0t.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    JudgeDecision,
    JudgeResponse,
    ValidationResponse,
)
from blinkb0t.core.agents.sequencer.moving_heads.specs import (
    get_judge_spec,
    get_planner_spec,
    get_validator_spec,
)
from blinkb0t.core.agents.state import AgentState
from blinkb0t.core.agents.state_machine import (
    OrchestrationState,
    OrchestrationStateMachine,
)

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationConfig:
    """Configuration for choreography orchestration."""

    max_iterations: int = 3
    token_budget: int | None = None
    prompt_base_path: Path | None = None
    context_shaper: MovingHeadContextShaper | None = None
    checkpoint_manager: Any | None = None  # CheckpointManager from core.utils.checkpoint

    def __post_init__(self) -> None:
        """Initialize defaults."""
        if self.prompt_base_path is None:
            # Default to prompts directory next to this file
            self.prompt_base_path = Path(__file__).parent / "prompts"

        if self.context_shaper is None:
            self.context_shaper = MovingHeadContextShaper()


@dataclass
class OrchestrationResult:
    """Result of orchestration."""

    success: bool
    plan: ChoreographyPlan | None
    iterations: int
    total_tokens: int
    duration_seconds: float
    final_state: OrchestrationState
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Orchestrator:
    """Orchestrates multi-agent choreography generation.

    Pipeline:
    1. Planner (conversational) - generates choreography
    2. Heuristic Validator - fast pre-checks
    3. Validator (LLM) - validates completeness/correctness
    4. Judge (LLM) - evaluates quality
    5. Iterate on SOFT_FAIL or HARD_FAIL until APPROVE or max iterations

    Example:
        provider = OpenAIProvider(api_key=api_key)
        config = OrchestrationConfig(max_iterations=3)
        orch = Orchestrator(provider=provider, config=config)

        result = orch.orchestrate(context)
        if result.success:
            print(f"Generated plan in {result.iterations} iterations")
    """

    def __init__(self, provider: LLMProvider, config: OrchestrationConfig):
        """Initialize orchestrator.

        Args:
            provider: LLM provider for agent execution
            config: Orchestration configuration
        """
        self.provider = provider
        self.config = config
        self.runner = AgentRunner(
            provider=provider,
            prompt_base_path=config.prompt_base_path or Path(__file__).parent / "prompts",
        )
        self.state_machine = OrchestrationStateMachine()
        self.feedback_manager = FeedbackManager()
        self.checkpoint_manager = config.checkpoint_manager

    def orchestrate(self, context: dict[str, Any]) -> OrchestrationResult:
        """Execute orchestration pipeline.

        Args:
            context: Choreography context (song structure, fixtures, templates, etc.)

        Returns:
            Orchestration result with plan, metrics, and status
        """
        logger.info("Starting orchestration")

        # Initialize state machine
        self.state_machine.transition(OrchestrationState.PLANNING)

        # Get agent specs
        planner_spec = get_planner_spec(token_budget=self.config.token_budget)
        validator_spec = get_validator_spec()
        judge_spec = get_judge_spec()

        # Initialize planner state (conversational)
        planner_state = AgentState(name="planner")

        # Track metrics
        total_duration = 0.0
        total_tokens = 0
        iterations = 0
        best_plan: ChoreographyPlan | None = None
        best_score = 0.0

        # Heuristic validator
        heuristic_validator = HeuristicValidator(
            available_templates=context.get("available_templates", []),
            song_structure=context.get("song_structure", {}),
        )

        # Shape context
        shaped = self.config.context_shaper.shape(context=context)  # type: ignore
        shaped_context = shaped.data

        # Iteration loop
        while iterations < self.config.max_iterations:
            # Check budget before starting iteration
            if self.config.token_budget and total_tokens >= self.config.token_budget:
                logger.warning(f"Token budget exhausted: {total_tokens}/{self.config.token_budget}")
                self.state_machine.transition(
                    OrchestrationState.BUDGET_EXHAUSTED,
                    duration_seconds=total_duration,
                    tokens_consumed=total_tokens,
                )
                break

            iterations += 1
            iteration_tokens = 0
            logger.info(f"Starting iteration {iterations}/{self.config.max_iterations}")

            # Prepare planner variables
            planner_vars = {
                "context": shaped_context,
                "feedback": self.feedback_manager.format_for_prompt(),
            }

            # 1. Run planner
            logger.info("Running planner agent")
            planner_result = self.runner.run(
                spec=planner_spec,
                variables=planner_vars,
                state=planner_state,
            )

            iteration_tokens += planner_result.tokens_used
            total_duration += planner_result.duration_seconds

            if not planner_result.success:
                logger.error(f"Planner failed: {planner_result.error_message}")
                self.state_machine.transition(
                    OrchestrationState.FAILED,
                    duration_seconds=total_duration,
                    tokens_consumed=iteration_tokens,
                )
                return OrchestrationResult(
                    success=False,
                    plan=None,
                    iterations=iterations,
                    total_tokens=total_tokens + iteration_tokens,
                    duration_seconds=total_duration,
                    final_state=OrchestrationState.FAILED,
                    error_message=f"Planner failed: {planner_result.error_message}",
                )

            plan = planner_result.data
            assert isinstance(plan, ChoreographyPlan), "Planner must return ChoreographyPlan"

            # Save raw plan checkpoint
            if self.checkpoint_manager:
                from blinkb0t.core.utils.checkpoint import CheckpointType

                self.checkpoint_manager.write_checkpoint(CheckpointType.RAW, plan.model_dump())
                logger.debug(f"Saved RAW checkpoint for iteration {iterations}")

            # 2. Heuristic validation
            logger.info("Running heuristic validator")
            heuristic_result = heuristic_validator.validate(plan)

            if not heuristic_result.valid:
                logger.warning(
                    f"Heuristic validation failed: {len(heuristic_result.errors)} errors"
                )
                # Add errors to feedback
                for error in heuristic_result.errors:
                    self.feedback_manager.add_validation_failure(error, iteration=iterations)

                # Continue to next iteration with feedback (no state transition needed - already in PLANNING)
                total_tokens += iteration_tokens
                continue

            # Add warnings to feedback (non-blocking)
            for warning in heuristic_result.warnings:
                self.feedback_manager.add_judge_soft_failure(warning, iteration=iterations)

            # 3. LLM Validator
            logger.info("Running validator agent")
            self.state_machine.transition(
                OrchestrationState.VALIDATING,
                duration_seconds=total_duration,
                tokens_consumed=iteration_tokens,
            )

            validator_vars = {
                "plan": plan.model_dump(),
                "context": shaped_context,
            }

            validator_result = self.runner.run(
                spec=validator_spec,
                variables=validator_vars,
            )

            iteration_tokens += validator_result.tokens_used
            total_duration += validator_result.duration_seconds

            if not validator_result.success:
                logger.warning(f"Validator agent failed: {validator_result.error_message}")
                self.feedback_manager.add_validation_failure(
                    f"Validator error: {validator_result.error_message}", iteration=iterations
                )
                total_tokens += iteration_tokens
                # Transition back to planning
                self.state_machine.transition(
                    OrchestrationState.PLANNING,
                    duration_seconds=total_duration,
                    tokens_consumed=iteration_tokens,
                )
                continue

            validation_response = validator_result.data
            assert isinstance(validation_response, ValidationResponse), (
                "Validator must return ValidationResponse"
            )

            if not validation_response.valid:
                logger.warning(f"Validation failed: {len(validation_response.errors)} errors")
                # Add errors to feedback
                for validation_error in validation_response.errors:
                    self.feedback_manager.add_validation_failure(
                        validation_error.message, iteration=iterations
                    )
                total_tokens += iteration_tokens
                # Transition back to planning
                self.state_machine.transition(
                    OrchestrationState.PLANNING,
                    duration_seconds=total_duration,
                    tokens_consumed=iteration_tokens,
                )
                continue

            # 4. Judge
            logger.info("Running judge agent")
            self.state_machine.transition(
                OrchestrationState.JUDGING,
                duration_seconds=total_duration,
                tokens_consumed=iteration_tokens,
            )

            judge_vars = {
                "plan": plan.model_dump(),
                "context": shaped_context,
                "iteration": iterations,
                "previous_feedback": self.feedback_manager.format_for_prompt(),
            }

            judge_result = self.runner.run(
                spec=judge_spec,
                variables=judge_vars,
            )

            iteration_tokens += judge_result.tokens_used
            total_duration += judge_result.duration_seconds
            total_tokens += iteration_tokens

            if not judge_result.success:
                logger.warning(f"Judge agent failed: {judge_result.error_message}")
                # Keep plan as best attempt
                if best_plan is None:
                    best_plan = plan
                continue

            judge_response = judge_result.data
            assert isinstance(judge_response, JudgeResponse), "Judge must return JudgeResponse"

            # Track best plan
            if judge_response.score > best_score:
                best_score = judge_response.score
                best_plan = plan

            # Save evaluation checkpoint
            if self.checkpoint_manager:
                from blinkb0t.core.utils.checkpoint import CheckpointType

                self.checkpoint_manager.write_checkpoint(
                    CheckpointType.EVALUATION, judge_response.model_dump()
                )
                logger.debug(f"Saved EVALUATION checkpoint for iteration {iterations}")

            # Handle judge decision
            if judge_response.decision == JudgeDecision.APPROVE:
                logger.info(f"Judge approved plan with score {judge_response.score}")

                # Save final approved plan checkpoint
                if self.checkpoint_manager:
                    self.checkpoint_manager.write_checkpoint(
                        CheckpointType.FINAL,
                        {
                            "status": "SUCCESS",
                            "plan": plan.model_dump(),
                            "evaluation": judge_response.model_dump(),
                            "iterations": iterations,
                            "total_tokens": total_tokens,
                            "duration_seconds": total_duration,
                        },
                    )
                    logger.debug("Saved FINAL checkpoint")

                self.state_machine.transition(
                    OrchestrationState.SUCCEEDED,
                    duration_seconds=total_duration,
                    tokens_consumed=iteration_tokens,
                )
                return OrchestrationResult(
                    success=True,
                    plan=plan,
                    iterations=iterations,
                    total_tokens=total_tokens,
                    duration_seconds=total_duration,
                    final_state=OrchestrationState.SUCCEEDED,
                    metadata={"final_score": judge_response.score},
                )

            elif judge_response.decision == JudgeDecision.SOFT_FAIL:
                logger.info(f"Judge soft fail (score {judge_response.score}), iterating")
                self.feedback_manager.add_judge_soft_failure(
                    judge_response.feedback_for_planner, iteration=iterations
                )

                # Transition back to planning
                self.state_machine.transition(
                    OrchestrationState.PLANNING,
                    duration_seconds=total_duration,
                    tokens_consumed=iteration_tokens,
                )

            elif judge_response.decision == JudgeDecision.HARD_FAIL:
                logger.warning(f"Judge hard fail (score {judge_response.score})")
                self.feedback_manager.add_judge_hard_failure(
                    judge_response.feedback_for_planner, iteration=iterations
                )
                # Transition back to planning
                self.state_machine.transition(
                    OrchestrationState.PLANNING,
                    duration_seconds=total_duration,
                    tokens_consumed=iteration_tokens,
                )

        # Max iterations reached without approval
        logger.warning(f"Max iterations ({self.config.max_iterations}) reached without approval")

        # Save best attempt as final checkpoint
        if self.checkpoint_manager and best_plan:
            from blinkb0t.core.utils.checkpoint import CheckpointType

            self.checkpoint_manager.write_checkpoint(
                CheckpointType.FINAL,
                {
                    "status": "INCOMPLETE",
                    "plan": best_plan.model_dump(),
                    "iterations": iterations,
                    "total_tokens": total_tokens,
                    "duration_seconds": total_duration,
                    "best_score": best_score,
                    "reason": "Max iterations reached without approval",
                },
            )
            logger.debug("Saved FINAL checkpoint (best attempt)")

        final_state = self.state_machine.current_state
        if final_state != OrchestrationState.BUDGET_EXHAUSTED:
            final_state = OrchestrationState.FAILED

        return OrchestrationResult(
            success=False,
            plan=best_plan,
            iterations=iterations,
            total_tokens=total_tokens,
            duration_seconds=total_duration,
            final_state=final_state,
            error_message=f"Max iterations ({self.config.max_iterations}) reached without approval",
            metadata={"best_score": best_score},
        )
