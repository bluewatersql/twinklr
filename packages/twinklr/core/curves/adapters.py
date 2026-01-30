"""Parameter adapters for curve generation.

Translates categorical intensity parameters (amplitude, frequency, center_offset)
to curve-specific parameters. This allows curves with different parameter signatures
to work uniformly with the intensity system.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from twinklr.core.sequencer.moving_heads.libraries.movement import MovementCategoricalParams

# Adapter signature: categorical params → curve-specific params
ParameterAdapter = Callable[[MovementCategoricalParams, dict[str, Any]], dict[str, Any]]


class ParameterAdapterRegistry:
    """Registry of parameter adapters for curves.

    Manages adapters that translate categorical intensity parameters
    to curve-specific parameters. Each adapter is registered by curve ID
    and applied when resolving curves with categorical params.
    """

    def __init__(self) -> None:
        """Initialize empty adapter registry."""
        self._adapters: dict[str, ParameterAdapter] = {}

    def register(self, curve_id: str, adapter: ParameterAdapter) -> None:
        """Register an adapter for a curve.

        Args:
            curve_id: Curve identifier (e.g., "pulse", "movement_pulse")
            adapter: Adapter function to register
        """
        self._adapters[curve_id] = adapter

    def adapt(
        self,
        curve_id: str,
        categorical: MovementCategoricalParams,
        base_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Adapt categorical params to curve-specific params.

        If a curve has a registered adapter, it will be used. Otherwise,
        a default mapping (amplitude, frequency) is applied.

        Args:
            curve_id: Curve identifier
            categorical: Categorical intensity parameters
            base_params: Base curve parameters (cycles, etc.)

        Returns:
            Adapted parameters ready for curve generator
        """
        if curve_id in self._adapters:
            return self._adapters[curve_id](categorical, base_params)

        # Default: direct mapping
        return {
            **base_params,
            "amplitude": categorical.amplitude,
            "frequency": categorical.frequency,
        }


def adapt_pulse_params(
    categorical: MovementCategoricalParams,
    base_params: dict[str, Any],
) -> dict[str, Any]:
    """Adapt amplitude to high/low for pulse curves.

    PULSE curves use high/low instead of amplitude. We map amplitude
    to the range around center_offset.

    Args:
        categorical: Categorical intensity parameters
        base_params: Base curve parameters

    Returns:
        Adapted parameters with high/low

    Example:
        >>> from twinklr.core.sequencer.moving_heads.libraries.movement import (
        ...     MovementCategoricalParams,
        ... )
        >>> categorical = MovementCategoricalParams(
        ...     amplitude=0.8, frequency=2.0, center_offset=0.5
        ... )
        >>> result = adapt_pulse_params(categorical, {"cycles": 2.0})
        >>> result["high"]  # 0.5 + 0.8/2
        0.9
        >>> result["low"]  # 0.5 - 0.8/2
        0.1
    """
    center = categorical.center_offset
    half_amp = categorical.amplitude / 2

    return {
        **base_params,
        "high": center + half_amp,
        "low": center - half_amp,
        "frequency": categorical.frequency,
        "duty_cycle": base_params.get("duty_cycle", 0.5),
    }


def adapt_movement_pulse_params(
    categorical: MovementCategoricalParams,
    base_params: dict[str, Any],
) -> dict[str, Any]:
    """Adapt amplitude to high/low for movement_pulse.

    Movement curves are centered at 0.5, so we map amplitude
    symmetrically around that center.

    Args:
        categorical: Categorical intensity parameters
        base_params: Base curve parameters

    Returns:
        Adapted parameters with high/low

    Example:
        >>> from twinklr.core.sequencer.moving_heads.libraries.movement import (
        ...     MovementCategoricalParams,
        ... )
        >>> categorical = MovementCategoricalParams(
        ...     amplitude=0.6, frequency=1.5, center_offset=0.7
        ... )
        >>> result = adapt_movement_pulse_params(categorical, {})
        >>> result["high"]  # Always 0.5 + amp/2
        0.8
        >>> result["low"]  # Always 0.5 - amp/2
        0.2
    """
    center = 0.5  # Movement curves always centered
    half_amp = categorical.amplitude / 2

    return {
        **base_params,
        "high": center + half_amp,
        "low": center - half_amp,
        "frequency": categorical.frequency,
        "duty_cycle": base_params.get("duty_cycle", 0.5),
        "cycles": base_params.get("cycles", 1.0),
    }


def adapt_bezier_params(
    categorical: MovementCategoricalParams,
    base_params: dict[str, Any],
) -> dict[str, Any]:
    """Adapt amplitude to bezier control point scaling.

    Bezier curves use control points. We scale their y-values by amplitude
    to control the curve intensity.

    Args:
        categorical: Categorical intensity parameters
        base_params: Base curve parameters (must include control_points)

    Returns:
        Adapted parameters with scaled control points

    Example:
        >>> from twinklr.core.sequencer.moving_heads.libraries.movement import (
        ...     MovementCategoricalParams,
        ... )
        >>> categorical = MovementCategoricalParams(
        ...     amplitude=0.5, frequency=1.0, center_offset=0.5
        ... )
        >>> result = adapt_bezier_params(
        ...     categorical,
        ...     {"control_points": [(0.0, 0.0), (0.5, 1.0), (1.0, 0.5)]},
        ... )
        >>> result["control_points"]
        [(0.0, 0.0), (0.5, 0.5), (1.0, 0.25)]
    """
    control_points = base_params.get("control_points", [(0.0, 0.0), (1.0, 1.0)])

    # Scale control point y-values by amplitude
    scaled_points = [(x, y * categorical.amplitude) for x, y in control_points]

    return {
        **base_params,
        "control_points": scaled_points,
    }


def adapt_lissajous_params(
    categorical: MovementCategoricalParams,
    base_params: dict[str, Any],
) -> dict[str, Any]:
    """Adapt frequency to lissajous b parameter.

    Lissajous uses b for frequency ratio. We scale b by frequency multiplier
    to control the curve complexity. The b parameter must be >= 1.

    Args:
        categorical: Categorical intensity parameters
        base_params: Base curve parameters (must include b)

    Returns:
        Adapted parameters with scaled b

    Example:
        >>> from twinklr.core.sequencer.moving_heads.libraries.movement import (
        ...     MovementCategoricalParams,
        ... )
        >>> categorical = MovementCategoricalParams(
        ...     amplitude=0.8, frequency=2.0, center_offset=0.5
        ... )
        >>> result = adapt_lissajous_params(
        ...     categorical, {"b": 2, "delta": 0}
        ... )
        >>> result["b"]  # max(1, int(2 * 2.0))
        4
    """
    b_base = base_params.get("b", 2)

    # Scale b by frequency, ensuring b >= 1 (lissajous requirement)
    # For low frequencies (< 0.5), use fractional scaling instead of int
    scaled_b = b_base * categorical.frequency
    b = max(1, int(scaled_b)) if scaled_b >= 1.0 else 1

    return {
        **base_params,
        "amplitude": categorical.amplitude,
        "b": b,
        "delta": base_params.get("delta", 0),
    }


def adapt_fixed_behavior(
    categorical: MovementCategoricalParams,
    base_params: dict[str, Any],
) -> dict[str, Any]:
    """Pass-through adapter for fixed behavior curves.

    These curves don't accept intensity params, so we just return
    the base params unchanged.

    Args:
        categorical: Categorical intensity parameters (ignored)
        base_params: Base curve parameters

    Returns:
        Base parameters unchanged

    Example:
        >>> from twinklr.core.sequencer.moving_heads.libraries.movement import (
        ...     MovementCategoricalParams,
        ... )
        >>> categorical = MovementCategoricalParams(
        ...     amplitude=0.8, frequency=2.0, center_offset=0.5
        ... )
        >>> result = adapt_fixed_behavior(categorical, {"param": 1})
        >>> result
        {'param': 1}
    """
    return dict(base_params)  # Return copy


def build_default_adapter_registry() -> ParameterAdapterRegistry:
    """Build registry with all standard adapters.

    Returns:
        Registry with adapters for all known curves

    Example:
        >>> registry = build_default_adapter_registry()
        >>> from twinklr.core.sequencer.moving_heads.libraries.movement import (
        ...     MovementCategoricalParams,
        ... )
        >>> categorical = MovementCategoricalParams(
        ...     amplitude=0.8, frequency=2.0, center_offset=0.5
        ... )
        >>> result = registry.adapt("pulse", categorical, {})
        >>> "high" in result and "low" in result
        True
    """
    registry = ParameterAdapterRegistry()

    # Register curve-specific adapters
    registry.register("pulse", adapt_pulse_params)
    registry.register("movement_pulse", adapt_movement_pulse_params)
    registry.register("bezier", adapt_bezier_params)
    registry.register("lissajous", adapt_lissajous_params)
    registry.register("movement_lissajous", adapt_lissajous_params)

    # Register fixed behavior curves (easing, dynamic, musical)
    fixed_curves = [
        # Easing curves
        "ease_in_sine",
        "ease_out_sine",
        "ease_in_out_sine",
        "ease_in_quad",
        "ease_out_quad",
        "ease_in_out_quad",
        "ease_in_cubic",
        "ease_out_cubic",
        "ease_in_out_cubic",
        "ease_in_back",
        "ease_out_back",
        "ease_in_out_back",
        "s_curve",
        "smooth_step",
        "smoother_step",
        "anticipate",
        "overshoot",
        # Dynamic curves
        "bounce_in",
        "bounce_out",
        "elastic_in",
        "elastic_out",
        # Musical curves
        "musical_accent",
        "musical_swell",
        "beat_pulse",
        # Basic curves
        "hold",
        "movement_hold",
    ]

    for curve in fixed_curves:
        registry.register(curve, adapt_fixed_behavior)

    return registry
