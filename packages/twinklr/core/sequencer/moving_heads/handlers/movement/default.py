"""Default movement handler that delegates to library patterns.

This handler looks up movement patterns from the MovementLibrary and
generates curves based on the library configuration. It serves as a
catch-all for movements that don't need specialized logic.
"""

import logging
from typing import Any

from twinklr.core.curves.generator import CurveGenerator
from twinklr.core.curves.library import CurveLibrary
from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.semantics import CurveKind
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.handlers.protocols import MovementResult
from twinklr.core.sequencer.moving_heads.libraries.movement import DEFAULT_MOVEMENT_PARAMS
from twinklr.core.utils.logging import get_renderer_logger, log_performance

logger = logging.getLogger(__name__)
renderer_log = get_renderer_logger()


class DefaultMovementHandler:
    """Default movement handler using library patterns.

    This handler looks up movement patterns from MovementLibrary
    and generates curves based on the categorical parameters.

    The handler_id is set to "__default__" to indicate it's a fallback.
    When get() is called with any unregistered movement ID, this handler
    receives the request and looks up the pattern from the library.

    Attributes:
        handler_id: Unique identifier ("__default__").

    Raises:
        ValueError: If movement_id not in params or not in library.
    """

    handler_id: str = "__default__"

    def __init__(self) -> None:
        """Initialize default handler with curve generator."""
        self._curve_gen = CurveGenerator()

    @log_performance
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
                - movement_pattern: Movement pattern (required)
                - geometry: Geometry type (required)
                - calibration: Calibration dictionary (optional)
                - base_pan_norm: Base pan position [0, 1] from geometry
                - base_tilt_norm: Base tilt position [0, 1] from geometry
            n_samples: Number of samples to generate.
            cycles: Number of movement cycles.
            intensity: Intensity level (SLOW, SMOOTH, FAST, DRAMATIC).

        Returns:
            MovementResult with curves scaled to fit within DMX constraints.

        Raises:
            ValueError: If handler is not correctly configured.
        """
        pattern = params.get("movement_pattern")
        if not pattern:
            raise ValueError(
                "Handler is not correctly configured. 'movement_pattern' is missing from params."
            )
        base_params = {**pattern.base_params, **params.get("base_params", {})}

        # The caller-supplied `intensity` argument is authoritative. It used to be
        # overwritten by a lookup in `params` — the step's movement params dict,
        # which never carries that key — so every movement in every show rendered
        # at SMOOTH regardless of what the plan asked for (P4-F1).
        categorical_params_set = pattern.categorical_params or DEFAULT_MOVEMENT_PARAMS
        categorical_params = categorical_params_set.get(
            intensity,
            DEFAULT_MOVEMENT_PARAMS.get(intensity, DEFAULT_MOVEMENT_PARAMS[Intensity.SMOOTH]),
        )

        renderer_log.debug(f"Categorical Params: {categorical_params}")
        renderer_log.debug(f"Intensity: {intensity}")

        geometry = params.get("geometry")
        if not geometry:
            raise ValueError(
                "Handler is not correctly configured. 'geometry' is missing from params."
            )

        calibration = params.get("calibration", {})
        pan_min = calibration.get("pan_min_dmx", 0) if calibration else 0
        pan_max = calibration.get("pan_max_dmx", 255) if calibration else 255
        tilt_min = calibration.get("tilt_min_dmx", 0) if calibration else 0
        tilt_max = calibration.get("tilt_max_dmx", 255) if calibration else 255
        renderer_log.debug(f"Pan Min: {pan_min}, Pan Max: {pan_max}")
        renderer_log.debug(f"Tilt Min: {tilt_min}, Tilt Max: {tilt_max}")

        base_pan_norm = params.get("base_pan_norm", 0.5)
        base_tilt_norm = params.get("base_tilt_norm", 0.5)

        # The calibrated windows, in the same normalized [0,1] space the curves use.
        # Every emitted point is scaled and re-centred into these bounds by
        # `_generate_curve`: the calibration used to reach the curve only through the
        # `center_offset` term, which every pattern in the library leaves at 0.5, so
        # it was multiplied by zero and a fixture calibrated to a narrow safe window
        # was still driven across its full mechanical range (P4-F9).
        pan_min_norm = pan_min / 255.0
        pan_max_norm = pan_max / 255.0
        tilt_min_norm = tilt_min / 255.0
        tilt_max_norm = tilt_max / 255.0

        renderer_log.debug(
            f"Calibrated window (norm): pan=[{pan_min_norm:.3f}, {pan_max_norm:.3f}], "
            f"tilt=[{tilt_min_norm:.3f}, {tilt_max_norm:.3f}]"
        )

        # Resolve amplitude (allow param override)
        amplitude = self._resolve_amplitude(params, categorical_params.amplitude)
        renderer_log.debug(f"Resolved Amplitude: {amplitude}")

        # Generate pan curve scaled to fit within pan_min/pan_max
        renderer_log.debug(
            f"Generating Pan Curve - type: {pattern.pan_curve.value}, amplitude: {amplitude}, frequency: {categorical_params.frequency}, center: {categorical_params.center_offset}"
        )
        pan_curve = self._generate_curve(
            curve_type=pattern.pan_curve,
            n_samples=n_samples,
            cycles=cycles,
            amplitude=amplitude,
            frequency=categorical_params.frequency,
            center=categorical_params.center_offset,
            base_norm=base_pan_norm,
            window_min_norm=pan_min_norm,
            window_max_norm=pan_max_norm,
            params=self._filter_base_params("curve", "pan", base_params),
        )

        if not pan_curve:
            pan_static_dmx = self._resolve_static_dmx_value(base_pan_norm, pan_min, pan_max)
        else:
            pan_static_dmx = None

        # Generate tilt curve scaled to fit within tilt_min/tilt_max
        tilt_curve_def = pattern.resolve_tilt_curve(geometry)

        tilt_curve = self._generate_curve(
            curve_type=tilt_curve_def,
            n_samples=n_samples,
            cycles=cycles,
            amplitude=amplitude,
            frequency=categorical_params.frequency,
            center=categorical_params.center_offset,
            base_norm=base_tilt_norm,
            window_min_norm=tilt_min_norm,
            window_max_norm=tilt_max_norm,
            params=self._filter_base_params("curve", "tilt", base_params),
        )

        if not tilt_curve:
            tilt_static_dmx = self._resolve_static_dmx_value(base_tilt_norm, tilt_min, tilt_max)
        else:
            tilt_static_dmx = None

        return MovementResult(
            pan_curve_type=pattern.pan_curve,
            pan_curve=pan_curve,
            pan_static_dmx=pan_static_dmx,
            tilt_curve_type=tilt_curve_def,
            tilt_curve=tilt_curve,
            tilt_static_dmx=tilt_static_dmx,
        )

    def _filter_base_params(self, prefix: str, type: str, params: dict[str, Any]) -> dict[str, Any]:
        key_prefix = f"{prefix}_{type}_"
        return {
            k.removeprefix(key_prefix): v for k, v in params.items() if k.startswith(key_prefix)
        }

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
        floor = max(clamp_min, 0)
        ceiling = min(clamp_max, 255)
        value = int(normalized_value * 255)
        return max(floor, min(ceiling, value))

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
        *,
        curve_type: CurveLibrary,
        n_samples: int,
        cycles: float,
        amplitude: float,
        frequency: float,
        center: float,
        base_norm: float,
        window_min_norm: float,
        window_max_norm: float,
        params: dict[str, Any] | None = None,
    ) -> list[CurvePoint] | None:
        """Generate a movement curve scaled and re-centred into the calibrated window.

        Intensity parameters (amplitude, frequency) are passed to the curve generator
        to modulate the base curve shape. The center_offset parameter is applied here
        at the handler level by offsetting the base position.

        The calibrated window bounds the output: the base position is pulled inside it
        and the amplitude is scaled so the excursion fits. Scale-and-recentre, rather
        than a hard clamp, because a clamp flattens the extremes of the curve into
        plateaus and reads on a real fixture as a stuck head.

        Args:
            curve_type: CurveLibrary enum value.
            n_samples: Number of samples.
            cycles: Number of cycles (base value, multiplied by frequency in curve).
            amplitude: Requested amplitude [0, 1] from categorical params (scaled later).
            frequency: Frequency multiplier from categorical params (passed to curve).
            center: Center offset [0, 1] from categorical params (applied to base_norm).
            base_norm: Base position from geometry [0, 1].
            window_min_norm: Calibrated lower bound for this axis, normalized [0, 1].
            window_max_norm: Calibrated upper bound for this axis, normalized [0, 1].
            params: Optional parameters to override defaults/presets.

        Returns:
            List of curve points, every one inside the calibrated window.
        """
        if curve_type == CurveLibrary.HOLD:
            return None

        window_min = max(0.0, min(window_min_norm, window_max_norm))
        window_max = min(1.0, max(window_min_norm, window_max_norm))

        # Scale: the excursion is the intensity's, reduced only if the window itself
        # is narrower than the movement asks for.
        desired_amplitude = amplitude * 0.5  # e.g. SMOOTH (0.4) -> 0.2 of full range
        effective_amplitude = min(desired_amplitude, (window_max - window_min) / 2)

        # Re-centre: shift the base far enough inside the window for that excursion to
        # fit. Clamping the base to the window edge instead would leave a fixture
        # posed at the edge with zero room to move -- a curve flattened to a plateau,
        # which on a real head reads as a stuck fixture rather than as choreography.
        inner_min = window_min + effective_amplitude
        inner_max = window_max - effective_amplitude
        centred_base_norm = max(inner_min, min(inner_max, base_norm))
        if abs(centred_base_norm - base_norm) > 1e-9:
            renderer_log.debug(
                f"Base {base_norm:.3f} leaves no room inside the calibrated window "
                f"[{window_min:.3f}, {window_max:.3f}] for an amplitude of "
                f"{effective_amplitude:.3f}; re-centred to {centred_base_norm:.3f}"
            )

        # Apply center offset to base position (center is [0, 1] where 0.5 = no shift),
        # scaled by the room left inside the window.
        max_amplitude_norm = min(centred_base_norm - inner_min, inner_max - centred_base_norm)
        center_offset_normalized = (center - 0.5) * max_amplitude_norm * 1.0
        adjusted_base_norm = max(
            inner_min, min(inner_max, centred_base_norm + center_offset_normalized)
        )

        # Build curve generation parameters with intensity params
        curve_params = {
            "cycles": cycles,
            "frequency": frequency,  # Pass frequency to curve function
            # NOTE: amplitude is NOT passed here - it's applied to the generated curve
            # below, after it has been scaled into the calibrated window
            **(params or {}),
        }

        # Generate base curve - already in normalized [0, 1] space
        base_curve = self._curve_gen.generate_custom_points(
            curve_id=curve_type.value,
            num_points=n_samples,
            **curve_params,
        )

        # Get curve definition to check kind
        curve_def = self._curve_gen._registry.get(curve_type.value)

        # Log if the window, not the intensity, decided the amplitude
        if effective_amplitude < desired_amplitude:
            renderer_log.debug(
                f"Amplitude limited by the calibrated window: desired="
                f"{desired_amplitude:.3f}, effective={effective_amplitude:.3f}, "
                f"window=[{window_min:.3f}, {window_max:.3f}]"
            )

        # Build scaled points based on curve kind
        scaled_points: list[CurvePoint] = []

        if curve_def.kind == CurveKind.MOVEMENT_OFFSET:
            # Movement offset curves are already centered at 0.5
            # Re-center at adjusted_base_norm and scale amplitude
            for point in base_curve:
                # Convert from [0, 1] centered at 0.5 to offset [-0.5, 0.5]
                offset = point.v - 0.5
                # Scale by effective amplitude
                scaled_offset = offset * (effective_amplitude / 0.5)
                # Apply to adjusted base position (already has center offset applied)
                new_v = adjusted_base_norm + scaled_offset

                # Safety net only: the amplitude scaling above already keeps every
                # point inside the window, so a clamp here means the maths drifted.
                if not (window_min <= new_v <= window_max):
                    logger.debug(
                        f"Curve point outside the calibrated window: {new_v:.3f} "
                        f"(adjusted_base={adjusted_base_norm:.3f}, scaled_offset={scaled_offset:.3f})"
                    )
                new_v = max(window_min, min(window_max, new_v))

                scaled_points.append(CurvePoint(t=point.t, v=new_v))

        elif curve_def.kind == CurveKind.DIMMER_ABSOLUTE:
            # Absolute curves go from 0 to 1
            # Center them at adjusted_base_norm and apply amplitude
            for point in base_curve:
                # Convert absolute [0, 1] to offset [-0.5, 0.5]
                normalized_offset = point.v - 0.5
                # Scale by effective amplitude
                scaled_offset = normalized_offset * (effective_amplitude / 0.5)
                # Apply to adjusted base position (already has center offset applied)
                new_v = adjusted_base_norm + scaled_offset

                # Safety net only: the amplitude scaling above already keeps every
                # point inside the window, so a clamp here means the maths drifted.
                if not (window_min <= new_v <= window_max):
                    logger.debug(
                        f"Curve point outside the calibrated window: {new_v:.3f} "
                        f"(adjusted_base={adjusted_base_norm:.3f}, scaled_offset={scaled_offset:.3f})"
                    )
                new_v = max(window_min, min(window_max, new_v))

                scaled_points.append(CurvePoint(t=point.t, v=new_v))

        else:
            # Unknown curve kind - treat as offset for safety
            for point in base_curve:
                offset = point.v - 0.5
                scaled_offset = offset * (effective_amplitude / 0.5)
                new_v = adjusted_base_norm + scaled_offset

                # Safety net only: the amplitude scaling above already keeps every
                # point inside the window, so a clamp here means the maths drifted.
                if not (window_min <= new_v <= window_max):
                    logger.debug(
                        f"Curve point outside the calibrated window: {new_v:.3f} "
                        f"(adjusted_base={adjusted_base_norm:.3f}, scaled_offset={scaled_offset:.3f})"
                    )
                new_v = max(window_min, min(window_max, new_v))
                scaled_points.append(CurvePoint(t=point.t, v=new_v))

        return scaled_points
