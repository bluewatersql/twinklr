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
    ChaseOrder,
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
)
from blinkb0t.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from blinkb0t.core.sequencer.moving_heads.libraries.geometry import GeometryType
from blinkb0t.core.sequencer.moving_heads.libraries.movement import MovementType
from blinkb0t.core.sequencer.moving_heads.templates.library import register_template
from blinkb0t.core.sequencer.moving_heads.templates.utils import (
    PoseByRoleHelper,
    TemplateRoleHelper,
)


@register_template(aliases=["Circle Asym Right Pulse", "circle asym right pulse"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="circle_asym_right_pulse",
            version=1,
            name="Circle Asym Right Pulse",
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
                        geometry_type=GeometryType.AUDIENCE_SCAN_ASYM,
                        pan_pose_by_role=PoseByRoleHelper.FAN_POSE_WIDE,
                        tilt_pose=TiltPose.AUDIENCE_CENTER,
                    ),
                    movement=Movement(
                        movement_type=MovementType.CIRCLE,
                        intensity=Intensity.DRAMATIC,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,
                        intensity=Intensity.DRAMATIC,
                        min_norm=0.20,
                        max_norm=1.00,
                        cycles=4.0,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="Asymmetric right-leaning circle with pulsing dimmer.",
                recommended_sections=["chorus", "drop"],
                energy_range=(55, 85),
                tags=["circle", "asym", "pulse"],
            ),
        ),
    )
