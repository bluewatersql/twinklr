from __future__ import annotations

from twinklr.core.config.poses import TiltPose
from twinklr.core.sequencer.models.enum import (
    Intensity,
    QuantizeMode,
    SemanticGroupType,
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


@register_template(aliases=["Crossfade Between Steps", "crossfade between steps"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        enabled=False,
        template=Template(
            template_id="crossfade_between_steps",
            version=1,
            name="Crossfade Between Steps",
            category=TemplateCategory.MEDIUM_ENERGY,
            roles=TemplateRoleHelper.IN_OUT_LEFT_RIGHT,
            repeat=RepeatContract(
                repeatable=True,
                mode=RepeatMode.PING_PONG,
                cycle_bars=4.0,
                loop_step_ids=["a", "b"],
                remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
            ),
            defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 255},
            steps=[
                TemplateStep(
                    step_id="a",
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            start_offset_bars=0.0,
                            duration_bars=2.0,
                            quantize_type=QuantizeMode.DOWNBEAT,
                        )
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
                        min_norm=0.20,
                        max_norm=1.00,
                        cycles=2.0,
                    ),
                ),
                TemplateStep(
                    step_id="b",
                    target=SemanticGroupType.ALL,
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            start_offset_bars=2.0,
                            duration_bars=2.0,
                            quantize_type=QuantizeMode.DOWNBEAT,
                        )
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
                        dimmer_type=DimmerType.HOLD,
                        intensity=Intensity.SMOOTH,
                        min_norm=0.10,
                        max_norm=1.00,
                        cycles=1.0,
                    ),
                ),
            ],
            metadata=TemplateMetadata(
                description="Two-step sequence with overlapping dimmer crossfades.",
                recommended_sections=["build", "chorus"],
                energy_range=(40, 75),
                tags=["transition", "crossfade"],
            ),
        ),
    )
