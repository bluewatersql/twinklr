"""Dimmer Handlers for the moving head sequencer.

This module implements dimmer handlers that generate absolute brightness
curves. Dimmer handlers determine how bright fixtures are over time.

All dimmer curves are absolute where v=0 is off and v=1 is full brightness.
Values are typically scaled to [min_norm, max_norm] range.
"""

from typing import Any

from blinkb0t.core.curves.generators import generate_hold, generate_linear, generate_sine
from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import DimmerResult


class FadeInHandler:
    """Dimmer handler for linear fade-in effect.

    Generates a linear ramp from min_norm to max_norm.
    This is the classic "lights up" effect.

    Attributes:
        handler_id: Unique identifier ("FADE_IN").

    Example:
        >>> handler = FadeInHandler()
        >>> result = handler.generate(
        ...     params={},
        ...     n_samples=16,
        ...     cycles=1.0,
        ...     intensity="SMOOTH",
        ...     min_norm=0.0,
        ...     max_norm=1.0,
        ... )
    """

    handler_id: str = "FADE_IN"

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: str,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult:
        """Generate fade-in dimmer curve.

        Args:
            params: Handler parameters (unused for basic fade).
            n_samples: Number of samples to generate.
            cycles: Number of cycles (unused for fade).
            intensity: Intensity level (unused for fade).
            min_norm: Starting brightness [0, 1].
            max_norm: Ending brightness [0, 1].

        Returns:
            DimmerResult with linear ramp curve.
        """
        # Generate base linear ramp [0, 1]
        base_curve = generate_linear(n_samples=n_samples, ascending=True)

        # Scale to [min_norm, max_norm]
        scaled_curve = self._scale_to_range(base_curve, min_norm, max_norm)

        return DimmerResult(dimmer_curve=scaled_curve)

    def _scale_to_range(
        self,
        curve: list[CurvePoint],
        min_norm: float,
        max_norm: float,
    ) -> list[CurvePoint]:
        """Scale curve values from [0, 1] to [min_norm, max_norm]."""
        range_size = max_norm - min_norm
        return [CurvePoint(t=p.t, v=min_norm + p.v * range_size) for p in curve]


class FadeOutHandler:
    """Dimmer handler for linear fade-out effect.

    Generates a linear ramp from max_norm to min_norm.
    This is the classic "lights down" effect.

    Attributes:
        handler_id: Unique identifier ("FADE_OUT").
    """

    handler_id: str = "FADE_OUT"

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: str,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult:
        """Generate fade-out dimmer curve.

        Args:
            params: Handler parameters (unused for basic fade).
            n_samples: Number of samples to generate.
            cycles: Number of cycles (unused for fade).
            intensity: Intensity level (unused for fade).
            min_norm: Ending brightness [0, 1].
            max_norm: Starting brightness [0, 1].

        Returns:
            DimmerResult with linear ramp down curve.
        """
        # Generate base linear ramp descending [1, 0]
        base_curve = generate_linear(n_samples=n_samples, ascending=False)

        # Scale to [min_norm, max_norm] (note: descending, so start at max)
        scaled_curve = self._scale_to_range(base_curve, min_norm, max_norm)

        return DimmerResult(dimmer_curve=scaled_curve)

    def _scale_to_range(
        self,
        curve: list[CurvePoint],
        min_norm: float,
        max_norm: float,
    ) -> list[CurvePoint]:
        """Scale curve values from [0, 1] to [min_norm, max_norm]."""
        range_size = max_norm - min_norm
        return [CurvePoint(t=p.t, v=min_norm + p.v * range_size) for p in curve]


class PulseHandler:
    """Dimmer handler for pulsing/breathing effect.

    Generates a sinusoidal brightness oscillation between min_norm and max_norm.
    The number of cycles determines how many pulses occur.

    Attributes:
        handler_id: Unique identifier ("PULSE").

    Example:
        >>> handler = PulseHandler()
        >>> result = handler.generate(
        ...     params={},
        ...     n_samples=64,
        ...     cycles=4.0,
        ...     intensity="SMOOTH",
        ...     min_norm=0.2,
        ...     max_norm=1.0,
        ... )
    """

    handler_id: str = "PULSE"

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: str,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult:
        """Generate pulsing dimmer curve.

        Args:
            params: Handler parameters (unused for basic pulse).
            n_samples: Number of samples to generate.
            cycles: Number of pulse cycles.
            intensity: Intensity level (unused for basic pulse).
            min_norm: Minimum brightness [0, 1].
            max_norm: Maximum brightness [0, 1].

        Returns:
            DimmerResult with sinusoidal pulse curve.
        """
        # Generate base sine wave [0, 1]
        base_curve = generate_sine(n_samples=n_samples, cycles=cycles)

        # Scale to [min_norm, max_norm]
        scaled_curve = self._scale_to_range(base_curve, min_norm, max_norm)

        return DimmerResult(dimmer_curve=scaled_curve)

    def _scale_to_range(
        self,
        curve: list[CurvePoint],
        min_norm: float,
        max_norm: float,
    ) -> list[CurvePoint]:
        """Scale curve values from [0, 1] to [min_norm, max_norm]."""
        range_size = max_norm - min_norm
        return [CurvePoint(t=p.t, v=min_norm + p.v * range_size) for p in curve]


class HoldHandler:
    """Dimmer handler for constant brightness.

    Generates a flat line at a specified brightness level.
    Useful for static looks or as a baseline.

    Attributes:
        handler_id: Unique identifier ("HOLD").

    Example:
        >>> handler = HoldHandler()
        >>> result = handler.generate(
        ...     params={},
        ...     n_samples=8,
        ...     cycles=1.0,
        ...     intensity="SMOOTH",
        ...     min_norm=0.0,
        ...     max_norm=1.0,
        ... )
    """

    handler_id: str = "HOLD"

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: str,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult:
        """Generate constant dimmer curve.

        Args:
            params: Handler parameters:
                - hold_value: Override brightness value [0, 1]
            n_samples: Number of samples to generate.
            cycles: Number of cycles (unused for hold).
            intensity: Intensity level (unused for hold).
            min_norm: Minimum brightness (unused unless hold_value not set).
            max_norm: Default brightness if hold_value not set.

        Returns:
            DimmerResult with constant curve.
        """
        # Determine hold value
        if "hold_value" in params:
            value = float(params["hold_value"])
        else:
            value = max_norm

        # Generate constant curve
        curve = generate_hold(n_samples=n_samples, value=value)

        return DimmerResult(dimmer_curve=curve)
