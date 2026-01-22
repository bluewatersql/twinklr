from __future__ import annotations

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


@register_template(aliases=["Circle Asym Left Strobe", "circle asym left strobe"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="circle_asym_left_strobe",
            version=1,
            name="Circle Asym Left Strobe",
            category=TemplateCategory.HIGH_ENERGY,
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
                        geometry_type=GeometryType.AUDIENCE_SCAN_ASYM,
                        params={
                            "order": "LEFT_TO_RIGHT",
                            "pan_positions": [68, 92, 132, 160],
                            "tilt_dmx": 128,
                        },
                    ),
                    movement=Movement(
                        movement_type=MovementType.CIRCLE,
                        intensity=Intensity.DRAMATIC,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,  # STROBE → PULSE with INTENSE
                        intensity=Intensity.INTENSE,
                        min_norm=0.05,
                        max_norm=1.00,
                        cycles=8.0,
                    ),
                    entry_transition=Transition(
                        mode=TransitionMode.SNAP, duration_bars=0.0, curve="linear"
                    ),
                    exit_transition=Transition(
                        mode=TransitionMode.CROSSFADE, duration_bars=0.0, curve="linear"
                    ),
                    priority=0,
                    blend_mode=BlendMode.OVERRIDE,
                )
            ],
            metadata=TemplateMetadata(
                description="Asymmetric left-leaning circle with strobe-like dimmer.",
                recommended_sections=["drop", "peak"],
                energy_range=(70, 100),
                tags=["circle", "asym", "strobe"],
            ),
        ),
        presets=[
            TemplatePreset(
                preset_id="INTENSE",
                name="Intense",
                defaults={"intensity": "INTENSE"},
            ),
        ],
    )
