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


@register_template(aliases=["Accent Snap Tunnel Hit", "accent snap tunnel hit"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="accent_snap_tunnel_hit",
            version=1,
            name="Accent Snap Tunnel Hit",
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
                            order=ChaseOrder.INSIDE_OUT,
                            spread_bars=0.5,
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
                        min_norm=0.10,
                        max_norm=1.00,
                        cycles=4.0,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="Rapid accent snaps in tunnel cone formation with matched pulse hits.",
                recommended_sections=["drop", "peak"],
                energy_range=(80, 100),
                tags=["accent_snap", "tunnel", "hit"],
            ),
        )
    )
