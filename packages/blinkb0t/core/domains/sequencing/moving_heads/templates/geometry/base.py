"""Base classes for geometry transformations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Valid tilt roles from geometry_library.json
TiltRole = Literal["above_horizon", "up", "zero"]
VALID_TILT_ROLES: set[str] = {"above_horizon", "up", "zero"}


class GeometryTransform(ABC):
    """Base class for geometry transformations.

    Geometry transforms take a base movement specification and apply
    spatial variations per fixture to create formations (mirror, wave,
    fan, etc.).

    Each transform implements a specific spatial pattern from the
    geometry_library.json.

    Phase 0 Enhancement: Transforms can now assign tilt roles (above_horizon,
    up, zero) to fixtures for vertical positioning control.
    """

    # Geometry identifier (e.g., "wave_lr", "mirror_lr")
    geometry_type: str = ""

    @abstractmethod
    def apply(
        self,
        targets: list[str],
        base_movement: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Apply geometry transformation to create per-fixture movements.

        Args:
            targets: List of fixture names (e.g., ["MH1", "MH2", "MH3", "MH4"])
            base_movement: Base movement specification from plan
            params: Optional geometry-specific parameters

        Returns:
            Dict mapping fixture name to transformed movement spec

        Example:
            >>> transform = WaveLRTransform()
            >>> base = {"pattern": "sweep_lr", "amplitude_deg": 60}
            >>> result = transform.apply(["MH1", "MH2"], base, {})
            >>> result
            {
                "MH1": {"pattern": "sweep_lr", "amplitude_deg": 60, "phase_deg": 0},
                "MH2": {"pattern": "sweep_lr", "amplitude_deg": 60, "phase_deg": 180}
            }
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement apply()")

    def _clone_movement(self, base_movement: dict[str, Any]) -> dict[str, Any]:
        """Helper to create a deep copy of base movement."""
        return dict(base_movement.items())

    def _validate_tilt_role(self, tilt_role: str) -> bool:
        """Validate that tilt_role is a recognized value.

        Args:
            tilt_role: Tilt role string to validate

        Returns:
            True if valid, False otherwise

        Valid roles:
            - "above_horizon": Audience-safe ~15° above horizon (default)
            - "up": Straight up (90°) for volumetric/overhead effects
            - "zero": Straight forward at horizon
        """
        if tilt_role not in VALID_TILT_ROLES:
            logger.warning(
                f"Invalid tilt_role '{tilt_role}' for {self.geometry_type}. "
                f"Valid: {VALID_TILT_ROLES}. Using 'above_horizon'."
            )
            return False
        return True

    def _assign_tilt_role(
        self, movement: dict[str, Any], tilt_role: str | None = None
    ) -> dict[str, Any]:
        """Assign a tilt role to a movement specification.

        Args:
            movement: Movement dict to modify (will be modified in-place)
            tilt_role: Tilt role to assign ("above_horizon", "up", "zero")
                      If None, defaults to "above_horizon"

        Returns:
            Modified movement dict (same object)

        Example:
            >>> movement = {"pattern": "sweep_lr", "amplitude_deg": 60}
            >>> self._assign_tilt_role(movement, "up")
            {"pattern": "sweep_lr", "amplitude_deg": 60, "tilt_role": "up"}
        """
        if tilt_role is None:
            tilt_role = "above_horizon"

        # Validate role
        if self._validate_tilt_role(tilt_role):
            movement["tilt_role"] = tilt_role
        else:
            # Fallback to default if invalid
            movement["tilt_role"] = "above_horizon"

        return movement

    def _get_tilt_role_from_params(
        self, params: dict[str, Any] | None, default: str = "above_horizon"
    ) -> str:
        """Extract tilt role from geometry parameters with validation.

        Args:
            params: Geometry parameters dict
            default: Default tilt role if not specified or invalid

        Returns:
            Validated tilt role string

        Example:
            >>> params = {"tilt": "up", "pan_spread_deg": 30}
            >>> role = self._get_tilt_role_from_params(params)
            "up"
        """
        if params is None:
            return default

        # Check for 'tilt' or 'tilt_role' param
        tilt_role = params.get("tilt") or params.get("tilt_role")

        if tilt_role is None:
            return default

        # Ensure tilt_role is a string
        if not isinstance(tilt_role, str):
            return default

        # Validate and return
        if self._validate_tilt_role(tilt_role):
            return tilt_role
        else:
            return default
