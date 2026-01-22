from typing import Any

from blinkb0t.core.curves.generators import generate_sine
from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import DimmerResult

from sequencer.moving_heads.models.base import Intensity


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
        ...     intensity=Intensity.SMOOTH,
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
        intensity: Intensity,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult:
        """Generate pulsing dimmer curve.

        Args:
            params: Handler parameters (unused for basic pulse).
            n_samples: Number of samples to generate.
            cycles: Number of pulse cycles.
            intensity: Intensity level.
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
