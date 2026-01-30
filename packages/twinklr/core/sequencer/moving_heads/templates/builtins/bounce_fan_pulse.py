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


@register_template(aliases=["Bounce Fan Pulse", "bounce fan pulse"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="bounce_fan_pulse",
            version=1,
            name="Bounce Fan Pulse",
            category=TemplateCategory.MEDIUM_ENERGY,
            roles=TemplateRoleHelper.IN_OUT_LEFT_RIGHT,
            repeat=RepeatContract(
                repeatable=True,
                mode=RepeatMode.PING_PONG,
                cycle_bars=4.0,
                loop_step_ids=["main"],
            ),
            steps=[
                TemplateStep(
                    step_id="main",
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            quantize_type=QuantizeMode.DOWNBEAT,
                            duration_bars=4.0,
                            start_offset_bars=0.0,
                        )
                    ),
                    geometry=Geometry(
                        pan_pose_by_role=PoseByRoleHelper.FAN_POSE_WIDE,
                        geometry_type=GeometryType.ROLE_POSE,
                        tilt_pose=TiltPose.HORIZON,
                    ),
                    movement=Movement(
                        movement_type=MovementType.BOUNCE,
                        intensity=Intensity.DRAMATIC,
                        cycles=2.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,
                        intensity=Intensity.DRAMATIC,
                        min_norm=0.20,
                        max_norm=1.00,
                        cycles=2.0,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="Fan bounce with pulsing dimmer hits.",
                recommended_sections=["chorus", "drop"],
                energy_range=(55, 85),
                tags=["bounce", "fan", "pulse"],
            ),
        )
    )
