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
from blinkb0t.core.domains.sequencer.moving_heads.models.geometry import RolePoseGeometrySpec
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

TEMPLATE = TemplateSpec(
    template_id="fan_pulse",
    version=1,
    name="Fan Pulse",
    category=Category.HIGH_ENERGY,
    # Roles/groups are role-space (not fixture ids)
    roles=["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"],
    groups={
        "ALL": ["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"],
        "LEFT": ["OUTER_LEFT", "INNER_LEFT"],
        "RIGHT": ["INNER_RIGHT", "OUTER_RIGHT"],
        "INNER": ["INNER_LEFT", "INNER_RIGHT"],
        "OUTER": ["OUTER_LEFT", "OUTER_RIGHT"],
        "ODD": ["OUTER_LEFT", "INNER_RIGHT"],
        "EVEN": ["INNER_LEFT", "OUTER_RIGHT"],
    },
    # Template timing defaults (compiler may not use yet; ok to include)
    timing={"mode": "musical", "default_cycle_bars": 4.0},
    # Repeat contract: loop the "main" step to fill section windows
    repeat=RepeatSpec(
        repeatable=True,
        mode=RepeatMode.PING_PONG,
        cycle_bars=4.0,
        loop_step_ids=["main"],
        boundary_transition=BoundaryTransition.CONTINUOUS,
        remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
    ),
    # Defaults: this is where your dimmer floor belongs for template-level policy
    defaults=TemplateDefaults(
        dimmer_floor_dmx=60,
        dimmer_ceiling_dmx=255,
    ),
    steps=[
        # Phase 1: intro “set the shape”, quick ramp-in, slight cascade (no per-fixture arrays)
        StepSpec(
            step_id="intro",
            target="ALL",
            timing=StepTiming(
                base_timing=BaseTiming(
                    mode=TimingMode.MUSICAL,
                    start_offset_bars=0.0,
                    duration_bars=1.0,
                    quantize_start=QuantizePoint.DOWNBEAT,
                    quantize_end=QuantizePoint.DOWNBEAT,
                ),
                phase_offset=PhaseOffsetSpec(
                    unit=PhaseUnit.BARS,
                    mode=PhaseOffsetMode.GROUP_ORDER,
                    group="ALL",
                    order=OrderMode.LEFT_TO_RIGHT,
                    spread_bars=0.5,
                    distribution=Distribution.LINEAR,
                    wrap=True,
                ),
            ),
            geometry=RolePoseGeometrySpec(
                pan_pose_by_role={
                    "OUTER_LEFT": "WIDE_LEFT",
                    "INNER_LEFT": "MID_LEFT",
                    "INNER_RIGHT": "MID_RIGHT",
                    "OUTER_RIGHT": "WIDE_RIGHT",
                },
                tilt_pose="HORIZON",
            ),
            movement=MovementSpec(
                movement_id=MovementID.SWEEP_LR,
                intensity=IntensityLevel.SMOOTH,
                cycles=0.5,  # half-sweep over the intro bar
            ),
            dimmer=DimmerSpec(
                dimmer_id=DimmerID.FADE_IN,
                intensity=IntensityLevel.DRAMATIC,
                min_norm=0.0,
                max_norm=1.0,
                cycles=1.0,
            ),
            entry_transition=TransitionSpec(
                mode=TransitionMode.SNAP, duration_bars=0.0, curve="linear"
            ),
            exit_transition=TransitionSpec(
                mode=TransitionMode.CROSSFADE, duration_bars=0.25, curve="sine"
            ),
            priority=0,
            blend_mode=BlendMode.OVERRIDE,
        ),
        # Phase 2: main loop (repeat-ready)
        StepSpec(
            step_id="main",
            target="ALL",
            timing=StepTiming(
                base_timing=BaseTiming(
                    mode=TimingMode.MUSICAL,
                    start_offset_bars=1.0,
                    duration_bars=3.0,
                    quantize_start=QuantizePoint.DOWNBEAT,
                    quantize_end=QuantizePoint.DOWNBEAT,
                ),
                phase_offset=None,
                internal_loop_enabled=False,
                internal_loop_mode=None,
            ),
            geometry=RolePoseGeometrySpec(
                pan_pose_by_role={
                    "OUTER_LEFT": "WIDE_LEFT",
                    "INNER_LEFT": "MID_LEFT",
                    "INNER_RIGHT": "MID_RIGHT",
                    "OUTER_RIGHT": "WIDE_RIGHT",
                },
                tilt_pose="HORIZON",
            ),
            movement=MovementSpec(
                movement_id=MovementID.SWEEP_LR,
                intensity=IntensityLevel.DRAMATIC,
                cycles=1.0,  # one sweep per 4-bar cycle window
            ),
            dimmer=DimmerSpec(
                dimmer_id=DimmerID.PULSE,
                intensity=IntensityLevel.DRAMATIC,
                min_norm=0.20,
                max_norm=1.00,
                cycles=2.0,  # two pulses per cycle window
            ),
            entry_transition=TransitionSpec(
                mode=TransitionMode.CROSSFADE, duration_bars=0.25, curve="sine"
            ),
            exit_transition=TransitionSpec(
                mode=TransitionMode.CROSSFADE, duration_bars=0.50, curve="sine"
            ),
            priority=0,
            blend_mode=BlendMode.OVERRIDE,
        ),
    ],
    metadata=TemplateMetadata(
        description=(
            "Role-based fan formation with repeat-ready L/R sweep and pulsing dimmer. "
            "Intro cascades in, then main locks into a clean loop."
        ),
        recommended_sections=["chorus", "drop", "peak"],
        energy_range=[75, 100],
        tags=["fan", "pulse", "sweep_lr", "repeat_ready", "role_pose"],
        best_with={"tempo_range": [110, 170]},
    ),
)
