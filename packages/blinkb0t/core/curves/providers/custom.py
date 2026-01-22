from __future__ import annotations

from blinkb0t.core.curves.models import (
    CurvePoint,
)
from blinkb0t.core.curves.registry import CurveDefinition, CurveRegistry


class CustomCurveProvider:
    """Provider for custom point array curves.

    Generates list[CurvePoint] for curves not supported natively by xLights.
    All curves are normalized to [0, 1] for time and value.
    """

    def __init__(self, registry: CurveRegistry) -> None:
        """Initialize custom curve provider with registry.

        Args:
            registry: Curve registry to lookup curve definitions
        """
        self.registry = registry

    def generate(
        self,
        curve_def: CurveDefinition,
        num_points: int = 100,
    ) -> list[CurvePoint]:
        """Generate custom curve as point array in DMX space.

        Args:
            curve_def: Curve definition from library
            num_points: Number of points to generate
            min_dmx: Minimum DMX value (generate curve for this range)
            max_dmx: Maximum DMX value (generate curve for this range)

        Returns:
            List of curve points with time [0,1] and value in [min_dmx, max_dmx]

        Raises:
            ValueError: If curve type is unknown
        """
        return self.registry.resolve(curve_def, n_samples=num_points)
