"""Default dimmer handler that delegates to library patterns.

This handler looks up dimmer patterns from the DimmerLibrary and
generates curves based on the library configuration. It serves as a
catch-all for dimmers that don't need specialized logic.
"""

import logging
from typing import Any

from blinkb0t.core.curves.generator import CurveGenerator
from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.semantics import CurveKind
from blinkb0t.core.sequencer.models.enum import Intensity
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import DimmerResult

logger = logging.getLogger(__name__)
renderer_log = logging.getLogger("DMX_MH_RENDER")


class DefaultDimmerHandler:
    """Default dimmer handler using library patterns.

    This handler looks up dimmer patterns from DimmerLibrary
    and generates curves based on the categorical parameters.

    The handler_id is set to "__default__" to indicate it's a fallback.
    When get() is called with any unregistered dimmer ID, this handler
    receives the request and looks up the pattern from the library.

    Attributes:
        handler_id: Unique identifier ("__default__").

    Raises:
        ValueError: If handler is not correctly configured.
    """

    handler_id: str = "__default__"

    def __init__(self) -> None:
        """Initialize default handler with curve generator."""
        self._curve_gen = CurveGenerator()

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: Intensity,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult:
        """Generate dimmer curves from library pattern.

        Args:
            params: Handler parameters:
                - dimmer_id: Dimmer pattern ID (required)
            n_samples: Number of samples to generate.
            cycles: Number of dimmer cycles (unused for most dimmers).
            intensity: Intensity level (used to select categorical params).
            min_norm: Starting brightness [0, 1].
            max_norm: Ending brightness [0, 1].

        Returns:
            DimmerResult with dimmer curve.

        Raises:
            ValueError: If handler is not correctly configured.
        """
        pattern = params.get("dimmer_pattern")
        if not pattern:
            raise ValueError(
                "Handler is not correctly configured. 'dimmer_pattern' is missing from params."
            )

        calibration = params.get("calibration", {})
        dimmer_min = calibration.get("dimmer_floor_dmx", 0) if calibration else 0
        dimmer_max = calibration.get("dimmer_ceiling_dmx", 255) if calibration else 255
        dimmer_amplitude_dmx = int((dimmer_max - dimmer_min) / 2)

        renderer_log.info(f"Dimmer Min: {dimmer_min}, Dimmer Max: {dimmer_max}")
        renderer_log.info(f"Dimmer Amplitude DMX: {dimmer_amplitude_dmx}")

        # Get categorical params for intensity
        if intensity not in pattern.categorical_params:
            # Fall back to SMOOTH if intensity not defined
            intensity = Intensity.SMOOTH

        cat_params = pattern.categorical_params[intensity]

        # Generate dimmer curve
        if pattern.curve == CurveLibrary.HOLD:
            dimmer_floor_dmx = calibration.get("dimmer_floor_dmx", 0) if calibration else 0
            dimmer_ceiling_dmx = calibration.get("dimmer_ceiling_dmx", 255) if calibration else 255
            dimmer_static_dmx = self._resolve_static_dmx_value(
                cat_params.max_intensity, dimmer_floor_dmx, dimmer_ceiling_dmx
            )

            return DimmerResult(dimmer_static_dmx=dimmer_static_dmx)
        else:
            dimmer_curve = self._generate_curve(
                curve_type=pattern.curve,
                n_samples=n_samples,
                min_intensity=cat_params.min_intensity,
                max_intensity=cat_params.max_intensity,
                min_norm=min_norm,
                max_norm=max_norm,
            )
            return DimmerResult(dimmer_curve=dimmer_curve)

    def _resolve_static_dmx_value(
        self, normalized_value: float, clamp_min: int = 0, clamp_max: int = 255
    ) -> int:
        """Resolve static DMX value from normalized value.

        Args:
            normalized_value: Normalized value [0, 1].
            clamp_min: Minimum DMX value [0, 255].
            clamp_max: Maximum DMX value [0, 255].

        Returns:
            Static DMX value [0, 255].
        """
        renderer_log.info(
            f"Resolving static DMX value: {normalized_value}, {clamp_min}, {clamp_max}"
        )
        floor = max(clamp_min, 0)
        ceiling = min(clamp_max, 255)
        value = int(normalized_value * 255)
        return max(floor, min(ceiling, value))

    def _generate_curve(
        self,
        curve_type: Any,
        n_samples: int,
        min_intensity: int,
        max_intensity: int,
        min_norm: float,
        max_norm: float,
    ) -> list[CurvePoint]:
        """Generate a dimmer curve with specified parameters.

        Args:
            curve_type: CurveLibrary enum value.
            n_samples: Number of samples.
            min_intensity: Min DMX intensity from categorical params [0, 255].
            max_intensity: Max DMX intensity from categorical params [0, 255].
            min_norm: Min normalized brightness [0, 1].
            max_norm: Max normalized brightness [0, 1].

        Returns:
            List of curve points in normalized space [0, 1].
        """
        # Generate base curve - already in normalized [0, 1] space
        base_curve = self._curve_gen.generate_custom_points(
            curve_id=curve_type.value,
            num_points=n_samples,
        )

        # Get curve definition to check kind
        curve_def = self._curve_gen._registry.get(curve_type.value)

        # Build scaled points based on curve kind
        scaled_points: list[CurvePoint] = []

        if curve_def.kind == CurveKind.DIMMER_ABSOLUTE:
            # Absolute curves go from 0 to 1
            # Scale to categorical intensity range, then to output range
            for point in base_curve:
                # 1. Scale from [0, 1] to categorical intensity range (normalized)
                min_intensity_norm = min_intensity / 255.0
                max_intensity_norm = max_intensity / 255.0
                intensity_value = min_intensity_norm + point.v * (
                    max_intensity_norm - min_intensity_norm
                )

                # 2. Scale to output range [min_norm, max_norm]
                final_value = min_norm + (intensity_value * (max_norm - min_norm))

                # Clamp to [0, 1]
                final_value = max(0.0, min(1.0, final_value))

                scaled_points.append(CurvePoint(t=point.t, v=final_value))

        elif curve_def.kind == CurveKind.MOVEMENT_OFFSET:
            # Offset curves are centered at 0.5
            # Convert to absolute [0, 1] range first
            for point in base_curve:
                # Convert offset [-0.5, 0.5] to absolute [0, 1]
                # Offset curves have 0.5 as center, so subtract 0.5 to get offset
                offset = point.v - 0.5  # [-0.5, 0.5]
                absolute = 0.5 + offset  # Back to [0, 1] but treating as absolute

                # Scale to categorical intensity range (normalized)
                min_intensity_norm = min_intensity / 255.0
                max_intensity_norm = max_intensity / 255.0
                intensity_value = min_intensity_norm + absolute * (
                    max_intensity_norm - min_intensity_norm
                )

                # Scale to output range [min_norm, max_norm]
                final_value = min_norm + (intensity_value * (max_norm - min_norm))

                # Clamp to [0, 1]
                final_value = max(0.0, min(1.0, final_value))

                scaled_points.append(CurvePoint(t=point.t, v=final_value))

        else:
            # Unknown curve kind - treat as absolute for safety
            for point in base_curve:
                min_intensity_norm = min_intensity / 255.0
                max_intensity_norm = max_intensity / 255.0
                intensity_value = min_intensity_norm + point.v * (
                    max_intensity_norm - min_intensity_norm
                )
                final_value = min_norm + (intensity_value * (max_norm - min_norm))
                final_value = max(0.0, min(1.0, final_value))
                scaled_points.append(CurvePoint(t=point.t, v=final_value))

        return scaled_points
