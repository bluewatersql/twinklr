"""Pose system - semantic position abstraction for moving heads.

Provides fixture-independent choreography through semantic poses
that are resolved to fixture-specific angles at render time.
"""

# Re-export models for convenience
from blinkb0t.core.domains.sequencing.models.poses import Pose, PoseConfig, PoseID

from .resolver import PoseResolver
from .standards import STANDARD_POSES, get_pose_by_name, get_standard_pose, list_standard_poses

__all__ = [
    "PoseResolver",
    "STANDARD_POSES",
    "get_standard_pose",
    "list_standard_poses",
    "get_pose_by_name",
    "Pose",
    "PoseID",
    "PoseConfig",
]
