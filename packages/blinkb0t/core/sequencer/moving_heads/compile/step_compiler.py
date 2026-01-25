"""Step Compiler for template compilation.

This module compiles a single TemplateStep into IR ChannelSegments
by invoking the appropriate handlers for geometry, movement, and dimmer.
"""

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict

from blinkb0t.core.curves.models import PointsCurve
from blinkb0t.core.curves.phase import apply_phase_shift_samples
from blinkb0t.core.sequencer.models.context import StepCompileContext
from blinkb0t.core.sequencer.models.enum import ChannelName
from blinkb0t.core.sequencer.models.template import TemplateStep
from blinkb0t.core.sequencer.moving_heads.channels.state import FixtureSegment
from blinkb0t.core.utils.logging import get_renderer_logger, log_performance

logger = logging.getLogger(__name__)
renderer_log = get_renderer_logger()


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


@log_performance
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
    """
    # Calculate timing
    t0_ms = context.start_ms
    t1_ms = context.start_ms + context.duration_ms
    renderer_log.info(f"Timing: {t0_ms} - {t1_ms}")

    # Get handlers
    geometry_handler = context.geometry_registry.get(step.geometry.geometry_type.value)

    renderer_log.info(
        f"Geometry Handler for {step.geometry.geometry_type.value}: {geometry_handler.handler_id}"
    )

    # Build geometry params
    geometry_params: dict[str, Any] = dict(step.geometry.params)
    if step.geometry.pan_pose_by_role:
        geometry_params["pan_pose_by_role"] = step.geometry.pan_pose_by_role
    if step.geometry.tilt_pose:
        geometry_params["tilt_pose"] = step.geometry.tilt_pose
    if step.geometry.aim_zone:
        geometry_params["aim_zone"] = step.geometry.aim_zone

    # Resolve geometry
    geometry_result = geometry_handler.resolve(
        fixture_id=context.fixture_id,
        role=context.role,
        params=geometry_params,
        calibration=context.calibration,
    )

    base_pan_norm = geometry_result.pan_norm
    base_tilt_norm = geometry_result.tilt_norm
    renderer_log.info(f"Base Pose (normalized): {base_pan_norm}, {base_tilt_norm}")

    movement_params = dict(step.movement.params)
    movement_params["base_pan_norm"] = base_pan_norm
    movement_params["base_tilt_norm"] = base_tilt_norm
    movement_params["calibration"] = context.calibration
    movement_params["geometry"] = step.geometry.geometry_type

    movement_handler = context.movement_registry.get_with_params(
        step.movement.movement_type.value, movement_params
    )
    renderer_log.info(
        f"Movement Handler for {step.movement.movement_type.value}: {movement_handler.handler_id}"
    )

    # Generate movement curves (use the params dict that has movement_id injected)
    movement_result = movement_handler.generate(
        params=movement_params,
        n_samples=context.n_samples,
        cycles=step.movement.cycles,
        intensity=step.movement.intensity,
    )

    # Build dimmer segment (absolute, not offset-centered)
    dimmer_params = dict(step.dimmer.params)
    dimmer_params["calibration"] = context.calibration
    dimmer_handler = context.dimmer_registry.get_with_params(
        step.dimmer.dimmer_type.value, dimmer_params
    )

    # Generate dimmer curve (use the params dict that has dimmer_id injected)
    dimmer_result = dimmer_handler.generate(
        params=dimmer_params,
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
        # Phase Offsets are time-domain based only shifts curves, no impact on static DMX values
        if pan_points is not None:
            pan_points = apply_phase_shift_samples(
                pan_points, phase_offset_norm, context.n_samples, wrap=True
            )
        if tilt_points is not None:
            tilt_points = apply_phase_shift_samples(
                tilt_points, phase_offset_norm, context.n_samples, wrap=True
            )
        if dimmer_points is not None:
            dimmer_points = apply_phase_shift_samples(
                dimmer_points, phase_offset_norm, context.n_samples, wrap=True
            )

    segment = FixtureSegment(
        section_id=context.section_id,
        step_id=step.step_id,
        template_id=context.template_id,
        preset_id=context.preset_id,
        fixture_id=context.fixture_id,
        t0_ms=t0_ms,
        t1_ms=t1_ms,
    )

    # Geometry Metadata
    segment.add_metadata("geometry_handler", geometry_handler.handler_id)
    segment.add_metadata("geometry_params", geometry_params)
    segment.add_metadata("base_pan_norm", base_pan_norm)
    segment.add_metadata("base_tilt_norm", base_tilt_norm)

    # Movement Metadata
    segment.add_metadata("movement_handler", movement_handler.handler_id)
    segment.add_metadata("movement_params", movement_params)

    # Pan Metadata
    segment.add_metadata("pan_curve_type", str(movement_result.pan_curve_type))
    segment.add_metadata("pan_static_dmx", movement_result.pan_static_dmx)
    segment.add_metadata("base_pan_norm", base_pan_norm)

    # Tilt Metadata
    segment.add_metadata("tilt_curve_type", str(movement_result.tilt_curve_type))
    segment.add_metadata("tilt_static_dmx", movement_result.tilt_static_dmx)
    segment.add_metadata("base_tilt_norm", base_tilt_norm)

    # Dimmer Metadata
    segment.add_metadata("dimmer_handler", dimmer_handler.handler_id)
    segment.add_metadata("dimmer_params", dimmer_params)
    segment.add_metadata("dimmer_curve_type", str(dimmer_result.dimmer_curve_type))
    segment.add_metadata("dimmer_static_dmx", dimmer_result.dimmer_static_dmx)

    # Misc Metadata
    segment.add_metadata("start_ms", t0_ms)
    segment.add_metadata("end_ms", t1_ms)
    segment.add_metadata("phase_offset_norm", phase_offset_norm)

    # Build pan segment - scale [0,1] curve to DMX boundaries
    segment.add_channel(
        channel=ChannelName.PAN,
        curve=PointsCurve(points=pan_points) if pan_points is not None else None,
        static_dmx=movement_result.pan_static_dmx,
        value_points=pan_points,
        offset_centered=False,
    )

    # Build tilt segment - scale [0,1] curve to DMX boundaries
    if movement_result.tilt_static_dmx is not None:
        renderer_log.info(f"Tilt Static DMX: {movement_result.tilt_static_dmx}")

    segment.add_channel(
        channel=ChannelName.TILT,
        curve=PointsCurve(points=tilt_points) if tilt_points is not None else None,
        static_dmx=movement_result.tilt_static_dmx,
        value_points=tilt_points,
        offset_centered=False,
    )

    if dimmer_result.dimmer_static_dmx is not None:
        renderer_log.info(f"Dimmer Static DMX: {dimmer_result.dimmer_static_dmx}")

    segment.add_channel(
        channel=ChannelName.DIMMER,
        curve=PointsCurve(points=dimmer_points) if dimmer_points is not None else None,
        static_dmx=dimmer_result.dimmer_static_dmx,
        value_points=dimmer_points,
        offset_centered=False,
    )

    return StepCompileResult(
        step_id=step.step_id,
        segment=segment,
    )
