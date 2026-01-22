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


@register_template(aliases=["Sweep UD Chevron Swell", "sweep ud chevron swell"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="sweep_ud_chevron_swell",
            version=1,
            name="Sweep UD Chevron Swell",
            category=TemplateCategory.MEDIUM_ENERGY,
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
                        geometry_type=GeometryType.CHEVRON_V,
                        params={
                            "order": "LEFT_TO_RIGHT",
                            "pan_start_dmx": 96,
                            "pan_end_dmx": 176,
                            "tilt_base_dmx": 128,
                            "tilt_inner_bias_dmx": 18,
                            "tilt_outer_bias_dmx": 0,
                        },
                    ),
                    movement=Movement(
                        movement_type=MovementType.SWEEP_UD,
                        intensity=Intensity.SMOOTH,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,  # SWELL → PULSE (similar effect)
                        intensity=Intensity.SMOOTH,
                        min_norm=0.10,
                        max_norm=1.00,
                        cycles=1.0,
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
                description="Chevron lift with vertical sweep and swelling dimmer.",
                recommended_sections=["build", "lift"],
                energy_range=(40, 70),
                tags=["sweep_ud", "chevron", "swell"],
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
