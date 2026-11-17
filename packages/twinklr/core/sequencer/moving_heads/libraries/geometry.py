"""Geometry identifiers `TemplateStep.geometry` validates."""

from __future__ import annotations

from enum import StrEnum


class GeometryType(StrEnum):
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
