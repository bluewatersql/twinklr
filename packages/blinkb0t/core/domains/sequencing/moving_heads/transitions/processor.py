"""
Transition processing orchestrator.

This module provides the TransitionProcessor class which orchestrates Phase 2
(Temporal Rendering) of the transitions and gap filling system:

1. Detect all gaps (GapDetector)
2. Resolve transition type (TransitionResolver)
3. Snap timing to boundaries
4. Render transitions (TransitionRenderer)
5. Merge with main effects
6. Sort by time

The processor is the main entry point for Phase 2, coordinating all components
to fill gaps with appropriate transitions and holds.

Example:
    >>> processor = TransitionProcessor(gap_detector, resolver, renderer)
    >>> effects = processor.process(timeline, song_duration_ms, fixtures)
    >>> # Returns complete list of effects (main + transitions)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement
from blinkb0t.core.domains.sequencing.models.transitions import (
    Timeline,
    TimelineEffect,
)

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureGroup
    from blinkb0t.core.domains.sequencing.moving_heads.transitions.gap_detector import (
        GapDetector,
    )
    from blinkb0t.core.domains.sequencing.moving_heads.transitions.renderer import (
        TransitionRenderer,
    )
    from blinkb0t.core.domains.sequencing.moving_heads.transitions.resolver import (
        TransitionResolver,
    )

logger = logging.getLogger(__name__)


class TransitionProcessor:
    """
    Phase 2 orchestrator: Fills all gaps with transitions/holds.

    This processor coordinates the complete Phase 2 workflow:
    1. Detect gaps (GapDetector)
    2. Resolve transition type (TransitionResolver)
    3. Snap timing to boundaries
    4. Render effects (TransitionRenderer + handlers)
    5. Merge effects with original timeline
    6. Sort by time

    Attributes:
        gap_detector: Detects all gaps in timeline
        resolver: Resolves transition type by priority
        transition_renderer: Renders transition effects

    Methods:
        process: Fill all gaps and return complete effects list

    Example:
        >>> processor = TransitionProcessor(detector, resolver, renderer)
        >>> timeline = [effect1, gap, effect2]
        >>> effects = processor.process(timeline, 180000.0, fixtures)
        >>> # Returns: [effect1, transition_effect, effect2] sorted by time
    """

    def __init__(
        self,
        gap_detector: GapDetector,
        resolver: TransitionResolver,
        transition_renderer: TransitionRenderer,
    ):
        """
        Initialize processor with dependencies.

        Args:
            gap_detector: GapDetector instance
            resolver: TransitionResolver instance
            transition_renderer: TransitionRenderer instance
        """
        self.gap_detector = gap_detector
        self.resolver = resolver
        self.transition_renderer = transition_renderer

    def process(
        self,
        timeline: Timeline,
        song_duration_ms: float,
        fixtures: FixtureGroup,
    ) -> list[EffectPlacement]:
        """
        Fill all gaps with transitions/holds.

        Algorithm:
        1. Detect all gaps (GapDetector)
        2. For each gap:
           a. Resolve transition type (TransitionResolver)
           b. Get transition config
           c. Snap timing to boundaries
           d. Render transition effects (TransitionRenderer)
        3. Merge transition effects with main effects
        4. Sort by time

        Args:
            timeline: Timeline with effects and explicit gaps
            song_duration_ms: Total song duration in milliseconds
            fixtures: FixtureGroup for rendering

        Returns:
            Complete list of EffectPlacement objects (main + transitions), sorted by time

        Example:
            >>> effects = processor.process(timeline, 180000.0, fixtures)
            >>> for effect in effects:
            ...     print(f"{effect.start_ms}-{effect.end_ms}ms")
        """
        # Step 1: Detect all gaps
        gaps = self.gap_detector.detect_all_gaps(timeline, song_duration_ms)

        logger.debug(f"Processing {len(gaps)} gaps")

        # Step 2: Render transitions for each gap
        transition_effects: list[EffectPlacement] = []

        for gap in gaps:
            # Resolve transition type (always use gap_fill for now)
            handler_name = "gap_fill"

            # Render the gap using anchor positions
            logger.debug(
                f"Rendering gap: {gap.start_ms:.0f}-{gap.end_ms:.0f}ms "
                f"({gap.gap_type}), from={gap.from_position}, to={gap.to_position}"
            )

            effects = self.transition_renderer.render_gap(
                mode_str=handler_name,
                start_ms=gap.start_ms,
                end_ms=gap.end_ms,
                from_position=gap.from_position,
                to_position=gap.to_position,
                fixture_id=gap.fixture_id,
                curve="ease_in_out_sine",
            )

            transition_effects.extend(effects)
            logger.debug(f"Generated {len(effects)} effects for gap")

        # Step 3: Merge with main effects
        main_effects = [item.effect for item in timeline if isinstance(item, TimelineEffect)]
        all_effects = main_effects + transition_effects

        # Step 4: Sort by time
        sorted_effects = sorted(all_effects, key=lambda e: e.start_ms)

        logger.info(
            f"Processed timeline: {len(main_effects)} main effects + "
            f"{len(transition_effects)} transition effects = "
            f"{len(sorted_effects)} total"
        )

        return sorted_effects

    def _snap_timing(
        self,
        gap_start_ms: float,
        gap_end_ms: float,
        transition_duration_ms: float,
    ) -> tuple[float, float]:
        """
        Snap transition timing to gap boundaries.

        Strategy:
        1. Round to nearest millisecond
        2. If gap < 10ms, expand to fill completely
        3. Clamp transition duration to available space
        4. Center transition if extra space available (padding > 5ms)
        5. Otherwise fill the gap

        Args:
            gap_start_ms: Gap start time
            gap_end_ms: Gap end time
            transition_duration_ms: Desired transition duration

        Returns:
            (actual_start_ms, actual_end_ms) tuple

        Example:
            >>> # Small gap - fill completely
            >>> start, end = processor._snap_timing(1000.0, 1005.0, 500.0)
            >>> assert start == 1000.0 and end == 1005.0

            >>> # Large gap - center transition
            >>> start, end = processor._snap_timing(1000.0, 2000.0, 200.0)
            >>> assert start == 1400.0 and end == 1600.0  # Centered
        """
        # Round to milliseconds
        start_ms = round(gap_start_ms, 0)
        end_ms = round(gap_end_ms, 0)
        available_ms = end_ms - start_ms

        # Handle micro-gaps (< 10ms)
        if available_ms < 10:
            logger.debug(f"Micro-gap ({available_ms}ms), filling completely")
            return (start_ms, end_ms)

        # Clamp transition duration to available space
        actual_duration = min(transition_duration_ms, available_ms)

        # Calculate padding
        padding = (available_ms - actual_duration) / 2

        # If padding is very small (< 5ms), just fill the gap
        if padding < 5:
            logger.debug(f"Small padding ({padding}ms), filling gap completely")
            return (start_ms, end_ms)

        # Center the transition
        logger.debug(f"Centering transition: {actual_duration}ms in {available_ms}ms gap")
        return (
            start_ms + padding,
            end_ms - padding,
        )
