"""Handler Registries for the moving head sequencer.

This module provides registry classes for managing handlers.
Registries support registration, lookup, and listing of handlers.

Each handler type (geometry, movement, dimmer) has its own registry
with type-specific error messages.
"""

from typing import Any, Generic, Protocol, TypeVar

from blinkb0t.core.sequencer.models.enum import Intensity
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import (
    DimmerResult,
    GeometryResult,
    MovementResult,
)


class HasHandlerId(Protocol):
    """Protocol for objects with a handler_id attribute."""

    handler_id: str


T = TypeVar("T", bound=HasHandlerId)


class HandlerNotFoundError(Exception):
    """Raised when a handler is not found in a registry.

    Attributes:
        handler_id: The ID that was not found.
        handler_type: The type of handler (geometry, movement, dimmer).
        available: List of available handler IDs.

    Example:
        >>> raise HandlerNotFoundError("UNKNOWN", "geometry", ["ROLE_POSE"])
        HandlerNotFoundError: Geometry handler 'UNKNOWN' not found.
        Available: ROLE_POSE
    """

    def __init__(
        self,
        handler_id: str,
        handler_type: str,
        available: list[str] | None = None,
    ) -> None:
        """Initialize HandlerNotFoundError.

        Args:
            handler_id: The ID that was not found.
            handler_type: The type of handler (geometry, movement, dimmer).
            available: Optional list of available handler IDs.
        """
        self.handler_id = handler_id
        self.handler_type = handler_type
        self.available = available or []

        message = f"{handler_type.capitalize()} handler '{handler_id}' not found."
        if self.available:
            message += f" Available: {', '.join(sorted(self.available))}"

        super().__init__(message)


class HandlerRegistry(Generic[T]):
    """Generic registry for handlers.

    Provides registration, lookup, and listing of handlers.
    Handlers must have a `handler_id` attribute.

    Supports optional default handler that is used when a specific
    handler is not found. Default handler is opt-in via register_default().

    Type Parameters:
        T: The handler type (must have handler_id attribute).

    Example:
        >>> registry: HandlerRegistry[SomeHandler] = HandlerRegistry()
        >>> registry.register(MyHandler())
        >>> registry.register_default(DefaultHandler())
        >>> handler = registry.get("MY_HANDLER")  # Returns MyHandler
        >>> handler = registry.get("UNKNOWN")  # Returns DefaultHandler
    """

    def __init__(self, handler_type: str = "handler") -> None:
        """Initialize registry.

        Args:
            handler_type: Type name for error messages.
        """
        self._handlers: dict[str, T] = {}
        self._default_handler: T | None = None
        self._handler_type = handler_type

    def register(self, handler: T) -> None:
        """Register a handler.

        Args:
            handler: Handler to register (must have handler_id).
        """
        self._handlers[handler.handler_id] = handler

    def register_default(self, handler: T) -> None:
        """Register a default handler.

        The default handler is used when get() is called with an
        unregistered handler_id. This is opt-in - if no default
        is registered, HandlerNotFoundError is raised as before.

        Args:
            handler: Default handler to use for unregistered IDs.

        Example:
            >>> registry.register_default(DefaultMovementHandler())
            >>> handler = registry.get("UNREGISTERED")  # Uses default
        """
        self._default_handler = handler

    def get(self, handler_id: str) -> T:
        """Get a handler by ID.

        Args:
            handler_id: The handler ID to look up.

        Returns:
            The registered handler, or default handler if registered
            and specific handler not found.

        Raises:
            HandlerNotFoundError: If handler is not registered and
                no default handler is available.
        """
        if handler_id in self._handlers:
            return self._handlers[handler_id]

        # Use default handler if available
        if self._default_handler is not None:
            return self._default_handler

        # No specific handler and no default - raise error
        raise HandlerNotFoundError(
            handler_id,
            self._handler_type,
            available=self.list_handlers(),
        )

    def has(self, handler_id: str) -> bool:
        """Check if a handler is registered.

        Args:
            handler_id: The handler ID to check.

        Returns:
            True if handler is registered, False otherwise.

        Note:
            This only checks specific handlers, not the default handler.
        """
        return handler_id in self._handlers

    def has_default(self) -> bool:
        """Check if a default handler is registered.

        Returns:
            True if default handler is registered, False otherwise.
        """
        return self._default_handler is not None

    def list_handlers(self) -> list[str]:
        """List all registered handler IDs.

        Returns:
            List of registered handler IDs (excludes default).
        """
        return list(self._handlers.keys())


# Type-specific registries with appropriate error messages


class GeometryRegistry(HandlerRegistry["GeometryHandlerProtocol"]):
    """Registry for geometry handlers.

    Example:
        >>> registry = GeometryRegistry()
        >>> registry.register(RolePoseHandler())
        >>> handler = registry.get("ROLE_POSE")
    """

    def __init__(self) -> None:
        """Initialize geometry registry."""
        super().__init__(handler_type="geometry")


class MovementRegistry(HandlerRegistry["MovementHandlerProtocol"]):
    """Registry for movement handlers.

    Supports default handler that receives movement_id in params.

    Example:
        >>> registry = MovementRegistry()
        >>> registry.register(SweepLRHandler())
        >>> registry.register_default(DefaultMovementHandler())
        >>> handler = registry.get("SWEEP_LR")  # Specific handler
        >>> handler = registry.get("CIRCLE")  # Falls back to default
    """

    def __init__(self) -> None:
        """Initialize movement registry."""
        super().__init__(handler_type="movement")
        self._movement_id_key = "movement_id"

    def get_with_params(self, handler_id: str, params: dict[str, Any]) -> Any:
        """Get handler and inject handler_id into params if using default.

        Args:
            handler_id: The handler ID to look up.
            params: Parameters dict to inject handler_id into.

        Returns:
            The handler (specific or default).
        """
        if handler_id in self._handlers:
            return self._handlers[handler_id]

        # Use default handler if available
        if self._default_handler is not None:
            # Inject movement_id into params for default handler
            params[self._movement_id_key] = handler_id
            return self._default_handler

        # No specific handler and no default - raise error
        raise HandlerNotFoundError(
            handler_id,
            self._handler_type,
            available=self.list_handlers(),
        )


class DimmerRegistry(HandlerRegistry["DimmerHandlerProtocol"]):
    """Registry for dimmer handlers.

    Supports default handler that receives dimmer_id in params.

    Example:
        >>> registry = DimmerRegistry()
        >>> registry.register(PulseHandler())
        >>> registry.register_default(DefaultDimmerHandler())
        >>> handler = registry.get("PULSE")  # Specific handler
        >>> handler = registry.get("FADE_IN")  # Falls back to default
    """

    def __init__(self) -> None:
        """Initialize dimmer registry."""
        super().__init__(handler_type="dimmer")
        self._dimmer_id_key = "dimmer_id"

    def get_with_params(self, handler_id: str, params: dict[str, Any]) -> Any:
        """Get handler and inject handler_id into params if using default.

        Args:
            handler_id: The handler ID to look up.
            params: Parameters dict to inject handler_id into.

        Returns:
            The handler (specific or default).
        """
        if handler_id in self._handlers:
            return self._handlers[handler_id]

        # Use default handler if available
        if self._default_handler is not None:
            # Inject dimmer_id into params for default handler
            params[self._dimmer_id_key] = handler_id
            return self._default_handler

        # No specific handler and no default - raise error
        raise HandlerNotFoundError(
            handler_id,
            self._handler_type,
            available=self.list_handlers(),
        )


class GeometryHandlerProtocol(Protocol):
    """Protocol for geometry handlers (for registry typing)."""

    handler_id: str

    def resolve(
        self,
        fixture_id: str,
        role: str,
        params: dict[str, Any],
        calibration: dict[str, Any],
    ) -> GeometryResult: ...


class MovementHandlerProtocol(Protocol):
    """Protocol for movement handlers (for registry typing)."""

    handler_id: str

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: Intensity,
    ) -> MovementResult: ...


class DimmerHandlerProtocol(Protocol):
    """Protocol for dimmer handlers (for registry typing)."""

    handler_id: str

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: Intensity,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult: ...
