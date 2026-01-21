"""Tests for Handler Registries.

Tests generic HandlerRegistry and type-specific registries.
Validates registration, lookup, and error handling.
"""

import pytest

from blinkb0t.core.sequencer.moving_heads.handlers.dimmer import (
    FadeInHandler,
    PulseHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry import RolePoseHandler
from blinkb0t.core.sequencer.moving_heads.handlers.movement import SweepLRHandler
from blinkb0t.core.sequencer.moving_heads.handlers.registry import (
    DimmerRegistry,
    GeometryRegistry,
    HandlerNotFoundError,
    HandlerRegistry,
    MovementRegistry,
)


class TestHandlerRegistry:
    """Tests for generic HandlerRegistry."""

    def test_register_and_get(self) -> None:
        """Test register and get handler."""
        registry: HandlerRegistry[RolePoseHandler] = HandlerRegistry()
        handler = RolePoseHandler()

        registry.register(handler)
        retrieved = registry.get("ROLE_POSE")

        assert retrieved is handler

    def test_get_unknown_raises_error(self) -> None:
        """Test get unknown handler raises HandlerNotFoundError."""
        registry: HandlerRegistry[RolePoseHandler] = HandlerRegistry()

        with pytest.raises(HandlerNotFoundError, match="UNKNOWN"):
            registry.get("UNKNOWN")

    def test_has_handler(self) -> None:
        """Test has method."""
        registry: HandlerRegistry[RolePoseHandler] = HandlerRegistry()
        handler = RolePoseHandler()

        assert not registry.has("ROLE_POSE")
        registry.register(handler)
        assert registry.has("ROLE_POSE")

    def test_list_handlers(self) -> None:
        """Test list_handlers returns all registered IDs."""
        registry: HandlerRegistry[SweepLRHandler] = HandlerRegistry()

        assert registry.list_handlers() == []

        handler = SweepLRHandler()
        registry.register(handler)

        assert registry.list_handlers() == ["SWEEP_LR"]

    def test_register_overwrites_existing(self) -> None:
        """Test registering with same ID overwrites."""
        registry: HandlerRegistry[RolePoseHandler] = HandlerRegistry()
        handler1 = RolePoseHandler()
        handler2 = RolePoseHandler()

        registry.register(handler1)
        registry.register(handler2)

        # Should have the second handler
        assert registry.get("ROLE_POSE") is handler2


class TestGeometryRegistry:
    """Tests for GeometryRegistry."""

    def test_is_type_specific(self) -> None:
        """Test GeometryRegistry accepts GeometryHandlers."""
        registry = GeometryRegistry()
        handler = RolePoseHandler()

        registry.register(handler)
        retrieved = registry.get("ROLE_POSE")

        assert retrieved.handler_id == "ROLE_POSE"

    def test_error_message_includes_type(self) -> None:
        """Test error message includes registry type."""
        registry = GeometryRegistry()

        with pytest.raises(HandlerNotFoundError) as exc_info:
            registry.get("UNKNOWN")

        assert "geometry" in str(exc_info.value).lower()


class TestMovementRegistry:
    """Tests for MovementRegistry."""

    def test_is_type_specific(self) -> None:
        """Test MovementRegistry accepts MovementHandlers."""
        registry = MovementRegistry()
        handler = SweepLRHandler()

        registry.register(handler)
        retrieved = registry.get("SWEEP_LR")

        assert retrieved.handler_id == "SWEEP_LR"

    def test_error_message_includes_type(self) -> None:
        """Test error message includes registry type."""
        registry = MovementRegistry()

        with pytest.raises(HandlerNotFoundError) as exc_info:
            registry.get("UNKNOWN")

        assert "movement" in str(exc_info.value).lower()


class TestDimmerRegistry:
    """Tests for DimmerRegistry."""

    def test_is_type_specific(self) -> None:
        """Test DimmerRegistry accepts DimmerHandlers."""
        registry = DimmerRegistry()
        handler = PulseHandler()

        registry.register(handler)
        retrieved = registry.get("PULSE")

        assert retrieved.handler_id == "PULSE"

    def test_multiple_handlers(self) -> None:
        """Test registry with multiple handlers."""
        registry = DimmerRegistry()

        registry.register(FadeInHandler())
        registry.register(PulseHandler())

        assert registry.has("FADE_IN")
        assert registry.has("PULSE")
        assert len(registry.list_handlers()) == 2

    def test_error_message_includes_type(self) -> None:
        """Test error message includes registry type."""
        registry = DimmerRegistry()

        with pytest.raises(HandlerNotFoundError) as exc_info:
            registry.get("UNKNOWN")

        assert "dimmer" in str(exc_info.value).lower()


class TestHandlerNotFoundError:
    """Tests for HandlerNotFoundError."""

    def test_error_includes_handler_id(self) -> None:
        """Test error message includes handler ID."""
        error = HandlerNotFoundError("MISSING_HANDLER", "geometry")
        assert "MISSING_HANDLER" in str(error)

    def test_error_includes_handler_type(self) -> None:
        """Test error message includes handler type."""
        error = HandlerNotFoundError("MISSING_HANDLER", "geometry")
        assert "geometry" in str(error).lower()

    def test_error_suggests_available(self) -> None:
        """Test error message suggests available handlers."""
        error = HandlerNotFoundError("MISSING", "geometry", available=["ROLE_POSE", "CUSTOM"])
        assert "ROLE_POSE" in str(error)
        assert "CUSTOM" in str(error)
