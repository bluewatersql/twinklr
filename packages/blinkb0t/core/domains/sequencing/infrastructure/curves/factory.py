"""Curve factory for generating appropriate curve specifications.

Abstracts away the complexity of determining whether a curve should be
Native (ValueCurveSpec) or Custom (CustomCurveSpec with point array).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
    CurveSource,
    CustomCurveType,
    NativeCurveType,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
    CustomCurveProvider,
    NativeCurveProvider,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import CustomCurveSpec
from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition, CurvePoint

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

logger = logging.getLogger(__name__)


class CurveFactory:
    """Factory for creating curve specifications.

    Determines whether a curve should be Native (xLights built-in) or Custom (point array)
    and returns the appropriate specification.

    Usage:
        >>> factory = CurveFactory()
        >>> spec = factory.create_curve("sine", min_dmx=75, max_dmx=200)
        >>> isinstance(spec, ValueCurveSpec)
        True
        >>> spec = factory.create_curve("cosine", min_dmx=75, max_dmx=200, num_points=100)
        >>> isinstance(spec, CustomCurveSpec)
        True
    """

    def __init__(self):
        """Initialize factory with curve providers."""
        self._native_provider = NativeCurveProvider()
        self._custom_provider = CustomCurveProvider()

    def create_curve(
        self,
        curve_name: str,
        min_dmx: float,
        max_dmx: float,
        params: dict | None = None,
        num_points: int = 100,
    ) -> ValueCurveSpec | CustomCurveSpec:
        """Create appropriate curve specification.

        Args:
            curve_name: Curve identifier (e.g., "sine", "cosine", "s_curve")
            min_dmx: Minimum DMX value for the curve range
            max_dmx: Maximum DMX value for the curve range
            params: Optional parameters (amplitude, center, etc.)
            num_points: Number of points for custom curves (default: 100)

        Returns:
            ValueCurveSpec for native curves, CustomCurveSpec for custom curves

        Raises:
            ValueError: If curve name is not recognized

        Example:
            >>> factory = CurveFactory()
            >>> # Native curve (xLights built-in)
            >>> sine_spec = factory.create_curve("sine", 0, 255, {"amplitude": 100})
            >>> # Custom curve (point array)
            >>> cosine_spec = factory.create_curve("cosine", 0, 255, num_points=100)
        """
        curve_name_lower = curve_name.lower()

        # Try native curve first
        if self._is_native_curve(curve_name_lower):
            return self._create_native_curve(curve_name_lower, min_dmx, max_dmx, params)

        # Try custom curve
        if self._is_custom_curve(curve_name_lower):
            return self._create_custom_curve(curve_name_lower, min_dmx, max_dmx, num_points)

        # Unknown curve
        raise ValueError(
            f"Unknown curve '{curve_name}'. Must be one of: "
            f"{', '.join([c.value for c in NativeCurveType])} (native) or "
            f"{', '.join([c.value for c in CustomCurveType])} (custom)"
        )

    def _is_native_curve(self, curve_name: str) -> bool:
        """Check if curve is a native xLights curve."""
        try:
            NativeCurveType(curve_name)
            return True
        except ValueError:
            return False

    def _is_custom_curve(self, curve_name: str) -> bool:
        """Check if curve is a custom (point array) curve."""
        try:
            CustomCurveType(curve_name)
            return True
        except ValueError:
            return False

    def _create_native_curve(
        self,
        curve_name: str,
        min_dmx: float,
        max_dmx: float,
        params: dict | None,
    ) -> ValueCurveSpec:
        """Create native curve specification.

        Args:
            curve_name: Native curve name
            min_dmx: Minimum DMX value
            max_dmx: Maximum DMX value
            params: Optional curve parameters (amplitude, center, etc.)

        Returns:
            ValueCurveSpec with appropriate parameters
        """
        # Calculate amplitude and center from DMX range if not provided
        # This ensures curves stay within valid DMX bounds (0-255)
        if params is None:
            params = {}

        # For sine/parabolic curves, calculate amplitude and center from DMX range
        curve_name_lower = curve_name.lower()
        if curve_name_lower in ("sine", "parabolic", "abs_sine") and "amplitude" not in params:
            # Amplitude is half the range (peak-to-peak)
            params["amplitude"] = (max_dmx - min_dmx) / 2.0

        if curve_name_lower in ("sine", "parabolic", "abs_sine") and "center" not in params:
            # Center is midpoint of the range
            params["center"] = (min_dmx + max_dmx) / 2.0

        curve_def = CurveDefinition(
            id=curve_name,
            source=CurveSource.NATIVE,
            base_curve=curve_name,
            base_curve_id=None,
            default_params=params or {},
        )

        # Generate native spec
        spec = self._native_provider.generate(curve_def, params)

        # Set min/max values
        spec.min_val = int(min_dmx)
        spec.max_val = int(max_dmx)

        logger.debug(
            f"Created native curve '{curve_name}': min={spec.min_val}, max={spec.max_val}, "
            f"p2={spec.p2:.2f}, p4={spec.p4:.2f}"
        )

        return spec

    def _create_custom_curve(
        self,
        curve_name: str,
        min_dmx: float,
        max_dmx: float,
        num_points: int,
    ) -> CustomCurveSpec:
        """Create custom curve specification with point array.

        Args:
            curve_name: Custom curve name
            min_dmx: Minimum DMX value (curve generated for this range)
            max_dmx: Maximum DMX value (curve generated for this range)
            num_points: Number of points to generate

        Returns:
            CustomCurveSpec with DMX point array
        """
        curve_def = CurveDefinition(
            id=curve_name,
            source=CurveSource.CUSTOM,
            base_curve=curve_name,
            base_curve_id=None,
            default_params={},
        )

        # Generate custom curve points in DMX space [min_dmx, max_dmx]
        points: list[CurvePoint] = self._custom_provider.generate(
            curve_def, num_points, min_dmx, max_dmx
        )

        # Return CustomCurveSpec
        spec = CustomCurveSpec(
            points=points,
            min_val=int(min_dmx),
            max_val=int(max_dmx),
            reverse=False,
        )

        logger.debug(
            f"Created custom curve '{curve_name}': {len(points)} points, "
            f"range=[{spec.min_val}, {spec.max_val}]"
        )

        return spec


# Global factory instance for convenience
_curve_factory: CurveFactory | None = None


def get_curve_factory() -> CurveFactory:
    """Get or create the global curve factory instance.

    Returns:
        Singleton CurveFactory instance
    """
    global _curve_factory
    if _curve_factory is None:
        _curve_factory = CurveFactory()
    return _curve_factory
