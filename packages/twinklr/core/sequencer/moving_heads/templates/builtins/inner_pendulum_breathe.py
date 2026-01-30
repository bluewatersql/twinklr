from __future__ import annotations

from twinklr.core.config.poses import TiltPose
from twinklr.core.sequencer.models.enum import (
    Intensity,
    QuantizeMode,
    TemplateCategory,
    TimingMode,
)
from twinklr.core.sequencer.models.template import (
    BaseTiming,
    Dimmer,
    Geometry,
    Movement,
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
    StepTiming,
    Template,
    TemplateDoc,
    TemplateMetadata,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType
from twinklr.core.sequencer.moving_heads.templates.library import register_template
from twinklr.core.sequencer.moving_heads.templates.utils import (
    PoseByRoleHelper,
    TemplateRoleHelper,
)


@register_template(aliases=["Inner Pendulum Breathe", "inner pendulum breathe"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="inner_pendulum_breathe",
            version=1,
            name="Inner Pendulum Breathe",
            category=TemplateCategory.LOW_ENERGY,
            roles=TemplateRoleHelper.IN_OUT_LEFT_RIGHT,
            repeat=RepeatContract(
                repeatable=True,
                mode=RepeatMode.JOINER,
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
                        )
                    ),
                    geometry=Geometry(
                        geometry_type=GeometryType.ROLE_POSE,
                        pan_pose_by_role=PoseByRoleHelper.FAN_POSE_NARROW,
                        tilt_pose=TiltPose.HORIZON,
                    ),
                    movement=Movement(
                        movement_type=MovementType.PENDULUM,
                        intensity=Intensity.SMOOTH,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,
                        intensity=Intensity.SMOOTH,
                        min_norm=0.20,
                        max_norm=1.00,
                        cycles=1.0,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="INNER group only targeting for subtle movement.",
                recommended_sections=["verse"],
                energy_range=(15, 40),
                tags=["group_target", "inner", "pendulum"],
            ),
        ),
    )
