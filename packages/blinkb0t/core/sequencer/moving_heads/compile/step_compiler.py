"""Step Compiler for template compilation.

This module compiles a single TemplateStep into IR ChannelSegments
by invoking the appropriate handlers for geometry, movement, and dimmer.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict

from blinkb0t.core.curves.models import PointsCurve
from blinkb0t.core.curves.phase import apply_phase_shift_samples
from blinkb0t.core.sequencer.moving_heads.channels.state import FixtureSegment
from blinkb0t.core.sequencer.moving_heads.models.channel import ChannelName
from blinkb0t.core.sequencer.moving_heads.models.context import StepCompileContext
from blinkb0t.core.sequencer.moving_heads.models.template import TemplateStep


class StepCompileResult(BaseModel):
    """Result of compiling a step.

    Contains the compiled ChannelSegments for pan, tilt, and dimmer.

    Attributes:
        step_id: The step that was compiled.
        fixture_id: The fixture this result is for.
        pan_segment: Pan channel segment.
        tilt_segment: Tilt channel segment.
        dimmer_segment: Dimmer channel segment.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    step_id: str
    segment: FixtureSegment


def compile_step(
    step: TemplateStep,
    context: StepCompileContext,
    phase_offset_norm: float = 0.0,
) -> StepCompileResult:
    """Compile a template step to IR segments.

    Invokes geometry, movement, and dimmer handlers to generate
    ChannelSegments for each channel type.

    Args:
        step: The template step to compile.
        context: Compilation context with fixture info and registries.
        phase_offset_norm: Optional phase offset [0, 1] to apply to curves.

    Returns:
        StepCompileResult with pan, tilt, and dimmer segments.

    Example:
        >>> step = TemplateStep(...)
        >>> context = StepCompileContext(...)
        >>> result = compile_step(step, context)
        >>> result.pan_segment.channel
        ChannelName.PAN
    """
    # Get handlers
    geometry_handler = context.geometry_registry.get(step.geometry.geometry_id)
    movement_handler = context.movement_registry.get(step.movement.movement_id)
    dimmer_handler = context.dimmer_registry.get(step.dimmer.dimmer_id)

    # Build geometry params
    geometry_params: dict[str, Any] = dict(step.geometry.params)
    if step.geometry.pan_pose_by_role:
        geometry_params["pan_pose_by_role"] = step.geometry.pan_pose_by_role
    if step.geometry.tilt_pose:
        geometry_params["tilt_pose"] = step.geometry.tilt_pose
    if step.geometry.aim_zone:
        geometry_params["aim_zone"] = step.geometry.aim_zone

    # Resolve geometry (static base pose)
    geometry_result = geometry_handler.resolve(
        fixture_id=context.fixture_id,
        role=context.role,
        params=geometry_params,
        calibration=context.calibration,
    )

    # Generate movement curves
    movement_result = movement_handler.generate(
        params=step.movement.params,
        n_samples=context.n_samples,
        cycles=step.movement.cycles,
        intensity=step.movement.intensity,
    )

    # Generate dimmer curve
    dimmer_result = dimmer_handler.generate(
        params=step.dimmer.params,
        n_samples=context.n_samples,
        cycles=step.dimmer.cycles,
        intensity=step.dimmer.intensity,
        min_norm=step.dimmer.min_norm,
        max_norm=step.dimmer.max_norm,
    )

    # Apply phase offset if needed
    pan_points = movement_result.pan_curve
    tilt_points = movement_result.tilt_curve
    dimmer_points = dimmer_result.dimmer_curve

    if phase_offset_norm != 0.0:
        pan_points = apply_phase_shift_samples(
            pan_points, phase_offset_norm, context.n_samples, wrap=True
        )
        tilt_points = apply_phase_shift_samples(
            tilt_points, phase_offset_norm, context.n_samples, wrap=True
        )
        dimmer_points = apply_phase_shift_samples(
            dimmer_points, phase_offset_norm, context.n_samples, wrap=True
        )

    # Calculate timing
    t0_ms = context.start_ms
    t1_ms = context.start_ms + context.duration_ms

    # Convert normalized geometry to DMX base values (0-255)
    pan_base_dmx = int(geometry_result.pan_norm * 255)
    tilt_base_dmx = int(geometry_result.tilt_norm * 255)

    # Movement amplitude - use a reasonable default (about 1/4 of range)
    # This can be configured via movement params if needed
    movement_amplitude_dmx = 64

    segment = FixtureSegment(
        fixture_id=context.fixture_id,
        t0_ms=t0_ms,
        t1_ms=t1_ms,
    )

    # Build pan segment
    segment.add_channel(
        channel=ChannelName.PAN,
        curve=PointsCurve(points=pan_points),
        offset_centered=True,
        base_dmx=pan_base_dmx,
        amplitude_dmx=movement_amplitude_dmx,
    )

    # Build tilt segment
    segment.add_channel(
        channel=ChannelName.TILT,
        curve=PointsCurve(points=tilt_points),
        offset_centered=True,
        base_dmx=tilt_base_dmx,
        amplitude_dmx=movement_amplitude_dmx,
    )

    # Build dimmer segment (absolute, not offset-centered)
    segment.add_channel(
        channel=ChannelName.DIMMER,
        curve=PointsCurve(points=dimmer_points),
        offset_centered=False,
    )

    return StepCompileResult(
        step_id=step.step_id,
        segment=segment,
    )
