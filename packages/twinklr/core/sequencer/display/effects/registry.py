"""Effect handler registry.

Manages registered EffectHandler instances and dispatches
render events to the appropriate handler by effect_type.
"""

from __future__ import annotations

import logging

from twinklr.core.sequencer.display.effects.protocol import (
    EffectHandler,
    EffectSettings,
    RenderContext,
)
from twinklr.core.sequencer.display.models.render_event import RenderEvent

logger = logging.getLogger(__name__)


class HandlerRegistry:
    """Registry for EffectHandler instances.

    Maps xLights effect type names to handler implementations.
    Unknown effect types fall back to the default handler (On).

    Example:
        >>> registry = HandlerRegistry()
        >>> registry.register(OnHandler())
        >>> registry.register(ColorWashHandler())
        >>> settings = registry.dispatch(event, ctx)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, EffectHandler] = {}
        self._default: EffectHandler | None = None

    def register(self, handler: EffectHandler) -> None:
        """Register an effect handler.

        Args:
            handler: EffectHandler implementation to register.
        """
        effect_type = handler.effect_type
        if effect_type in self._handlers:
            logger.warning(
                "Overwriting handler for effect type '%s' (old=%s, new=%s)",
                effect_type,
                type(self._handlers[effect_type]).__name__,
                type(handler).__name__,
            )
        self._handlers[effect_type] = handler
        logger.debug(
            "Registered handler '%s' for effect type '%s'",
            type(handler).__name__,
            effect_type,
        )

    def set_default(self, handler: EffectHandler) -> None:
        """Set the default fallback handler.

        Args:
            handler: Handler to use for unknown effect types.
        """
        self._default = handler

    def get(self, effect_type: str) -> EffectHandler | None:
        """Get the handler for an effect type.

        Args:
            effect_type: xLights effect type name.

        Returns:
            EffectHandler if registered, None otherwise.
        """
        return self._handlers.get(effect_type)

    def dispatch(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Dispatch a render event to the appropriate handler.

        Args:
            event: Render event to process.
            ctx: Rendering context.

        Returns:
            EffectSettings from the matched handler.

        Raises:
            ValueError: If no handler found and no default set.
        """
        handler = self._handlers.get(event.effect_type)

        if handler is None:
            if self._default is not None:
                logger.warning(
                    "No handler for effect type '%s', using default '%s'",
                    event.effect_type,
                    self._default.effect_type,
                )
                handler = self._default
            else:
                raise ValueError(
                    f"No handler registered for effect type '{event.effect_type}' "
                    f"and no default handler set"
                )

        return handler.build_settings(event, ctx)

    @property
    def registered_types(self) -> list[str]:
        """List all registered effect types."""
        return sorted(self._handlers.keys())

    def __len__(self) -> int:
        return len(self._handlers)


__all__ = [
    "HandlerRegistry",
]
