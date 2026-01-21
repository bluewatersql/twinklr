"""Tests for Default Handler Setup.

Tests factory functions that create pre-populated registries.
Validates that all default handlers are registered.
"""

from blinkb0t.core.sequencer.moving_heads.handlers.defaults import (
    create_default_dimmer_registry,
    create_default_geometry_registry,
    create_default_movement_registry,
    create_default_registries,
)


class TestDefaultGeometryRegistry:
    """Tests for default geometry registry."""

    def test_has_role_pose(self) -> None:
        """Test default geometry registry has ROLE_POSE handler."""
        registry = create_default_geometry_registry()
        assert registry.has("ROLE_POSE")

    def test_can_get_handler(self) -> None:
        """Test can get handler from default registry."""
        registry = create_default_geometry_registry()
        handler = registry.get("ROLE_POSE")
        assert handler.handler_id == "ROLE_POSE"


class TestDefaultMovementRegistry:
    """Tests for default movement registry."""

    def test_has_sweep_lr(self) -> None:
        """Test default movement registry has SWEEP_LR handler."""
        registry = create_default_movement_registry()
        assert registry.has("SWEEP_LR")

    def test_can_get_handler(self) -> None:
        """Test can get handler from default registry."""
        registry = create_default_movement_registry()
        handler = registry.get("SWEEP_LR")
        assert handler.handler_id == "SWEEP_LR"


class TestDefaultDimmerRegistry:
    """Tests for default dimmer registry."""

    def test_has_fade_in(self) -> None:
        """Test default dimmer registry has FADE_IN handler."""
        registry = create_default_dimmer_registry()
        assert registry.has("FADE_IN")

    def test_has_fade_out(self) -> None:
        """Test default dimmer registry has FADE_OUT handler."""
        registry = create_default_dimmer_registry()
        assert registry.has("FADE_OUT")

    def test_has_pulse(self) -> None:
        """Test default dimmer registry has PULSE handler."""
        registry = create_default_dimmer_registry()
        assert registry.has("PULSE")

    def test_has_hold(self) -> None:
        """Test default dimmer registry has HOLD handler."""
        registry = create_default_dimmer_registry()
        assert registry.has("HOLD")

    def test_can_get_all_handlers(self) -> None:
        """Test can get all handlers from default registry."""
        registry = create_default_dimmer_registry()

        for handler_id in ["FADE_IN", "FADE_OUT", "PULSE", "HOLD"]:
            handler = registry.get(handler_id)
            assert handler.handler_id == handler_id


class TestCreateDefaultRegistries:
    """Tests for create_default_registries bundle."""

    def test_returns_all_registries(self) -> None:
        """Test returns geometry, movement, and dimmer registries."""
        registries = create_default_registries()

        assert "geometry" in registries
        assert "movement" in registries
        assert "dimmer" in registries

    def test_all_registries_populated(self) -> None:
        """Test all registries have default handlers."""
        registries = create_default_registries()

        assert registries["geometry"].has("ROLE_POSE")
        assert registries["movement"].has("SWEEP_LR")
        assert registries["dimmer"].has("PULSE")

    def test_registries_are_independent(self) -> None:
        """Test registries from multiple calls are independent."""
        registries1 = create_default_registries()
        registries2 = create_default_registries()

        # Should be different instances
        assert registries1["geometry"] is not registries2["geometry"]
        assert registries1["movement"] is not registries2["movement"]
        assert registries1["dimmer"] is not registries2["dimmer"]
