"""Identity context shaper (no reduction)."""

from typing import Any

from blinkb0t.core.agents.context.base import BaseContextShaper, ShapedContext


class IdentityContextShaper(BaseContextShaper):
    """Pass-through context shaper (no reduction).

    Useful for:
    - Testing
    - Agents with small context
    - When shaping not needed
    """

    def shape(
        self, agent: Any, context: dict[str, Any], budget: int | None = None
    ) -> ShapedContext:
        """Return context unchanged.

        Args:
            agent: Agent specification (unused)
            context: Raw context data
            budget: Optional token budget (unused)

        Returns:
            ShapedContext with unchanged data
        """
        tokens = self.estimator.estimate(context)

        return ShapedContext(
            data=context.copy(),
            stats={
                "original_estimate": tokens,
                "shaped_estimate": tokens,
                "reduction_pct": 0.0,
                "notes": ["Identity shaper (no reduction)"],
            },
        )
