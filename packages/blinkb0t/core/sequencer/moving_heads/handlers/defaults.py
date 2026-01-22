"""Default Handler Setup for the moving head sequencer.

This module provides factory functions to create pre-populated
handler registries with all default handlers registered.

Use these functions to get ready-to-use registries in your application.
"""

from typing import TypedDict

from blinkb0t.core.sequencer.moving_heads.handlers.dimmers.default import (
    DefaultDimmerHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.none import NoneGeometryHandler
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.role_pose import RolePoseHandler
from blinkb0t.core.sequencer.moving_heads.handlers.movement.default import (
    DefaultMovementHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.registry import (
    DimmerRegistry,
    GeometryRegistry,
    MovementRegistry,
)


def create_default_geometry_registry() -> GeometryRegistry:
    """Create a geometry registry with default handlers.

    Currently includes:
    - ROLE_POSE: Maps role tokens to base poses
    - NONE: Returns center position

    Returns:
        GeometryRegistry with default handlers registered.

    Example:
        >>> registry = create_default_geometry_registry()
        >>> handler = registry.get("ROLE_POSE")
    """
    registry = GeometryRegistry()
    registry.register(RolePoseHandler())
    registry.register(NoneGeometryHandler())
    return registry


def create_default_movement_registry() -> MovementRegistry:
    """Create a movement registry with default handlers.

    Uses DefaultMovementHandler which looks up patterns from MovementLibrary.
    This provides automatic support for all 29 movement patterns without
    requiring individual handler implementations.

    Supported movements include:
    - SWEEP_LR, SWEEP_UD: Horizontal/vertical sweeps
    - CIRCLE, FIGURE8, INFINITY: Parametric patterns
    - HOLD, NONE: Static positions
    - PAN_SHAKE, TILT_ROCK, BOUNCE, PENDULUM: Oscillations
    - And 20+ more patterns from MovementLibrary

    Returns:
        MovementRegistry with default handler registered.

    Example:
        >>> registry = create_default_movement_registry()
        >>> handler = registry.get("SWEEP_LR")  # Uses default
        >>> handler = registry.get("CIRCLE")    # Uses default
    """
    registry = MovementRegistry()
    # Register default handler to handle all movements from library
    registry.register_default(DefaultMovementHandler())
    return registry


def create_default_dimmer_registry() -> DimmerRegistry:
    """Create a dimmer registry with default handlers.

    Uses DefaultDimmerHandler which looks up patterns from DimmerLibrary.
    This provides automatic support for all dimmer patterns without
    requiring individual handler implementations.

    Supported dimmers include:
    - FADE_IN: Linear fade from min to max
    - FADE_OUT: Linear fade from max to min
    - PULSE: Sinusoidal pulsing effect
    - HOLD: Constant brightness
    - NONE: Zero brightness (lights off)

    Returns:
        DimmerRegistry with default handler registered.

    Example:
        >>> registry = create_default_dimmer_registry()
        >>> handler = registry.get("PULSE")     # Uses default
        >>> handler = registry.get("FADE_IN")   # Uses default
    """
    registry = DimmerRegistry()
    # Register default handler to handle all dimmers from library
    registry.register_default(DefaultDimmerHandler())
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
