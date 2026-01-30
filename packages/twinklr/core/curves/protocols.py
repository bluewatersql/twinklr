"""Protocol definitions for curve parameter interfaces.

Defines standard interfaces that curves can implement to support
categorical intensity parameters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from twinklr.core.curves.models import CurvePoint


@runtime_checkable
class IntensityParameterizable(Protocol):
    """Curves that support categorical intensity parameters.

    These curves accept amplitude and frequency parameters that can be
    controlled via intensity levels (SLOW, SMOOTH, FAST, DRAMATIC, INTENSE).

    Example:
        >>> def generate_sine(
        ...     n_samples: int,
        ...     amplitude: float,
        ...     frequency: float,
        ...     **kwargs,
        ... ) -> list[CurvePoint]:
        ...     # Generate sine wave with intensity params
        ...     ...
    """

    def __call__(
        self,
        n_samples: int,
        amplitude: float,
        frequency: float,
        **kwargs,
    ) -> list[CurvePoint]:
        """Generate curve with intensity parameters.

        Args:
            n_samples: Number of samples to generate
            amplitude: Amplitude scaling [0, 1]
            frequency: Frequency multiplier [0, 10]
            **kwargs: Curve-specific additional parameters

        Returns:
            List of curve points
        """
        ...


@runtime_checkable
class CycleParameterizable(Protocol):
    """Curves that support cycle-based timing.

    These curves generate a specified number of complete cycles
    over the normalized time domain [0, 1].

    Example:
        >>> def generate_wave(
        ...     n_samples: int,
        ...     cycles: float,
        ...     amplitude: float,
        ...     frequency: float,
        ...     **kwargs,
        ... ) -> list[CurvePoint]:
        ...     # Generate wave with cycle timing
        ...     ...
    """

    def __call__(
        self,
        n_samples: int,
        cycles: float,
        amplitude: float,
        frequency: float,
        **kwargs,
    ) -> list[CurvePoint]:
        """Generate curve with cycle timing.

        Args:
            n_samples: Number of samples to generate
            cycles: Number of complete cycles
            amplitude: Amplitude scaling [0, 1]
            frequency: Frequency multiplier [0, 10]
            **kwargs: Curve-specific additional parameters

        Returns:
            List of curve points
        """
        ...


@runtime_checkable
class FixedBehavior(Protocol):
    """Curves with fixed algorithmic behavior.

    These curves have predetermined behavior (easing, bounce, elastic, etc.)
    and do not accept intensity parameters. They generate output based
    solely on their algorithm.

    Example:
        >>> def generate_ease_in(
        ...     n_samples: int,
        ...     **kwargs,
        ... ) -> list[CurvePoint]:
        ...     # Generate easing curve (no intensity params)
        ...     ...
    """

    def __call__(
        self,
        n_samples: int,
        **kwargs,
    ) -> list[CurvePoint]:
        """Generate curve (no intensity params).

        Args:
            n_samples: Number of samples to generate
            **kwargs: Optional curve-specific parameters

        Returns:
            List of curve points
        """
        ...
