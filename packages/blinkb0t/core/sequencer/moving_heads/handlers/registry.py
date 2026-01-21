"""Handler Registries for the moving head sequencer.

This module provides registry classes for managing handlers.
Registries support registration, lookup, and listing of handlers.

Each handler type (geometry, movement, dimmer) has its own registry
with type-specific error messages.
"""

from typing import Any, Generic, Protocol, TypeVar

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

    Type Parameters:
        T: The handler type (must have handler_id attribute).

    Example:
        >>> registry: HandlerRegistry[SomeHandler] = HandlerRegistry()
        >>> registry.register(MyHandler())
        >>> handler = registry.get("MY_HANDLER")
    """

    def __init__(self, handler_type: str = "handler") -> None:
        """Initialize registry.

        Args:
            handler_type: Type name for error messages.
        """
        self._handlers: dict[str, T] = {}
        self._handler_type = handler_type

    def register(self, handler: T) -> None:
        """Register a handler.

        Args:
            handler: Handler to register (must have handler_id).
        """
        self._handlers[handler.handler_id] = handler

    def get(self, handler_id: str) -> T:
        """Get a handler by ID.

        Args:
            handler_id: The handler ID to look up.

        Returns:
            The registered handler.

        Raises:
            HandlerNotFoundError: If handler is not registered.
        """
        if handler_id not in self._handlers:
            raise HandlerNotFoundError(
                handler_id,
                self._handler_type,
                available=self.list_handlers(),
            )
        return self._handlers[handler_id]

    def has(self, handler_id: str) -> bool:
        """Check if a handler is registered.

        Args:
            handler_id: The handler ID to check.

        Returns:
            True if handler is registered, False otherwise.
        """
        return handler_id in self._handlers

    def list_handlers(self) -> list[str]:
        """List all registered handler IDs.

        Returns:
            List of registered handler IDs.
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

    Example:
        >>> registry = MovementRegistry()
        >>> registry.register(SweepLRHandler())
        >>> handler = registry.get("SWEEP_LR")
    """

    def __init__(self) -> None:
        """Initialize movement registry."""
        super().__init__(handler_type="movement")


class DimmerRegistry(HandlerRegistry["DimmerHandlerProtocol"]):
    """Registry for dimmer handlers.

    Example:
        >>> registry = DimmerRegistry()
        >>> registry.register(PulseHandler())
        >>> handler = registry.get("PULSE")
    """

    def __init__(self) -> None:
        """Initialize dimmer registry."""
        super().__init__(handler_type="dimmer")


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
        intensity: str,
    ) -> MovementResult: ...


class DimmerHandlerProtocol(Protocol):
    """Protocol for dimmer handlers (for registry typing)."""

    handler_id: str

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: str,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult: ...
