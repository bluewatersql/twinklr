from __future__ import annotations

from twinklr.core.config.poses import PanPose, TiltPose
from twinklr.core.sequencer.models.enum import (
    ChaseOrder,
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
    PhaseOffset,
    PhaseOffsetMode,
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
    StepPatch,
    StepTiming,
    Template,
    TemplateDoc,
    TemplateMetadata,
    TemplatePreset,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType
from twinklr.core.sequencer.moving_heads.templates.library import register_template
from twinklr.core.sequencer.moving_heads.templates.utils import (
    PoseByRoleHelper,
)


@register_template(aliases=["Sweep LR Chevron Breathe", "sweep lr chevron breathe"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="sweep_lr_chevron_breathe",
            version=1,
            name="Sweep LR Chevron Breathe",
            category=TemplateCategory.MEDIUM_ENERGY,
            repeat=RepeatContract(
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
                            wrap=True,
                        ),
                    ),
                    geometry=Geometry(
                        geometry_type=GeometryType.CHEVRON_V,
                        params={
                            "pan_start_dmx": PanPose.WIDE_LEFT.value,
                            "pan_end_dmx": PanPose.WIDE_RIGHT.value,
                            "tilt_base_dmx": TiltPose.CEILING.value,
                            "tilt_inner_bias_dmx": 18,
                            "tilt_outer_bias_dmx": 0,
                        },
                        pan_pose_by_role=PoseByRoleHelper.FAN_POSE_WIDE,
                    ),
                    movement=Movement(
                        movement_type=MovementType.SWEEP_LR,
                        intensity=Intensity.SMOOTH,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,
                        intensity=Intensity.SMOOTH,
                        min_norm=0.25,
                        max_norm=1.00,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="Chevron sweep with breathing dimmer effect.",
                recommended_sections=["verse", "chorus"],
                energy_range=(40, 70),
                tags=["sweep_lr", "chevron", "breathe"],
            ),
        ),
        presets=[
            TemplatePreset(
                preset_id="gentle",
                name="Gentle",
                step_patches={
                    "main": StepPatch(
                        movement={"intensity": "SLOW", "cycles": 0.5},
                        dimmer={"min_norm": 0.50, "max_norm": 0.90},
                    ),
                },
            ),
            TemplatePreset(
                preset_id="intense",
                name="Intense",
                step_patches={
                    "main": StepPatch(
                        movement={"intensity": "DRAMATIC", "cycles": 2.0},
                        dimmer={"min_norm": 0.05, "max_norm": 1.00},
                    ),
                },
            ),
        ],
    )
