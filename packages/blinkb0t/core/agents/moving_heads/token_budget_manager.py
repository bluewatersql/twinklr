"""Token budget tracking and enforcement.

Tracks token usage across agent stages and enforces limits.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.agents.moving_heads.context import Stage
from blinkb0t.core.config.models import JobConfig

logger = logging.getLogger(__name__)


class StageTokenUsage(BaseModel):
    """Token usage for a single stage.

    Converted from dataclass to Pydantic for validation and serialization.
    Note: @property methods work with Pydantic models.
    """

    stage: Stage = Field(description="Stage that used tokens")
    input_tokens: int = Field(ge=0, description="Number of input tokens")
    output_tokens: int = Field(ge=0, description="Number of output tokens")
    total_tokens: int = Field(ge=0, description="Total tokens (input + output)")

    model_config = ConfigDict(frozen=True, extra="forbid")

    @property
    def cost_estimate_usd(self) -> float:
        """Estimate cost in USD (gpt-5.2 pricing).

        Rough estimate:
        - Input: $5 per 1M tokens
        - Output: $15 per 1M tokens

        Returns:
            Estimated cost in USD
        """
        input_cost = (self.input_tokens / 1_000_000) * 5.0
        output_cost = (self.output_tokens / 1_000_000) * 15.0
        return input_cost + output_cost


class BudgetStatus(BaseModel):
    """Current budget status.

    Converted from dataclass to Pydantic for validation and serialization.
    """

    total_used: int = Field(ge=0, description="Total tokens used so far")
    total_budget: int = Field(ge=0, description="Total token budget")
    remaining: int = Field(description="Remaining tokens (can be negative if exceeded)")
    used_pct: float = Field(ge=0.0, description="Percentage of budget used (can exceed 100%)")
    can_continue: bool = Field(description="Whether we can continue within budget")
    predicted_total: int | None = Field(
        default=None, ge=0, description="Predicted total token usage"
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


class TokenBudgetReport(BaseModel):
    """Complete token budget report.

    Converted from dataclass to Pydantic for validation and serialization.
    """

    stage_usage: list[StageTokenUsage] = Field(
        default_factory=list, description="Token usage per stage"
    )
    total_used: int = Field(default=0, ge=0, description="Total tokens used")
    total_budget: int = Field(default=0, ge=0, description="Total token budget")
    budget_exceeded: bool = Field(default=False, description="Whether budget was exceeded")
    iterations: int = Field(default=0, ge=0, description="Number of iterations")

    model_config = ConfigDict(frozen=False, extra="forbid")  # Allow mutation for building report

    @property
    def total_cost_estimate_usd(self) -> float:
        """Total cost estimate.

        Returns:
            Total estimated cost in USD
        """
        return sum(stage.cost_estimate_usd for stage in self.stage_usage)


class BudgetExceededError(Exception):
    """Raised when token budget is exceeded."""

    pass


class TokenBudgetManager:
    """Manages token budget tracking and enforcement.

    Tracks tokens used across agent pipeline and enforces limits.

    Example:
        manager = TokenBudgetManager(job_config=job_config)

        # Record stage usage
        manager.record_stage(
            stage=Stage.PLAN,
            input_tokens=4000,
            output_tokens=1500
        )

        # Check if can continue
        status = manager.get_status()
        if not status.can_continue:
            print("Budget exhausted!")

        # Check if retry is affordable
        if manager.can_afford_retry(stage=Stage.PLAN):
            print("Can retry planning")
        else:
            print("Not enough budget for retry")
    """

    def __init__(self, job_config: JobConfig):
        """Initialize token budget manager.

        Args:
            job_config: Job configuration with agent config
        """
        self.job_config = job_config
        self.agent_config = job_config.agent

        # Budget settings (using actual field names from AgentOrchestrationConfig)
        self.total_budget = self.agent_config.token_budget
        self.enforce_budget = self.agent_config.enforce_token_budget
        self.buffer_pct = self.agent_config.token_buffer_pct

        # Usage tracking
        self.stage_usage: list[StageTokenUsage] = []
        self.total_used = 0
        self.iterations = 0

        # Stage estimates (for prediction)
        self.stage_estimates = {
            Stage.PLAN: 5500,
            Stage.VALIDATE: 0,  # No LLM call
            Stage.IMPLEMENTATION: 8500,
            Stage.JUDGE: 6500,
            Stage.REFINEMENT: 7000,
        }

        logger.debug(
            f"TokenBudgetManager initialized: "
            f"budget={self.total_budget}, enforce={self.enforce_budget}"
        )

    def record_stage(self, stage: Stage, input_tokens: int, output_tokens: int) -> None:
        """Record token usage for a stage.

        Args:
            stage: Stage that was executed
            input_tokens: Input tokens used
            output_tokens: Output tokens generated

        Raises:
            BudgetExceededError: If budget exceeded and enforcement enabled
        """
        total_tokens = input_tokens + output_tokens

        # Record usage
        usage = StageTokenUsage(
            stage=stage,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        self.stage_usage.append(usage)
        self.total_used += total_tokens

        logger.info(
            f"Stage {stage.value}: {total_tokens} tokens "
            f"(in={input_tokens}, out={output_tokens}), "
            f"total used={self.total_used}/{self.total_budget}"
        )

        # Check budget
        if self.enforce_budget and self.total_used > self.total_budget:
            raise BudgetExceededError(
                f"Token budget exceeded: used {self.total_used}, budget {self.total_budget}"
            )
        elif self.total_used > self.total_budget:
            logger.warning(
                f"Token budget exceeded (warning only): "
                f"used {self.total_used}, budget {self.total_budget}"
            )

    def get_status(self) -> BudgetStatus:
        """Get current budget status.

        Returns:
            BudgetStatus with usage and remaining budget
        """
        remaining = self.total_budget - self.total_used
        used_pct = (self.total_used / self.total_budget) * 100 if self.total_budget > 0 else 0
        can_continue = remaining > 0 or not self.enforce_budget

        return BudgetStatus(
            total_used=self.total_used,
            total_budget=self.total_budget,
            remaining=remaining,
            used_pct=used_pct,
            can_continue=can_continue,
        )

    def can_afford_retry(self, stage: Stage) -> bool:
        """Check if retry is affordable.

        Args:
            stage: Stage to retry

        Returns:
            True if retry is affordable, False otherwise
        """
        estimate = self.stage_estimates[stage]

        # Add buffer
        estimate_with_buffer = int(estimate * (1 + self.buffer_pct))

        remaining = self.total_budget - self.total_used

        can_afford = remaining >= estimate_with_buffer

        logger.debug(
            f"Retry affordability check: stage={stage.value}, "
            f"estimate={estimate_with_buffer}, remaining={remaining}, "
            f"affordable={can_afford}"
        )

        return can_afford

    def predict_remaining_cost(
        self, remaining_stages: list[Stage], include_buffer: bool = True
    ) -> int:
        """Predict token cost for remaining stages.

        Args:
            remaining_stages: Stages yet to execute
            include_buffer: Whether to include buffer

        Returns:
            Predicted token cost
        """
        total_estimate = sum(self.stage_estimates[stage] for stage in remaining_stages)

        if include_buffer:
            total_estimate = int(total_estimate * (1 + self.buffer_pct))

        return total_estimate

    def get_report(self) -> TokenBudgetReport:
        """Get complete budget report.

        Returns:
            TokenBudgetReport with all usage data
        """
        return TokenBudgetReport(
            stage_usage=self.stage_usage.copy(),
            total_used=self.total_used,
            total_budget=self.total_budget,
            budget_exceeded=self.total_used > self.total_budget,
            iterations=self.iterations,
        )

    def increment_iteration(self) -> None:
        """Increment iteration counter."""
        self.iterations += 1
        logger.debug(f"Iteration incremented: {self.iterations}")

    def reset(self) -> None:
        """Reset budget tracking (for testing)."""
        self.stage_usage.clear()
        self.total_used = 0
        self.iterations = 0
        logger.debug("Budget tracking reset")
