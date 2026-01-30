from __future__ import annotations

from blinkb0t.core.config.poses import TiltPose
from blinkb0t.core.sequencer.models.enum import (
    Intensity,
    QuantizeMode,
    TemplateCategory,
    TimingMode,
)
from blinkb0t.core.sequencer.models.template import (
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
from blinkb0t.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from blinkb0t.core.sequencer.moving_heads.libraries.geometry import GeometryType
from blinkb0t.core.sequencer.moving_heads.libraries.movement import MovementType
from blinkb0t.core.sequencer.moving_heads.templates.library import register_template
from blinkb0t.core.sequencer.moving_heads.templates.utils import (
    PoseByRoleHelper,
    TemplateRoleHelper,
)


@register_template(aliases=["Circle Fan Hold", "circle fan hold"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="circle_fan_hold",
            version=1,
            name="Circle Fan Hold",
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
                        )
                    ),
                    geometry=Geometry(
                        geometry_type=GeometryType.ROLE_POSE,
                        pan_pose_by_role=PoseByRoleHelper.FAN_POSE_WIDE,
                        tilt_pose=TiltPose.HORIZON,
                    ),
                    movement=Movement(
                        movement_type=MovementType.CIRCLE,
                        intensity=Intensity.DRAMATIC,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.HOLD,
                        intensity=Intensity.SMOOTH,
                        min_norm=0.10,
                        max_norm=1.00,
                        cycles=1.0,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="Symmetric circular motion with steady dimmer.",
                recommended_sections=["verse", "bridge"],
                energy_range=(35, 60),
                tags=["circle", "fan", "hold"],
            ),
        ),
    )
