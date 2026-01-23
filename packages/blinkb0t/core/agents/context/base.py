"""Base context shaping protocol and utilities."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.agents.context.token_estimator import TokenEstimator

logger = logging.getLogger(__name__)


class ShapedContext(BaseModel):
    """Result of context shaping.

    Contains:
    - Shaped data (reduced/filtered for agent)
    - Statistics about shaping (tokens, reduction %)
    """

    data: dict[str, Any] = Field(description="Shaped context data")

    stats: dict[str, Any] = Field(
        description="Shaping statistics",
        default_factory=lambda: {
            "original_estimate": 0,
            "shaped_estimate": 0,
            "reduction_pct": 0.0,
            "notes": [],
        },
    )

    model_config = ConfigDict(frozen=False)


class ContextShaper(Protocol):
    """Protocol for context shaping.

    Implementations are domain-specific but follow this interface.
    """

    def shape(
        self, agent: Any, context: dict[str, Any], budget: int | None = None
    ) -> ShapedContext:
        """Shape context for agent execution.

        Args:
            agent: Agent specification (for stage-aware shaping)
            context: Raw context data
            budget: Optional token budget for this agent

        Returns:
            ShapedContext with reduced data and stats
        """
        ...


class BaseContextShaper:
    """Base context shaper with common utilities.

    Provides:
    - Token estimation
    - Reduction calculation
    - Logging helpers

    Subclasses implement domain-specific shaping logic.
    """

    def __init__(self) -> None:
        """Initialize base shaper."""
        self.estimator = TokenEstimator()

    def shape(
        self, agent: Any, context: dict[str, Any], budget: int | None = None
    ) -> ShapedContext:
        """Shape context (must be implemented by subclass).

        Args:
            agent: Agent specification
            context: Raw context data
            budget: Optional token budget

        Returns:
            ShapedContext with reduced data
        """
        raise NotImplementedError("Subclass must implement shape()")

    def _calculate_reduction(
        self, original: dict[str, Any], shaped: dict[str, Any]
    ) -> tuple[int, int, float]:
        """Calculate token reduction statistics.

        Args:
            original: Original context
            shaped: Shaped context

        Returns:
            Tuple of (original_tokens, shaped_tokens, reduction_pct)
        """
        original_tokens = self.estimator.estimate(original)
        shaped_tokens = self.estimator.estimate(shaped)

        if original_tokens > 0:
            reduction_pct = ((original_tokens - shaped_tokens) / original_tokens) * 100
        else:
            reduction_pct = 0.0

        return original_tokens, shaped_tokens, reduction_pct

    def _log_shaping(
        self, agent_name: str, original_tokens: int, shaped_tokens: int, reduction_pct: float
    ) -> None:
        """Log shaping statistics.

        Args:
            agent_name: Agent name
            original_tokens: Original token count
            shaped_tokens: Shaped token count
            reduction_pct: Reduction percentage
        """
        logger.info(
            f"Context shaped for {agent_name}: "
            f"{original_tokens} → {shaped_tokens} tokens "
            f"(reduced {reduction_pct:.1f}%)"
        )
