from __future__ import annotations

from typing import Any

from twinklr.core.curves.native import NativeCurveType, xLightsNativeCurve
from twinklr.core.curves.registry import NativeCurveDefinition


class NativeCurveProvider:
    """Provider for xLights native parametric curves.

    Generates ValueCurveSpec with p1-p4 parameters for xLights native curves.
    Each curve type has different parameter mappings.
    """

    def generate(
        self, curve_def: NativeCurveDefinition, params: dict[str, Any] | None = None
    ) -> xLightsNativeCurve:
        """Generate native curve specification.

        Args:
            curve_def: Curve definition from library
            params: Optional parameters to override defaults

        Returns:
            ValueCurveSpec with curve type and p1-p4 parameters

        Raises:
            ValueError: If curve type is unknown
        """
        # Merge default params with provided params
        merged_params = {**(curve_def.default_params or {}), **(params or {})}
        curve_type = NativeCurveType(curve_def.curve_id.lower())

        # Map parameters based on curve type
        if curve_type == NativeCurveType.SINE:
            return self._generate_sine(merged_params)
        elif curve_type == NativeCurveType.RAMP:
            return self._generate_ramp(merged_params)
        elif curve_type == NativeCurveType.PARABOLIC:
            return self._generate_parabolic(merged_params)
        elif curve_type == NativeCurveType.SAW_TOOTH:
            return self._generate_saw_tooth(merged_params)
        elif curve_type == NativeCurveType.FLAT:
            return self._generate_flat(merged_params)
        elif curve_type == NativeCurveType.ABS_SINE:
            return self._generate_abs_sine(merged_params)
        elif curve_type == NativeCurveType.LOGARITHMIC:
            return self._generate_logarithmic(merged_params)
        elif curve_type == NativeCurveType.EXPONENTIAL:
            return self._generate_exponential(merged_params)
        else:
            raise ValueError(f"Unsupported native curve type: {curve_type}")

    def _generate_sine(self, params: dict[str, Any]) -> xLightsNativeCurve:
        """Generate sine curve spec (p2=amplitude, p4=center)."""
        return xLightsNativeCurve(
            type=NativeCurveType.SINE,
            p2=float(params.get("amplitude", 100.0)),
            p4=float(params.get("center", 128.0)),
        )

    def _generate_ramp(self, params: dict[str, Any]) -> xLightsNativeCurve:
        """Generate ramp curve spec (p1=min, p2=max)."""
        return xLightsNativeCurve(
            type=NativeCurveType.RAMP,
            p1=float(params.get("min", 0.0)),
            p2=float(params.get("max", 255.0)),
        )

    def _generate_parabolic(self, params: dict[str, Any]) -> xLightsNativeCurve:
        """Generate parabolic curve spec (p2=amplitude, p4=center)."""
        return xLightsNativeCurve(
            type=NativeCurveType.PARABOLIC,
            p2=float(params.get("amplitude", 100.0)),
            p4=float(params.get("center", 128.0)),
        )

    def _generate_saw_tooth(self, params: dict[str, Any]) -> xLightsNativeCurve:
        """Generate saw tooth curve spec (p1=min, p2=max)."""
        return xLightsNativeCurve(
            type=NativeCurveType.SAW_TOOTH,
            p1=float(params.get("min", 0.0)),
            p2=float(params.get("max", 255.0)),
        )

    def _generate_flat(self, params: dict[str, Any]) -> xLightsNativeCurve:
        """Generate flat curve spec (constant value)."""
        return xLightsNativeCurve(
            type=NativeCurveType.FLAT,
            p1=float(params.get("value", 128.0)),
        )

    def _generate_abs_sine(self, params: dict[str, Any]) -> xLightsNativeCurve:
        """Generate absolute sine curve spec."""
        return xLightsNativeCurve(
            type=NativeCurveType.ABS_SINE,
            p2=float(params.get("amplitude", 100.0)),
            p4=float(params.get("center", 128.0)),
        )

    def _generate_logarithmic(self, params: dict[str, Any]) -> xLightsNativeCurve:
        """Generate logarithmic curve spec."""
        return xLightsNativeCurve(
            type=NativeCurveType.LOGARITHMIC,
            p1=float(params.get("min", 0.0)),
            p2=float(params.get("max", 255.0)),
        )

    def _generate_exponential(self, params: dict[str, Any]) -> xLightsNativeCurve:
        """Generate exponential curve spec."""
        return xLightsNativeCurve(
            type=NativeCurveType.EXPONENTIAL,
            p1=float(params.get("min", 0.0)),
            p2=float(params.get("max", 255.0)),
        )
