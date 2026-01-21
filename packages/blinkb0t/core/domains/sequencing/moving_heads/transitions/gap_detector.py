"""
Gap detection for transition rendering.

This module provides the GapDetector class which identifies all gaps in a
timeline, including:
- Sequence START: 0ms → first effect
- Sequence END: last effect → song duration
- Inter-section: gaps between sections
- Explicit: gaps created by TemplateTimePlanner for transitions

The detector extracts anchor positions from adjacent effects to enable
smooth transition rendering in Phase 2.

Example:
    >>> detector = GapDetector()
    >>> gaps = detector.detect_all_gaps(timeline, song_duration_ms=180000.0)
    >>> # Returns list of all gaps with anchors, sorted by time
"""

from __future__ import annotations

import logging

from blinkb0t.core.domains.sequencing.models.transitions import (
    GapType,
    Timeline,
    TimelineEffect,
    TimelineGap,
)

logger = logging.getLogger(__name__)


class GapDetector:
    """
    Detects all gaps in a timeline for transition rendering.

    This detector identifies both explicit gaps (created by TemplateTimePlanner)
    and implicit gaps (sequence start/end, section boundaries). It extracts
    anchor positions from adjacent effects to enable smooth transitions.

    Gap Types:
        - START: 0ms → first effect (implicit)
        - MID_SEQUENCE: Between effects (explicit from planner)
        - INTER_SECTION: Between sections (implicit)
        - END: Last effect → song duration (implicit)

    Methods:
        detect_all_gaps: Find all gaps in timeline with anchors

    Example:
        >>> detector = GapDetector()
        >>> timeline = [effect1, gap, effect2]
        >>> gaps = detector.detect_all_gaps(timeline, 180000.0)
        >>> # Returns: [START_gap, explicit_gap, END_gap]
    """

    def __init__(self, min_gap_ms: float = 100.0):
        """Initialize gap detector.

        Args:
            min_gap_ms: Minimum gap duration to detect (default: 100ms).
                       Gaps smaller than this are ignored (likely artifacts from per_fixture_offsets).
        """
        self.min_gap_ms = min_gap_ms
        logger.debug(f"GapDetector initialized with min_gap_ms={min_gap_ms}ms")

    def detect_all_gaps(self, timeline: Timeline, song_duration_ms: float) -> list[TimelineGap]:
        """
        Find all gaps in timeline.

        Algorithm:
        1. Extract explicit gaps from timeline
        2. Extract effects from timeline
        3. Check sequence start (0 → first effect)
        4. Check sequence end (last effect → song_duration_ms)
        5. Sort by start time

        Args:
            timeline: Timeline with effects and gaps
            song_duration_ms: Total song duration in milliseconds

        Returns:
            Complete list of gaps with types and anchors, sorted by time

        Example:
            >>> gaps = detector.detect_all_gaps(timeline, 180000.0)
            >>> for gap in gaps:
            ...     print(f"{gap.gap_type}: {gap.start_ms}-{gap.end_ms}ms")
        """
        gaps: list[TimelineGap] = []

        # Extract effects and explicit gaps
        effects = [item for item in timeline if isinstance(item, TimelineEffect)]
        explicit_gaps = [item for item in timeline if isinstance(item, TimelineGap)]

        # Handle empty timeline
        if not effects:
            # Create single gap covering entire song
            gaps.append(
                TimelineGap(
                    start_ms=0.0,
                    end_ms=song_duration_ms,
                    gap_type=GapType.START,
                    fixture_id="",  # No fixture ID available
                    from_position=None,
                    to_position=None,
                )
            )
            return gaps

        # Sort effects by time
        effects_sorted = sorted(effects, key=lambda e: e.start_ms)

        # Determine fixture ID (use first effect's fixture)
        fixture_id = effects_sorted[0].fixture_id if effects_sorted else ""

        # Check sequence START gap (0 → first effect)
        first_effect = effects_sorted[0]
        if first_effect.start_ms > 0:
            gaps.append(
                TimelineGap(
                    start_ms=0.0,
                    end_ms=first_effect.start_ms,
                    gap_type=GapType.START,
                    fixture_id=fixture_id,
                    from_position=None,  # No previous effect
                    to_position=(first_effect.pan_start, first_effect.tilt_start),
                )
            )

        # Add explicit gaps from timeline
        gaps.extend(explicit_gaps)

        # Check for implicit gaps BETWEEN effects (not already covered by explicit gaps)
        for i in range(len(effects_sorted) - 1):
            current_effect = effects_sorted[i]
            next_effect = effects_sorted[i + 1]

            # Check if there's a gap between this effect and the next
            if current_effect.end_ms < next_effect.start_ms:
                # Check if this gap is already covered by an explicit gap
                gap_start = current_effect.end_ms
                gap_end = next_effect.start_ms
                gap_duration = gap_end - gap_start

                # BUG FIX #1: Ignore tiny gaps (artifacts from per_fixture_offsets)
                # When fixtures have staggered timing from different sections/offsets,
                # tiny gaps appear that shouldn't be filled
                if gap_duration < self.min_gap_ms:
                    logger.debug(
                        f"Skipping tiny gap {gap_start:.1f}-{gap_end:.1f}ms "
                        f"(duration {gap_duration:.1f}ms < threshold {self.min_gap_ms}ms)"
                    )
                    continue

                is_covered = any(
                    g.start_ms <= gap_start and g.end_ms >= gap_end for g in explicit_gaps
                )

                if not is_covered:
                    # Create implicit mid-sequence gap
                    logger.debug(
                        f"Detected gap {gap_start:.1f}-{gap_end:.1f}ms "
                        f"(duration {gap_duration:.1f}ms)"
                    )
                    gaps.append(
                        TimelineGap(
                            start_ms=gap_start,
                            end_ms=gap_end,
                            gap_type=GapType.MID_SEQUENCE,
                            fixture_id=fixture_id,
                            from_position=(current_effect.pan_end, current_effect.tilt_end),
                            to_position=(next_effect.pan_start, next_effect.tilt_start),
                        )
                    )
                    logger.debug(
                        f"Detected implicit gap between effects {i} and {i + 1}: "
                        f"{gap_start:.0f}-{gap_end:.0f}ms ({gap_end - gap_start:.0f}ms)"
                    )

        # Check sequence END gap (last effect → song_duration_ms)
        last_effect = effects_sorted[-1]
        if last_effect.end_ms < song_duration_ms:
            gaps.append(
                TimelineGap(
                    start_ms=last_effect.end_ms,
                    end_ms=song_duration_ms,
                    gap_type=GapType.END,
                    fixture_id=fixture_id,
                    from_position=(last_effect.pan_end, last_effect.tilt_end),
                    to_position=None,  # No next effect
                )
            )

        # Sort gaps by start time
        gaps_sorted = sorted(gaps, key=lambda g: g.start_ms)

        logger.debug(
            f"Detected {len(gaps_sorted)} gaps: "
            f"{sum(1 for g in gaps_sorted if g.gap_type == GapType.START)} START, "
            f"{sum(1 for g in gaps_sorted if g.gap_type == GapType.MID_SEQUENCE)} MID, "
            f"{sum(1 for g in gaps_sorted if g.gap_type == GapType.END)} END"
        )

        return gaps_sorted
