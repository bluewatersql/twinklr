"""Default Handler Setup for the moving head sequencer.

This module provides factory functions to create pre-populated
handler registries with all default handlers registered.

Use these functions to get ready-to-use registries in your application.
"""

from typing import TypedDict

from blinkb0t.core.sequencer.moving_heads.handlers.dimmer import (
    FadeInHandler,
    FadeOutHandler,
    HoldHandler,
    PulseHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry import RolePoseHandler
from blinkb0t.core.sequencer.moving_heads.handlers.movement import SweepLRHandler
from blinkb0t.core.sequencer.moving_heads.handlers.registry import (
    DimmerRegistry,
    GeometryRegistry,
    MovementRegistry,
)


def create_default_geometry_registry() -> GeometryRegistry:
    """Create a geometry registry with default handlers.

    Currently includes:
    - ROLE_POSE: Maps role tokens to base poses

    Returns:
        GeometryRegistry with default handlers registered.

    Example:
        >>> registry = create_default_geometry_registry()
        >>> handler = registry.get("ROLE_POSE")
    """
    registry = GeometryRegistry()
    registry.register(RolePoseHandler())
    return registry


def create_default_movement_registry() -> MovementRegistry:
    """Create a movement registry with default handlers.

    Currently includes:
    - SWEEP_LR: Left-to-right sinusoidal sweep

    Returns:
        MovementRegistry with default handlers registered.

    Example:
        >>> registry = create_default_movement_registry()
        >>> handler = registry.get("SWEEP_LR")
    """
    registry = MovementRegistry()
    registry.register(SweepLRHandler())
    return registry


def create_default_dimmer_registry() -> DimmerRegistry:
    """Create a dimmer registry with default handlers.

    Currently includes:
    - FADE_IN: Linear fade from min to max
    - FADE_OUT: Linear fade from max to min
    - PULSE: Sinusoidal pulsing effect
    - HOLD: Constant brightness

    Returns:
        DimmerRegistry with default handlers registered.

    Example:
        >>> registry = create_default_dimmer_registry()
        >>> handler = registry.get("PULSE")
    """
    registry = DimmerRegistry()
    registry.register(FadeInHandler())
    registry.register(FadeOutHandler())
    registry.register(PulseHandler())
    registry.register(HoldHandler())
    return registry


class DefaultRegistries(TypedDict):
    """Type definition for default registries bundle."""

    geometry: GeometryRegistry
    movement: MovementRegistry
    dimmer: DimmerRegistry


def create_default_registries() -> DefaultRegistries:
    """Create all default registries as a bundle.

    Returns a dict with geometry, movement, and dimmer registries,
    each pre-populated with default handlers.

    Returns:
        Dict with 'geometry', 'movement', and 'dimmer' keys.

    Example:
        >>> registries = create_default_registries()
        >>> geo_handler = registries["geometry"].get("ROLE_POSE")
        >>> mov_handler = registries["movement"].get("SWEEP_LR")
        >>> dim_handler = registries["dimmer"].get("PULSE")
    """
    return {
        "geometry": create_default_geometry_registry(),
        "movement": create_default_movement_registry(),
        "dimmer": create_default_dimmer_registry(),
    }
