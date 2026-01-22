"""Default dimmer handler that delegates to library patterns.

This handler looks up dimmer patterns from the DimmerLibrary and
generates curves based on the library configuration. It serves as a
catch-all for dimmers that don't need specialized logic.
"""

from typing import Any

from blinkb0t.core.curves.generator import CurveGenerator
from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.semantics import CurveKind
from blinkb0t.core.sequencer.models.enum import Intensity
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import DimmerResult
from blinkb0t.core.sequencer.moving_heads.libraries.dimmer import (
    DimmerLibrary,
    DimmerType,
)


class DefaultDimmerHandler:
    """Default dimmer handler using library patterns.

    This handler looks up dimmer patterns from DimmerLibrary
    and generates curves based on the categorical parameters.

    The handler_id is set to "__default__" to indicate it's a fallback.
    When get() is called with any unregistered dimmer ID, this handler
    receives the request and looks up the pattern from the library.

    Attributes:
        handler_id: Unique identifier ("__default__").

    Example:
        >>> handler = DefaultDimmerHandler()
        >>> # This will look up "fade_in" from DimmerLibrary
        >>> result = handler.generate(
        ...     params={"dimmer_id": "fade_in"},
        ...     n_samples=64,
        ...     cycles=1.0,
        ...     intensity=Intensity.SMOOTH,
        ...     min_norm=0.0,
        ...     max_norm=1.0,
        ... )

    Raises:
        ValueError: If dimmer_id not in params or not in library.
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
            ValueError: If dimmer_id not in params.
            ValueError: If dimmer_id not found in library.
        """
        # Extract dimmer_id from params
        if "dimmer_id" not in params:
            raise ValueError(
                "DefaultDimmerHandler requires 'dimmer_id' in params. "
                "This should be set automatically by the handler registry."
            )

        dimmer_id_str = params["dimmer_id"]

        # Look up pattern in library
        try:
            # Convert string to enum
            dimmer_type = DimmerType(dimmer_id_str)
        except ValueError as e:
            raise ValueError(
                f"Dimmer '{dimmer_id_str}' not found in DimmerLibrary. "
                f"Valid: {[d.value for d in DimmerType]}"
            ) from e

        pattern = DimmerLibrary.PATTERNS[dimmer_type]

        # Get categorical params for intensity
        if intensity not in pattern.categorical_params:
            # Fall back to SMOOTH if intensity not defined
            intensity = Intensity.SMOOTH

        cat_params = pattern.categorical_params[intensity]

        # Generate dimmer curve
        dimmer_curve = self._generate_curve(
            curve_type=pattern.curve,
            n_samples=n_samples,
            min_intensity=cat_params.min_intensity,
            max_intensity=cat_params.max_intensity,
            min_norm=min_norm,
            max_norm=max_norm,
        )

        return DimmerResult(dimmer_curve=dimmer_curve)

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
