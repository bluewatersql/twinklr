"""Default dimmer handler that delegates to library patterns.

This handler looks up dimmer patterns from the DimmerLibrary and
generates curves based on the library configuration. It serves as a
catch-all for dimmers that don't need specialized logic.
"""

import logging
from typing import Any

from twinklr.core.curves.generator import CurveGenerator
from twinklr.core.curves.library import CurveLibrary
from twinklr.core.curves.models import CurvePoint
from twinklr.core.curves.semantics import CurveKind
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.handlers.protocols import DimmerResult
from twinklr.core.sequencer.moving_heads.libraries.dimmer import (
    DEFAULT_DIMMER_PARAMS,
    DimmerCategoricalParams,
)
from twinklr.core.utils.logging import get_renderer_logger, log_performance

logger = logging.getLogger(__name__)
renderer_log = get_renderer_logger()


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

    @log_performance
    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: Intensity,
        min_norm: float,
        max_norm: float,
        template_duration_ms: int | None = None,
        beat_grid: Any | None = None,
    ) -> DimmerResult:
        """Generate dimmer curves from library pattern.

        Args:
            params: Handler parameters:
                - dimmer_pattern: Dimmer pattern (required).
            n_samples: Number of samples to generate.
            cycles: Number of dimmer cycles (base value, may be unused).
            intensity: Intensity level (used to select categorical params).
            min_norm: Starting brightness [0, 1].
            max_norm: Ending brightness [0, 1].
            template_duration_ms: Template duration in milliseconds (for period conversion).
            beat_grid: Beat grid for converting period_bars to milliseconds.

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

        categorical_params = self._resolve_categorical_params(pattern, intensity)
        renderer_log.debug(f"Categorical Params: {categorical_params}")
        renderer_log.debug(f"Intensity: {intensity}")

        dimmer_min, dimmer_max = self._resolve_dimmer_bounds(params, pattern)
        renderer_log.debug(f"Dimmer Min: {dimmer_min}, Dimmer Max: {dimmer_max}")

        # Generate dimmer curve
        if pattern.curve == CurveLibrary.HOLD:
            dimmer_static_dmx = self._resolve_static_dmx_value(
                categorical_params.max_intensity, dimmer_min, dimmer_max
            )

            return DimmerResult(
                dimmer_static_dmx=dimmer_static_dmx,
                dimmer_curve_type=pattern.curve,
                intensity=intensity,
                min_intensity=categorical_params.min_intensity,
                max_intensity=categorical_params.max_intensity,
                period=categorical_params.period,
                clamp_min_dmx=dimmer_min,
                clamp_max_dmx=dimmer_max,
            )
        else:
            # Convert period_bars to cycles if both template_duration_ms and beat_grid are available
            computed_cycles = cycles  # Default to passed cycles
            period_bars = categorical_params.period

            if template_duration_ms is not None and beat_grid is not None and period_bars > 0:
                # Convert period from bars to milliseconds using beat_grid.ms_per_bar
                period_ms = period_bars * beat_grid.ms_per_bar
                # Calculate cycles: how many periods fit in the template duration
                computed_cycles = template_duration_ms / period_ms
                renderer_log.debug(
                    f"Period conversion: {period_bars} bars = {period_ms:.0f}ms → {computed_cycles:.2f} cycles (template: {template_duration_ms}ms)"
                )
            else:
                renderer_log.warning(
                    f"Cannot compute cycles from period_bars ({period_bars}): "
                    f"template_duration_ms={template_duration_ms}, beat_grid={'present' if beat_grid else 'missing'}"
                )

            dimmer_curve = self._generate_curve(
                curve_type=pattern.curve,
                n_samples=n_samples,
                cycles=computed_cycles,  # Use computed cycles
                amplitude=1.0,  # Amplitude handled via min/max intensity
                min_intensity=categorical_params.min_intensity,
                max_intensity=categorical_params.max_intensity,
                min_norm=min_norm,
                max_norm=max_norm,
                invert=pattern.invert,
            )
            return DimmerResult(
                dimmer_curve=dimmer_curve,
                dimmer_curve_type=pattern.curve,
                intensity=intensity,
                min_intensity=categorical_params.min_intensity,
                max_intensity=categorical_params.max_intensity,
                period=categorical_params.period,
                clamp_min_dmx=dimmer_min,
                clamp_max_dmx=dimmer_max,
            )

    def _resolve_categorical_params(
        self, pattern: Any, intensity: Intensity
    ) -> DimmerCategoricalParams:
        """Pick the params for `intensity`, never discarding the pattern's semantics.

        The fallback used to be the library defaults' SMOOTH entry, so BLACKOUT --
        which declares only a SMOOTH entry of its own -- resolved to that entry's
        `max_intensity=128` for every other intensity. Combined
        with the unit bug in `_resolve_static_dmx_value` that rendered a blackout as
        full brightness (P4-M2). A pattern that declares any table of its own is now
        only ever served from that table.

        Args:
            pattern: The dimmer pattern being rendered.
            intensity: The intensity the plan asked for.

        Returns:
            The categorical params to render with.
        """
        declared = pattern.categorical_params

        if not declared:
            if intensity not in DEFAULT_DIMMER_PARAMS:
                # Adding an Intensity member without an entry here is what produced
                # P4-F8: the missing member resolved to SMOOTH and the plan's request
                # vanished silently. Say so instead.
                raise ValueError(
                    f"DEFAULT_DIMMER_PARAMS has no entry for {intensity}; every "
                    "Intensity member needs one, or a plan asking for it renders "
                    "some other intensity without saying so."
                )
            return DEFAULT_DIMMER_PARAMS[intensity]

        if intensity in declared:
            resolved: DimmerCategoricalParams = declared[intensity]
            return resolved

        fallback: DimmerCategoricalParams = declared.get(
            Intensity.SMOOTH, next(iter(declared.values()))
        )
        renderer_log.debug(
            f"Pattern '{pattern.id}' declares no {intensity} entry; "
            f"using its own {fallback} rather than the library default"
        )
        return fallback

    def _resolve_dimmer_bounds(self, params: dict[str, Any], pattern: Any) -> tuple[int, int]:
        """Combine the template's declared dimmer bounds with the rig's calibration.

        The template declares an anti-flicker floor (`defaults["dimmer_floor_dmx"]`,
        60 on every shipped template) which nothing used to read; the rig declares a
        physical floor/ceiling. Both are lower/upper bounds, so the effective floor
        is the higher of the two and the effective ceiling the lower.

        Args:
            params: Handler params, carrying `calibration` and `template_defaults`.
            pattern: The dimmer pattern (a blackout is exempt from the floor).

        Returns:
            (floor_dmx, ceiling_dmx).
        """
        calibration = params.get("calibration") or {}
        template_defaults = params.get("template_defaults") or {}

        floor = max(
            int(calibration.get("dimmer_floor_dmx", 0) or 0),
            int(template_defaults.get("dimmer_floor_dmx", 0) or 0),
        )
        ceiling = min(
            int(calibration.get("dimmer_ceiling_dmx", 255) or 255),
            int(template_defaults.get("dimmer_ceiling_dmx", 255) or 255),
        )

        if pattern.bypasses_dimmer_floor:
            # A blackout is the one intent the floor must not lift off zero.
            floor = 0

        floor = max(0, min(255, floor))
        ceiling = max(floor, min(255, ceiling))
        return floor, ceiling

    def _resolve_static_dmx_value(
        self, dmx_value: float, clamp_min: int = 0, clamp_max: int = 255
    ) -> int:
        """Clamp a DMX intensity into the fixture's usable range.

        `max_intensity` is already a DMX value in [0, 255]; this used to multiply it
        by 255 as if it were normalized, so BLACKOUT's fallback `128` became `32 640`
        and clamped to the ceiling -- full brightness (P4-M2). HOLD's `255 * 255`
        clamped to 255 as well, which is why the bug was invisible there.

        Args:
            dmx_value: DMX intensity [0, 255].
            clamp_min: Minimum DMX value [0, 255].
            clamp_max: Maximum DMX value [0, 255].

        Returns:
            Static DMX value [0, 255].
        """
        renderer_log.debug(f"Resolving static DMX value: {dmx_value}, {clamp_min}, {clamp_max}")
        floor = max(clamp_min, 0)
        ceiling = min(clamp_max, 255)
        return max(floor, min(ceiling, int(dmx_value)))

    def _generate_curve(
        self,
        curve_type: Any,
        n_samples: int,
        cycles: float,
        amplitude: float,
        min_intensity: int,
        max_intensity: int,
        min_norm: float,
        max_norm: float,
        invert: bool = False,
    ) -> list[CurvePoint]:
        """Generate a dimmer curve with specified parameters.

        Intensity parameters (amplitude, cycles) are passed to the curve generator.
        The amplitude parameter is typically 1.0 for dimmers since min/max_intensity
        already control the range.

        Args:
            curve_type: CurveLibrary enum value.
            n_samples: Number of samples.
            cycles: Number of cycles (converted from period_bars by caller).
            amplitude: Amplitude scaling [0, 1] (typically 1.0 for dimmers).
            min_intensity: Min DMX intensity from categorical params [0, 255].
            max_intensity: Max DMX intensity from categorical params [0, 255].
            min_norm: Min normalized brightness [0, 1].
            max_norm: Max normalized brightness [0, 1].
            invert: Emit `1 - v`, so an ascending ramp becomes a descending one.

        Returns:
            List of curve points in normalized space [0, 1].
        """
        # Build curve generation parameters with intensity params
        curve_params = {
            "cycles": cycles,
            "amplitude": amplitude,
            # frequency is NOT passed - cycles already incorporates timing
        }

        # Generate base curve - already in normalized [0, 1] space
        base_curve = self._curve_gen.generate_custom_points(
            curve_id=curve_type.value,
            num_points=n_samples,
            **curve_params,
        )

        if invert:
            base_curve = [CurvePoint(t=point.t, v=1.0 - point.v) for point in base_curve]

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
