"""Default movement handler that delegates to library patterns.

This handler looks up movement patterns from the MovementLibrary and
generates curves based on the library configuration. It serves as a
catch-all for movements that don't need specialized logic.
"""

from typing import Any

from blinkb0t.core.curves.generator import CurveGenerator
from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.curves.semantics import CurveKind
from blinkb0t.core.sequencer.models.enum import Intensity
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import MovementResult
from blinkb0t.core.sequencer.moving_heads.libraries.movement import (
    MovementLibrary,
    MovementType,
)


class DefaultMovementHandler:
    """Default movement handler using library patterns.

    This handler looks up movement patterns from MovementLibrary
    and generates curves based on the categorical parameters.

    The handler_id is set to "__default__" to indicate it's a fallback.
    When get() is called with any unregistered movement ID, this handler
    receives the request and looks up the pattern from the library.

    Attributes:
        handler_id: Unique identifier ("__default__").

    Example:
        >>> handler = DefaultMovementHandler()
        >>> # This will look up "sweep_lr" from MovementLibrary
        >>> result = handler.generate(
        ...     params={"movement_id": "sweep_lr"},
        ...     n_samples=64,
        ...     cycles=2.0,
        ...     intensity=Intensity.SMOOTH,
        ... )

    Raises:
        ValueError: If movement_id not in params or not in library.
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
    ) -> MovementResult:
        """Generate movement curves from library pattern.

        Args:
            params: Handler parameters:
                - movement_id: Movement pattern ID (required)
                - amplitude_degrees: Override amplitude (0-180)
            n_samples: Number of samples to generate.
            cycles: Number of movement cycles.
            intensity: Intensity level (SLOW, SMOOTH, FAST, DRAMATIC).

        Returns:
            MovementResult with offset-centered pan/tilt curves.

        Raises:
            ValueError: If movement_id not in params.
            ValueError: If movement_id not found in library.
        """
        # Extract movement_id from params
        if "movement_id" not in params:
            raise ValueError(
                "DefaultMovementHandler requires 'movement_id' in params. "
                "This should be set automatically by the handler registry."
            )

        movement_id_str = params["movement_id"]

        # Look up pattern in library
        try:
            # Convert string to enum
            movement_type = MovementType(movement_id_str)
        except ValueError as e:
            raise ValueError(
                f"Movement '{movement_id_str}' not found in MovementLibrary. "
                f"Valid: {[m.value for m in MovementType]}"
            ) from e

        pattern = MovementLibrary.PATTERNS[movement_type]

        # Get categorical params for intensity
        if intensity not in pattern.categorical_params:
            # Fall back to SMOOTH if intensity not defined
            intensity = Intensity.SMOOTH

        cat_params = pattern.categorical_params[intensity]

        # Resolve amplitude (allow param override)
        amplitude = self._resolve_amplitude(params, cat_params.amplitude)

        # Generate pan curve
        pan_curve = self._generate_curve(
            curve_type=pattern.pan_curve,
            n_samples=n_samples,
            cycles=cycles,
            amplitude=amplitude,
            frequency=cat_params.frequency,
            center=cat_params.center,
        )

        # Generate tilt curve
        tilt_curve = self._generate_curve(
            curve_type=pattern.tilt_curve,
            n_samples=n_samples,
            cycles=cycles,
            amplitude=amplitude,
            frequency=cat_params.frequency,
            center=cat_params.center,
        )

        return MovementResult(
            pan_curve_type=pattern.pan_curve,
            pan_curve=pan_curve,
            tilt_curve_type=pattern.tilt_curve,
            tilt_curve=tilt_curve,
        )

    def _resolve_amplitude(self, params: dict[str, Any], default_amplitude: float) -> float:
        """Resolve amplitude from params or categorical default.

        Args:
            params: Handler parameters (may contain amplitude_degrees).
            default_amplitude: Default amplitude from categorical params [0, 1].

        Returns:
            Normalized amplitude [0, 1].
        """
        # Check for explicit amplitude param
        if "amplitude_degrees" in params:
            degrees = float(params["amplitude_degrees"])
            # Convert degrees to normalized amplitude (180 degrees = 1.0 full range)
            return min(1.0, max(0.0, degrees / 180.0))

        # Use default from categorical params
        return default_amplitude

    def _generate_curve(
        self,
        curve_type: Any,
        n_samples: int,
        cycles: float,
        amplitude: float,
        frequency: float,
        center: int,
    ) -> list[CurvePoint]:
        """Generate a movement curve with specified parameters.

        Args:
            curve_type: CurveLibrary enum value.
            n_samples: Number of samples.
            cycles: Number of cycles (may be scaled by frequency).
            amplitude: Normalized amplitude [0, 1].
            frequency: Frequency multiplier.
            center: DMX center value [0, 255] (unused - curves are normalized).

        Returns:
            List of curve points, offset-centered at 0.5.
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

        if curve_def.kind == CurveKind.MOVEMENT_OFFSET:
            # Movement offset curves are already centered at 0.5
            # Scale amplitude around center
            for point in base_curve:
                # Convert from [0, 1] centered at 0.5 to scaled version
                offset = point.v - 0.5  # Now in [-0.5, 0.5]
                scaled_offset = offset * (amplitude / 0.5)  # Scale amplitude
                new_v = 0.5 + scaled_offset

                # Clamp to [0, 1]
                new_v = max(0.0, min(1.0, new_v))

                scaled_points.append(CurvePoint(t=point.t, v=new_v))

        elif curve_def.kind == CurveKind.DIMMER_ABSOLUTE:
            # Absolute curves go from 0 to 1
            # Center them at 0.5 and apply amplitude
            for point in base_curve:
                # Convert absolute [0, 1] to offset-centered [-amplitude, +amplitude]
                # First normalize to [-0.5, 0.5], then scale by amplitude
                normalized_offset = point.v - 0.5  # [-0.5, 0.5]
                scaled_offset = normalized_offset * (amplitude / 0.5)  # Scale amplitude
                new_v = 0.5 + scaled_offset

                # Clamp to [0, 1]
                new_v = max(0.0, min(1.0, new_v))

                scaled_points.append(CurvePoint(t=point.t, v=new_v))

        else:
            # Unknown curve kind - treat as offset for safety
            for point in base_curve:
                offset = point.v - 0.5
                scaled_offset = offset * (amplitude / 0.5)
                new_v = 0.5 + scaled_offset
                new_v = max(0.0, min(1.0, new_v))
                scaled_points.append(CurvePoint(t=point.t, v=new_v))

        return scaled_points
