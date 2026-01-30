"""Pose resolution - converts semantic poses to fixture-specific angles.

The PoseResolver handles:
1. Loading standard poses + user overrides
2. Converting pose IDs to pan/tilt angles
3. Composition with geometry offsets

Note: This is a simplified Phase 0 implementation focused on core functionality.
Range validation and fixture orientation will be enhanced in future phases.
"""

from __future__ import annotations

import logging

from twinklr.core.config.poses import STANDARD_POSES, Pose, PoseConfig, PoseLibrary

logger = logging.getLogger(__name__)


class PoseResolver:
    """Resolves semantic poses to pan/tilt angles.

    Handles:
    - Standard poses with user overrides
    - Custom user-defined poses
    - Geometry offset composition

    Example:
        resolver = PoseResolver(pose_config)

        # Resolve pose to angles
        pan, tilt = resolver.resolve_pose(PoseID.FORWARD)

        # With geometry offset
        pan, tilt = resolver.resolve_pose_with_offset(
            PoseID.FORWARD,
            pan_offset_deg=15.0,
            tilt_offset_deg=0.0
        )
    """

    def __init__(
        self,
        pose_config: PoseConfig | None = None,
        pan_range_deg: float = 540.0,
        tilt_range_deg: float = 270.0,
    ):
        """Initialize PoseResolver with pose configuration and optional range limits.

        Args:
            pose_config: Optional pose configuration (overrides, custom poses)
            pan_range_deg: Maximum pan range in degrees (default 540°)
            tilt_range_deg: Maximum tilt range in degrees (default 270°)
        """
        self.pose_config = pose_config or PoseConfig()
        self.pan_range_deg = pan_range_deg
        self.tilt_range_deg = tilt_range_deg

        # Build complete pose library (standard + overrides + custom)
        self.poses = self._build_pose_library()

        logger.debug(
            f"PoseResolver initialized with {len(self.poses)} poses "
            f"({len(STANDARD_POSES)} standard, "
            f"{len(self.pose_config.pose_overrides)} overrides, "
            f"{len(self.pose_config.custom_poses)} custom)"
        )

    def resolve_pose(self, pose_id: str | PoseLibrary) -> tuple[float, float]:
        """Resolve pose ID to pan/tilt angles.

        Args:
            pose_id: Pose identifier (enum or string)

        Returns:
            (pan_deg, tilt_deg) tuple

        Raises:
            KeyError: If pose_id not found in library

        Example:
            pan, tilt = resolver.resolve_pose(PoseID.FORWARD)
            # (0.0, 0.0) for default pose
        """
        # Convert string to PoseID if needed
        if isinstance(pose_id, str):
            # Check if it's a standard pose
            try:
                pose_id = PoseLibrary(pose_id.lower())
            except ValueError:
                # Custom pose (string key)
                pass

        # Get pose definition
        pose = self.poses.get(pose_id)
        if pose is None:
            raise KeyError(f"Pose '{pose_id}' not found. Available: {list(self.poses.keys())}")

        # Get base angles
        pan_deg = pose.pan_deg
        tilt_deg = pose.tilt_deg

        # Validate ranges
        pan_deg, tilt_deg = self._validate_ranges(pan_deg, tilt_deg)

        return pan_deg, tilt_deg

    def resolve_pose_with_offset(
        self,
        pose_id: str | PoseLibrary,
        pan_offset_deg: float = 0.0,
        tilt_offset_deg: float = 0.0,
    ) -> tuple[float, float]:
        """Resolve pose with geometry offset (pose + geometry composition).

        This is the primary method for pattern step rendering where
        poses compose with geometry transforms.

        Args:
            pose_id: Pose identifier
            pan_offset_deg: Pan offset from geometry (relative to pose)
            tilt_offset_deg: Tilt offset from geometry (relative to pose)

        Returns:
            (pan_deg, tilt_deg) tuple with pose + offsets

        Example:
            # FORWARD pose (0°, 0°) + fan geometry offset (+15°, 0°)
            pan, tilt = resolver.resolve_pose_with_offset(
                PoseID.FORWARD,
                pan_offset_deg=15.0,
                tilt_offset_deg=0.0
            )
            # Result: (15.0, 0.0)
        """
        # Get base pose angles
        base_pan, base_tilt = self.resolve_pose(pose_id)

        # Add geometry offsets
        final_pan = base_pan + pan_offset_deg
        final_tilt = base_tilt + tilt_offset_deg

        # Validate final position
        final_pan, final_tilt = self._validate_ranges(final_pan, final_tilt)

        return final_pan, final_tilt

    def get_pose(self, pose_id: str | PoseLibrary) -> Pose:
        """Get raw pose definition.

        Args:
            pose_id: Pose identifier

        Returns:
            Pose definition

        Raises:
            KeyError: If pose not found
        """
        if isinstance(pose_id, str):
            try:
                pose_id = PoseLibrary(pose_id.lower())
            except ValueError:
                pass

        pose = self.poses.get(pose_id)
        if pose is None:
            raise KeyError(f"Pose '{pose_id}' not found")
        return pose

    def list_poses(self) -> list[str]:
        """List all available pose IDs (standard + custom).

        Returns:
            List of pose ID strings
        """
        return [p.value if isinstance(p, PoseLibrary) else p for p in self.poses.keys()]

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _build_pose_library(self) -> dict[str | PoseLibrary, Pose]:
        """Build complete pose library (standard + overrides + custom)."""
        poses: dict[str | PoseLibrary, Pose] = {}

        # Start with standard poses (cast to correct type)
        for pose_id, pose in STANDARD_POSES.items():
            poses[pose_id] = pose

        # Apply overrides
        for pose_id, override_pose in self.pose_config.pose_overrides.items():
            poses[pose_id] = override_pose
            logger.debug(f"Applied override for standard pose: {pose_id}")

        # Add custom poses (string keys)
        for pose_id_str, custom_pose in self.pose_config.custom_poses.items():
            poses[pose_id_str] = custom_pose
            logger.debug(f"Added custom pose: {pose_id_str}")

        return poses

    def _validate_ranges(
        self,
        pan_deg: float,
        tilt_deg: float,
    ) -> tuple[float, float]:
        """Validate and clamp angles to physical range.

        Args:
            pan_deg: Desired pan angle
            tilt_deg: Desired tilt angle

        Returns:
            (pan_deg, tilt_deg) clamped to valid range
        """
        # Get ranges (centered at 0°)
        pan_max = self.pan_range_deg / 2
        pan_min = -pan_max

        tilt_max = self.tilt_range_deg / 2
        tilt_min = -tilt_max

        # Clamp to range
        if pan_deg < pan_min or pan_deg > pan_max:
            original_pan = pan_deg
            pan_deg = max(pan_min, min(pan_max, pan_deg))
            logger.warning(
                f"Pan {original_pan:.1f}° out of range [{pan_min:.1f}°, {pan_max:.1f}°], "
                f"clamped to {pan_deg:.1f}°"
            )

        if tilt_deg < tilt_min or tilt_deg > tilt_max:
            original_tilt = tilt_deg
            tilt_deg = max(tilt_min, min(tilt_max, tilt_deg))
            logger.warning(
                f"Tilt {original_tilt:.1f}° out of range [{tilt_min:.1f}°, {tilt_max:.1f}°], "
                f"clamped to {tilt_deg:.1f}°"
            )

        return pan_deg, tilt_deg
