from typing import Any

from blinkb0t.core.curves.generators import generate_linear
from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import DimmerResult
from blinkb0t.core.sequencer.moving_heads.models.base import Intensity


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
        intensity: Intensity,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult:
        """Generate fade-out dimmer curve.

        Args:
            params: Handler parameters (unused for basic fade).
            n_samples: Number of samples to generate.
            cycles: Number of cycles (unused for fade).
            intensity: Intensity level.
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
