from __future__ import annotations

from blinkb0t.core.config.poses import PanPose, TiltPose
from blinkb0t.core.sequencer.models.enum import (
    Intensity,
    QuantizeMode,
    TemplateCategory,
    TimingMode,
)
from blinkb0t.core.sequencer.models.template import (
    BaseTiming,
    ChaseOrder,
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
    TemplateRoleHelper,
)


@register_template(aliases=["Pendulum Chevron Breathe", "pendulum chevron breathe"])
def make_template() -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="pendulum_chevron_breathe",
            version=1,
            name="Pendulum Chevron Breathe",
            category=TemplateCategory.LOW_ENERGY,
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
                        geometry_type=GeometryType.CHEVRON_V,
                        params={
                            "pan_start_dmx": PanPose.WIDE_LEFT.value,
                            "pan_end_dmx": PanPose.WIDE_RIGHT.value,
                            "tilt_base_dmx": TiltPose.CEILING.value,
                            "tilt_inner_bias_dmx": 18,
                            "tilt_outer_bias_dmx": 0,
                        },
                    ),
                    movement=Movement(
                        movement_type=MovementType.PENDULUM,
                        intensity=Intensity.SMOOTH,
                        cycles=1.0,
                    ),
                    dimmer=Dimmer(
                        dimmer_type=DimmerType.PULSE,
                        intensity=Intensity.SMOOTH,
                        min_norm=0.20,
                        max_norm=1.00,
                        cycles=1.0,
                    ),
                )
            ],
            metadata=TemplateMetadata(
                description="Smooth pendulum pan over a chevron with breathing dimmer.",
                recommended_sections=["verse", "bridge"],
                energy_range=(20, 50),
                tags=["pendulum", "chevron", "breathe"],
            ),
        ),
    )
