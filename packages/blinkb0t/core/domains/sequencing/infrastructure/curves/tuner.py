"""Native curve parameter tuning for xLights curves.

Mathematically adjusts p1-p4 parameters for xLights native curves
to fit within DMX boundaries without clipping.

More efficient than generating point arrays for native curves.
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec


class NativeCurveTuner:
    """Tunes xLights native curve parameters to fit DMX boundaries.

    Uses mathematical algorithms to adjust p1-p4 parameters so curves
    fit within specified boundaries without clipping, while preserving
    their characteristic shape.

    This is more efficient than generating point arrays and re-normalizing.
    """

    def tune_to_fit(
        self, spec: ValueCurveSpec, min_limit: float, max_limit: float
    ) -> ValueCurveSpec:
        """Tune curve parameters to fit within DMX boundaries.

        Args:
            spec: Original ValueCurveSpec with potentially out-of-bounds parameters
            min_limit: Minimum DMX boundary (e.g., 0 or fixture-specific min)
            max_limit: Maximum DMX boundary (e.g., 255 or fixture-specific max)

        Returns:
            New ValueCurveSpec with tuned parameters that fit within boundaries

        Note:
            Returns a new instance; original spec is unchanged (immutability)
        """
        if spec.type in (
            NativeCurveType.SINE,
            NativeCurveType.ABS_SINE,
            NativeCurveType.PARABOLIC,
        ):
            return self._tune_amplitude_center(spec, min_limit, max_limit)
        elif spec.type in (
            NativeCurveType.RAMP,
            NativeCurveType.SAW_TOOTH,
            NativeCurveType.EXPONENTIAL,
            NativeCurveType.LOGARITHMIC,
        ):
            return self._tune_min_max(spec, min_limit, max_limit)
        elif spec.type == NativeCurveType.FLAT:
            return self._tune_flat(spec, min_limit, max_limit)
        else:
            # Unknown type: return as-is
            return spec

    def _tune_amplitude_center(
        self, spec: ValueCurveSpec, min_limit: float, max_limit: float
    ) -> ValueCurveSpec:
        """Tune curves with amplitude (p2) and center (p4) parameters.

        Used for: Sine, Abs Sine, Parabolic

        Original range: [center - amplitude, center + amplitude]
        Tuned to fit: [min_limit, max_limit]

        Algorithm:
            1. Calculate current min/max: [p4 - p2, p4 + p2]
            2. If already fits, return unchanged
            3. Otherwise:
               - new_center = (min_limit + max_limit) / 2
               - new_amplitude = (max_limit - min_limit) / 2
        """
        current_min = spec.p4 - spec.p2
        current_max = spec.p4 + spec.p2

        # Check if already fits
        if current_min >= min_limit and current_max <= max_limit:
            return spec

        # Calculate new center and amplitude
        new_center = (min_limit + max_limit) / 2.0
        new_amplitude = (max_limit - min_limit) / 2.0

        # Return new spec with tuned parameters
        return ValueCurveSpec(
            type=spec.type,
            p1=spec.p1,  # Preserve p1 (frequency, etc.)
            p2=new_amplitude,  # Tuned amplitude
            p3=spec.p3,  # Preserve p3 (phase, etc.)
            p4=new_center,  # Tuned center
            reverse=spec.reverse,
            min_val=spec.min_val,
            max_val=spec.max_val,
        )

    def _tune_min_max(
        self, spec: ValueCurveSpec, min_limit: float, max_limit: float
    ) -> ValueCurveSpec:
        """Tune curves with min (p1) and max (p2) parameters.

        Used for: Ramp, Saw Tooth, Exponential, Logarithmic

        Original range: [p1, p2]
        Tuned to fit: [min_limit, max_limit]

        Algorithm:
            1. Check if [p1, p2] exceeds [min_limit, max_limit]
            2. Clamp p1 to min_limit if below
            3. Clamp p2 to max_limit if above
        """
        # Clamp to boundaries
        new_p1 = max(spec.p1, min_limit)
        new_p2 = min(spec.p2, max_limit)

        # If already within bounds, return unchanged
        if new_p1 == spec.p1 and new_p2 == spec.p2:
            return spec

        # Return new spec with clamped parameters
        return ValueCurveSpec(
            type=spec.type,
            p1=new_p1,  # Clamped min
            p2=new_p2,  # Clamped max
            p3=spec.p3,
            p4=spec.p4,
            reverse=spec.reverse,
            min_val=spec.min_val,
            max_val=spec.max_val,
        )

    def _tune_flat(
        self, spec: ValueCurveSpec, min_limit: float, max_limit: float
    ) -> ValueCurveSpec:
        """Tune flat curve (constant value).

        Used for: Flat

        Original value: p1
        Tuned to fit: [min_limit, max_limit]

        Algorithm:
            Clamp p1 to [min_limit, max_limit]
        """
        # Clamp to boundaries
        new_p1 = max(min_limit, min(spec.p1, max_limit))

        # If already within bounds, return unchanged
        if new_p1 == spec.p1:
            return spec

        # Return new spec with clamped value
        return ValueCurveSpec(
            type=spec.type,
            p1=new_p1,  # Clamped constant value
            p2=spec.p2,
            p3=spec.p3,
            p4=spec.p4,
            reverse=spec.reverse,
            min_val=spec.min_val,
            max_val=spec.max_val,
        )
