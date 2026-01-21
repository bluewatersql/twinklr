"""SNAP transition handler - instant cut with no blending.

Follows established handler pattern.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import TransitionHandler

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement

    from ..context import TransitionContext

logger = logging.getLogger(__name__)


class SnapHandler(TransitionHandler):
    """Handler for SNAP transitions (instant cut).

    No blending needed - steps are independent.
    Returns empty list as no transition effects are generated.
    """

    def render(self, context: TransitionContext) -> list[EffectPlacement]:
        """Render SNAP transition (no-op).

        Args:
            context: Transition context

        Returns:
            Empty list (no transition effects needed)
        """
        logger.debug(
            f"SNAP transition at {context.start_ms}ms for fixture {context.fixture_id} - no effects"
        )
        return []
