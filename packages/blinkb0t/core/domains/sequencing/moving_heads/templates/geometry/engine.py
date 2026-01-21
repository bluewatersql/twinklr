"""Geometry Engine for managing and applying geometry transformations."""

from __future__ import annotations

import logging
from typing import Any

from .base import GeometryTransform

logger = logging.getLogger(__name__)


class GeometryEngine:
    """Central geometry transformation engine.

    Manages a registry of geometry transforms and routes geometry
    types to appropriate transform implementations.

    Usage:
        engine = GeometryEngine()
        per_fixture_movements = engine.apply_geometry(
            geometry_type="wave_lr",
            targets=["MH1", "MH2", "MH3", "MH4"],
            base_movement={"pattern": "sweep_lr", "amplitude_deg": 60}
        )
    """

    def __init__(self):
        """Initialize geometry engine with built-in transforms."""
        self.transforms: dict[str, GeometryTransform] = {}
        self._register_builtin_transforms()
        logger.debug(f"Geometry engine initialized with {len(self.transforms)} transforms")

    def _register_builtin_transforms(self) -> None:
        """Register all built-in geometry transforms.

        Imports are done here to avoid circular dependencies.
        """
        # Import transforms locally to avoid circular imports
        from .patterns.alternating_updown import AlternatingUpDownTransform
        from .patterns.audience_scan import AudienceScanTransform
        from .patterns.center_out import CenterOutTransform
        from .patterns.chevron_v import ChevronVTransform
        from .patterns.fan import FanTransform
        from .patterns.mirror_lr import MirrorLRTransform
        from .patterns.rainbow_arc import RainbowArcTransform
        from .patterns.scattered_chaos import ScatteredChaosTransform
        from .patterns.spotlight_cluster import SpotlightClusterTransform
        from .patterns.tunnel_cone import TunnelConeTransform
        from .patterns.wall_wash import WallWashTransform
        from .patterns.wave_lr import WaveLRTransform
        from .patterns.x_cross import XCrossTransform

        # Register built-in transforms
        self.register(MirrorLRTransform())
        self.register(WaveLRTransform())
        self.register(FanTransform())
        self.register(ChevronVTransform())
        self.register(AudienceScanTransform())
        self.register(WallWashTransform())
        self.register(SpotlightClusterTransform())
        self.register(RainbowArcTransform())
        self.register(AlternatingUpDownTransform())  # type: ignore[arg-type]
        self.register(TunnelConeTransform())  # type: ignore[arg-type]
        self.register(CenterOutTransform())
        self.register(XCrossTransform())
        self.register(ScatteredChaosTransform())

        logger.debug(f"Registered {len(self.transforms)} geometry transforms")

    def register(self, transform: GeometryTransform) -> None:
        """Register a geometry transform.

        Args:
            transform: GeometryTransform instance to register
        """
        if not transform.geometry_type:
            raise ValueError(f"Transform {transform.__class__.__name__} missing geometry_type")

        if transform.geometry_type in self.transforms:
            logger.warning(
                f"Transform for '{transform.geometry_type}' already registered. Overwriting."
            )

        self.transforms[transform.geometry_type] = transform
        logger.debug(f"Registered geometry transform: {transform.geometry_type}")

    def contains_offsets(
        self,
        geometry_type: str | None,
        params: dict[str, Any] | None = None,
    ) -> bool:
        """Check if a geometry configuration contains per-fixture offsets.

        This hides the complexity of checking various geometry parameters
        to determine if fixtures will have different positions/movements.

        Used to optimize effect creation - if no offsets exist, we can create
        one EffectDB entry and reuse it for all fixtures instead of creating
        N separate entries.

        Args:
            geometry_type: Geometry pattern name (e.g., "wave_lr", "mirror_lr")
            params: Optional geometry-specific parameters

        Returns:
            True if geometry contains offsets (fixtures differ), False otherwise
        """
        # No geometry - no offsets
        if not geometry_type:
            return False

        params = params or {}

        # Check each geometry type for parameters that create NO offsets
        if geometry_type == "wall_wash":
            # tight spacing = all zeros = no offsets
            spacing = params.get("spacing", "tight")
            base_offset = params.get("base_pan_offset_deg", 0)
            pan_spread = params.get("pan_spread_deg")
            # If explicitly set to 0 spread and tight spacing, no offsets
            if spacing == "tight" and (pan_spread == 0 or base_offset == 0):
                return False
            return True

        elif geometry_type == "fan":
            # Zero spread = no offsets
            total_spread = params.get("total_spread_deg", 60)
            return bool(total_spread != 0)

        elif geometry_type == "spotlight_cluster":
            # Zero spread with single fixture = no offsets
            spread = params.get("spread", 0.2)
            return bool(spread != 0.0)

        elif geometry_type == "rainbow_arc":
            # Zero arc width = no offsets
            arc_width = params.get("arc_width_deg", 120.0)
            return bool(arc_width != 0.0)

        elif geometry_type == "tunnel_cone":
            # Zero pan_spread_deg = no offsets
            pan_spread = params.get("pan_spread_deg", 90.0)
            return bool(pan_spread != 0.0)

        elif geometry_type == "alternating_updown":
            # Always contains offsets (different tilt roles per fixture)
            return True

        # Most geometry types inherently contain offsets
        # wave_lr, mirror_lr, chevron_v, audience_scan
        return True

    def apply_geometry(
        self,
        geometry_type: str | None,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply geometry transformation to create per-fixture movements.

        Args:
            geometry_type: Geometry pattern name (e.g., "wave_lr", "mirror_lr")
                          If None, returns base movement for all targets
            targets: List of fixture names
            base_movement: Base movement specification
            params: Optional geometry-specific parameters

        Returns:
            Dict mapping fixture name to transformed movement spec

        Example:
            >>> engine = GeometryEngine()
            >>> result = engine.apply_geometry(
            ...     geometry_type="wave_lr",
            ...     targets=["MH1", "MH2", "MH3", "MH4"],
            ...     base_movement={"pattern": "sweep_lr", "amplitude_deg": 60}
            ... )
        """
        # No geometry specified - return base movement for all targets
        if not geometry_type:
            return {target: base_movement.copy() for target in targets}

        # Get transform
        transform = self.transforms.get(geometry_type)
        if not transform:
            logger.warning(
                f"No geometry transform for '{geometry_type}'. "
                f"Available: {list(self.transforms.keys())}. "
                f"Returning base movement for all targets."
            )
            return {target: base_movement.copy() for target in targets}

        # Apply geometry transformation
        try:
            result = transform.apply(targets, base_movement, params or {})
            logger.debug(f"Applied geometry '{geometry_type}' to {len(targets)} targets")
            return result
        except Exception as e:
            logger.error(
                f"Error applying geometry '{geometry_type}': {e}. Falling back to base movement."
            )
            return {target: base_movement.copy() for target in targets}

    def list_geometries(self) -> list[str]:
        """Get list of available geometry types.

        Returns:
            Sorted list of geometry type names
        """
        return sorted(self.transforms.keys())

    def has_geometry(self, geometry_type: str) -> bool:
        """Check if a geometry type is registered.

        Args:
            geometry_type: Geometry pattern name

        Returns:
            True if geometry is registered
        """
        return geometry_type in self.transforms
