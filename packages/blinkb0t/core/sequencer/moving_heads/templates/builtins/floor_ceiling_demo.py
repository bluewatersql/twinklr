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


@register_template(aliases=["Floor Ceiling Demo", "floor ceiling demo"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="floor_ceiling_demo",
            version=1,
            name="Floor/Ceiling Demo",
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
            defaults={"dimmer_floor_dmx": 80, "dimmer_ceiling_dmx": 220},
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
                        dimmer_type=DimmerType.PULSE,
                        intensity=Intensity.DRAMATIC,
                        min_norm=0.05,
                        max_norm=1.00,
                        cycles=2.0,
                    ),
                    entry_transition=Transition(
                        mode=TransitionMode.SNAP, duration_bars=0.0, curve="linear"
                    ),
                    exit_transition=Transition(
                        mode=TransitionMode.CROSSFADE, duration_bars=0.0, curve="linear"
                    ),
                    priority=0,
                    blend_mode=BlendMode.OVERRIDE,
                    # Note: Step-level floor/ceiling overrides removed (handled at template level)
                )
            ],
            metadata=TemplateMetadata(
                description="Dimmer clamp precedence demo with custom floor/ceiling.",
                recommended_sections=["verse"],
                energy_range=(10, 30),
                tags=["clamp", "floor", "ceiling"],
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
