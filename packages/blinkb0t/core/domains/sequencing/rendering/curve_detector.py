"""Curve type detection for Native vs Custom classification.

Extracted from curve_pipeline.py to reduce complexity and improve maintainability.
Handles detection of curve types to determine appropriate rendering strategy.
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
from blinkb0t.core.utils.logging import get_logger

from .models import SequencedEffect

logger = get_logger(__name__)


class CurveTypeDetector:
    """Detects curve types (Native vs Custom) to determine rendering strategy.

    Responsibilities:
    - Check for presence of Native curves (ValueCurveSpec)
    - Examine all channels (movement and appearance)
    - Return classification to guide pipeline routing

    Native curves require SNAP transitions (no blending) because xLights
    renders them directly. Custom curves can use blending for smooth transitions.

    This class contains the detection logic extracted from CurvePipeline to
    reduce its complexity and make the logic more testable.
    """

    def detect_native_curves(self, effects: list[SequencedEffect]) -> bool:
        """Check if any effect contains Native curves (ValueCurveSpec).

        Native curves require SNAP transitions (no blending) because xLights
        renders them directly. Custom curves and static values can use blending.

        Checks all movement channels (pan, tilt, dimmer) and appearance channels
        (shutter) for ValueCurveSpec instances.

        Args:
            effects: List of effects to check (for single fixture)

        Returns:
            True if any Native curves present, False if all Custom/static

        Example:
            >>> effects = [SequencedEffect(...pan=ValueCurveSpec(type=NativeCurveType.SINE)...)]
            >>> has_native = detector.detect_native_curves(effects)
            >>> assert has_native is True  # Uses SNAP (no blending)
        """
        for effect in effects:
            # Check movement channels
            if isinstance(effect.channels.pan, ValueCurveSpec):
                return True
            if isinstance(effect.channels.tilt, ValueCurveSpec):
                return True
            if isinstance(effect.channels.dimmer, ValueCurveSpec):
                return True

            # Check appearance channels (if present)
            if effect.channels.shutter and isinstance(effect.channels.shutter, ValueCurveSpec):
                return True

        return False
