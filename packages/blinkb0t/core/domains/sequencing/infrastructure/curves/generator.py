"""Curve generation with provider pattern.

Orchestrates curve generation through specialized providers:
- NativeCurveProvider: xLights parametric curves (p1-p4)
- CustomCurveProvider: Custom point array curves

Avoids god-class anti-pattern by separating concerns.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
    CurveSource,
    CustomCurveType,
    NativeCurveType,
)
from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
from blinkb0t.core.domains.sequencing.models.curves import (
    CurveDefinition,
    CurvePoint,
    ValueCurveSpec,
)


class NativeCurveProvider:
    """Provider for xLights native parametric curves.

    Generates ValueCurveSpec with p1-p4 parameters for xLights native curves.
    Each curve type has different parameter mappings.
    """

    def generate(
        self, curve_def: CurveDefinition, params: dict[str, Any] | None = None
    ) -> ValueCurveSpec:
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
        merged_params = {**curve_def.default_params, **(params or {})}

        # Parse curve type (case-insensitive for robustness)
        try:
            # Try exact match first
            curve_type = NativeCurveType(curve_def.base_curve)
        except ValueError:
            # Try case-insensitive match
            try:
                curve_type = NativeCurveType(
                    curve_def.base_curve.lower() if curve_def.base_curve else None
                )
            except ValueError as e:
                raise ValueError(f"Unknown native curve type: {curve_def.base_curve}") from e

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

    def _generate_sine(self, params: dict[str, Any]) -> ValueCurveSpec:
        """Generate sine curve spec (p2=amplitude, p4=center)."""
        return ValueCurveSpec(
            type=NativeCurveType.SINE,
            p2=float(params.get("amplitude", 100.0)),
            p4=float(params.get("center", 128.0)),
        )

    def _generate_ramp(self, params: dict[str, Any]) -> ValueCurveSpec:
        """Generate ramp curve spec (p1=min, p2=max)."""
        return ValueCurveSpec(
            type=NativeCurveType.RAMP,
            p1=float(params.get("min", 0.0)),
            p2=float(params.get("max", 255.0)),
        )

    def _generate_parabolic(self, params: dict[str, Any]) -> ValueCurveSpec:
        """Generate parabolic curve spec (p2=amplitude, p4=center)."""
        return ValueCurveSpec(
            type=NativeCurveType.PARABOLIC,
            p2=float(params.get("amplitude", 100.0)),
            p4=float(params.get("center", 128.0)),
        )

    def _generate_saw_tooth(self, params: dict[str, Any]) -> ValueCurveSpec:
        """Generate saw tooth curve spec (p1=min, p2=max)."""
        return ValueCurveSpec(
            type=NativeCurveType.SAW_TOOTH,
            p1=float(params.get("min", 0.0)),
            p2=float(params.get("max", 255.0)),
        )

    def _generate_flat(self, params: dict[str, Any]) -> ValueCurveSpec:
        """Generate flat curve spec (constant value)."""
        return ValueCurveSpec(
            type=NativeCurveType.FLAT,
            p1=float(params.get("value", 128.0)),
        )

    def _generate_abs_sine(self, params: dict[str, Any]) -> ValueCurveSpec:
        """Generate absolute sine curve spec."""
        return ValueCurveSpec(
            type=NativeCurveType.ABS_SINE,
            p2=float(params.get("amplitude", 100.0)),
            p4=float(params.get("center", 128.0)),
        )

    def _generate_logarithmic(self, params: dict[str, Any]) -> ValueCurveSpec:
        """Generate logarithmic curve spec."""
        return ValueCurveSpec(
            type=NativeCurveType.LOGARITHMIC,
            p1=float(params.get("min", 0.0)),
            p2=float(params.get("max", 255.0)),
        )

    def _generate_exponential(self, params: dict[str, Any]) -> ValueCurveSpec:
        """Generate exponential curve spec."""
        return ValueCurveSpec(
            type=NativeCurveType.EXPONENTIAL,
            p1=float(params.get("min", 0.0)),
            p2=float(params.get("max", 255.0)),
        )


class CustomCurveProvider:
    """Provider for custom point array curves.

    Generates list[CurvePoint] for curves not supported natively by xLights.
    All curves are normalized to [0, 1] for time and value.
    """

    def generate(
        self,
        curve_def: CurveDefinition,
        num_points: int = 100,
        min_dmx: float = 0.0,
        max_dmx: float = 255.0,
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
        # Parse curve type (case-insensitive for robustness)
        try:
            # Try exact match first
            curve_type = CustomCurveType(curve_def.base_curve)
        except ValueError:
            # Try case-insensitive match
            try:
                curve_type = CustomCurveType(
                    curve_def.base_curve.lower() if curve_def.base_curve else None
                )
            except ValueError as e:
                raise ValueError(f"Unknown custom curve type: {curve_def.base_curve}") from e

        # Generate normalized time array [0, 1]
        t = np.linspace(0, 1, num_points)

        # Generate curve values based on type
        if curve_type == CustomCurveType.COSINE:
            values = self._generate_cosine(t)
        elif curve_type == CustomCurveType.TRIANGLE:
            values = self._generate_triangle(t)
        elif curve_type == CustomCurveType.S_CURVE:
            values = self._generate_s_curve(t)
        elif curve_type == CustomCurveType.SQUARE:
            values = self._generate_square(t)
        elif curve_type == CustomCurveType.SMOOTHER_STEP:
            values = self._generate_smoother_step(t)
        elif curve_type == CustomCurveType.SMOOTH_STEP:
            values = self._generate_smooth_step(t)
        elif curve_type == CustomCurveType.EASE_IN_SINE:
            values = self._generate_ease_in_sine(t)
        elif curve_type == CustomCurveType.EASE_OUT_SINE:
            values = self._generate_ease_out_sine(t)
        elif curve_type == CustomCurveType.EASE_IN_OUT_SINE:
            values = self._generate_ease_in_out_sine(t)
        elif curve_type == CustomCurveType.EASE_IN_QUAD:
            values = self._generate_ease_in_quad(t)
        elif curve_type == CustomCurveType.EASE_OUT_QUAD:
            values = self._generate_ease_out_quad(t)
        elif curve_type == CustomCurveType.EASE_IN_OUT_QUAD:
            values = self._generate_ease_in_out_quad(t)
        elif curve_type == CustomCurveType.EASE_IN_CUBIC:
            values = self._generate_ease_in_cubic(t)
        elif curve_type == CustomCurveType.EASE_OUT_CUBIC:
            values = self._generate_ease_out_cubic(t)
        elif curve_type == CustomCurveType.EASE_IN_OUT_CUBIC:
            values = self._generate_ease_in_out_cubic(t)
        elif curve_type == CustomCurveType.BOUNCE_IN:
            values = self._generate_bounce_in(t)
        elif curve_type == CustomCurveType.BOUNCE_OUT:
            values = self._generate_bounce_out(t)
        elif curve_type == CustomCurveType.ELASTIC_IN:
            values = self._generate_elastic_in(t)
        elif curve_type == CustomCurveType.ELASTIC_OUT:
            values = self._generate_elastic_out(t)
        elif curve_type == CustomCurveType.PERLIN_NOISE:
            values = self._generate_perlin_noise(t)
        elif curve_type == CustomCurveType.LISS_AJOUS:
            values = self._generate_lissajous(t)
        elif curve_type == CustomCurveType.BEZIER:
            values = self._generate_bezier(t)
        elif curve_type == CustomCurveType.ANTICIPATE:
            values = self._generate_anticipate(t)
        elif curve_type == CustomCurveType.OVERSHOOT:
            values = self._generate_overshoot(t)
        else:
            # Default to linear for unknown curves
            values = t

        # Map normalized values [0, 1] to DMX range [min_dmx, max_dmx]
        dmx_values = min_dmx + values * (max_dmx - min_dmx)

        # Clamp values to ensure they stay within [min_dmx, max_dmx]
        # Some curves (elastic, overshoot, anticipate, bounce) can exceed [0, 1]
        dmx_values = np.clip(dmx_values, min_dmx, max_dmx)

        # Create CurvePoint objects with DMX values
        return [CurvePoint(time=float(t[i]), value=float(dmx_values[i])) for i in range(len(t))]

    def _generate_cosine(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Generate cosine wave (complementary to sine).

        Starts at 1, dips to 0 at middle, returns to 1.
        """
        result: np.ndarray = (np.cos(2 * np.pi * t) + 1) / 2  # type: ignore[type-arg]
        return result

    def _generate_triangle(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Generate triangle wave (linear rise and fall)."""
        # Rise from 0 to 1 then fall back to 0
        result: np.ndarray = 1 - np.abs((t * 2) % 2 - 1)  # type: ignore[type-arg]
        return result

    def _generate_s_curve(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Generate S-curve (sigmoid).

        Smooth transition from 0 to 1.
        """
        # Sigmoid function scaled to [0, 1]
        # Use range [-6, 6] for good S-shape
        x = (t - 0.5) * 12  # Scale to [-6, 6]
        result: np.ndarray = 1 / (1 + np.exp(-x))  # type: ignore[type-arg]
        return result

    def _generate_square(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Generate square wave (binary on/off)."""
        result: np.ndarray = (np.sign(np.sin(2 * np.pi * t)) + 1) / 2  # type: ignore[type-arg]
        return result

    def _generate_smoother_step(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Generate smoother-step function.

        6x^5 - 15x^4 + 10x^3 - smoother than smoothstep.
        """
        result: np.ndarray = t * t * t * (t * (t * 6 - 15) + 10)  # type: ignore[type-arg]
        return result

    def _generate_smooth_step(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Generate smooth-step function.

        3x^2 - 2x^3 - simpler than smoother-step.
        """
        result: np.ndarray = t * t * (3 - 2 * t)  # type: ignore[type-arg]
        return result

    # Easing Sine Curves
    def _generate_ease_in_sine(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Ease-in sine: starts slow, accelerates."""
        result: np.ndarray = 1 - np.cos((t * np.pi) / 2)  # type: ignore[type-arg]
        return result

    def _generate_ease_out_sine(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Ease-out sine: starts fast, decelerates."""
        result: np.ndarray = np.sin((t * np.pi) / 2)  # type: ignore[type-arg]
        return result

    def _generate_ease_in_out_sine(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Ease-in-out sine: slow-fast-slow."""
        result: np.ndarray = -(np.cos(np.pi * t) - 1) / 2  # type: ignore[type-arg]
        return result

    # Easing Quad Curves
    def _generate_ease_in_quad(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Ease-in quadratic: x^2."""
        result: np.ndarray = t * t  # type: ignore[type-arg]
        return result

    def _generate_ease_out_quad(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Ease-out quadratic: 1 - (1-x)^2."""
        result: np.ndarray = 1 - (1 - t) * (1 - t)  # type: ignore[type-arg]
        return result

    def _generate_ease_in_out_quad(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Ease-in-out quadratic."""
        result: np.ndarray = np.where(  # type: ignore[type-arg]
            t < 0.5, 2 * t * t, 1 - np.power(-2 * t + 2, 2) / 2
        )
        return result

    # Easing Cubic Curves
    def _generate_ease_in_cubic(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Ease-in cubic: x^3."""
        result: np.ndarray = t * t * t  # type: ignore[type-arg]
        return result

    def _generate_ease_out_cubic(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Ease-out cubic: 1 - (1-x)^3."""
        result: np.ndarray = 1 - np.power(1 - t, 3)  # type: ignore[type-arg]
        return result

    def _generate_ease_in_out_cubic(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Ease-in-out cubic."""
        result: np.ndarray = np.where(  # type: ignore[type-arg]
            t < 0.5, 4 * t * t * t, 1 - np.power(-2 * t + 2, 3) / 2
        )
        return result

    # Bounce Curves
    def _generate_bounce_out(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Bounce-out: bounces and settles at 1.0."""
        n1 = 7.5625
        d1 = 2.75

        def bounce_single(x: float) -> float:
            if x < 1 / d1:
                return n1 * x * x
            elif x < 2 / d1:
                x -= 1.5 / d1
                return n1 * x * x + 0.75
            elif x < 2.5 / d1:
                x -= 2.25 / d1
                return n1 * x * x + 0.9375
            else:
                x -= 2.625 / d1
                return n1 * x * x + 0.984375

        result: np.ndarray = np.array([bounce_single(x) for x in t])  # type: ignore[type-arg]
        return result

    def _generate_bounce_in(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Bounce-in: reverse of bounce-out."""
        result: np.ndarray = 1 - self._generate_bounce_out(1 - t)  # type: ignore[type-arg]
        return result

    # Elastic Curves
    def _generate_elastic_out(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Elastic-out: elastic oscillation at end."""
        c4 = (2 * np.pi) / 3
        result: np.ndarray = np.where(  # type: ignore[type-arg]
            (t == 0) | (t == 1),
            t,
            np.power(2, -10 * t) * np.sin((t * 10 - 0.75) * c4) + 1,
        )
        return result

    def _generate_elastic_in(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Elastic-in: reverse of elastic-out."""
        result: np.ndarray = 1 - self._generate_elastic_out(1 - t)  # type: ignore[type-arg]
        return result

    # Advanced Curves
    def _generate_perlin_noise(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Perlin noise: smooth procedural noise.

        Simplified Perlin-like noise using multiple sine waves.
        """
        # Multi-octave noise approximation
        result: np.ndarray = (  # type: ignore[type-arg]
            np.sin(t * 2 * np.pi) * 0.5
            + np.sin(t * 4 * np.pi) * 0.25
            + np.sin(t * 8 * np.pi) * 0.125
            + 0.5
        )
        # Normalize to [0, 1]
        r_min = result.min()
        r_max = result.max()
        if r_max - r_min > 0:
            result = (result - r_min) / (r_max - r_min)
        else:
            result = np.ones_like(result) * 0.5  # Constant value if no variation
        return result

    def _generate_lissajous(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Lissajous curve: complex oscillating pattern.

        Uses frequency ratio a=3, b=2 for interesting pattern.
        Returns y-component only (normalized to [0, 1]).
        """
        b = 2  # Frequency parameter for y-component
        delta = np.pi / 2
        # Y-component of Lissajous
        result: np.ndarray = (np.sin(b * 2 * np.pi * t + delta) + 1) / 2  # type: ignore[type-arg]
        return result

    def _generate_bezier(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Cubic Bezier curve with default control points.

        Control points: P0=(0,0), P1=(0.25,0.1), P2=(0.75,0.9), P3=(1,1)
        """
        # Cubic Bezier formula: B(t) = (1-t)^3*P0 + 3*(1-t)^2*t*P1 + 3*(1-t)*t^2*P2 + t^3*P3
        p0_y, p1_y, p2_y, p3_y = 0.0, 0.1, 0.9, 1.0
        result: np.ndarray = (  # type: ignore[type-arg]
            np.power(1 - t, 3) * p0_y
            + 3 * np.power(1 - t, 2) * t * p1_y
            + 3 * (1 - t) * np.power(t, 2) * p2_y
            + np.power(t, 3) * p3_y
        )
        return result

    # Motion Curves
    def _generate_anticipate(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Anticipate: pulls back before moving forward.

        Constrained to [0, 1] for valid DMX output.
        Strategy: Dips to 10% in first 30%, then accelerates to 100%.
        """
        pullback_phase = 0.3  # First 30% is the pullback
        pullback_min = 0.1  # Pull back to 10% (not negative)

        # Accelerate from pullback_min to 1.0
        result: np.ndarray = np.where(  # type: ignore[type-arg]
            t <= pullback_phase,
            # Pullback phase: ease from 0 to pullback_min
            pullback_min * np.sin((t / pullback_phase) * np.pi / 2),
            # Acceleration phase: quadratic ease from pullback_min to 1.0
            pullback_min
            + (1.0 - pullback_min) * ((t - pullback_phase) / (1 - pullback_phase)) ** 2,
        )
        return result

    def _generate_overshoot(self, t: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
        """Overshoot: overshoots target then settles.

        Constrained to [0, 1] for valid DMX output.
        Strategy: Rapid ease to ~98%, small bounce to 100%, settle at 100%.
        """
        # Use smoothstep as base (guaranteed [0, 1])
        base: np.ndarray = t * t * (3 - 2 * t)  # type: ignore[type-arg]

        # Add controlled overshoot effect in the range [0.6, 0.9]
        # This creates a subtle "bounce" that settles
        overshoot_window = np.logical_and(t >= 0.6, t <= 0.9)
        t_local = (t - 0.6) / 0.3  # Normalize to [0, 1] within window

        # Damped oscillation: starts strong, fades out
        # Scale by (1 - base) to ensure we never exceed 1.0
        bounce_factor = 0.05 * (1.0 - base) * np.sin(t_local * np.pi * 3) * np.exp(-t_local * 3)

        # Apply bounce only in window
        result: np.ndarray = base + np.where(overshoot_window, bounce_factor, 0.0)  # type: ignore[type-arg]

        # Mathematically guaranteed to stay in [0, 1]:
        # - base is in [0, 1]
        # - bounce_factor is scaled by (1 - base), so base + bounce <= 1
        return result


class CurveGenerator:
    """Orchestrator for curve generation.

    Routes curve generation requests to appropriate providers
    based on curve source type.
    """

    def __init__(
        self,
        library: CurveLibrary,
        native_provider: NativeCurveProvider,
        custom_provider: CustomCurveProvider,
    ) -> None:
        """Initialize curve generator with library and providers.

        Args:
            library: Curve library containing definitions
            native_provider: Provider for native xLights curves
            custom_provider: Provider for custom point array curves
        """
        self._library = library
        self._native = native_provider
        self._custom = custom_provider

    def generate_native_spec(
        self, curve_id: str, params: dict[str, Any] | None = None
    ) -> ValueCurveSpec:
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
        curve_def = self._library.get(curve_id)
        if curve_def is None:
            raise ValueError(f"Curve '{curve_id}' not found in library")

        # Handle preset resolution
        if curve_def.source == CurveSource.PRESET:
            return self._resolve_preset_native(curve_def, params)

        if curve_def.source != CurveSource.NATIVE:
            raise ValueError(f"Curve '{curve_id}' is not a native curve")

        return self._native.generate(curve_def, params)

    def generate_custom_points(
        self,
        curve_id: str,
        num_points: int = 100,
        min_dmx: float = 0.0,
        max_dmx: float = 255.0,
    ) -> list[CurvePoint]:
        """Generate custom curve as point array in DMX space.

        Supports preset resolution: if curve is a preset, resolves to base curve
        and applies modifiers.

        Args:
            curve_id: Unique curve identifier
            num_points: Number of points to generate
            min_dmx: Minimum DMX value (generate curve for this range)
            max_dmx: Maximum DMX value (generate curve for this range)

        Returns:
            List of curve points with time [0,1] and value in [min_dmx, max_dmx]

        Raises:
            ValueError: If curve not found or not a custom/preset curve
        """
        curve_def = self._library.get(curve_id)
        if curve_def is None:
            raise ValueError(f"Curve '{curve_id}' not found in library")

        # Handle preset resolution
        if curve_def.source == CurveSource.PRESET:
            return self._resolve_preset_custom(curve_def, num_points, min_dmx, max_dmx)

        if curve_def.source != CurveSource.CUSTOM:
            raise ValueError(f"Curve '{curve_id}' is not a custom curve")

        return self._custom.generate(curve_def, num_points, min_dmx, max_dmx)

    def _resolve_preset_native(
        self, preset_def: CurveDefinition, params: dict[str, Any] | None = None
    ) -> ValueCurveSpec:
        """Resolve preset to native curve specification.

        Args:
            preset_def: Preset curve definition
            params: Optional runtime parameter overrides

        Returns:
            ValueCurveSpec for the resolved native curve

        Raises:
            ValueError: If base curve not found or preset references another preset
        """
        if not preset_def.base_curve_id:
            raise ValueError("Preset must have 'base_curve_id'")

        # Get base curve
        base_curve = self._library.get(preset_def.base_curve_id)
        if base_curve is None:
            raise ValueError(f"Base curve '{preset_def.base_curve_id}' not found")

        # Prevent nested presets
        if base_curve.source == CurveSource.PRESET:
            raise ValueError("Preset cannot reference another preset")

        if base_curve.source != CurveSource.NATIVE:
            raise ValueError(f"Base curve '{preset_def.base_curve_id}' is not native")

        # Merge parameters: base defaults < preset params < runtime params
        merged_params = {
            **base_curve.default_params,
            **preset_def.preset_params,
            **(params or {}),
        }

        # Generate native spec with merged params
        return self._native.generate(base_curve, merged_params)

    def _resolve_preset_custom(
        self,
        preset_def: CurveDefinition,
        num_points: int = 100,
        min_dmx: float = 0.0,
        max_dmx: float = 255.0,
    ) -> list[CurvePoint]:
        """Resolve preset to custom curve points in DMX space.

        Args:
            preset_def: Preset curve definition
            num_points: Number of points to generate
            min_dmx: Minimum DMX value
            max_dmx: Maximum DMX value

        Returns:
            List of curve points (with modifiers applied) in DMX space

        Raises:
            ValueError: If base curve not found or preset references another preset
        """
        if not preset_def.base_curve_id:
            raise ValueError("Preset must have 'base_curve_id'")

        # Get base curve
        base_curve = self._library.get(preset_def.base_curve_id)
        if base_curve is None:
            raise ValueError(f"Base curve '{preset_def.base_curve_id}' not found")

        # Prevent nested presets
        if base_curve.source == CurveSource.PRESET:
            raise ValueError("Preset cannot reference another preset")

        if base_curve.source != CurveSource.CUSTOM:
            raise ValueError(f"Base curve '{preset_def.base_curve_id}' is not custom")

        # Generate base custom curve points IN DMX SPACE
        points = self._custom.generate(base_curve, num_points, min_dmx, max_dmx)

        # Apply modifiers
        points = self._apply_modifiers(points, preset_def.modifiers)

        return points

    def _apply_modifiers(self, points: list[CurvePoint], modifiers: list[str]) -> list[CurvePoint]:
        """Apply modifiers to curve points.

        Args:
            points: Original curve points
            modifiers: List of modifier names to apply

        Returns:
            Modified curve points
        """
        from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveModifier

        result = points

        for modifier_str in modifiers:
            try:
                modifier = CurveModifier(modifier_str)
            except ValueError:
                continue  # Skip unknown modifiers

            if modifier == CurveModifier.REVERSE:
                # Reverse the values (not the time)
                result = [CurvePoint(time=p.time, value=1.0 - p.value) for p in result]
            # Add more modifier implementations as needed

        return result
