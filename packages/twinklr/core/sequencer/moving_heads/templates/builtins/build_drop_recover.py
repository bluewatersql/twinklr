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


@register_template(aliases=["Build Drop Recover", "build drop recover"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="build_drop_recover",
            version=1,
            name="Build Drop Recover",
            category=TemplateCategory.HIGH_ENERGY,
            roles=TemplateRoleHelper.IN_OUT_LEFT_RIGHT,
            repeat=RepeatContract(
                repeatable=True,
                mode=RepeatMode.PING_PONG,
                cycle_bars=2.0,
                loop_step_ids=["drop"],
                remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
            ),
            defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 255},
            steps=[
                TemplateStep(
                    step_id="build",
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            start_offset_bars=0.0,
                            duration_bars=2.0,
                            quantize_type=QuantizeMode.DOWNBEAT,
                        ),
                        phase_offset=PhaseOffset(
                            mode=PhaseOffsetMode.GROUP_ORDER,
                            order=ChaseOrder.LEFT_TO_RIGHT,
                            spread_bars=0.5,
                        ),
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
                        dimmer_type=DimmerType.FADE_IN,
                        intensity=Intensity.SMOOTH,
                        min_norm=0.10,
                        max_norm=1.00,
                        cycles=1.0,
                    ),
                    exit_transition=Transition(
                        mode=TransitionMode.CROSSFADE,
                        duration_bars=0.25,
                    ),
                ),
                TemplateStep(
                    step_id="drop",
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            start_offset_bars=2.0,
                            duration_bars=2.0,
                            quantize_type=QuantizeMode.DOWNBEAT,
                        ),
                        phase_offset=PhaseOffset(
                            mode=PhaseOffsetMode.GROUP_ORDER,
                            order=ChaseOrder.ODD_EVEN,
                            spread_bars=0.25,
                        ),
                    ),
                    geometry=Geometry(
                        geometry_type=GeometryType.TUNNEL_CONE,
                    ),
                    movement=Movement(
                        movement_type=MovementType.ACCENT_SNAP,
                        intensity=Intensity.INTENSE,
                        cycles=4.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,
                        intensity=Intensity.INTENSE,
                        min_norm=0.05,
                        max_norm=1.00,
                        cycles=8.0,
                    ),
                    entry_transition=Transition(
                        mode=TransitionMode.CROSSFADE,
                        duration_bars=0.25,
                    ),
                    exit_transition=Transition(
                        mode=TransitionMode.CROSSFADE,
                        duration_bars=0.25,
                    ),
                ),
                TemplateStep(
                    step_id="recover",
                    timing=StepTiming(
                        base_timing=BaseTiming(
                            mode=TimingMode.MUSICAL,
                            start_offset_bars=4.0,
                            duration_bars=2.0,
                            quantize_type=QuantizeMode.DOWNBEAT,
                        ),
                    ),
                    geometry=Geometry(
                        geometry_type=GeometryType.ROLE_POSE,
                        pan_pose_by_role=PoseByRoleHelper.FAN_POSE_WIDE,
                        tilt_pose=TiltPose.HORIZON,
                    ),
                    movement=Movement(
                        movement_type=MovementType.GROOVE_SWAY,
                        intensity=Intensity.SMOOTH,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.FADE_OUT,
                        intensity=Intensity.SMOOTH,
                        min_norm=0.10,
                        max_norm=1.00,
                        cycles=1.0,
                    ),
                    entry_transition=Transition(
                        mode=TransitionMode.CROSSFADE,
                        duration_bars=0.25,
                    ),
                ),
            ],
            metadata=TemplateMetadata(
                description="Three-phase arc: sweep build, accent-snap drop (loops), groove-sway recovery.",
                recommended_sections=["drop", "chorus"],
                energy_range=(60, 100),
                tags=["multi_step", "build", "drop", "recover", "transition"],
            ),
        ),
    )
