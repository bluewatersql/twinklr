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


@register_template(aliases=["Pump Up Loop", "pump up loop"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        enabled=False,
        template=Template(
            template_id="pump_up_loop",
            version=1,
            name="Pump Up Loop",
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
                        movement_type=MovementType.SWEEP_LR,
                        intensity=Intensity.SMOOTH,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,
                        intensity=Intensity.DRAMATIC,
                        min_norm=0.10,
                        max_norm=1.00,
                        cycles=2.0,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="Looped sweep + pulse for building energy.",
                recommended_sections=["build", "chorus"],
                energy_range=(45, 85),
                tags=["repeat", "loop", "sweep_lr", "pulse"],
            ),
        ),
    )
