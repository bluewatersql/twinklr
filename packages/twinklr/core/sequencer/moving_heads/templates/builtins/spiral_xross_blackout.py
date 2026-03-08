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


@register_template(aliases=["Spiral X-Cross Blackout", "spiral x-cross blackout"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="spiral_xross_blackout",
            version=1,
            name="Spiral X-Cross Blackout",
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
                            order=ChaseOrder.OUTSIDE_IN,
                            spread_bars=1.0,
                        ),
                    ),
                    geometry=Geometry(
                        geometry_type=GeometryType.X_CROSS,
                    ),
                    movement=Movement(
                        movement_type=MovementType.SPIRAL,
                        intensity=Intensity.DRAMATIC,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.BLACKOUT,
                        min_norm=0.0,
                        max_norm=1.0,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="Spiraling beams in X-cross formation punctuated by blackout.",
                recommended_sections=["drop", "breakdown"],
                energy_range=(70, 95),
                tags=["spiral", "x_cross", "blackout"],
            ),
        )
    )
