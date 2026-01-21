"""Boundary detection for channel integration pipeline."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.models.channels import SequencedEffect

logger = logging.getLogger(__name__)


class BoundaryDetector:
    """Detect time boundaries where channel sets change.

    A boundary is any time point where:
    - An effect starts
    - An effect ends

    Boundaries are used to split the timeline into segments where the
    set of active effects is constant.

    Example:
        >>> effects = [
        ...     SequencedEffect(targets=["ALL"], channels={...}, start_ms=100, end_ms=500),
        ...     SequencedEffect(targets=["ALL"], channels={...}, start_ms=200, end_ms=400),
        ... ]
        >>> detector = BoundaryDetector()
        >>> boundaries = detector.detect(effects)
        >>> assert boundaries == [100, 200, 400, 500]
    """

    def detect(self, effects: list[SequencedEffect]) -> list[int]:
        """Detect all time boundaries in a list of effects.

        Args:
            effects: List of sequenced effects

        Returns:
            Sorted list of unique time points (in milliseconds)
        """
        if not effects:
            return []

        boundaries = set()

        # Add start/end of each effect
        for effect in effects:
            boundaries.add(effect.start_ms)
            boundaries.add(effect.end_ms)

        sorted_boundaries = sorted(boundaries)

        logger.debug(f"Detected {len(sorted_boundaries)} boundaries: {sorted_boundaries}")

        return sorted_boundaries
