"""Stage execution coordinator with error handling and retry logic.

Extracted from orchestrator.py to reduce complexity and improve maintainability.
Handles standardized stage execution, error handling, token tracking, and logging.
"""

from __future__ import annotations

import logging
from typing import Any

from blinkb0t.core.agents.moving_heads.context import Stage
from blinkb0t.core.agents.moving_heads.heuristic_validator import HeuristicValidator
from blinkb0t.core.agents.moving_heads.implementation_expander import ImplementationExpander
from blinkb0t.core.agents.moving_heads.judge_critic import JudgeCritic
from blinkb0t.core.agents.moving_heads.plan_generator import PlanGenerator
from blinkb0t.core.agents.moving_heads.refinement_agent import RefinementAgent
from blinkb0t.core.agents.moving_heads.token_budget_manager import TokenBudgetManager

logger = logging.getLogger(__name__)


class StageCoordinator:
    """Coordinates individual stage executions with standardized error handling.

    Responsibilities:
    - Execute individual agent stages
    - Handle errors and logging consistently
    - Record token usage
    - Provide clean interface for orchestrator

    This class extracts the stage execution logic from AgentOrchestrator,
    reducing orchestrator complexity while maintaining functionality.
    """

    def __init__(
        self,
        plan_generator: PlanGenerator,
        judge_critic: JudgeCritic,
        token_manager: TokenBudgetManager,
        implementation_expander: ImplementationExpander | None = None,
        refinement_agent: RefinementAgent | None = None,
    ):
        """Initialize stage coordinator.

        Args:
            plan_generator: Plan generation agent
            judge_critic: Judge/evaluation agent
            token_manager: Token budget manager
            implementation_expander: Optional implementation expander (set later)
            refinement_agent: Optional refinement agent (set later)
        """
        self.plan_generator = plan_generator
        self.judge_critic = judge_critic
        self.token_manager = token_manager
        self.implementation_expander = implementation_expander
        self.refinement_agent = refinement_agent

        # Store messages for conversational refinement
        self.last_plan_messages: list[dict[str, str]] | None = None
        self.last_implementation_messages: list[dict[str, str]] | None = None

    def set_implementation_expander(self, expander: ImplementationExpander) -> None:
        """Set implementation expander (initialized after coordinator creation)."""
        self.implementation_expander = expander

    def set_refinement_agent(self, agent: RefinementAgent) -> None:
        """Set refinement agent (initialized after coordinator creation)."""
        self.refinement_agent = agent

    def execute_plan_stage(
        self,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any] | None,
        template_metadata: list[dict[str, Any]],
    ) -> Any | None:
        """Stage 1: Generate plan.

        Args:
            song_features: Song features
            seq_fingerprint: Optional sequence fingerprint
            template_metadata: Template metadata

        Returns:
            AgentPlan or None if failed
        """
        logger.info("\n--- Stage 1: Plan Generation ---")

        result = self.plan_generator.generate_plan(
            song_features=song_features,
            seq_fingerprint=seq_fingerprint or {},
            template_metadata=template_metadata,
        )

        if not result.success:
            logger.error(f"Plan generation failed: {result.error}")
            return None

        # Store original messages for refinement
        self.last_plan_messages = result.original_messages

        # Record tokens
        self.token_manager.record_stage(
            Stage.PLAN,
            result.tokens_used // 2,  # Estimate input
            result.tokens_used // 2,  # Estimate output
        )

        if result.plan:
            logger.info(
                f"Plan generated: {len(result.plan.sections)} sections, {result.tokens_used} tokens"
            )

        return result.plan

    def execute_validation_stage(self, plan: Any, validator: HeuristicValidator) -> bool:
        """Stage 2: Heuristic validation.

        Args:
            plan: AgentPlan to validate
            validator: HeuristicValidator instance

        Returns:
            True if validation passed, False otherwise
        """
        logger.info("\n--- Stage 2: Heuristic Validation ---")

        validation = validator.validate(plan)

        if validation.passed:
            logger.info("✅ Validation PASSED")
            return True
        else:
            logger.warning(
                f"❌ Validation FAILED: {validation.error_count} errors\n"
                f"{validation.get_error_summary()}"
            )
            return False

    def execute_implementation_stage(
        self,
        plan: Any,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any] | None,
        template_metadata: list[dict[str, Any]],
    ) -> Any | None:
        """Stage 3: Implementation expansion.

        Args:
            plan: AgentPlan
            song_features: Song features
            seq_fingerprint: Optional sequence fingerprint
            template_metadata: Template metadata

        Returns:
            AgentImplementation or None if failed
        """
        logger.info("\n--- Stage 3: Implementation Expansion ---")

        if self.implementation_expander is None:
            logger.error("Implementation expander not initialized")
            return None

        result = self.implementation_expander.expand_implementation(
            plan=plan,
            song_features=song_features,
            seq_fingerprint=seq_fingerprint or {},
            template_metadata=template_metadata,
        )

        if not result.success:
            logger.error(f"Implementation expansion failed: {result.error}")
            return None

        # Store original messages for refinement
        self.last_implementation_messages = result.original_messages

        # Record tokens
        self.token_manager.record_stage(
            Stage.IMPLEMENTATION, result.tokens_used // 2, result.tokens_used // 2
        )

        if result.implementation:
            logger.info(
                f"Implementation expanded: {len(result.implementation.sections)} sections, "
                f"{result.tokens_used} tokens"
            )

        return result.implementation

    def execute_judge_stage(
        self, plan: Any, implementation: Any, song_features: dict[str, Any]
    ) -> Any | None:
        """Stage 4: Judge/evaluation.

        Args:
            plan: AgentPlan
            implementation: AgentImplementation
            song_features: Song features

        Returns:
            Evaluation or None if failed
        """
        logger.info("\n--- Stage 4: Judge/Evaluation ---")

        result = self.judge_critic.evaluate(
            plan=plan, implementation=implementation, song_features=song_features
        )

        if not result.success:
            logger.error(f"Evaluation failed: {result.error}")
            return None

        # Record tokens
        self.token_manager.record_stage(
            Stage.JUDGE, result.tokens_used // 2, result.tokens_used // 2
        )

        if result.evaluation:
            logger.info(
                f"Evaluation: {result.evaluation.overall_score:.1f}/100 "
                f"({'PASS' if result.evaluation.pass_threshold else 'FAIL'}), "
                f"{result.tokens_used} tokens"
            )

        return result.evaluation

    def execute_refinement_stage(
        self,
        plan: Any,
        implementation: Any,
        evaluation: Any,
        song_features: dict[str, Any],
        seq_fingerprint: dict[str, Any] | None,
        template_metadata: list[dict[str, Any]],
    ) -> Any | None:
        """Stage 5: Refinement.

        Args:
            plan: AgentPlan
            implementation: AgentImplementation
            evaluation: Evaluation
            song_features: Song features
            seq_fingerprint: Optional sequence fingerprint
            template_metadata: Template metadata

        Returns:
            RefinementResult or None if failed
        """
        logger.info("\n--- Stage 5: Refinement ---")

        # Check budget before refining
        if not self.token_manager.can_afford_retry(Stage.REFINEMENT):
            logger.warning("Budget exhausted, cannot refine")
            return None

        if self.refinement_agent is None:
            logger.error("Refinement agent not initialized")
            return None

        result = self.refinement_agent.refine(
            plan=plan,
            implementation=implementation,
            evaluation=evaluation,
            failure_analysis=None,  # Will analyze internally
            song_features=song_features,
            seq_fingerprint=seq_fingerprint or {},
            template_metadata=template_metadata,
            plan_original_messages=self.last_plan_messages,
            implementation_original_messages=self.last_implementation_messages,
        )

        if not result.success:
            logger.error(f"Refinement failed: {result.error}")
            return None

        # Record tokens
        self.token_manager.record_stage(
            Stage.REFINEMENT, result.tokens_used // 2, result.tokens_used // 2
        )

        logger.info(
            f"Refinement complete: strategy={result.strategy.value}, {result.tokens_used} tokens"
        )

        return result
