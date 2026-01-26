from __future__ import annotations

from typing import Any

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
        **kwargs: Any,
    ) -> list[CurvePoint]:
        """Generate custom curve as point array.

        All kwargs (including intensity parameters) are passed through
        to the registry resolver and ultimately to the curve function.

        Args:
            curve_def: Curve definition from library.
            num_points: Number of points to generate.
            **kwargs: Intensity params (amplitude, frequency, etc.) + curve-specific params.

        Returns:
            List of curve points with time [0,1] and value in [0, 1].

        Raises:
            ValueError: If curve type is unknown.
        """
        return self.registry.resolve(curve_def, n_samples=num_points, **kwargs)
