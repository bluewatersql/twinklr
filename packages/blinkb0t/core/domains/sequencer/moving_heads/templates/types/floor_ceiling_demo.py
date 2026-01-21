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
from blinkb0t.core.domains.sequencer.moving_heads.models.geometry import RolePoseGeometry
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

TEMPLATE = Template(
    template_id="floor_ceiling_demo",
    version=1,
    name="Floor/Ceiling Demo",
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
    defaults=TemplateDefaults(dimmer_floor_dmx=80, dimmer_ceiling_dmx=220),
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
            geometry=RolePoseGeometry(
                pan_pose_by_role={
                    "OUTER_LEFT": "CENTER",
                    "INNER_LEFT": "CENTER",
                    "INNER_RIGHT": "CENTER",
                    "OUTER_RIGHT": "CENTER",
                },
                tilt_pose="HORIZON",
            ),
            movement=Movement(
                movement_id=MovementID.HOLD,
                intensity=IntensityLevel.SMOOTH,
                cycles=1.0,
            ),
            dimmer=Dimmer(
                dimmer_id=DimmerID.PULSE,
                intensity=IntensityLevel.DRAMATIC,
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
            dimmer_floor_dmx=100,
            dimmer_ceiling_dmx=200,
            priority=0,
            blend_mode=BlendMode.OVERRIDE,
        )
    ],
    metadata=TemplateMetadata(
        description="Clamp precedence demo: rig vs template vs step.",
        recommended_sections=["verse"],
        energy_range=[10, 30],
        tags=["clamp", "floor", "ceiling", "demo05"],
    ),
)
