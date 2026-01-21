"""DMX Curve Mapper - Integration layer for curve-to-channel mapping.

Orchestrates curve generation, normalization, tuning, and boundary enforcement
with flexible auto-fit control.
"""

from __future__ import annotations

from typing import Any

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource
from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import CurveGenerator
from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import CustomCurveSpec
from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec


def calculate_optimal_point_count(
    duration_ms: int | None = None,
    min_points: int = 100,
    max_points: int = 300,
    points_per_second: float = 10.0,
) -> int:
    """Calculate optimal number of points for custom curve based on duration.

    Args:
        duration_ms: Duration of the section in milliseconds (None = use default)
        min_points: Minimum number of points (for very short sections)
        max_points: Maximum number of points (to avoid bloat)
        points_per_second: Target density (default: 10 points per second for smooth curves)

    Returns:
        Optimal point count between min_points and max_points

    Examples:
        >>> calculate_optimal_point_count(1000)  # 1 second
        20
        >>> calculate_optimal_point_count(5000)  # 5 seconds
        50
        >>> calculate_optimal_point_count(20000)  # 20 seconds
        200
        >>> calculate_optimal_point_count(None)  # No duration provided
        50
    """
    if duration_ms is None:
        # Default to moderate fidelity (50 points)
        return 50

    # Calculate based on duration
    duration_sec = duration_ms / 1000.0
    target_points = int(duration_sec * points_per_second)

    # Clamp to min/max bounds
    return max(min_points, min(target_points, max_points))


class DMXCurveMapper:
    """Maps curves to DMX channels with optional auto-fit enforcement.

    Provides high-level API that ties together:
    - CurveGenerator: Creates curves from library
    - CurveNormalizer: Normalizes and maps to DMX ranges
    - NativeCurveTuner: Tunes native curve parameters
    - Auto-fit logic: Selective boundary enforcement

    Auto-fit Priority (highest to lowest):
    1. Explicit `auto_fit` parameter
    2. Geometry config `enforce_boundaries` setting
    3. Channel-specific defaults (pan/tilt: True, dimmer: False)
    4. Global default: True (safe choice)
    """

    # Channel-specific defaults for auto-fit
    _CHANNEL_DEFAULTS = {
        "pan": True,  # Physical limits
        "tilt": True,  # Physical limits
        "dimmer": False,  # Can use full range
    }

    def __init__(
        self,
        generator: CurveGenerator,
        normalizer: CurveNormalizer,
        tuner: NativeCurveTuner,
    ) -> None:
        """Initialize DMXCurveMapper with dependencies.

        Args:
            generator: CurveGenerator for creating curves
            normalizer: CurveNormalizer for mapping to DMX ranges
            tuner: NativeCurveTuner for parameter optimization
        """
        self._generator = generator
        self._normalizer = normalizer
        self._tuner = tuner

    def map_to_channel(
        self,
        curve_id: str,
        channel_name: str,
        min_limit: float,
        max_limit: float,
        geometry_config: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auto_fit: bool | None = None,
        duration_ms: int | None = None,
    ) -> ValueCurveSpec | CustomCurveSpec:
        """Map curve to DMX channel with optional auto-fit.

        Args:
            curve_id: Curve identifier from library
            channel_name: Channel name (e.g., "pan", "tilt", "dimmer")
            min_limit: Minimum DMX value for channel
            max_limit: Maximum DMX value for channel
            geometry_config: Optional geometry configuration
            params: Optional parameter overrides
            auto_fit: Optional explicit auto-fit override
            duration_ms: Optional duration in milliseconds (for custom curve fidelity)

        Returns:
            ValueCurveSpec for native curves, CustomCurveSpec for custom curves

        Raises:
            ValueError: If curve not found in library

        Example:
            # Fan pattern: enforce auto-fit
            mapper.map_to_channel(
                curve_id="sine",
                channel_name="pan",
                min_limit=0,
                max_limit=255,
                geometry_config={"type": "fan", "enforce_boundaries": True},
                duration_ms=5000
            )

            # Sky circles: don't enforce auto-fit
            mapper.map_to_channel(
                curve_id="sine",
                channel_name="pan",
                min_limit=0,
                max_limit=255,
                geometry_config={"type": "sky_circles", "enforce_boundaries": False},
                duration_ms=8000
            )
        """
        # Get curve definition
        curve_def = self._generator._library.get(curve_id)
        if curve_def is None:
            raise ValueError(f"Curve '{curve_id}' not found in library")

        # Determine if auto-fit should be applied
        should_auto_fit = self._should_apply_auto_fit(
            channel_name=channel_name,
            geometry_config=geometry_config,
            explicit_override=auto_fit,
        )

        # Route based on curve source
        if curve_def.source == CurveSource.NATIVE:
            return self._map_native_curve(
                curve_id=curve_id,
                params=params,
                min_limit=min_limit,
                max_limit=max_limit,
                should_auto_fit=should_auto_fit,
            )
        elif curve_def.source == CurveSource.CUSTOM:
            return self._map_custom_curve(
                curve_id=curve_id,
                params=params,
                min_limit=min_limit,
                max_limit=max_limit,
                should_auto_fit=should_auto_fit,
                duration_ms=duration_ms,
            )
        elif curve_def.source == CurveSource.PRESET:
            # For presets, determine if base curve is native or custom
            return self._map_preset_curve(
                curve_id=curve_id,
                params=params,
                min_limit=min_limit,
                max_limit=max_limit,
                should_auto_fit=should_auto_fit,
                duration_ms=duration_ms,
            )
        else:
            raise ValueError(f"Unknown curve source: {curve_def.source}")

    def _map_native_curve(
        self,
        curve_id: str,
        params: dict[str, Any] | None,
        min_limit: float,
        max_limit: float,
        should_auto_fit: bool,
    ) -> ValueCurveSpec:
        """Map native curve with optional parameter tuning.

        Args:
            curve_id: Curve identifier
            params: Optional parameter overrides
            min_limit: Minimum DMX value
            max_limit: Maximum DMX value
            should_auto_fit: Whether to tune parameters

        Returns:
            ValueCurveSpec (tuned or original)
        """
        # Generate base spec
        spec = self._generator.generate_native_spec(curve_id, params)

        if should_auto_fit:
            # Apply parameter tuning for efficiency
            spec = self._tuner.tune_to_fit(spec, min_limit, max_limit)

        return spec

    def _map_custom_curve(
        self,
        curve_id: str,
        params: dict[str, Any] | None,
        min_limit: float,
        max_limit: float,
        should_auto_fit: bool,
        duration_ms: int | None = None,
    ) -> CustomCurveSpec:
        """Map custom curve with correct DMX generation.

        NEW APPROACH (correct):
        1. Generate curve directly in target DMX space [min_limit, max_limit]
        2. Normalize to [0-1] for xLights output format (value / 255.0)
        3. No rescaling, no clamping, no auto-fit complexity!

        Args:
            curve_id: Curve identifier
            params: Optional parameter overrides (unused for now)
            min_limit: Minimum DMX value (curve generated for this range)
            max_limit: Maximum DMX value (curve generated for this range)
            should_auto_fit: Ignored - curves now generated correctly from start
            duration_ms: Optional duration in milliseconds (for point fidelity)

        Returns:
            CustomCurveSpec with DMX points and limits
        """
        # Calculate optimal point count based on duration
        num_points = calculate_optimal_point_count(duration_ms)

        # Generate curve DIRECTLY in target DMX range
        # Example: for pan [75, 200], sine generates [75, 137.5, 200, 137.5, 75]
        points = self._generator.generate_custom_points(
            curve_id=curve_id,
            num_points=num_points,
            min_dmx=min_limit,
            max_dmx=max_limit,
        )

        # Return CustomCurveSpec with DMX points
        # XLightsAdapter will normalize these to [0-1] for output
        return CustomCurveSpec(
            points=points,
            min_val=int(min_limit),
            max_val=int(max_limit),
            reverse=False,
        )

    def _should_apply_auto_fit(
        self,
        channel_name: str,
        geometry_config: dict[str, Any] | None,
        explicit_override: bool | None,
    ) -> bool:
        """Determine if auto-fit should be applied (priority order).

        Priority:
        1. Explicit override (highest)
        2. Geometry config
        3. Channel defaults
        4. Global default (lowest)

        Args:
            channel_name: Channel name (e.g., "pan", "tilt")
            geometry_config: Optional geometry configuration
            explicit_override: Optional explicit override

        Returns:
            True if auto-fit should be applied, False otherwise
        """
        # 1. Explicit override has highest priority
        if explicit_override is not None:
            return explicit_override

        # 2. Geometry config
        if geometry_config and "enforce_boundaries" in geometry_config:
            boundaries = geometry_config["enforce_boundaries"]

            if isinstance(boundaries, dict):
                # Per-channel configuration
                return bool(boundaries.get(channel_name, True))
            else:
                # Global for this geometry
                return bool(boundaries)

        # 3. Channel-specific defaults
        if channel_name in self._CHANNEL_DEFAULTS:
            return self._CHANNEL_DEFAULTS[channel_name]

        # 4. Safe default: enforce auto-fit
        return True

    def _map_preset_curve(
        self,
        curve_id: str,
        params: dict[str, Any] | None,
        min_limit: float,
        max_limit: float,
        should_auto_fit: bool,
        duration_ms: int | None = None,
    ) -> ValueCurveSpec | CustomCurveSpec:
        """Map preset curve by resolving base curve.

        Args:
            curve_id: Preset curve identifier
            params: Optional runtime parameter overrides
            min_limit: Minimum DMX value
            max_limit: Maximum DMX value
            should_auto_fit: Whether to apply auto-fit
            duration_ms: Optional duration in milliseconds (for custom curve fidelity)

        Returns:
            ValueCurveSpec for native base curves, CustomCurveSpec for custom base curves

        Raises:
            ValueError: If preset base curve not found
        """
        preset_def = self._generator._library.get(curve_id)
        if not preset_def or not preset_def.base_curve_id:
            raise ValueError(f"Invalid preset: {curve_id}")

        # Get base curve to determine type
        base_curve = self._generator._library.get(preset_def.base_curve_id)
        if base_curve is None:
            raise ValueError(f"Preset base curve not found: {preset_def.base_curve_id}")

        # Route based on base curve source
        if base_curve.source == CurveSource.NATIVE:
            # Preset with native base - generate native spec (will resolve preset)
            return self._map_native_curve(
                curve_id=curve_id,  # Pass preset ID, generator will resolve
                params=params,
                min_limit=min_limit,
                max_limit=max_limit,
                should_auto_fit=should_auto_fit,
            )
        elif base_curve.source == CurveSource.CUSTOM:
            # Preset with custom base - generate custom points (will resolve preset)
            return self._map_custom_curve(
                curve_id=curve_id,  # Pass preset ID, generator will resolve
                params=params,
                min_limit=min_limit,
                max_limit=max_limit,
                should_auto_fit=should_auto_fit,
                duration_ms=duration_ms,
            )
        else:
            raise ValueError(f"Preset base curve has invalid source: {base_curve.source}")
