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
from blinkb0t.core.domains.sequencer.moving_heads.models.dimmer import DimmerID, DimmerSpec
from blinkb0t.core.domains.sequencer.moving_heads.models.geometry import GeometryIdSpec
from blinkb0t.core.domains.sequencer.moving_heads.models.movement import MovementID, MovementSpec
from blinkb0t.core.domains.sequencer.moving_heads.models.templates import (
    BaseTiming,
    RepeatSpec,
    StepSpec,
    StepTiming,
    TemplateDefaults,
    TemplateMetadata,
    TemplateSpec,
    TransitionSpec,
)
from blinkb0t.core.domains.sequencing.libraries.moving_heads.geometry import GeometryID

TEMPLATE = TemplateSpec(
    template_id="circle_asym_left_strobe",
    version=1,
    name="Circle Asym Left Strobe",
    category=Category.HIGH_ENERGY,
    roles=[],
    groups={},
    timing={"mode": "musical", "default_cycle_bars": 4.0},
    repeat=RepeatSpec(
        repeatable=True,
        mode=RepeatMode.PING_PONG,
        cycle_bars=4.0,
        loop_step_ids=["main"],
        boundary_transition=BoundaryTransition.CONTINUOUS,
        remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
    ),
    defaults=TemplateDefaults(dimmer_floor_dmx=60, dimmer_ceiling_dmx=255),
    steps=[
        StepSpec(
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
            geometry=GeometryIdSpec(
                geometry_id=GeometryID.AUDIENCE_SCAN_ASYM,
                geometry_params={
                    "order": "LEFT_TO_RIGHT",
                    "pan_positions": [68, 92, 132, 160],
                    "tilt_dmx": 128,
                },
            ),
            movement=MovementSpec(
                movement_id=MovementID.CIRCLE,
                intensity=IntensityLevel.DRAMATIC,
                cycles=1.0,
            ),
            dimmer=DimmerSpec(
                dimmer_id=DimmerID.STROBE,
                intensity=IntensityLevel.INTENSE,
                min_norm=0.05,
                max_norm=1.00,
                cycles=8.0,
            ),
            entry_transition=TransitionSpec(
                mode=TransitionMode.SNAP, duration_bars=0.0, curve="linear"
            ),
            exit_transition=TransitionSpec(
                mode=TransitionMode.CROSSFADE, duration_bars=0.0, curve="linear"
            ),
            priority=0,
            blend_mode=BlendMode.OVERRIDE,
        )
    ],
    metadata=TemplateMetadata(
        description="Asymmetric left-leaning circle with strobe dimmer.",
        recommended_sections=["drop", "peak"],
        energy_range=[70, 100],
        tags=["demo08c", "circle", "asym", "strobe"],
    ),
)
