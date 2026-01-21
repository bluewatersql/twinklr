"""Registry for transition handlers.

Follows established ResolverRegistry pattern.
"""

from __future__ import annotations

import logging

from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.base import (
    TransitionHandler,
)
from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.crossfade import (
    CrossfadeHandler,
)
from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.fade_through_black import (
    FadeThroughBlackHandler,
)
from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.gap_fill import (
    GapFillHandler,
)
from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.snap import SnapHandler

logger = logging.getLogger(__name__)


class TransitionHandlerRegistry:
    """Registry of transition handlers.

    Routes transition modes to appropriate TransitionHandler instances.
    Follows same pattern as ResolverRegistry.
    """

    def __init__(self) -> None:
        """Initialize registry with built-in handlers."""
        self.handlers: dict[str, TransitionHandler] = {}
        self._register_builtin_handlers()

    def _register_builtin_handlers(self) -> None:
        """Register built-in transition handlers."""
        # Register SNAP handler
        self.handlers["snap"] = SnapHandler()
        logger.debug("Registered SNAP transition handler")

        # Register CROSSFADE handler
        self.handlers["crossfade"] = CrossfadeHandler()
        logger.debug("Registered CROSSFADE transition handler")

        # Register FADE_THROUGH_BLACK handler
        self.handlers["fade_through_black"] = FadeThroughBlackHandler()
        logger.debug("Registered FADE_THROUGH_BLACK transition handler")

        # Register GAP_FILL handler (Phase 3 feature)
        # Pass self so gap_fill can delegate to other handlers
        self.handlers["gap_fill"] = GapFillHandler(handler_registry=self)
        logger.debug("Registered GAP_FILL transition handler (Phase 3)")

    def register(self, mode: str, handler: TransitionHandler) -> None:
        """Register a custom transition handler.

        Args:
            mode: Transition mode name
            handler: Handler instance
        """
        self.handlers[mode] = handler
        logger.debug(f"Registered custom transition handler for mode: {mode}")

    def get_handler(self, mode: str) -> TransitionHandler:
        """Get handler for transition mode.

        Args:
            mode: Transition mode (snap, crossfade, fade_through_black)

        Returns:
            TransitionHandler instance

        Raises:
            ValueError: If mode is unknown
        """
        if mode not in self.handlers:
            raise ValueError(
                f"Unknown transition mode: {mode}. Available modes: {list(self.handlers.keys())}"
            )
        return self.handlers[mode]

    def list_modes(self) -> list[str]:
        """List all registered transition modes.

        Returns:
            List of mode names
        """
        return list(self.handlers.keys())
