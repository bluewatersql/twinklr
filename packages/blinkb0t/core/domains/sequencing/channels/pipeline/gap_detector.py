"""Gap detection for channel integration pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.models.channels import DmxEffect

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Gap:
    """A gap in the timeline with no active effects.

    Attributes:
        start_ms: Gap start time
        end_ms: Gap end time

    Example:
        >>> gap = Gap(start_ms=100, end_ms=200)
        >>> gap.start_ms  # 100
        >>> gap.end_ms    # 200
    """

    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        """Validate gap after initialization."""
        if self.end_ms <= self.start_ms:
            raise ValueError(f"end_ms ({self.end_ms}) must be > start_ms ({self.start_ms})")


class GapDetector:
    """Detect gaps in the timeline.

    A gap is a time range within a section where no effects are active.
    Gaps should be filled with soft home position to prevent fixtures
    from jerking back to DMX 0,0.

    Example:
        >>> effects = [
        ...     DmxEffect(fixture_id="MH1", start_ms=100, end_ms=200, channels={...}),
        ...     DmxEffect(fixture_id="MH1", start_ms=300, end_ms=400, channels={...}),
        ... ]
        >>> detector = GapDetector()
        >>> gaps = detector.detect(effects, section_start_ms=0, section_end_ms=500)
        >>> # Gaps: 0-100, 200-300, 400-500
    """

    def detect(
        self, effects: list[DmxEffect], section_start_ms: int, section_end_ms: int
    ) -> list[Gap]:
        """Detect gaps within a section.

        Args:
            effects: List of DMX effects (already filled)
            section_start_ms: Section start time
            section_end_ms: Section end time

        Returns:
            List of gaps (time ranges with no effects)
        """
        if not effects:
            # Entire section is a gap
            return [Gap(start_ms=section_start_ms, end_ms=section_end_ms)]

        gaps = []

        # Sort effects by start time
        sorted_effects = sorted(effects, key=lambda e: e.start_ms)

        # Check for gap at section start
        first_effect_start = sorted_effects[0].start_ms
        if section_start_ms < first_effect_start:
            gaps.append(Gap(start_ms=section_start_ms, end_ms=first_effect_start))

        # Check for gaps between effects
        for i in range(len(sorted_effects) - 1):
            curr_end = sorted_effects[i].end_ms
            next_start = sorted_effects[i + 1].start_ms

            if curr_end < next_start:
                gaps.append(Gap(start_ms=curr_end, end_ms=next_start))

        # Check for gap at section end
        last_effect_end = sorted_effects[-1].end_ms
        if last_effect_end < section_end_ms:
            gaps.append(Gap(start_ms=last_effect_end, end_ms=section_end_ms))

        logger.debug(f"Detected {len(gaps)} gaps for section {section_start_ms}-{section_end_ms}ms")

        return gaps
