from blinkb0t.core.domains.sequencer.moving_heads.models.base import (
    BlendMode,
    BoundaryTransition,
    Category,
    IntensityLevel,
    QuantizePoint,
    RemainderPolicy,
    RepeatMode,
    TimingMode,
    TransitionMode,
)
from blinkb0t.core.domains.sequencer.moving_heads.models.dimmer import Dimmer, DimmerID
from blinkb0t.core.domains.sequencer.moving_heads.models.geometry import GeometryType
from blinkb0t.core.domains.sequencer.moving_heads.models.movement import Movement, MovementID
from blinkb0t.core.domains.sequencer.moving_heads.models.templates import (
    BaseTiming,
    Repeat,
    Step,
    StepTiming,
    Template,
    TemplateDefaults,
    TemplateMetadata,
    Transition,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.geometry import GeometryID

TEMPLATE = Template(
    template_id="pendulum_chevron_breathe",
    version=1,
    name="Pendulum Chevron Breathe",
    category=Category.LOW_ENERGY,
    roles=["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"],
    groups={"ALL": ["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"]},
    timing={"mode": "musical", "default_cycle_bars": 4.0},
    repeat=Repeat(
        repeatable=True,
        mode=RepeatMode.PING_PONG,
        cycle_bars=4.0,
        loop_step_ids=["main"],
        boundary_transition=BoundaryTransition.CONTINUOUS,
        remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
    ),
    defaults=TemplateDefaults(dimmer_floor_dmx=60, dimmer_ceiling_dmx=255),
    steps=[
        Step(
            step_id="main",
            target="ALL",
            timing=StepTiming(
                base_timing=BaseTiming(
                    mode=TimingMode.MUSICAL,
                    start_offset_bars=0.0,
                    duration_bars=4.0,
                    quantize_start=QuantizePoint.DOWNBEAT,
                    quantize_end=QuantizePoint.DOWNBEAT,
                )
            ),
            geometry=GeometryType(
                geometry_id=GeometryID.CHEVRON_V,
                geometry_params={
                    "order": "LEFT_TO_RIGHT",
                    "pan_start_dmx": 96,
                    "pan_end_dmx": 176,
                    "tilt_base_dmx": 128,
                    "tilt_inner_bias_dmx": 18,
                    "tilt_outer_bias_dmx": 0,
                },
            ),
            movement=Movement(
                movement_id=MovementID.PENDULUM,
                intensity=IntensityLevel.SMOOTH,
                cycles=1.0,
            ),
            dimmer=Dimmer(
                dimmer_id=DimmerID.BREATHE,
                intensity=IntensityLevel.SMOOTH,
                min_norm=0.20,
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
        description="Smooth pendulum pan over a chevron with breathing dimmer.",
        recommended_sections=["verse", "bridge"],
        energy_range=[20, 50],
        tags=["demo10", "pendulum", "chevron", "breathe"],
    ),
)
