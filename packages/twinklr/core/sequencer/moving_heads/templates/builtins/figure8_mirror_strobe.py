from __future__ import annotations

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


@register_template(aliases=["Figure 8 Mirror Strobe", "figure 8 mirror strobe"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="figure8_mirror_strobe",
            version=1,
            name="Figure 8 Mirror Strobe",
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
                            quantize_type=QuantizeMode.DOWNBEAT,
                            duration_bars=4.0,
                            start_offset_bars=0.0,
                        ),
                        phase_offset=PhaseOffset(
                            mode=PhaseOffsetMode.GROUP_ORDER,
                            order=ChaseOrder.LEFT_TO_RIGHT,
                            spread_bars=0.5,
                        ),
                    ),
                    geometry=Geometry(
                        geometry_type=GeometryType.MIRROR_LR,
                    ),
                    movement=Movement(
                        movement_type=MovementType.FIGURE8,
                        intensity=Intensity.INTENSE,
                        cycles=2.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,
                        intensity=Intensity.INTENSE,
                        min_norm=0.05,
                        max_norm=1.00,
                        cycles=8.0,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="Mirrored figure-8 patterns with strobe-rate dimmer pulses.",
                recommended_sections=["drop", "peak"],
                energy_range=(75, 100),
                tags=["figure8", "mirror", "strobe"],
            ),
        )
    )
