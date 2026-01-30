from __future__ import annotations

from twinklr.core.config.poses import TiltPose
from twinklr.core.sequencer.models.enum import (
    ChaseOrder,
    Intensity,
    QuantizeMode,
    TemplateCategory,
    TimingMode,
    TransitionMode,
)
from twinklr.core.sequencer.models.template import (
    BaseTiming,
    Dimmer,
    Geometry,
    Movement,
    PhaseOffset,
    PhaseOffsetMode,
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
    StepTiming,
    Template,
    TemplateDoc,
    TemplateMetadata,
    TemplateStep,
    Transition,
)
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType
from twinklr.core.sequencer.moving_heads.templates.library import register_template
from twinklr.core.sequencer.moving_heads.templates.utils import (
    PoseByRoleHelper,
    TemplateRoleHelper,
)


@register_template(aliases=["Cascade Pulse LR", "cascade pulse lr"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="cascade_pulse_lr",
            version=1,
            name="Cascade Pulse (L→R)",
            category=TemplateCategory.MEDIUM_ENERGY,
            roles=TemplateRoleHelper.IN_OUT_LEFT_RIGHT,
            repeat=RepeatContract(
                repeatable=True,
                mode=RepeatMode.PING_PONG,
                cycle_bars=4.0,
                loop_step_ids=["main"],
                remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
            ),
            defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 255},
            steps=[
                TemplateStep(
                    step_id="main",
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            start_offset_bars=0.0,
                            duration_bars=4.0,
                            quantize_type=QuantizeMode.DOWNBEAT,
                        ),
                        phase_offset=PhaseOffset(
                            mode=PhaseOffsetMode.GROUP_ORDER,
                            order=ChaseOrder.LEFT_TO_RIGHT,
                            spread_bars=1.0,
                        ),
                    ),
                    geometry=Geometry(
                        geometry_type=GeometryType.ROLE_POSE,
                        pan_pose_by_role=PoseByRoleHelper.FAN_POSE_WIDE,
                        tilt_pose=TiltPose.HORIZON,
                    ),
                    movement=Movement(
                        movement_type=MovementType.HOLD,
                        intensity=Intensity.SMOOTH,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,
                        intensity=Intensity.DRAMATIC,
                        min_norm=0.10,
                        max_norm=1.00,
                        cycles=4.0,
                    ),
                    exit_transition=Transition(mode=TransitionMode.CROSSFADE, duration_bars=0.25),
                )
            ],
            metadata=TemplateMetadata(
                description="Dimmer pulse cascades left-to-right using PhaseOffset.",
                recommended_sections=["verse", "groove", "build"],
                energy_range=(45, 80),
                tags=["phase_offset", "cascade", "pulse"],
            ),
        )
    )
