"""Template Compiler (Orchestrator) for the moving head sequencer.

This module provides the top-level compilation function that orchestrates
all components to compile a complete template to IR segments.
"""

import logging

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.sequencer.models.context import FixtureContext, TemplateCompileContext
from blinkb0t.core.sequencer.models.enum import ChaseOrder
from blinkb0t.core.sequencer.models.template import (
    Template,
    TemplatePreset,
    TemplateStep,
)
from blinkb0t.core.sequencer.moving_heads.channels.state import FixtureSegment
from blinkb0t.core.sequencer.moving_heads.compile.phase_offset import (
    PhaseOffsetResult,
    calculate_fixture_offsets,
)
from blinkb0t.core.sequencer.moving_heads.compile.preset import apply_preset
from blinkb0t.core.sequencer.moving_heads.compile.scheduler import schedule_repeats
from blinkb0t.core.sequencer.moving_heads.compile.step_compiler import (
    StepCompileContext,
    compile_step,
)

logger = logging.getLogger(__name__)
renderer_log = logging.getLogger("DMX_MH_RENDER")


class TemplateCompileResult(BaseModel):
    """Result of compiling a template.

    Contains all compiled IR segments and metadata.

    Attributes:
        template_id: The template that was compiled.
        segments: All compiled channel segments.
        num_complete_cycles: Number of complete repeat cycles.
        provenance: Provenance tracking list.
    """

    model_config = ConfigDict(extra="forbid")

    template_id: str
    segments: list[FixtureSegment] = Field(default_factory=list)
    num_complete_cycles: int = Field(default=0)
    provenance: list[str] = Field(default_factory=list)

    def segments_by_fixture(self, fixture_id: str) -> list[FixtureSegment]:
        """Get segments for a specific fixture."""
        return [seg for seg in self.segments if seg.fixture_id == fixture_id]


def compile_template(
    template: Template,
    context: TemplateCompileContext,
    preset: TemplatePreset | None = None,
) -> TemplateCompileResult:
    """Compile a template to IR segments.

    Orchestrates all compilation steps:
    1. Apply preset if provided
    2. Schedule repeat cycles
    3. Calculate phase offsets
    4. Compile each step for each fixture

    Args:
        template: The template to compile.
        context: Compilation context.
        preset: Optional preset to apply.

    Returns:
        TemplateCompileResult with all compiled segments.

    Example:
        >>> template = Template(...)
        >>> context = TemplateCompileContext(...)
        >>> result = compile_template(template, context)
    """
    # Initialize provenance
    renderer_log.info(f"Template: {template.template_id}")
    provenance: list[str] = [f"template:{template.template_id}"]

    # Apply preset if provided
    working_template = template

    if preset:
        renderer_log.info(f"Applying preset: {preset.preset_id}")
        working_template = apply_preset(template, preset)
        provenance.append(f"preset:{preset.preset_id}")

    # Build step duration map
    step_durations: dict[str, float] = {}
    step_map: dict[str, TemplateStep] = {}
    for step in working_template.steps:
        step_durations[step.step_id] = step.timing.base_timing.duration_bars
        step_map[step.step_id] = step

    # Schedule repeats
    schedule_result = schedule_repeats(
        working_template.repeat,
        context.duration_bars,
        step_durations=step_durations,
    )

    # Compile each scheduled instance for each fixture
    all_segments: list[FixtureSegment] = []

    for instance in schedule_result.instances:
        renderer_log.info(f"Step: {instance.step_id}")
        step = step_map[instance.step_id]

        # Filter fixtures based on step's target semantic group
        target_group = step.target
        target_roles = working_template.groups.get(target_group.value, [])

        if not target_roles:
            # If group not defined in template, default to all fixtures
            target_fixtures = list(context.fixtures)
        else:
            # Filter fixtures by role membership in target group
            target_fixtures = [f for f in context.fixtures if f.role in target_roles]

        renderer_log.info(f"Target group: {step.target}")
        renderer_log.info(f"Target roles: {working_template.groups.get(step.target.value, [])}")
        renderer_log.info(f"# of Target fixtures: {len(target_fixtures)}")

        if not target_fixtures:
            # No fixtures for this group, skip
            continue

        # Order fixtures according to ChaseOrder for phase offsets
        phase_config = step.timing.phase_offset
        ordered_fixtures = _order_fixtures_for_chase(
            target_fixtures, phase_config.order if phase_config else ChaseOrder.LEFT_TO_RIGHT
        )
        fixture_ids = [f.fixture_id for f in ordered_fixtures]

        renderer_log.info(f"Fixture IDs (Ordered for phase offsets): {fixture_ids}")

        if phase_config:
            phase_offsets = calculate_fixture_offsets(phase_config, fixture_ids)
        else:
            phase_offsets = PhaseOffsetResult(offsets=dict.fromkeys(fixture_ids, 0.0))

        # Calculate timing in milliseconds
        start_ms = context.start_ms + int(instance.start_bars * context.ms_per_bar)
        duration_ms = int(instance.duration_bars * context.ms_per_bar)
        renderer_log.info(f"Section Timing (ms): {start_ms} - {duration_ms}")

        # Check if this step uses phase offsets
        # If yes, mark all segments as non-groupable (even those with offset=0)
        uses_phase_offsets = phase_config is not None and phase_config.spread_bars > 0
        renderer_log.info(f"Uses phase offsets: {uses_phase_offsets}")

        # Compile for each target fixture (use original list, not ordered)
        for fixture in target_fixtures:
            # Get phase offset for this fixture
            offset_bars = phase_offsets.offsets.get(fixture.fixture_id, 0.0)
            step_duration = step.timing.base_timing.duration_bars
            phase_offset_norm = offset_bars / step_duration if step_duration > 0 else 0.0
            if phase_offsets.wrap:
                phase_offset_norm = phase_offset_norm % 1.0

            renderer_log.info(
                f"Fixture {fixture.fixture_id} Offset: {offset_bars} - Phase offset norm: {phase_offset_norm} - Wrap: {phase_offsets.wrap}"
            )

            # Build step compile context
            step_context = StepCompileContext(
                section_id=context.section_id,
                template_id=context.template_id,
                preset_id=context.preset_id,
                fixture_id=fixture.fixture_id,
                role=fixture.role,
                calibration=fixture.calibration,
                start_ms=start_ms,
                duration_ms=duration_ms,
                n_samples=context.n_samples,
                curve_registry=context.curve_registry,
                geometry_registry=context.geometry_registry,
                movement_registry=context.movement_registry,
                dimmer_registry=context.dimmer_registry,
            )

            # Compile the step
            step_result = compile_step(step, step_context, phase_offset_norm)

            # Mark segment as non-groupable if template uses phase offsets
            if uses_phase_offsets:
                step_result.segment.allow_grouping = False

            # TODO: Handle TRUNCATE repeat policy
            # TODO: Need to apply time clipping to boundaries to handle section boundaries and truncate repeat policy
            # - See _clip_segments_to_window from demo compiler

            # Add segments
            all_segments.append(step_result.segment)

    return TemplateCompileResult(
        template_id=working_template.template_id,
        segments=all_segments,
        num_complete_cycles=schedule_result.num_complete_cycles,
        provenance=provenance,
    )


def _order_fixtures_for_chase(
    fixtures: list[FixtureContext],
    order: ChaseOrder,
) -> list[FixtureContext]:
    """Order fixtures according to ChaseOrder.

    Args:
        fixtures: List of fixtures to order.
        order: Chase order to apply.

    Returns:
        Ordered list of fixtures.
    """
    # Role ordering for common patterns
    ROLE_ORDER_LR = [
        "FAR_LEFT",
        "OUTER_LEFT",
        "MID_LEFT",
        "INNER_LEFT",
        "CENTER_LEFT",
        "CENTER",
        "CENTER_RIGHT",
        "INNER_RIGHT",
        "MID_RIGHT",
        "OUTER_RIGHT",
        "FAR_RIGHT",
    ]

    if order == ChaseOrder.LEFT_TO_RIGHT:
        # Order by role position (left to right)
        return sorted(
            fixtures, key=lambda f: ROLE_ORDER_LR.index(f.role) if f.role in ROLE_ORDER_LR else 999
        )

    elif order == ChaseOrder.RIGHT_TO_LEFT:
        # Reverse of left to right
        return sorted(
            fixtures,
            key=lambda f: ROLE_ORDER_LR.index(f.role) if f.role in ROLE_ORDER_LR else 999,
            reverse=True,
        )

    elif order == ChaseOrder.OUTSIDE_IN:
        # Start from edges, move to center
        center_idx = len(ROLE_ORDER_LR) // 2
        return sorted(
            fixtures,
            key=lambda f: abs(ROLE_ORDER_LR.index(f.role) - center_idx)
            if f.role in ROLE_ORDER_LR
            else 999,
            reverse=True,
        )

    elif order == ChaseOrder.INSIDE_OUT:
        # Start from center, move to edges
        center_idx = len(ROLE_ORDER_LR) // 2
        return sorted(
            fixtures,
            key=lambda f: abs(ROLE_ORDER_LR.index(f.role) - center_idx)
            if f.role in ROLE_ORDER_LR
            else 999,
        )

    elif order == ChaseOrder.ODD_EVEN:
        # Odd positions first, then even (by left-to-right index)
        ordered = sorted(
            fixtures, key=lambda f: ROLE_ORDER_LR.index(f.role) if f.role in ROLE_ORDER_LR else 999
        )
        odd = [f for i, f in enumerate(ordered) if i % 2 == 0]
        even = [f for i, f in enumerate(ordered) if i % 2 == 1]
        return odd + even

    else:
        # Default: maintain current order
        return list(fixtures)
