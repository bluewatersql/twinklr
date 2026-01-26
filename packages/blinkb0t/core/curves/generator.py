from __future__ import annotations

from typing import Any

from blinkb0t.core.curves.library import build_default_registry
from blinkb0t.core.curves.models import (
    CurvePoint,
)
from blinkb0t.core.curves.native import NativeCurveType, xLightsNativeCurve
from blinkb0t.core.curves.providers.custom import CustomCurveProvider
from blinkb0t.core.curves.providers.native import NativeCurveProvider
from blinkb0t.core.curves.registry import NativeCurveDefinition


class CurveGenerator:
    """Orchestrator for curve generation.

    Routes curve generation requests to appropriate providers
    based on curve source type.
    """

    def __init__(self) -> None:
        """Initialize curve generator with library and providers.

        Args:
            library: Curve library containing definitions
            native_provider: Provider for native xLights curves
            custom_provider: Provider for custom point array curves
        """
        self._registry = build_default_registry()
        self._native = NativeCurveProvider()
        self._custom = CustomCurveProvider(self._registry)

    def generate_native_spec(
        self, curve_id: str, params: dict[str, Any] | None = None
    ) -> xLightsNativeCurve:
        """Generate native xLights curve specification.

        Supports preset resolution: if curve is a preset, resolves to base curve
        and merges preset parameters with runtime parameters.

        Args:
            curve_id: Unique curve identifier
            params: Optional parameters to override defaults/presets

        Returns:
            ValueCurveSpec with curve type and p1-p4 parameters

        Raises:
            ValueError: If curve not found or not a native/preset curve
        """
        try:
            _ = NativeCurveType(curve_id.lower())
        except Exception as e:
            raise ValueError(f"Curve '{curve_id}' not a valid native curve type") from e

        curve_def = NativeCurveDefinition(curve_id=curve_id, default_params=params)
        return self._native.generate(curve_def, params)

    def generate_custom_points(
        self,
        curve_id: str,
        num_points: int = 100,
        **kwargs: Any,
    ) -> list[CurvePoint]:
        """Generate custom curve as point array.

        Supports preset resolution and intensity parameter injection.

        Args:
            curve_id: Unique curve identifier.
            num_points: Number of points to generate.
            **kwargs: Intensity params (amplitude, frequency, center_offset)
                      and curve-specific params (cycles, phase, etc.).

        Returns:
            List of curve points with time [0,1] and value in [0, 1].

        Raises:
            ValueError: If curve not found in library.
        """
        curve_def = self._registry.get(curve_id)
        if curve_def is None:
            raise ValueError(f"Curve '{curve_id}' not found in library")

        return self._custom.generate(curve_def, num_points, **kwargs)
