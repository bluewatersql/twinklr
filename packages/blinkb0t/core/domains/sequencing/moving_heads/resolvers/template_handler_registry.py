"""Registry for movement resolvers."""

from __future__ import annotations

import logging

from blinkb0t.core.domains.sequencing.moving_heads.resolvers.context import MovementResolver
from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.default import (
    DefaultMovementHandler,
)

logger = logging.getLogger(__name__)


class ResolverRegistry:
    """Registry of movement resolvers.

    Routes movement patterns to appropriate MovementResolver instances.
    """

    def __init__(self) -> None:
        """Initialize resolver registry."""
        self.resolvers: dict[str, MovementResolver] = {}
        self._register_builtin_resolvers()

    def _register_builtin_resolvers(self) -> None:
        """Register built-in handlers."""
        default_handler = DefaultMovementHandler()
        self.resolvers["default"] = default_handler  # type: ignore[assignment]
        logger.debug("Registered default movement resolver")

    def register(self, pattern: str, resolver: MovementResolver) -> None:
        """Register a resolver for a specific pattern.

        Args:
            pattern: Pattern name (e.g., "sweep_lr", "ballyhoo")
            resolver: Resolver instance
        """
        self.resolvers[pattern] = resolver
        logger.debug(f"Registered resolver for pattern: {pattern}")

    def get_resolver(self, pattern: str | None) -> MovementResolver:
        """Get resolver for a pattern.

        Args:
            pattern: Pattern name from instruction (None defaults to default)

        Returns:
            Resolver instance (looks up specific handler or returns default)
        """
        if pattern and pattern in self.resolvers:
            return self.resolvers[pattern]
        return self.resolvers["default"]
