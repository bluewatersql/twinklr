"""Template Compiler (Orchestrator) for the moving head sequencer.

This module provides the top-level compilation function that orchestrates
all components to compile a complete template to IR segments.
"""

import logging

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.curves.models import CurvePoint, PointsCurve
from blinkb0t.core.sequencer.models.context import FixtureContext, TemplateCompileContext
from blinkb0t.core.sequencer.models.enum import ChannelName, ChaseOrder
from blinkb0t.core.sequencer.models.template import (
    RemainderPolicy,
    Template,
    TemplatePreset,
    TemplateStep,
)
from blinkb0t.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
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
from blinkb0t.core.sequencer.moving_heads.utils import resolve_semantic_group
from blinkb0t.core.utils.logging import get_renderer_logger, log_performance

logger = logging.getLogger(__name__)
renderer_log = get_renderer_logger()


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


@log_performance
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
    5. Clip segments to boundaries for TRUNCATE/FADE_OUT policies

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
    renderer_log.debug(f"Template: {template.template_id}")
    provenance: list[str] = [f"template:{template.template_id}"]

    # Apply preset if provided
    working_template = template

    if preset:
        renderer_log.debug(f"Applying preset: {preset.preset_id}")
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
        renderer_log.debug(f"Step: {instance.step_id}")
        step = step_map[instance.step_id]

        # Filter fixtures based on step's target semantic group
        target_roles = resolve_semantic_group(step.target, template.roles)

        if not target_roles:
            # If group not defined in template, default to all fixtures
            target_fixtures = list(context.fixtures)
        else:
            # Filter fixtures by role membership in target group
            target_fixtures = [f for f in context.fixtures if f.role in target_roles]

        renderer_log.debug(f"Target group: {step.target}")
        renderer_log.debug(f"# of Target fixtures: {len(target_fixtures)}")

        if not target_fixtures:
            # No fixtures for this group, skip
            continue

        # Order fixtures according to ChaseOrder for phase offsets
        phase_config = step.timing.phase_offset
        ordered_fixtures = _order_fixtures_for_chase(
            target_fixtures, phase_config.order if phase_config else ChaseOrder.LEFT_TO_RIGHT
        )
        fixture_ids = [f.fixture_id for f in ordered_fixtures]

        renderer_log.debug(f"Fixture IDs (Ordered for phase offsets): {fixture_ids}")

        if phase_config:
            phase_offsets = calculate_fixture_offsets(phase_config, fixture_ids)
        else:
            phase_offsets = PhaseOffsetResult(offsets=dict.fromkeys(fixture_ids, 0.0))

        # Calculate timing in milliseconds
        start_ms = context.start_ms + int(instance.start_bars * context.ms_per_bar)
        duration_ms = int(instance.duration_bars * context.ms_per_bar)
        renderer_log.debug(f"Section Timing (ms): {start_ms} - {duration_ms}")

        # Check if this step uses phase offsets
        # If yes, mark all segments as non-groupable (even those with offset=0)
        uses_phase_offsets = phase_config is not None and phase_config.spread_bars > 0
        renderer_log.debug(f"Uses phase offsets: {uses_phase_offsets}")

        # Compile for each target fixture (use original list, not ordered)
        for fixture in target_fixtures:
            # Get phase offset for this fixture
            offset_bars = phase_offsets.offsets.get(fixture.fixture_id, 0.0)
            step_duration = step.timing.base_timing.duration_bars
            phase_offset_norm = offset_bars / step_duration if step_duration > 0 else 0.0
            if phase_offsets.wrap:
                phase_offset_norm = phase_offset_norm % 1.0

            renderer_log.debug(
                f"Fixture {fixture.fixture_id} Offset: {offset_bars} - Phase offset norm: {phase_offset_norm} - Wrap: {phase_offsets.wrap}"
            )

            section_segment = context.section_id.split("|")
            section_id = section_segment[0]
            segment_id = section_segment[1] if len(section_segment) > 1 else "A"

            # Build step compile context
            step_context = StepCompileContext(
                section_id=section_id,
                segment_id=segment_id,
                template_id=context.template_id,
                preset_id=context.preset_id,
                fixture_id=fixture.fixture_id,
                role=fixture.role,
                calibration=fixture.calibration,
                start_ms=start_ms,
                duration_ms=duration_ms,
                n_samples=context.n_samples,
                beat_grid=context.beat_grid,  # Added for period_bars → cycles conversion
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

            # Add segments
            all_segments.append(step_result.segment)

    # Clip segments to section boundary for TRUNCATE/FADE_OUT policies
    if schedule_result.remainder_policy in (RemainderPolicy.TRUNCATE, RemainderPolicy.FADE_OUT):
        section_end_ms = context.start_ms + int(context.duration_bars * context.ms_per_bar)
        all_segments = _clip_segments_to_boundary(
            all_segments,
            section_end_ms,
            fade_out=(schedule_result.remainder_policy == RemainderPolicy.FADE_OUT),
        )

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


def _clip_segments_to_boundary(
    segments: list[FixtureSegment],
    boundary_ms: int,
    fade_out: bool = False,
) -> list[FixtureSegment]:
    """Clip segments to a time boundary for TRUNCATE/FADE_OUT remainder policies.

    For TRUNCATE: Hard clip all segments at boundary_ms
    For FADE_OUT: Clip segments and apply fade to dimmer channel in clipped region

    Args:
        segments: List of fixture segments to clip
        boundary_ms: Time boundary in milliseconds (section end)
        fade_out: If True, apply fade-out to dimmer channel

    Returns:
        List of clipped segments (some may be removed entirely if beyond boundary)
    """
    clipped_segments: list[FixtureSegment] = []

    for segment in segments:
        # Segment entirely before boundary - keep as-is
        if segment.t1_ms <= boundary_ms:
            clipped_segments.append(segment)
            continue

        # Segment entirely after boundary - discard
        if segment.t0_ms >= boundary_ms:
            continue

        # Segment crosses boundary - clip it
        # Calculate what fraction of the segment to keep
        original_duration = segment.t1_ms - segment.t0_ms
        clipped_duration = boundary_ms - segment.t0_ms
        keep_fraction = clipped_duration / original_duration if original_duration > 0 else 1.0

        # Clip curves for each channel
        clipped_channels: dict[ChannelName, ChannelValue] = {}

        for channel_name, channel_value in segment.channels.items():
            # If channel has a curve, clip it
            if channel_value.curve and channel_value.value_points:
                clipped_points = _clip_curve_points(channel_value.value_points, keep_fraction)

                # For FADE_OUT on dimmer channel, apply fade
                if fade_out and channel_name.value == "DIMMER":
                    clipped_points = _apply_fade_out(clipped_points)

                clipped_channels[channel_name] = ChannelValue(
                    channel=channel_name,
                    curve=PointsCurve(points=clipped_points),
                    value_points=clipped_points,
                    static_dmx=None,
                    offset_centered=channel_value.offset_centered,
                    base_dmx=channel_value.base_dmx,
                    amplitude_dmx=channel_value.amplitude_dmx,
                    clamp_min=channel_value.clamp_min,
                    clamp_max=channel_value.clamp_max,
                )
            else:
                # Static value - keep as-is
                clipped_channels[channel_name] = channel_value

        # Create clipped segment
        clipped_segment = FixtureSegment(
            section_id=segment.section_id,
            segment_id=segment.segment_id,
            step_id=segment.step_id,
            template_id=segment.template_id,
            preset_id=segment.preset_id,
            fixture_id=segment.fixture_id,
            t0_ms=segment.t0_ms,
            t1_ms=boundary_ms,  # Clip end time
            channels=clipped_channels,
            allow_grouping=segment.allow_grouping,
        )

        clipped_segments.append(clipped_segment)

    return clipped_segments


def _clip_curve_points(points: list[CurvePoint], keep_fraction: float) -> list[CurvePoint]:
    """Clip curve points to a fraction of the original duration.

    Args:
        points: Original curve points (t in [0, 1])
        keep_fraction: Fraction of curve to keep (0.0 to 1.0)

    Returns:
        Clipped curve points with t values rescaled to [0, 1]
    """
    if keep_fraction >= 1.0:
        return points

    # Find points within the keep fraction
    clipped: list[CurvePoint] = []

    for point in points:
        if point.t <= keep_fraction:
            # Rescale t to [0, 1] over the clipped duration
            new_t = point.t / keep_fraction if keep_fraction > 0 else 0.0
            clipped.append(CurvePoint(t=new_t, v=point.v))
        else:
            # Interpolate the final point at exactly keep_fraction
            if clipped and point.t > keep_fraction:
                # Find the previous point
                prev_point = clipped[-1]
                # Linear interpolation to get value at keep_fraction
                t_range = point.t - prev_point.t * keep_fraction
                if t_range > 0:
                    alpha = (keep_fraction - prev_point.t * keep_fraction) / t_range
                    interpolated_v = prev_point.v + alpha * (point.v - prev_point.v)
                    clipped.append(CurvePoint(t=1.0, v=interpolated_v))
                break

    # Ensure we have at least 2 points for a valid curve
    if len(clipped) < 2 and points:
        # Add final point at t=1.0 with last value
        if clipped:
            clipped.append(CurvePoint(t=1.0, v=clipped[-1].v))
        else:
            # Use first point of original curve
            clipped = [CurvePoint(t=0.0, v=points[0].v), CurvePoint(t=1.0, v=points[0].v)]

    return clipped


def _apply_fade_out(points: list[CurvePoint]) -> list[CurvePoint]:
    """Apply a linear fade-out to curve points.

    Multiplies the value by (1 - t) to create a fade to zero.

    Args:
        points: Original curve points

    Returns:
        Curve points with fade-out applied
    """
    faded: list[CurvePoint] = []

    for point in points:
        # Fade multiplier: 1.0 at t=0, 0.0 at t=1.0
        fade_multiplier = 1.0 - point.t
        faded_value = point.v * fade_multiplier
        faded.append(CurvePoint(t=point.t, v=faded_value))

    return faded
