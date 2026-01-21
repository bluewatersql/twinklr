"""Movement Handlers for the moving head sequencer.

This module implements movement handlers that generate motion curves
applied as offsets around geometry base poses. Movement handlers
determine HOW fixtures move over time, but NOT where they start.

All movement curves are offset-centered where v=0.5 means "no offset".
"""

from enum import Enum
from typing import Any

from blinkb0t.core.curves.generators import generate_hold, generate_sine
from blinkb0t.core.curves.models import CurvePoint
from blinkb0t.core.sequencer.moving_heads.handlers.protocols import MovementResult


class Intensity(str, Enum):
    """Movement intensity levels.

    Maps intensity names to amplitude values.
    Higher intensity = larger motion amplitude.

    Attributes:
        SLOW: Minimal motion (0.08 amplitude).
        SMOOTH: Gentle motion (0.15 amplitude).
        FAST: Moderate motion (0.25 amplitude).
        DRAMATIC: Large motion (0.4 amplitude).
    """

    SLOW = "SLOW"
    SMOOTH = "SMOOTH"
    FAST = "FAST"
    DRAMATIC = "DRAMATIC"

    @property
    def amplitude(self) -> float:
        """Get normalized amplitude for this intensity.

        Returns amplitude as fraction of full range.
        For pan/tilt, this represents half the total swing.
        """
        amplitudes = {
            Intensity.SLOW: 0.08,
            Intensity.SMOOTH: 0.15,
            Intensity.FAST: 0.25,
            Intensity.DRAMATIC: 0.4,
        }
        return amplitudes[self]


class SweepLRHandler:
    """Movement handler for left-to-right sweep motion.

    Generates a sinusoidal pan motion centered around 0.5.
    Tilt remains static (no vertical motion).

    The amplitude is determined by:
    1. amplitude_degrees param (if specified)
    2. intensity level mapping (default)

    Attributes:
        handler_id: Unique identifier ("SWEEP_LR").

    Example:
        >>> handler = SweepLRHandler()
        >>> result = handler.generate(
        ...     params={},
        ...     n_samples=64,
        ...     cycles=2.0,
        ...     intensity="SMOOTH",
        ... )
        >>> len(result.pan_curve)
        64
    """

    handler_id: str = "SWEEP_LR"

    def generate(
        self,
        params: dict[str, Any],
        n_samples: int,
        cycles: float,
        intensity: str,
    ) -> MovementResult:
        """Generate sweep motion curves.

        Args:
            params: Handler parameters:
                - amplitude_degrees: Override amplitude (0-180)
            n_samples: Number of samples to generate.
            cycles: Number of sweep cycles.
            intensity: Intensity level (SLOW, SMOOTH, FAST, DRAMATIC).

        Returns:
            MovementResult with offset-centered pan/tilt curves.
        """
        # Determine amplitude
        amplitude = self._resolve_amplitude(params, intensity)

        # Generate pan curve: sine wave centered at 0.5
        pan_curve = self._generate_pan_curve(n_samples, cycles, amplitude)

        # Generate tilt curve: static at 0.5 (no motion)
        tilt_curve = generate_hold(n_samples=n_samples, value=0.5)

        return MovementResult(pan_curve=pan_curve, tilt_curve=tilt_curve)

    def _resolve_amplitude(self, params: dict[str, Any], intensity: str) -> float:
        """Resolve amplitude from params or intensity.

        Priority:
        1. amplitude_degrees param (converted to normalized)
        2. intensity level mapping
        3. SMOOTH default
        """
        # Check for explicit amplitude param
        if "amplitude_degrees" in params:
            degrees = float(params["amplitude_degrees"])
            # Convert degrees to normalized amplitude (180 degrees = 1.0 full range)
            return min(0.5, max(0.0, degrees / 180.0))

        # Use intensity mapping
        try:
            return Intensity(intensity).amplitude
        except ValueError:
            # Unknown intensity, default to SMOOTH
            return Intensity.SMOOTH.amplitude

    def _generate_pan_curve(
        self,
        n_samples: int,
        cycles: float,
        amplitude: float,
    ) -> list[CurvePoint]:
        """Generate offset-centered pan curve.

        Creates a sine wave centered at 0.5 with the specified amplitude.
        Values are clamped to [0, 1].
        """
        # Generate base sine wave (already centered at 0.5, amplitude 0.5)
        base_sine = generate_sine(n_samples=n_samples, cycles=cycles)

        # Scale amplitude: base sine has amplitude 0.5, we want custom amplitude
        # base value range: [0, 1] centered at 0.5
        # new value range: [0.5 - amplitude, 0.5 + amplitude]
        scaled_points: list[CurvePoint] = []
        for point in base_sine:
            # Convert from [0, 1] centered at 0.5 to scaled version
            offset = point.v - 0.5  # Now in [-0.5, 0.5]
            scaled_offset = offset * (amplitude / 0.5)  # Scale amplitude
            new_v = 0.5 + scaled_offset

            # Clamp to [0, 1]
            new_v = max(0.0, min(1.0, new_v))

            scaled_points.append(CurvePoint(t=point.t, v=new_v))

        return scaled_points
