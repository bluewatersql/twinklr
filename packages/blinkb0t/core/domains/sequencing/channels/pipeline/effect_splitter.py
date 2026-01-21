"""Effect splitting for channel integration pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.models.channels import SequencedEffect

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimeSegment:
    """A time segment with active effects.

    Attributes:
        start_ms: Segment start time
        end_ms: Segment end time
        effects: Effects active in this segment

    Example:
        >>> segment = TimeSegment(start_ms=100, end_ms=200, effects=[effect1])
        >>> segment.start_ms  # 100
        >>> len(segment.effects)  # 1
    """

    start_ms: int
    end_ms: int
    effects: list[SequencedEffect]


class EffectSplitter:
    """Split effects at time boundaries.

    Creates time segments where the set of active effects is constant.

    Example:
        >>> effects = [
        ...     SequencedEffect(targets=["ALL"], channels={...}, start_ms=100, end_ms=500),
        ...     SequencedEffect(targets=["ALL"], channels={...}, start_ms=200, end_ms=400),
        ... ]
        >>> boundaries = [100, 200, 400, 500]
        >>> splitter = EffectSplitter()
        >>> segments = splitter.split(effects, boundaries)
        >>> assert len(segments) == 3
        >>> assert segments[0].start_ms == 100
        >>> assert segments[0].end_ms == 200
        >>> assert len(segments[0].effects) == 1  # Only first effect active
    """

    def split(self, effects: list[SequencedEffect], boundaries: list[int]) -> list[TimeSegment]:
        """Split effects at boundaries into time segments.

        Args:
            effects: List of sequenced effects
            boundaries: Sorted list of time boundaries

        Returns:
            List of time segments with active effects
        """
        if not boundaries:
            return []

        if len(boundaries) < 2:
            logger.warning("Need at least 2 boundaries to create segments")
            return []

        segments = []

        for i in range(len(boundaries) - 1):
            start_ms = boundaries[i]
            end_ms = boundaries[i + 1]

            # Find all effects active in this segment
            active = [eff for eff in effects if eff.start_ms <= start_ms and eff.end_ms >= end_ms]

            segments.append(TimeSegment(start_ms=start_ms, end_ms=end_ms, effects=active))

        logger.debug(f"Split into {len(segments)} segments")

        return segments
