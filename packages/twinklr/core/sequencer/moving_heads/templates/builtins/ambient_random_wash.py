from __future__ import annotations

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
from twinklr.core.sequencer.moving_heads.templates.utils import TemplateRoleHelper


@register_template(aliases=["Ambient Random Wash", "ambient random wash"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="ambient_random_wash",
            version=1,
            name="Ambient Random Wash",
            category=TemplateCategory.LOW_ENERGY,
            roles=TemplateRoleHelper.IN_OUT_LEFT_RIGHT,
            repeat=RepeatContract(
                repeatable=True,
                mode=RepeatMode.JOINER,
                cycle_bars=8.0,
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
                            duration_bars=8.0,
                            quantize_type=QuantizeMode.DOWNBEAT,
                        )
                    ),
                    geometry=Geometry(geometry_type=GeometryType.WALL_WASH),
                    movement=Movement(
                        movement_type=MovementType.RANDOM_WALK,
                        intensity=Intensity.SLOW,
                        cycles=0.5,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.HOLD,
                        intensity=Intensity.SMOOTH,
                        min_norm=0.60,
                        max_norm=0.90,
                        cycles=1.0,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="Ultra-slow random drift across a wall wash for atmospheric ambient moments.",
                recommended_sections=["intro", "ambient", "verse"],
                energy_range=(5, 25),
                tags=["ambient", "random_walk", "wall_wash", "atmospheric"],
            ),
        ),
    )
