from __future__ import annotations

from blinkb0t.core.sequencer.models.enum import (
    ChaseOrder,
    Intensity,
    QuantizeMode,
    TemplateCategory,
    TimingMode,
)
from blinkb0t.core.sequencer.models.template import (
    BaseTiming,
    Dimmer,
    Distribution,
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
from blinkb0t.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from blinkb0t.core.sequencer.moving_heads.libraries.geometry import GeometryType
from blinkb0t.core.sequencer.moving_heads.libraries.movement import MovementType
from blinkb0t.core.sequencer.moving_heads.templates.library import register_template
from blinkb0t.core.sequencer.moving_heads.templates.utils import (
    PoseByRoleHelper,
    TemplateRoleHelper,
)


@register_template(aliases=["Wave Scattered Fade Out", "wave scattered fade out"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="wave_scattered_fade_out",
            version=1,
            name="Wave Scattered Fade Out",
            category=TemplateCategory.MEDIUM_ENERGY,
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
                            start_offset_bars=0.0,
                            duration_bars=4.0,
                            quantize_type=QuantizeMode.DOWNBEAT,
                        ),
                        phase_offset=PhaseOffset(
                            mode=PhaseOffsetMode.GROUP_ORDER,
                            order=ChaseOrder.LEFT_TO_RIGHT,
                            spread_bars=1.0,
                            distribution=Distribution.LINEAR,
                            wrap=True,
                        ),
                    ),
                    geometry=Geometry(
                        geometry_type=GeometryType.SCATTERED_CHAOS,
                        pan_pose_by_role=PoseByRoleHelper.FAN_POSE_WIDE,
                        params={
                            "seed": 7,
                            "pan_center_deg": 0.0,  # CENTER
                            "tilt_center_deg": 30.0,  # HORIZON_UP_45
                            "pan_spread_dmx": 70,
                            "tilt_spread_dmx": 40,
                        },
                    ),
                    movement=Movement(
                        movement_type=MovementType.WAVE_HORIZONTAL,
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
                )
            ],
            metadata=TemplateMetadata(
                description="Horizontal wave over scattered chaos with fade-out dimmer.",
                recommended_sections=["outro"],
                energy_range=(35, 60),
                tags=["wave_horizontal", "scatter", "fade_out"],
            ),
        ),
    )
