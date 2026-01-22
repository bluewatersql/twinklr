from typing import Any

from blinkb0t.core.curves.generators import generate_hold
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import DimmerResult
from blinkb0t.core.sequencer.moving_heads.models.base import Intensity


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
        intensity: Intensity,
        min_norm: float,
        max_norm: float,
    ) -> DimmerResult:
        """Generate constant dimmer curve.

        Args:
            params: Handler parameters:
                - hold_value: Override brightness value [0, 1]
            n_samples: Number of samples to generate.
            cycles: Number of cycles (unused for hold).
            intensity: Intensity level.
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
