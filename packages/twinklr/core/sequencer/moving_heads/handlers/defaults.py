"""Default Handler Setup for the moving head sequencer.

This module provides factory functions to create pre-populated
handler registries with all default handlers registered.

Use these functions to get ready-to-use registries in your application.
"""

from typing import TypedDict

from twinklr.core.sequencer.moving_heads.handlers.dimmers.default import (
    DefaultDimmerHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.alternating_updown import (
    AlternatingUpDownHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.audience_scan import (
    AudienceScanAsymHandler,
    AudienceScanHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.center_out import (
    CenterOutHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.chevron import ChevronVHandler
from twinklr.core.sequencer.moving_heads.handlers.geometry.fan import FanHandler
from twinklr.core.sequencer.moving_heads.handlers.geometry.mirror_lr import (
    MirrorLRHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.none import NoneGeometryHandler
from twinklr.core.sequencer.moving_heads.handlers.geometry.rainbow_arc import (
    RainbowArcHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.role_pose import RolePoseHandler
from twinklr.core.sequencer.moving_heads.handlers.geometry.role_pose_tilt_bias import (
    RolePoseTiltBiasHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.scattered import (
    ScatteredChaosHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.spotlight_cluster import (
    SpotlightClusterHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.tilt_bias_by_group import (
    TiltBiasByGroupHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.tunnel_cone import (
    TunnelConeHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.wall_wash import (
    WallWashHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.geometry.wave_lr import WaveLRHandler
from twinklr.core.sequencer.moving_heads.handlers.geometry.x_cross import XCrossHandler
from twinklr.core.sequencer.moving_heads.handlers.movement.default import (
    DefaultMovementHandler,
)
from twinklr.core.sequencer.moving_heads.handlers.registry import (
    DimmerRegistry,
    GeometryRegistry,
    MovementRegistry,
)


def create_default_geometry_registry() -> GeometryRegistry:
    """Create a geometry registry with default handlers.

    Uses RolePoseHandler as default fallback for unimplemented geometry types.

    Returns:
        GeometryRegistry with handlers registered.
    """
    registry = GeometryRegistry()

    # Core handlers
    role_pose_handler = RolePoseHandler()
    registry.register(role_pose_handler)
    registry.register(NoneGeometryHandler())

    # Pattern handlers
    registry.register(FanHandler())
    registry.register(ChevronVHandler())
    registry.register(ScatteredChaosHandler())
    registry.register(AudienceScanHandler())
    registry.register(AudienceScanAsymHandler())
    registry.register(AlternatingUpDownHandler())
    registry.register(CenterOutHandler())
    registry.register(MirrorLRHandler())
    registry.register(RainbowArcHandler())
    registry.register(RolePoseTiltBiasHandler())
    registry.register(TiltBiasByGroupHandler())
    registry.register(SpotlightClusterHandler())
    registry.register(TunnelConeHandler())
    registry.register(WallWashHandler())
    registry.register(WaveLRHandler())
    registry.register(XCrossHandler())

    # Register RolePoseHandler as default fallback for unimplemented geometry types
    registry.register_default(role_pose_handler)

    return registry


def create_default_movement_registry() -> MovementRegistry:
    """Create a movement registry with default handlers.

    Uses DefaultMovementHandler which looks up patterns from MovementLibrary.
    This provides automatic support for all 29 movement patterns without
    requiring individual handler implementations.

    Returns:
        MovementRegistry with default handler registered.
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

    Returns:
        DimmerRegistry with default handler registered.
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
    """
    return {
        "geometry": create_default_geometry_registry(),
        "movement": create_default_movement_registry(),
        "dimmer": create_default_dimmer_registry(),
    }
