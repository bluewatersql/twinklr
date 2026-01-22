from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class GeometryDefinition(BaseModel):
    """Definition of a geometry pattern."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    summary: str
    description: str = Field(default="")


class GeometryType(str, Enum):
    """All available geometry transform identifiers."""

    # Core geometries
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
    ROLE_POSE = "role_pose"
    NONE = "none"


class GeometryLibrary:
    """Library of predefined geometry patterns."""

    PATTERNS: dict[GeometryType, GeometryDefinition] = {
        GeometryType.AUDIENCE_SCAN_ASYM: GeometryDefinition(
            id="audience_scan_asym",
            name="Audience Scan (Asymmetric)",
            summary="Leaning scan that biases pan positions to one side for asymmetry",
            description=(
                "Creates an asymmetric audience scan by biasing pan positions to one side. "
                "Useful for creating visual interest and breaking symmetry."
            ),
        ),
        GeometryType.ROLE_POSE_TILT_BIAS: GeometryDefinition(
            id="role_pose_tilt_bias",
            name="Role Pose Tilt Bias",
            summary="Role-based pan with per-group tilt bias for contrast",
            description=(
                "Uses role-based pan positioning while applying group-specific tilt bias. "
                "Creates vertical contrast between different fixture groups."
            ),
        ),
        GeometryType.TILT_BIAS_BY_GROUP: GeometryDefinition(
            id="tilt_bias_by_group",
            name="Tilt Bias By Group",
            summary="Constant pan with per-group tilt offsets",
            description=(
                "Maintains constant pan position while applying different tilt offsets "
                "to each group. Useful for layered looks with vertical separation."
            ),
        ),
        GeometryType.ALTERNATING_UPDOWN: GeometryDefinition(
            id="alternating_updown",
            name="Alternating Up/Down",
            summary="Alternates fixtures between up and horizon tilt positions",
            description=(
                "Creates vertical contrast by alternating fixtures between upward and "
                "horizon tilt positions. Effective for high-energy, dynamic looks."
            ),
        ),
        GeometryType.AUDIENCE_SCAN: GeometryDefinition(
            id="audience_scan",
            name="Audience Scan",
            summary="Spreads fixtures across audience width",
            description=(
                "Evenly distributes fixtures across the audience width for inclusive, "
                "communal moments. Creates wide coverage and engagement."
            ),
        ),
        GeometryType.CENTER_OUT: GeometryDefinition(
            id="center_out",
            name="Center Outward",
            summary="Fixtures positioned from center outward",
            description=(
                "Positions fixtures radiating outward from the center point. "
                "Creates expanding or converging visual effects."
            ),
        ),
        GeometryType.CHEVRON_V: GeometryDefinition(
            id="chevron_v",
            name="Chevron V-Shape",
            summary="V-shaped chevron formation",
            description=(
                "Arranges fixtures in a V-shaped chevron pattern. Strong, directional "
                "geometric formation useful for dramatic moments."
            ),
        ),
        GeometryType.FAN: GeometryDefinition(
            id="fan",
            name="Fan Spread",
            summary="Fixtures spread out in fan pattern from center",
            description=(
                "Classic fan formation spreading from a central point. Versatile "
                "pattern suitable for many musical contexts."
            ),
        ),
        GeometryType.MIRROR_LR: GeometryDefinition(
            id="mirror_lr",
            name="Left/Right Mirror",
            summary="Symmetric left/right mirror around center",
            description=(
                "Creates perfect symmetry with left and right sides mirroring each other. "
                "Clean, powerful look ideal for balanced compositions."
            ),
        ),
        GeometryType.RAINBOW_ARC: GeometryDefinition(
            id="rainbow_arc",
            name="Rainbow Arc",
            summary="Horizontal arc formation with optional vertical curve",
            description=(
                "Smooth arc formation resembling a rainbow. Uplifting and visually "
                "pleasing formation for positive, energetic moments."
            ),
        ),
        GeometryType.SCATTERED_CHAOS: GeometryDefinition(
            id="scattered_chaos",
            name="Scattered Chaos",
            summary="Randomized offsets within constraints",
            description=(
                "Applies controlled randomization to create scattered, chaotic patterns. "
                "Perfect for modern, aggressive sections and breakdown moments."
            ),
        ),
        GeometryType.SPOTLIGHT_CLUSTER: GeometryDefinition(
            id="spotlight_cluster",
            name="Spotlight Cluster",
            summary="Converging beams creating focal point",
            description=(
                "Fixtures converge to create a tight focal point like a spotlight. "
                "Ideal for intimate moments and dramatic focus on specific areas."
            ),
        ),
        GeometryType.TUNNEL_CONE: GeometryDefinition(
            id="tunnel_cone",
            name="Tunnel/Cone",
            summary="Circular overhead pattern creating volumetric cone",
            description=(
                "Creates circular pattern overhead forming a cone or tunnel effect. "
                "Immersive volumetric look for high-impact moments."
            ),
        ),
        GeometryType.WALL_WASH: GeometryDefinition(
            id="wall_wash",
            name="Wall Wash",
            summary="Unified parallel beams for directional moments",
            description=(
                "All fixtures aim in the same direction creating parallel beams. "
                "Simple, powerful look for unified directional emphasis."
            ),
        ),
        GeometryType.WAVE_LR: GeometryDefinition(
            id="wave_lr",
            name="Left/Right Wave",
            summary="Sequential wave effect across fixtures",
            description=(
                "Creates wave-like progression across fixtures from left to right. "
                "Flowing, organic movement pattern."
            ),
        ),
        GeometryType.X_CROSS: GeometryDefinition(
            id="x_cross",
            name="X-Cross",
            summary="Two groups cross diagonally through center",
            description=(
                "Groups cross diagonally creating an X pattern. High-energy, readable "
                "motion perfect for peak moments."
            ),
        ),
        GeometryType.ROLE_POSE: GeometryDefinition(
            id="role_pose",
            name="Role Pose",
            summary="Direct role-to-pose mapping",
            description=(
                "Maps each fixture role directly to a specific pose. Foundation pattern "
                "for role-based choreography."
            ),
        ),
        GeometryType.NONE: GeometryDefinition(
            id="none",
            name="None (Center)",
            summary="No geometry transformation (center position)",
            description="Returns center position for all fixtures. No transformation applied.",
        ),
    }

    @classmethod
    def get_all_metadata(cls) -> list[dict[str, str]]:
        """Get metadata for all geometry patterns (optimized for LLM context).

        Returns:
            List of dictionaries with pattern metadata

        Example:
            >>> meta = GeometryLibrary.get_all_metadata()
            >>> meta[0]["geometry_id"]
            'fan'
        """
        return [
            {
                "geometry_id": pattern.id,
                "name": pattern.name,
                "summary": pattern.summary,
                "description": pattern.description,
            }
            for pattern in cls.PATTERNS.values()
        ]
