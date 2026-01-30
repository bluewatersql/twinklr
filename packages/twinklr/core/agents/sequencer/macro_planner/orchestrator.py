"""Orchestrator for MacroPlanner choreography generation.

Coordinates the multi-agent pipeline using StandardIterationController:
Planner -> Heuristic Validation -> Judge with iteration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
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

logger = logging.getLogger(__name__)


@dataclass
class MacroPlannerConfig:
    """Configuration for MacroPlanner orchestration."""

    max_iterations: int = 5
    token_budget: int | None = None
    prompt_base_path: Path | None = None
    llm_logger: LLMCallLogger | None = None

    def __post_init__(self) -> None:
        """Initialize defaults."""
        if self.prompt_base_path is None:
            # Default to prompts directory next to this file
            self.prompt_base_path = Path(__file__).parent / "prompts"

        if self.llm_logger is None:
            self.llm_logger = NullLLMCallLogger()


class MacroPlannerOrchestrator:
    """Orchestrates MacroPlanner multi-agent choreography generation.

    Pipeline:
    1. Planner (conversational) - generates high-level choreography plan
    2. Heuristic Validator - fast pre-checks
    3. Judge (LLM) - evaluates quality with 4-dimension rubric
    4. Iterate on SOFT_FAIL or HARD_FAIL until APPROVE or max iterations

    Uses StandardIterationController for iteration management.

    Example:
        provider = OpenAIProvider(api_key=api_key)
        config = MacroPlannerConfig(max_iterations=5)
        orch = MacroPlannerOrchestrator(provider=provider, config=config)

        result = await orch.orchestrate_async(audio_profile)
        if result.success:
            print(f"Generated plan in {result.context.current_iteration} iterations")
    """

    def __init__(self, provider: LLMProvider, config: MacroPlannerConfig):
        """Initialize orchestrator.

        Args:
            provider: LLM provider for agent execution
            config: Orchestration configuration
        """
        self.provider = provider
        self.config = config
        self.llm_logger = config.llm_logger or NullLLMCallLogger()

        # Create heuristic validator
        self.heuristic_validator = MacroPlanHeuristicValidator()

    async def orchestrate_async(
        self,
        audio_profile: AudioProfileModel,
    ) -> IterationResult[MacroPlan]:
        """Execute orchestration pipeline asynchronously.

        Args:
            audio_profile: AudioProfileModel from Phase 1

        Returns:
            Iteration result with plan, metrics, and status
        """
        logger.info("Starting MacroPlanner orchestration")

        try:
            return await self._orchestrate_impl(audio_profile)
        finally:
            # Flush LLM logs on completion (success or failure)
            try:
                await self.llm_logger.flush_async()
                logger.debug("Flushed LLM call logs")
            except Exception as e:
                logger.warning(f"Failed to flush LLM logs: {e}")

    async def _orchestrate_impl(
        self,
        audio_profile: AudioProfileModel,
    ) -> IterationResult[MacroPlan]:
        """Internal orchestration implementation.

        Args:
            audio_profile: AudioProfileModel from Phase 1

        Returns:
            Iteration result
        """
        # Get agent specs
        planner_spec = get_planner_spec(token_budget=self.config.token_budget)
        judge_spec = get_judge_spec(token_budget=self.config.token_budget)

        # Create iteration config
        iteration_config = IterationConfig(
            max_iterations=self.config.max_iterations,
            token_budget=self.config.token_budget,
        )

        # Create feedback manager
        feedback_manager = FeedbackManager()

        # Create iteration controller
        controller: StandardIterationController[MacroPlan] = StandardIterationController(
            config=iteration_config,
            feedback_manager=feedback_manager,
            checkpoint_manager=None,  # No checkpoints for now
        )

        # Prepare initial variables (context for planner)
        initial_variables = {
            "audio_profile": audio_profile.model_dump(mode="python"),
        }

        # Validator function (returns list of error strings)
        def validator(plan: MacroPlan) -> list[str]:
            issues = self.heuristic_validator.validate(plan)
            return [f"{issue.message} (fix: {issue.fix_hint})" for issue in issues]

        # Run iteration loop
        logger.info(f"Running iteration loop (max {self.config.max_iterations} iterations)")
        result = await controller.run(
            planner_spec=planner_spec,
            judge_spec=judge_spec,
            initial_variables=initial_variables,
            validator=validator,
            provider=self.provider,
            llm_logger=self.llm_logger,
        )

        logger.info(
            f"Orchestration complete: {result.context.state.value}, "
            f"{result.context.current_iteration} iterations, "
            f"{result.context.total_tokens_used} tokens"
        )

        return result
