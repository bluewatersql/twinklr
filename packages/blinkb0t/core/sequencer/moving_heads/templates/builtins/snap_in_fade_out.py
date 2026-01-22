from __future__ import annotations

from blinkb0t.core.config.poses import PanPose, TiltPose
from blinkb0t.core.sequencer.models.enum import (
    BlendMode,
    Intensity,
    QuantizeMode,
    SemanticGroupType,
    TemplateCategory,
    TemplateRole,
    TimingMode,
    TransitionMode,
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
    TemplatePreset,
    TemplateStep,
    Transition,
)
from blinkb0t.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from blinkb0t.core.sequencer.moving_heads.libraries.geometry import GeometryType
from blinkb0t.core.sequencer.moving_heads.libraries.movement import MovementType
from blinkb0t.core.sequencer.moving_heads.templates.library import register_template


@register_template(aliases=["Snap In Fade Out", "snap in fade out"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="snap_in_fade_out",
            version=1,
            name="Snap In, Fade Out",
            category=TemplateCategory.LOW_ENERGY,
            roles=[
                TemplateRole.OUTER_LEFT,
                TemplateRole.INNER_LEFT,
                TemplateRole.INNER_RIGHT,
                TemplateRole.OUTER_RIGHT,
            ],
            groups={
                SemanticGroupType.ALL: [
                    TemplateRole.OUTER_LEFT,
                    TemplateRole.INNER_LEFT,
                    TemplateRole.INNER_RIGHT,
                    TemplateRole.OUTER_RIGHT,
                ]
            },
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
                    target=SemanticGroupType.ALL,
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
                        pan_pose_by_role={
                            TemplateRole.OUTER_LEFT: PanPose.CENTER,
                            TemplateRole.INNER_LEFT: PanPose.CENTER,
                            TemplateRole.INNER_RIGHT: PanPose.CENTER,
                            TemplateRole.OUTER_RIGHT: PanPose.CENTER,
                        },
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
                    entry_transition=Transition(
                        mode=TransitionMode.SNAP, duration_bars=0.0, curve="linear"
                    ),
                    exit_transition=Transition(
                        mode=TransitionMode.CROSSFADE,  # FADE_THROUGH_BLACK → CROSSFADE
                        duration_bars=0.5,
                        curve="linear",
                    ),
                    priority=0,
                    blend_mode=BlendMode.OVERRIDE,
                )
            ],
            metadata=TemplateMetadata(
                description="Single-step with snap entry and fade exit transition demo.",
                recommended_sections=["verse"],
                energy_range=(10, 30),
                tags=["transition", "fade"],
            ),
        ),
        presets=[
            TemplatePreset(
                preset_id="CHILL",
                name="Chill",
                defaults={"intensity": "SMOOTH"},
            ),
        ],
    )
