from __future__ import annotations

from blinkb0t.core.config.poses import TiltPose
from blinkb0t.core.sequencer.models.enum import (
    ChaseOrder,
    Intensity,
    QuantizeMode,
    TemplateCategory,
    TimingMode,
    TransitionMode,
)
from blinkb0t.core.sequencer.models.template import (
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
from blinkb0t.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from blinkb0t.core.sequencer.moving_heads.libraries.geometry import GeometryType
from blinkb0t.core.sequencer.moving_heads.libraries.movement import MovementType
from blinkb0t.core.sequencer.moving_heads.templates.library import register_template
from blinkb0t.core.sequencer.moving_heads.templates.utils import (
    PoseByRoleHelper,
    TemplateRoleHelper,
)


@register_template(aliases=["Circle Asym Left Strobe", "circle asym left strobe"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="circle_asym_left_strobe",
            version=1,
            name="Circle Asym Left Strobe",
            category=TemplateCategory.HIGH_ENERGY,
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
                        intensity=Intensity.INTENSE,
                        min_norm=0.05,
                        max_norm=1.00,
                        cycles=8.0,
                    ),
                    exit_transition=Transition(mode=TransitionMode.CROSSFADE, duration_bars=0.0),
                )
            ],
            metadata=TemplateMetadata(
                description="Asymmetric left-leaning circle with strobe-like dimmer.",
                recommended_sections=["drop", "peak"],
                energy_range=(70, 100),
                tags=["circle", "asym", "strobe"],
            ),
        ),
    )
