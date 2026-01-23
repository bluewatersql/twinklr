"""Default Handler Setup for the moving head sequencer.

This module provides factory functions to create pre-populated
handler registries with all default handlers registered.

Use these functions to get ready-to-use registries in your application.
"""

from typing import TypedDict

from blinkb0t.core.sequencer.moving_heads.handlers.dimmers.default import (
    DefaultDimmerHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.alternating_updown import (
    AlternatingUpDownHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.audience_scan import (
    AudienceScanAsymHandler,
    AudienceScanHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.center_out import (
    CenterOutHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.chevron import ChevronVHandler
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.fan import FanHandler
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.mirror_lr import (
    MirrorLRHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.none import NoneGeometryHandler
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.rainbow_arc import (
    RainbowArcHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.role_pose import RolePoseHandler
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.role_pose_tilt_bias import (
    RolePoseTiltBiasHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.scattered import (
    ScatteredChaosHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.spotlight_cluster import (
    SpotlightClusterHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.tilt_bias_by_group import (
    TiltBiasByGroupHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.tunnel_cone import (
    TunnelConeHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.wall_wash import (
    WallWashHandler,
)
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.wave_lr import WaveLRHandler
from blinkb0t.core.sequencer.moving_heads.handlers.geometry.x_cross import XCrossHandler
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

    Includes commonly used geometry patterns:
    - ROLE_POSE: Maps role tokens to base poses
    - NONE: Returns center position
    - FAN: Fan spread formation
    - CHEVRON_V: V-shaped chevron pattern
    - SCATTERED_CHAOS: Randomized positions
    - AUDIENCE_SCAN: Symmetric audience spread
    - AUDIENCE_SCAN_ASYM: Asymmetric audience spread
    - ALTERNATING_UPDOWN: Alternating up/down tilt positions
    - CENTER_OUT: Center-outward radiating pattern
    - MIRROR_LR: Left/right mirror symmetry
    - RAINBOW_ARC: Rainbow arc formation
    - ROLE_POSE_TILT_BIAS: Role-based pan with group tilt bias
    - TILT_BIAS_BY_GROUP: Constant pan with group tilt offsets
    - SPOTLIGHT_CLUSTER: Converging beams to focal point
    - TUNNEL_CONE: Circular overhead cone pattern
    - WALL_WASH: Unified parallel beams
    - WAVE_LR: Sequential wave progression left-to-right
    - X_CROSS: Diagonal crossing pattern

    Uses RolePoseHandler as default fallback for unimplemented geometry types.

    Returns:
        GeometryRegistry with handlers registered.

    Example:
        >>> registry = create_default_geometry_registry()
        >>> handler = registry.get("FAN")
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
