"""Standard pose definitions for moving head choreography.

Provides a curated set of semantic positions that work across
different venue types and rig configurations.
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.models.poses import Pose, PoseID

# ============================================================================
# Standard Poses - Default Definitions
# ============================================================================

STANDARD_POSES: dict[PoseID, Pose] = {
    # ========================================================================
    # Horizontal Reference Poses
    # ========================================================================
    PoseID.FORWARD: Pose(
        pose_id="FORWARD",
        name="Forward Horizon",
        description=(
            "Straight ahead at horizon level. Neutral, versatile starting position. "
            "Good for scanning effects, sweeps, and general coverage."
        ),
        pan_deg=0.0,
        tilt_deg=0.0,
    ),
    PoseID.LEFT_45: Pose(
        pose_id="LEFT_45",
        name="Left Diagonal",
        description=(
            "45° left of center at horizon level. Creates diagonal lines and "
            "asymmetric looks. Works well with RIGHT_45 for contrast."
        ),
        pan_deg=-45.0,
        tilt_deg=0.0,
    ),
    PoseID.RIGHT_45: Pose(
        pose_id="RIGHT_45",
        name="Right Diagonal",
        description=(
            "45° right of center at horizon level. Mirror of LEFT_45. "
            "Creates diagonal lines and asymmetric looks."
        ),
        pan_deg=45.0,
        tilt_deg=0.0,
    ),
    PoseID.LEFT_90: Pose(
        pose_id="LEFT_90",
        name="Left Wall",
        description=(
            "90° left (perpendicular) at horizon level. Extreme side lighting, "
            "wall washes, or dramatic asymmetric looks."
        ),
        pan_deg=-90.0,
        tilt_deg=0.0,
    ),
    PoseID.RIGHT_90: Pose(
        pose_id="RIGHT_90",
        name="Right Wall",
        description=(
            "90° right (perpendicular) at horizon level. Extreme side lighting, "
            "wall washes, or dramatic asymmetric looks."
        ),
        pan_deg=90.0,
        tilt_deg=0.0,
    ),
    # ========================================================================
    # Vertical Reference Poses
    # ========================================================================
    PoseID.UP: Pose(
        pose_id="UP",
        name="Sky Point",
        description=(
            "Straight up (90° tilt). Anthemic, uplifting moments. Creates vertical beams "
            "through haze. Often used for builds, drops, and high-energy sections."
        ),
        pan_deg=0.0,
        tilt_deg=90.0,
    ),
    PoseID.DOWN: Pose(
        pose_id="DOWN",
        name="Stage/Floor",
        description=(
            "Angled down toward stage/floor. Intimate, grounded feel. Can light performers "
            "or create floor patterns. Typical tilt: -15° to -30° depending on rig height."
        ),
        pan_deg=0.0,
        tilt_deg=-20.0,  # Default assumes rig mounted above stage
    ),
    PoseID.CEILING: Pose(
        pose_id="CEILING",
        name="Ceiling/Overhead",
        description=(
            "Nearly vertical (90° tilt). Lights ceiling or creates overhead patterns. "
            "Straight up for maximum vertical reach."
        ),
        pan_deg=0.0,
        tilt_deg=90.0,
    ),
    # ========================================================================
    # Audience-Oriented Poses
    # ========================================================================
    PoseID.AUDIENCE_CENTER: Pose(
        pose_id="AUDIENCE_CENTER",
        name="Audience Center",
        description=(
            "Center audience area at typical crowd height. Engaging, inclusive. "
            "Creates connection between stage and crowd."
        ),
        pan_deg=0.0,
        tilt_deg=-15.0,  # Slight downward angle to reach crowd
    ),
    PoseID.AUDIENCE_LEFT: Pose(
        pose_id="AUDIENCE_LEFT",
        name="Audience Left Section",
        description=(
            "Left audience section at crowd height. Directs attention to stage left crowd."
        ),
        pan_deg=-35.0,
        tilt_deg=-15.0,
    ),
    PoseID.AUDIENCE_RIGHT: Pose(
        pose_id="AUDIENCE_RIGHT",
        name="Audience Right Section",
        description=(
            "Right audience section at crowd height. Directs attention to stage right crowd."
        ),
        pan_deg=35.0,
        tilt_deg=-15.0,
    ),
    # ========================================================================
    # Neutral/Home Positions
    # ========================================================================
    PoseID.SOFT_HOME: Pose(
        pose_id="SOFT_HOME",
        name="Soft Home / Neutral",
        description=(
            "Neutral resting position (0° pan, 0° tilt). Used during gaps between sections "
            "and as default transition waypoint. Represents straight-ahead horizon position. "
            "This is the safe, non-intrusive position for fixtures when not actively in use."
        ),
        pan_deg=0.0,
        tilt_deg=0.0,
    ),
}


# ============================================================================
# Accessor Functions
# ============================================================================


def get_standard_pose(pose_id: PoseID) -> Pose:
    """Get standard pose by ID.

    Args:
        pose_id: Standard pose enum value

    Returns:
        Standard pose definition

    Raises:
        KeyError: If pose_id not in standard poses

    Example:
        pose = get_standard_pose(PoseID.FORWARD)
        print(f"Pan: {pose.pan_deg}°, Tilt: {pose.tilt_deg}°")
    """
    return STANDARD_POSES[pose_id]


def list_standard_poses() -> list[PoseID]:
    """Get list of all standard pose IDs.

    Returns:
        List of standard pose enum values
    """
    return list(STANDARD_POSES.keys())


def get_pose_by_name(name: str) -> Pose | None:
    """Get pose by human-readable name (case-insensitive).

    Args:
        name: Pose name (e.g., "Forward Horizon")

    Returns:
        Matching pose or None if not found
    """
    name_lower = name.lower()
    for pose in STANDARD_POSES.values():
        if pose.name.lower() == name_lower:
            return pose
    return None
