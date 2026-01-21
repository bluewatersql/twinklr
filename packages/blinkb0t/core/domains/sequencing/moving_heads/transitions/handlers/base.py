"""Base transition handler interface.

Follows established MovementResolver pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement

    from ..context import TransitionContext


class TransitionHandler(ABC):
    """Interface for transition handlers.

    Handlers implement specific transition modes (SNAP, CROSSFADE, etc.)
    and generate appropriate EffectPlacements.

    Follows same pattern as MovementResolver.
    """

    @abstractmethod
    def render(self, context: TransitionContext) -> list[EffectPlacement]:
        """Render transition effects.

        Args:
            context: Transition context with all dependencies

        Returns:
            List of EffectPlacement objects for transition
        """
        pass
