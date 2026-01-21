"""Curve normalization and auto-fit algorithms.

Handles:
- Normalization of curves to [0, 1] range
- Linear mapping from normalized space to DMX ranges
- Auto-fit to prevent boundary clipping while preserving shape
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.models.curves import CurvePoint


class CurveNormalizer:
    """Normalizes and maps curve points to DMX ranges.

    Provides algorithms to:
    - Normalize curve values to [0, 1] space
    - Linearly map normalized curves to specific DMX ranges
    - Auto-fit curves to boundaries without clipping
    """

    def normalize_to_unit_range(self, points: list[CurvePoint]) -> list[CurvePoint]:
        """Normalize curve points to [0, 1] range.

        Args:
            points: List of curve points with arbitrary value range

        Returns:
            New list of curve points with values normalized to [0, 1]
            Time values are preserved unchanged

        Edge cases:
            - Empty list returns empty list
            - Single point returns point with value 0.5
            - Constant values return all 0.5
        """
        if not points:
            return []

        if len(points) == 1:
            # Single point: map to middle of range
            return [CurvePoint(time=points[0].time, value=0.5)]

        # Find min and max values
        values = [p.value for p in points]
        min_val = min(values)
        max_val = max(values)

        # Handle constant value case
        if max_val == min_val:
            # All values same: map to middle of range
            return [CurvePoint(time=p.time, value=0.5) for p in points]

        # Normalize to [0, 1]
        value_range = max_val - min_val
        return [
            CurvePoint(
                time=p.time,
                value=(p.value - min_val) / value_range,
            )
            for p in points
        ]

    def linear_map_to_range(
        self, points: list[CurvePoint], min_val: float, max_val: float
    ) -> list[CurvePoint]:
        """Map normalized curve points to specific DMX range.

        Args:
            points: List of curve points (typically normalized to [0, 1])
            min_val: Minimum output value (e.g., 0 for DMX)
            max_val: Maximum output value (e.g., 255 for 8-bit DMX, 65535 for 16-bit)

        Returns:
            New list of curve points with values mapped to [min_val, max_val]
            Time values are preserved unchanged

        Formula:
            output = min_val + (value * (max_val - min_val))
        """
        if not points:
            return []

        output_range = max_val - min_val
        return [
            CurvePoint(
                time=p.time,
                value=min_val + (p.value * output_range),
            )
            for p in points
        ]

    def auto_fit_to_range(
        self, points: list[CurvePoint], min_limit: float, max_limit: float
    ) -> list[CurvePoint]:
        """Auto-fit curve to boundaries without clipping, preserving shape.

        Scales the curve to fit within [min_limit, max_limit] by:
        1. Finding the current min/max of the curve
        2. Normalizing to [0, 1]
        3. Mapping to the available range

        This preserves the curve's shape (relative proportions) while
        ensuring no clipping occurs.

        Args:
            points: List of curve points with arbitrary values
            min_limit: Lower boundary limit (e.g., pan min range)
            max_limit: Upper boundary limit (e.g., pan max range)

        Returns:
            New list of curve points fitted to [min_limit, max_limit]
            Time values are preserved unchanged

        Example:
            Curve with values [-50, 128, 350] fitted to [0, 255]:
            - Normalizes to [0.0, 0.445, 1.0]
            - Maps to [0, 113.475, 255]
        """
        if not points:
            return []

        # Step 1: Normalize to [0, 1] (handles all edge cases)
        normalized = self.normalize_to_unit_range(points)

        # Step 2: Map to target range
        return self.linear_map_to_range(normalized, min_limit, max_limit)
