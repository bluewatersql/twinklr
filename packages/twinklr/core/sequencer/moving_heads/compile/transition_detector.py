"""Transition boundary detection for the moving head sequencer.

This module detects boundaries between choreography-plan sections.
"""

from __future__ import annotations

import logging

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.sequencer.models.transition import Boundary, BoundaryType
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

logger = logging.getLogger(__name__)


class TransitionDetector:
    """Detects boundaries where transitions may occur.

    Identifies points in time where transitions can be applied:
    - Section boundaries: between choreography plan sections
    """

    def detect_section_boundaries(
        self, plan: ChoreographyPlan, beat_grid: BeatGrid
    ) -> list[Boundary]:
        """Detect boundaries between sections in choreography plan.

        Args:
            plan: Choreography plan to analyze.
            beat_grid: Beat grid for time conversion.

        Returns:
            List of boundaries between consecutive sections.

        Example:
            >>> plan = ChoreographyPlan(sections=[
            ...     PlanSection(start_bar=1, end_bar=8, section_name="intro"),
            ...     PlanSection(start_bar=9, end_bar=16, section_name="verse"),
            ... ])
            >>> detector = TransitionDetector()
            >>> boundaries = detector.detect_section_boundaries(plan, beat_grid)
            >>> len(boundaries)
            1
            >>> boundaries[0].source_id
            'intro'
            >>> boundaries[0].target_id
            'verse'
        """
        boundaries: list[Boundary] = []

        # Iterate through consecutive section pairs
        for i in range(len(plan.sections) - 1):
            source_section = plan.sections[i]
            target_section = plan.sections[i + 1]

            # Boundary is at the end of source section (start of target section)
            # Use target section's start_bar as the boundary position
            boundary_bar = float(target_section.start_bar)

            # Convert bar position to milliseconds through the beat grid's detected
            # downbeats — the same conversion the compile context uses, so boundaries
            # land on the section starts they separate.
            boundary_ms = int(beat_grid.get_bar_start_ms(boundary_bar - 1.0))

            boundary = Boundary(
                type=BoundaryType.SECTION_BOUNDARY,
                source_id=source_section.section_name,
                target_id=target_section.section_name,
                time_ms=boundary_ms,
                bar_position=boundary_bar,
            )

            boundaries.append(boundary)
            logger.debug(
                f"Detected section boundary: {source_section.section_name} → "
                f"{target_section.section_name} at bar {boundary_bar} ({boundary_ms}ms)"
            )

        logger.debug(f"Detected {len(boundaries)} section boundaries")
        return boundaries
