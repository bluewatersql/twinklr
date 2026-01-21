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
    template_id="circle_fan_hold",
    version=1,
    name="Circle Fan Hold",
    category=Category.MEDIUM_ENERGY,
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
            geometry=RolePoseGeometry(
                pan_pose_by_role={
                    "OUTER_LEFT": "WIDE_LEFT",
                    "INNER_LEFT": "MID_LEFT",
                    "INNER_RIGHT": "MID_RIGHT",
                    "OUTER_RIGHT": "WIDE_RIGHT",
                },
                tilt_pose="HORIZON",
            ),
            movement=Movement(
                movement_id=MovementID.CIRCLE,
                intensity=IntensityLevel.DRAMATIC,
                cycles=1.0,
            ),
            dimmer=Dimmer(
                dimmer_id=DimmerID.HOLD,
                intensity=IntensityLevel.SMOOTH,
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
        description="Symmetric circular motion with steady dimmer.",
        recommended_sections=["verse", "bridge"],
        energy_range=[35, 60],
        tags=["demo08a", "circle", "fan", "hold"],
    ),
)
