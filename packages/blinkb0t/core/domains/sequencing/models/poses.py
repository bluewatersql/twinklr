"""Semantic pose models for fixture-independent choreography."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PoseID(str, Enum):
    """Standard pose identifiers."""

    CENTER = "CENTER"
    CENTER_SOFT = "CENTER_SOFT"
    MID_LEFT = "MID_LEFT"
    MID_RIGHT = "MID_RIGHT"
    WIDE_LEFT = "WIDE_LEFT"
    WIDE_RIGHT = "WIDE_RIGHT"
    MAX_LEFT = "MAX_LEFT"
    MAX_RIGHT = "MAX_RIGHT"
    CURRENT = "CURRENT"
    FORWARD = "FORWARD"
    UP = "UP"
    DOWN = "DOWN"
    CEILING = "CEILING"
    SOFT_HOME = "SOFT_HOME"


class Pose(BaseModel):
    """Semantic position definition.

    A pose defines a fixture-independent target position using pan/tilt angles.
    These angles are relative to the fixture's home position and can be adjusted
    based on fixture orientation.
    """

    model_config = ConfigDict(frozen=True)

    pose_id: str = Field(description="Unique pose identifier (e.g., 'FORWARD', 'AUDIENCE_CENTER')")

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


class PoseConfig(BaseModel):
    """Pose configuration for JobConfig.

    Allows users to override standard poses or add custom poses.
    Standard poses are loaded by default and can be supplemented.
    """

    # User-defined custom poses (added to standard set)
    custom_poses: dict[str, Pose] = Field(
        default_factory=dict,
        description="Custom poses defined by user (added to standard poses)",
    )

    # Overrides for standard poses (replace default values)
    pose_overrides: dict[PoseID, Pose] = Field(
        default_factory=dict,
        description="Override standard pose definitions (e.g., adjust FORWARD for rig orientation)",
    )
