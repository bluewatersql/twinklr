"""Transition boundary detection for the moving head sequencer.

This module provides functionality to detect boundaries where transitions
may occur between sections and steps.
"""

from __future__ import annotations

import logging

from blinkb0t.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from blinkb0t.core.sequencer.models.context import TemplateCompileContext
from blinkb0t.core.sequencer.models.template import Template
from blinkb0t.core.sequencer.models.transition import Boundary, BoundaryType
from blinkb0t.core.sequencer.moving_heads.compile.scheduler import ScheduleResult
from blinkb0t.core.sequencer.timing.beat_grid import BeatGrid

logger = logging.getLogger(__name__)


class TransitionDetector:
    """Detects boundaries where transitions may occur.

    Identifies points in time where transitions can be applied:
    - Section boundaries: between choreography plan sections
    - Step boundaries: between template steps
    - Cycle boundaries: between repeat cycles (future)
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

            # Convert bar position to milliseconds
            # Bars are 1-indexed, so bar N starts at (N-1) * ms_per_bar
            boundary_ms = int((boundary_bar - 1.0) * beat_grid.ms_per_bar)

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

    def detect_step_boundaries(
        self,
        template: Template,
        schedule_result: ScheduleResult,
        context: TemplateCompileContext,
    ) -> list[Boundary]:
        """Detect boundaries between steps within a template.

        Args:
            template: Template to analyze.
            schedule_result: Scheduled step instances.
            context: Template compilation context.

        Returns:
            List of boundaries between consecutive step instances.

        Example:
            >>> template = Template(
            ...     steps=[
            ...         TemplateStep(step_id="intro", ...),
            ...         TemplateStep(step_id="main", ...),
            ...     ]
            ... )
            >>> detector = TransitionDetector()
            >>> boundaries = detector.detect_step_boundaries(
            ...     template, schedule_result, context
            ... )
        """
        boundaries: list[Boundary] = []

        # Iterate through consecutive step instances
        instances = schedule_result.instances
        for i in range(len(instances) - 1):
            source_instance = instances[i]
            target_instance = instances[i + 1]

            # Boundary is at the end of source step (start of target step)
            # Calculate absolute boundary position
            boundary_bar = source_instance.start_bars + source_instance.duration_bars
            boundary_ms = context.start_ms + int(boundary_bar * context.ms_per_bar)

            boundary = Boundary(
                type=BoundaryType.STEP_BOUNDARY,
                source_id=f"{context.section_id}:{source_instance.step_id}",
                target_id=f"{context.section_id}:{target_instance.step_id}",
                time_ms=boundary_ms,
                bar_position=boundary_bar,
            )

            boundaries.append(boundary)
            logger.debug(
                f"Detected step boundary: {source_instance.step_id} → "
                f"{target_instance.step_id} at bar {boundary_bar:.2f} ({boundary_ms}ms)"
            )

        logger.debug(
            f"Detected {len(boundaries)} step boundaries in template {template.template_id}"
        )
        return boundaries

    def detect_cycle_boundaries(
        self,
        template: Template,
        schedule_result: ScheduleResult,
        context: TemplateCompileContext,
    ) -> list[Boundary]:
        """Detect boundaries between repeat cycles within a template.

        This is a placeholder for future cycle transition support.

        Args:
            template: Template to analyze.
            schedule_result: Scheduled step instances.
            context: Template compilation context.

        Returns:
            List of boundaries between repeat cycles (currently empty).
        """
        # TODO: Implement cycle boundary detection when cycle transitions are supported
        logger.debug("Cycle boundary detection not yet implemented")
        return []
