from blinkb0t.core.domains.sequencer.moving_heads.models.base import (
    BlendMode,
    BoundaryTransition,
    Category,
    Distribution,
    IntensityLevel,
    OrderMode,
    PhaseOffsetMode,
    PhaseUnit,
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
    PhaseOffsetSpec,
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
    template_id="wave_scattered_fade_out",
    version=1,
    name="Wave Scattered Fade Out",
    category=Category.MEDIUM_ENERGY,
    roles=["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"],
    groups={"ALL": ["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"]},
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
                ),
                phase_offset=PhaseOffsetSpec(
                    unit=PhaseUnit.BARS,
                    mode=PhaseOffsetMode.GROUP_ORDER,
                    group="ALL",
                    order=OrderMode.LEFT_TO_RIGHT,
                    spread_bars=1.0,
                    distribution=Distribution.LINEAR,
                    wrap=True,
                ),
            ),
            geometry=GeometryIdSpec(
                geometry_id=GeometryID.SCATTERED_CHAOS,
                geometry_params={
                    "seed": 7,
                    "pan_center_dmx": 128,
                    "pan_spread_dmx": 36,
                    "tilt_center_dmx": 128,
                    "tilt_spread_dmx": 18,
                },
            ),
            movement=MovementSpec(
                movement_id=MovementID.WAVE_HORIZONTAL,
                intensity=IntensityLevel.SMOOTH,
                cycles=1.0,
            ),
            dimmer=DimmerSpec(
                dimmer_id=DimmerID.FADE_OUT,
                intensity=IntensityLevel.SMOOTH,
                min_norm=0.10,
                max_norm=1.00,
                cycles=1.0,
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
        description="Horizontal wave over scattered chaos with fade-out dimmer.",
        recommended_sections=["outro"],
        energy_range=[35, 60],
        tags=["demo11c", "wave_horizontal", "scatter", "fade_out"],
    ),
)
