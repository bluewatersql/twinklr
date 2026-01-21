"""Geometry transform library - Python-based with type safety.

Provides spatial transformation definitions for fixture positioning and grouping.
This is a simplified implementation with core geometries for Phase 0.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class GeometryID(str, Enum):
    """All available geometry transform identifiers."""

    # Core geometries (implemented)
    ALTERNATING_UPDOWN = "alternating_updown"
    AUDIENCE_SCAN_ASYM = "audience_scan_asym"
    AUDIENCE_SCAN = "audience_scan"
    ROLE_POSE_TILT_BIAS = "role_pose_tilt_bias"
    TILT_BIAS_BY_GROUP = "tilt_bias_by_group"
    CENTER_OUT = "center_out"
    CHEVRON_V = "chevron_v"
    FAN = "fan"
    MIRROR_LR = "mirror_lr"
    RAINBOW_ARC = "rainbow_arc"
    SCATTERED_CHAOS = "scattered_chaos"
    SPOTLIGHT_CLUSTER = "spotlight_cluster"
    TUNNEL_CONE = "tunnel_cone"
    WALL_WASH = "wall_wash"
    WAVE_LR = "wave_lr"
    X_CROSS = "x_cross"
    NONE = "none"  # No geometry (identity transform)
    ROLE_POSE = "role_pose"


class GeometryDefinition(BaseModel):
    """Simple geometry definition for Phase 0.

    Full implementation will include detailed params, variants, combos, etc.
    This provides enough structure for templates to reference geometries.
    """

    model_config = ConfigDict(frozen=True)

    id: GeometryID
    name: str
    summary: str


# ============================================================================
# Geometry Library - Content (Simplified for Phase 0)
# ============================================================================

GEOMETRY_LIBRARY: dict[GeometryID, GeometryDefinition] = {
    GeometryID.AUDIENCE_SCAN_ASYM: GeometryDefinition(
        id=GeometryID.AUDIENCE_SCAN_ASYM,
        name="Audience Scan (Asymmetric)",
        summary="Leaning scan that biases pan positions to one side for asymmetry",
    ),
    GeometryID.ROLE_POSE_TILT_BIAS: GeometryDefinition(
        id=GeometryID.ROLE_POSE_TILT_BIAS,
        name="Role Pose Tilt Bias",
        summary="Role-based pan with per-group tilt bias for contrast",
    ),
    GeometryID.TILT_BIAS_BY_GROUP: GeometryDefinition(
        id=GeometryID.TILT_BIAS_BY_GROUP,
        name="Tilt Bias By Group",
        summary="Constant pan with per-group tilt offsets",
    ),
    GeometryID.ALTERNATING_UPDOWN: GeometryDefinition(
        id=GeometryID.ALTERNATING_UPDOWN,
        name="Alternating Up/Down",
        summary="Alternates fixtures between up and horizon tilt positions for vertical contrast",
    ),
    GeometryID.AUDIENCE_SCAN: GeometryDefinition(
        id=GeometryID.AUDIENCE_SCAN,
        name="Audience Scan",
        summary="Spreads fixtures across audience width for inclusive, communal moments",
    ),
    GeometryID.CENTER_OUT: GeometryDefinition(
        id=GeometryID.CENTER_OUT,
        name="Center Outward",
        summary="Fixtures positioned from center outward",
    ),
    GeometryID.CHEVRON_V: GeometryDefinition(
        id=GeometryID.CHEVRON_V,
        name="Chevron V-Shape",
        summary="V-shaped chevron formation",
    ),
    GeometryID.FAN: GeometryDefinition(
        id=GeometryID.FAN,
        name="Fan Spread",
        summary="Fixtures spread out in fan pattern from center",
    ),
    GeometryID.MIRROR_LR: GeometryDefinition(
        id=GeometryID.MIRROR_LR,
        name="Left/Right Mirror",
        summary="Symmetric left/right mirror around center for clean, powerful looks",
    ),
    GeometryID.RAINBOW_ARC: GeometryDefinition(
        id=GeometryID.RAINBOW_ARC,
        name="Rainbow Arc",
        summary="Horizontal arc formation with optional vertical curve for uplifting moments",
    ),
    GeometryID.SCATTERED_CHAOS: GeometryDefinition(
        id=GeometryID.SCATTERED_CHAOS,
        name="Scattered Chaos",
        summary="Randomized offsets within constraints for modern disorder and breakdown sections",
    ),
    GeometryID.SPOTLIGHT_CLUSTER: GeometryDefinition(
        id=GeometryID.SPOTLIGHT_CLUSTER,
        name="Spotlight Cluster",
        summary="Converging beams creating focal point for intimate moments and dramatic focus",
    ),
    GeometryID.TUNNEL_CONE: GeometryDefinition(
        id=GeometryID.TUNNEL_CONE,
        name="Tunnel/Cone",
        summary="Circular overhead pattern creating volumetric cone or tunnel effect",
    ),
    GeometryID.WALL_WASH: GeometryDefinition(
        id=GeometryID.WALL_WASH,
        name="Wall Wash",
        summary="Unified parallel beams for simple, powerful directional moments",
    ),
    GeometryID.WAVE_LR: GeometryDefinition(
        id=GeometryID.WAVE_LR,
        name="Left/Right Wave",
        summary="Sequential wave effect across fixtures",
    ),
    GeometryID.X_CROSS: GeometryDefinition(
        id=GeometryID.X_CROSS,
        name="X-Cross",
        summary="Two groups cross diagonally through center for high-energy, readable motion",
    ),
    GeometryID.NONE: GeometryDefinition(
        id=GeometryID.NONE,
        name="None (Identity)",
        summary="No geometry transformation applied",
    ),
    GeometryID.ROLE_POSE: GeometryDefinition(
        id=GeometryID.ROLE_POSE,
        name="Role Pose",
        summary="Role-based pose transformation",
    ),
}


# ============================================================================
# Accessor Functions
# ============================================================================


def get_geometry(geometry_id: GeometryID) -> GeometryDefinition:
    """Get geometry definition by ID.

    Args:
        geometry_id: Geometry enum value

    Returns:
        Geometry definition

    Example:
        geo = get_geometry(GeometryID.FAN)
        print(geo.name)  # "Fan Spread"
    """
    return GEOMETRY_LIBRARY[geometry_id]


def list_geometries() -> list[GeometryID]:
    """List all geometry IDs, optionally filtered to implemented only.

    Args:
        implemented_only: If True, only return implemented geometries

    Returns:
        List of geometry IDs
    """
    return list(GEOMETRY_LIBRARY.keys())
