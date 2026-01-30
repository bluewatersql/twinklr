"""Semantic pose models for fixture-independent choreography."""

from __future__ import annotations

from enum import Enum
from typing import TypeGuard

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PoseLibrary(str, Enum):
    """Standard pose identifiers.

    All enum values should have corresponding definitions in ``STANDARD_POSES``.
    """

    # Audience-facing poses
    AUDIENCE_CENTER = "audience_center"
    AUDIENCE_LEFT = "audience_left"
    AUDIENCE_RIGHT = "audience_right"

    # Neutral/home positions
    SOFT_HOME = "soft_home"

    # --- Normalized helpers (still exposed via PanPose/TiltPose) ---
    # Pan normalized anchors
    WIDE_LEFT = "wide_left"
    MID_LEFT = "mid_left"
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    MID_RIGHT = "mid_right"
    WIDE_RIGHT = "wide_right"

    # Tilt normalized anchors
    SKY = "sky"
    CEILING = "ceiling"
    HORIZON_UP_45 = "horizon_up_45"
    HORIZON = "horizon"
    CROWD = "crowd"
    STAGE = "stage"


class Pose(BaseModel):
    """Semantic position definition.

    A pose defines a fixture-independent target position using pan/tilt angles.
    These angles are relative to the fixture's home position and can be adjusted
    based on fixture orientation.
    """

    model_config = ConfigDict(frozen=True)

    pose_id: PoseLibrary | str = Field(
        description="Unique pose identifier (PoseLibrary for standard poses; string for custom poses)."
    )
    name: str = Field(description="Human-readable pose name")
    description: str = Field(
        default="", description="Detailed description of what this pose represents"
    )

    pan_deg: float = Field(
        ge=-180.0, le=180.0, description="Pan angle in degrees relative to forward (0° = forward)"
    )
    tilt_deg: float = Field(
        ge=-90.0,
        le=90.0,
        description="Tilt angle in degrees relative to horizon (0° = horizon, 90° = up)",
    )

    @field_validator("pose_id")
    @classmethod
    def _normalize_pose_id(cls, v: PoseLibrary | str) -> PoseLibrary | str:
        # Accept PoseLibrary or string. Normalize strings to uppercase for consistency.
        if isinstance(v, PoseLibrary):
            return v
        if not isinstance(v, str) or not v.strip():
            raise TypeError("pose_id must be a PoseLibrary or a non-empty string")
        return v.strip().upper()


class PoseConfig(BaseModel):
    """Pose configuration for JobConfig.

    Allows users to override standard poses or add custom poses.
    Standard poses are loaded by default and can be supplemented.
    """

    model_config = ConfigDict(frozen=True)

    custom_poses: dict[str, Pose] = Field(
        default_factory=dict,
        description="Custom poses defined by user (added to standard poses). Keys are pose_id strings.",
    )

    pose_overrides: dict[PoseLibrary, Pose] = Field(
        default_factory=dict,
        description="Override standard pose definitions (e.g., adjust FORWARD for rig orientation).",
    )


class PanPose(str, Enum):
    """Normalized pan pose positions.

    This is a *collection* (subset) of :class:`PoseLibrary` for horizontal positioning helpers.
    Values are ordered from left (0.0) to right (1.0).
    """

    WIDE_LEFT = PoseLibrary.WIDE_LEFT.value
    MID_LEFT = PoseLibrary.MID_LEFT.value
    LEFT = PoseLibrary.LEFT.value
    CENTER = PoseLibrary.CENTER.value
    RIGHT = PoseLibrary.RIGHT.value
    MID_RIGHT = PoseLibrary.MID_RIGHT.value
    WIDE_RIGHT = PoseLibrary.WIDE_RIGHT.value
    AUDIENCE_CENTER = PoseLibrary.AUDIENCE_CENTER.value
    AUDIENCE_LEFT = PoseLibrary.AUDIENCE_LEFT.value
    AUDIENCE_RIGHT = PoseLibrary.AUDIENCE_RIGHT.value

    @property
    def pose_id(self) -> PoseLibrary:
        return PoseLibrary(self.value)

    @property
    def norm_value(self) -> float:
        values = {
            PanPose.WIDE_LEFT: 0.1,
            PanPose.MID_LEFT: 0.2,
            PanPose.LEFT: 0.3,
            PanPose.CENTER: 0.5,
            PanPose.RIGHT: 0.7,
            PanPose.MID_RIGHT: 0.8,
            PanPose.WIDE_RIGHT: 0.9,
            PanPose.AUDIENCE_CENTER: 0.5,
            PanPose.AUDIENCE_LEFT: 0.3,
            PanPose.AUDIENCE_RIGHT: 0.7,
        }
        return values[self]


class TiltPose(str, Enum):
    """Normalized tilt pose positions.

    This is a *collection* (subset) of :class:`PoseLibrary` for vertical positioning helpers.
    Values are ordered from up/sky (high) to down/stage (low).
    """

    SKY = PoseLibrary.SKY.value
    CEILING = PoseLibrary.CEILING.value
    HORIZON_UP_45 = PoseLibrary.HORIZON_UP_45.value
    HORIZON = PoseLibrary.HORIZON.value
    CROWD = PoseLibrary.CROWD.value
    STAGE = PoseLibrary.STAGE.value
    AUDIENCE_CENTER = PoseLibrary.AUDIENCE_CENTER.value
    AUDIENCE_LEFT = PoseLibrary.AUDIENCE_LEFT.value
    AUDIENCE_RIGHT = PoseLibrary.AUDIENCE_RIGHT.value

    @property
    def pose_id(self) -> PoseLibrary:
        return PoseLibrary(self.value)

    @property
    def norm_value(self) -> float:
        values = {
            TiltPose.SKY: 1.0,
            TiltPose.CEILING: 0.85,
            TiltPose.HORIZON_UP_45: 0.65,
            TiltPose.HORIZON: 0.5,
            TiltPose.CROWD: 0.3,
            TiltPose.STAGE: 0.1,
            TiltPose.AUDIENCE_CENTER: 0.3,
            TiltPose.AUDIENCE_LEFT: 0.3,
            TiltPose.AUDIENCE_RIGHT: 0.3,
        }
        return values[self]


def _is_pose_library_id(pose_id: PoseLibrary | str) -> TypeGuard[PoseLibrary]:
    return isinstance(pose_id, PoseLibrary)


# --- Standard pose definitions -------------------------------------------------
# NOTE: Keep these fixture-independent. Calibration/orientation happens elsewhere.
STANDARD_POSES: dict[PoseLibrary, Pose] = {
    # Audience-facing
    PoseLibrary.AUDIENCE_CENTER: Pose(
        pose_id=PoseLibrary.AUDIENCE_CENTER, name="Audience Center", pan_deg=0.0, tilt_deg=-20.0
    ),
    PoseLibrary.AUDIENCE_LEFT: Pose(
        pose_id=PoseLibrary.AUDIENCE_LEFT, name="Audience Left", pan_deg=-35.0, tilt_deg=-20.0
    ),
    PoseLibrary.AUDIENCE_RIGHT: Pose(
        pose_id=PoseLibrary.AUDIENCE_RIGHT, name="Audience Right", pan_deg=35.0, tilt_deg=-20.0
    ),
    # Neutral/home
    PoseLibrary.SOFT_HOME: Pose(
        pose_id=PoseLibrary.SOFT_HOME, name="Soft Home", pan_deg=0.0, tilt_deg=0.0
    ),
    # Normalized anchors (expressed as angles; these are generic defaults)
    PoseLibrary.WIDE_LEFT: Pose(
        pose_id=PoseLibrary.WIDE_LEFT, name="Wide Left", pan_deg=-120.0, tilt_deg=0.0
    ),
    PoseLibrary.MID_LEFT: Pose(
        pose_id=PoseLibrary.MID_LEFT, name="Mid Left", pan_deg=-90.0, tilt_deg=0.0
    ),
    PoseLibrary.LEFT: Pose(pose_id=PoseLibrary.LEFT, name="Left", pan_deg=-60.0, tilt_deg=0.0),
    PoseLibrary.CENTER: Pose(pose_id=PoseLibrary.CENTER, name="Center", pan_deg=0.0, tilt_deg=0.0),
    PoseLibrary.RIGHT: Pose(pose_id=PoseLibrary.RIGHT, name="Right", pan_deg=60.0, tilt_deg=0.0),
    PoseLibrary.MID_RIGHT: Pose(
        pose_id=PoseLibrary.MID_RIGHT, name="Mid Right", pan_deg=90.0, tilt_deg=0.0
    ),
    PoseLibrary.WIDE_RIGHT: Pose(
        pose_id=PoseLibrary.WIDE_RIGHT, name="Wide Right", pan_deg=120.0, tilt_deg=0.0
    ),
    PoseLibrary.SKY: Pose(pose_id=PoseLibrary.SKY, name="Sky", pan_deg=0.0, tilt_deg=80.0),
    PoseLibrary.CEILING: Pose(pose_id=PoseLibrary.CEILING, name="Sky", pan_deg=0.0, tilt_deg=80.0),
    PoseLibrary.HORIZON_UP_45: Pose(
        pose_id=PoseLibrary.HORIZON_UP_45, name="Horizon Up 45", pan_deg=0.0, tilt_deg=30.0
    ),
    PoseLibrary.HORIZON: Pose(
        pose_id=PoseLibrary.HORIZON, name="Horizon", pan_deg=0.0, tilt_deg=0.0
    ),
    PoseLibrary.CROWD: Pose(pose_id=PoseLibrary.CROWD, name="Crowd", pan_deg=0.0, tilt_deg=-20.0),
    PoseLibrary.STAGE: Pose(pose_id=PoseLibrary.STAGE, name="Stage", pan_deg=0.0, tilt_deg=-60.0),
}


def resolve_pose(pose_id: PoseLibrary | str, config: PoseConfig | None = None) -> Pose:
    """Resolve a pose id to a concrete Pose.

    Resolution order:
      1) Standard overrides (PoseLibrary only)
      2) Standard definitions (PoseLibrary only)
      3) Custom poses (string keys)

    Args:
        pose_id: Standard PoseLibrary id or custom string id.
        config: Optional PoseConfig.

    Returns:
        Resolved Pose.

    Raises:
        KeyError: if pose_id cannot be resolved.
    """
    cfg = config or PoseConfig()

    if _is_pose_library_id(pose_id):
        if pose_id in cfg.pose_overrides:
            return cfg.pose_overrides[pose_id]
        if pose_id in STANDARD_POSES:
            return STANDARD_POSES[pose_id]

    key = pose_id.value if isinstance(pose_id, PoseLibrary) else str(pose_id).upper()
    if key in cfg.custom_poses:
        return cfg.custom_poses[key]

    raise KeyError(f"Unknown pose_id: {pose_id!r}")


def all_poses(config: PoseConfig | None = None) -> dict[str, Pose]:
    """Return the merged pose dictionary (standard + overrides + custom).

    Args:
        config: Optional PoseConfig.

    Returns:
        Dict keyed by pose_id string.
    """
    cfg = config or PoseConfig()
    merged: dict[str, Pose] = {pose_key.value: pose for pose_key, pose in STANDARD_POSES.items()}

    for override_key, override_pose in cfg.pose_overrides.items():
        merged[override_key.value] = override_pose

    for custom_key, custom_pose in cfg.custom_poses.items():
        merged[str(custom_key).upper()] = custom_pose

    return merged
