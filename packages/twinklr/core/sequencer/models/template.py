"""Template Models for the moving head sequencer.

This module defines all template-related models:
- Timing models: BaseTiming, PhaseOffset, RepeatContract
- Step components: Geometry, Movement, Dimmer, StepTiming, TemplateStep
- Physical renderer step data: PhysicalMovementSpec and its PathTransform,
  PhysicalPulseSpec and its dimmer and shutter forms, named shutter, color and gobo
  states, ComponentRefs, PhaseDistribution, the VisibilityEnvelope and the
  PhysicalZoomSpec
- Template structure: Template (with its physical AttributeOverlays), TemplatePreset,
  TemplateDoc

These models define how choreography is structured and executed.
"""

from enum import StrEnum
from itertools import pairwise
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from twinklr.core.config.fixtures.presets import PresetId, StateName
from twinklr.core.config.poses import PanPose, TiltPose
from twinklr.core.sequencer.models.enum import (
    AimZone,
    ChannelName,
    ChaseOrder,
    Intensity,
    QuantizeMode,
    SemanticGroupType,
    TemplateCategory,
    TemplateRole,
    TimingMode,
)
from twinklr.core.sequencer.models.moving_heads.topology import (
    PhaseDistribution,
    check_domain_ownership,
)
from twinklr.core.sequencer.moving_heads.libraries.color import ColorPreset
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType
from twinklr.core.sequencer.moving_heads.libraries.shutter import ShutterPattern
from twinklr.core.sequencer.timing.musical_phase import exact_decimal


class RepeatMode(StrEnum):
    PING_PONG = "PING_PONG"
    JOINER = "JOINER"
    # Physical renderer only: one cycle, never repeated; see `RepeatContract`.
    ONCE = "ONCE"


class RemainderPolicy(StrEnum):
    HOLD_LAST_POSE = "HOLD_LAST_POSE"
    FADE_OUT = "FADE_OUT"
    TRUNCATE = "TRUNCATE"


class PhaseOffsetMode(StrEnum):
    NONE = "NONE"
    GROUP_ORDER = "GROUP_ORDER"


class BaseTiming(BaseModel):
    """Base timing specification for a template element.

    Defines when an element starts (relative to parent) and how long it lasts.

    Attributes:
        start_offset_bars: When to start, in bars from parent start.
        duration_bars: How long the element lasts, in bars.
        quantize_start: When to start, in bars from parent start.
        quantize_end: When to end, in bars from parent start.
    """

    model_config = ConfigDict(extra="forbid")
    mode: Literal[TimingMode.MUSICAL] = TimingMode.MUSICAL
    quantize_type: Literal[QuantizeMode.DOWNBEAT] = QuantizeMode.DOWNBEAT
    start_offset_bars: float
    duration_bars: float


class PhaseOffset(BaseModel):
    """Configuration for phase offset spreading across fixtures.

    Phase offsets create chase-like effects by starting each fixture's
    animation at a different point in the cycle.

    Attributes:
        mode: How to apply phase offsets.
        spread_bars: Total spread across all fixtures, in bars.
        wrap: Whether to wrap offsets that exceed 1.0.
    """

    model_config = ConfigDict(extra="forbid")

    mode: PhaseOffsetMode = PhaseOffsetMode.NONE
    order: ChaseOrder = ChaseOrder.LEFT_TO_RIGHT
    spread_bars: float = 0.0
    wrap: bool = True

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            removed = sorted({"group", "distribution"} & value.keys())
            if removed:
                raise ValueError(
                    f"phase-offset fields {removed} were removed because ordered fixture IDs "
                    "already determine the linear distribution"
                )
        return value


class RepeatContract(BaseModel):
    """Configuration for repeating template sections.

    Defines how a template section loops during playback.

    Attributes:
        mode: How to repeat (PING_PONG or JOINER), or ONCE: the physical renderer plays
            one cycle at its nominal rate and never repeats it. Every step of a ONCE
            template is finite and its move ends within the step, so a head without a
            phase offset reaches its terminal pose by the cycle end. After the cycle,
            HOLD_LAST_POSE extends the cues that close it to the section end (one cue,
            one phase origin): a head holds its terminal pose there, and a
            phase-lagged head completes its move first. TRUNCATE schedules nothing, so
            a lagged head that has not finished is cut where it is and held dark by
            the transaction pass. A section shorter than the cycle is refused.
        cycle_bars: Duration of one complete cycle, in bars.
        loop_step_ids: Which steps are included in the loop.
        remainder_policy: What to do with time remaining after last full cycle.
    """

    model_config = ConfigDict(extra="forbid")

    mode: RepeatMode = RepeatMode.PING_PONG
    cycle_bars: float
    loop_step_ids: list[str] = Field(default_factory=list)
    remainder_policy: RemainderPolicy = RemainderPolicy.HOLD_LAST_POSE

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict) and "repeatable" in value:
            raise ValueError("repeat field 'repeatable' was removed because scheduling ignored it")
        return value

    @model_validator(mode="after")
    def _validate_loop_step_ids(self) -> "RepeatContract":
        """A repeat schedule must declare at least one loop step."""
        if len(self.loop_step_ids) == 0:
            raise ValueError("loop_step_ids must have at least 1 item")
        return self


# =============================================================================
# Step Component Models
# =============================================================================


class Geometry(BaseModel):
    """Geometry specification for a template step.

    Defines the spatial formation of fixtures (e.g., fan, line, chevron).
    Geometry is static - it doesn't animate over time.

    Attributes:
        geometry_id: Identifier for the geometry handler (e.g., "FAN", "ROLE_POSE").
        params: Additional parameters for the geometry handler.
        pan_pose_by_role: Role-specific pan poses (for ROLE_POSE handler).
        tilt_pose: Tilt pose name (for ROLE_POSE handler).
        aim_zone: Aim zone (e.g., "CROWD", "SKY").
    """

    model_config = ConfigDict(extra="forbid")

    geometry_type: GeometryType = GeometryType.NONE
    params: dict[str, Any] = Field(default_factory=dict)

    # ROLE_POSE specific fields
    pan_pose_by_role: dict[TemplateRole, PanPose] | None = None
    tilt_pose: TiltPose = TiltPose.HORIZON
    aim_zone: AimZone = AimZone.HORIZON


MIN_PHYSICAL_PERIOD_BEATS = 1 / 64
"""Shortest physical period: 1/64 beat is under 8 ms at 120 BPM, already far below one
20 ms frame, so anything shorter is an authoring error rather than a pulse."""


RELATIVE_PATH_SHAPES = ("circle", "lissajous", "sweep")
"""Shapes evaluated as a centered displacement about the base aim; only these take a
`PathTransform`."""


class PathTransform(BaseModel):
    """Template-owned transform of a relative path (`RELATIVE_PATH_SHAPES`).

    `rotation_deg` turns the centered displacement before each axis is scaled by its
    extent. `phase_cycles` shifts where along its travel the path is, in cycles of its
    period, at its exact decimal value. `reverse` runs the travel backwards; pulses and
    every other phase domain are unaffected by either.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rotation_deg: float = Field(default=0.0, allow_inf_nan=False)
    reverse: bool = False
    phase_cycles: float = Field(default=0.0, allow_inf_nan=False)


class PhysicalMovementSpec(BaseModel):
    """Physical motion of a step for the physical renderer, in fixture-local degrees.

    Template-owned renderer data, never an LLM control. Reach (`*_extent_deg`) and
    rate (`period_beats`) are independent. Kernels: `hold` keeps the start pose;
    `sine_pan`/`sine_tilt` add the selected extent times sin(2*pi*phase) and are
    periodic; `linear` moves from start to start plus extent over one period, then
    holds, and is finite. `circle`, `lissajous` (periodic) and `sweep` (periodic or
    finite) move about the start pose; each extent is that axis's maximum signed
    displacement before rotation, and `transform` rotates, shifts or reverses them
    (`evaluate_physical_path` states each formula). `lissajous_ratio` is the pan and
    tilt cycles per period, default 1:2. A start angle left unset comes from the
    step's position reference (`TemplateStep.component_refs`); a step without one
    must set both.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    shape: Literal["hold", "sine_pan", "sine_tilt", "linear", "circle", "lissajous", "sweep"]
    mode: Literal["periodic", "finite"]
    start_pan_deg: float | None = Field(default=None, allow_inf_nan=False)
    start_tilt_deg: float | None = Field(default=None, allow_inf_nan=False)
    pan_extent_deg: float = Field(default=0.0, allow_inf_nan=False)
    tilt_extent_deg: float = Field(default=0.0, allow_inf_nan=False)
    period_beats: float | None = Field(
        default=None,
        ge=MIN_PHYSICAL_PERIOD_BEATS,
        allow_inf_nan=False,
        description="Required unless shape is hold",
    )
    # Left out of dumps when absent, so existing physical templates dump as before.
    lissajous_ratio: tuple[PositiveInt, PositiveInt] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    transform: PathTransform | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def _validate_kernel(self) -> "PhysicalMovementSpec":
        if self.shape == "linear" and self.mode != "finite":
            raise ValueError("linear motion is finite; periodic linear is not supported")
        if self.shape in ("sine_pan", "sine_tilt") and self.mode != "periodic":
            raise ValueError(f"{self.shape} is periodic; finite sine is not supported")
        if self.shape in ("circle", "lissajous") and self.mode != "periodic":
            raise ValueError(f"{self.shape} is periodic; a finite {self.shape} is not supported")
        if self.lissajous_ratio is not None and self.shape != "lissajous":
            raise ValueError("lissajous_ratio applies only to the lissajous shape")
        if self.transform is not None and self.shape not in RELATIVE_PATH_SHAPES:
            raise ValueError(
                f"transform applies only to the relative shapes {list(RELATIVE_PATH_SHAPES)}; "
                f"{self.shape} keeps its Phase 1 meaning"
            )
        if self.shape == "hold":
            if self.pan_extent_deg or self.tilt_extent_deg or self.period_beats is not None:
                raise ValueError("hold takes no extent or period")
            return self
        if self.period_beats is None:
            raise ValueError(f"{self.shape} needs period_beats")
        unused = {"sine_pan": self.tilt_extent_deg, "sine_tilt": self.pan_extent_deg}
        if unused.get(self.shape):
            raise ValueError(f"{self.shape} moves one axis; the other extent must be zero")
        if self.shape == "sweep":
            self._validate_sweep()
        return self

    def _validate_sweep(self) -> None:
        """Refuse sweep settings that would change nothing: reversing a periodic sweep
        (it is symmetric in time), and an extent on an axis the turned sweep never moves
        (tilt unless turned off the pan line, pan when turned a quarter turn)."""
        transform = self.transform or PathTransform()
        if transform.reverse and self.mode == "periodic":
            raise ValueError(
                "reverse leaves a periodic sweep unchanged; shift it with phase_cycles instead"
            )
        rest = transform.rotation_deg % 180
        if rest == 0 and self.tilt_extent_deg:
            raise ValueError("a sweep along pan ignores tilt_extent_deg; set it to zero")
        if rest == 90 and self.pan_extent_deg:
            raise ValueError("a sweep turned onto tilt ignores pan_extent_deg; set it to zero")


class PhysicalPulseSpec(BaseModel):
    """A musical-phase pulse: high while the fractional phase is in `[0, duty_cycle)`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    period_beats: float = Field(ge=MIN_PHYSICAL_PERIOD_BEATS, allow_inf_nan=False)
    duty_cycle: float = Field(gt=0, le=1)
    phase_cycles: float = Field(default=0.0, allow_inf_nan=False)


class PhysicalDimmerPulse(PhysicalPulseSpec):
    """A dimmer pulse between explicit normalized levels; duty 1 holds `high`."""

    low: float = Field(ge=0, le=1)
    high: float = Field(ge=0, le=1)


class PhysicalShutterPulse(PhysicalPulseSpec):
    """A shutter pulse between named profile states."""

    low_state: StateName
    high_state: StateName


class VisibilityEnvelope(BaseModel):
    """Where along its movement a physical step is lit; dark everywhere else.

    The phases are fractions of the step's movement period (`period_beats`), read at the
    fixture's own movement phase: the step phase minus its pan/tilt distribution offset,
    so a lagging head's lit window lags with its path, and, where a cycle continues the
    previous cycle's phase (a step spanning its cycle, cycles meeting at a quantized
    frame), measured on from that phase. The window is in phase before the
    path's own `transform` (`phase_cycles`, `reverse`), which moves no pulse either; a
    transform changes which arc of the path is lit, not when. A periodic movement is lit
    in `[visible_phase_start, visible_phase_end)` of every cycle. A finite movement's
    phase clamps to `[0, 1]` as its motion does and a window ending at 1 includes 1, so
    it stays lit through the terminal hold (and takes no release); one ending before 1
    leaves the hold dark. The envelope replaces the dimmer: lit at `level`, ramping
    linearly up over `attack_beats` from the window start and down over `release_beats`
    to the window end. The dark complement is left between cues, so the transaction pass
    performs every dark return.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    visible_phase_start: float = Field(ge=0, lt=1, allow_inf_nan=False)
    visible_phase_end: float = Field(gt=0, le=1, allow_inf_nan=False)
    attack_beats: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    release_beats: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    level: float = Field(default=1.0, gt=0, le=1)

    @model_validator(mode="after")
    def _validate_window(self) -> "VisibilityEnvelope":
        if self.visible_phase_end <= self.visible_phase_start:
            raise ValueError("visible_phase_end must be after visible_phase_start")
        return self


class PhysicalZoomSpec(BaseModel):
    """The beam angle of a physical step on the fixture's zoom axis, in degrees.

    Template-owned renderer data, never an LLM control. `hold` keeps `start_deg`;
    `sine` adds `extent_deg * sin(2*pi*phase)`, where the phase is the step's movement
    phase (`movement.physical.period_beats`) at the head's pan distribution offset, so
    the beam follows the path's own rate and wave. A fixture whose profile declares no
    zoom axis refuses the step, unless `if_unsupported` is `omit_optional_zoom`: the step
    then plays without its zoom, and the render trace records that.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    shape: Literal["hold", "sine"]
    start_deg: float = Field(allow_inf_nan=False)
    extent_deg: float = Field(default=0.0, allow_inf_nan=False)
    if_unsupported: Literal["error", "omit_optional_zoom"] = "error"

    @model_validator(mode="after")
    def _validate_kernel(self) -> "PhysicalZoomSpec":
        if self.shape == "hold" and self.extent_deg:
            raise ValueError("a zoom hold takes no extent_deg")
        if self.shape == "sine" and not self.extent_deg:
            raise ValueError("a zoom sine needs a nonzero extent_deg")
        return self


class AttributeOverlay(BaseModel):
    """A temporary wheel state over part of every cycle of a physical template.

    `start_beats` and `end_beats` are offsets from the cycle start and may span a step
    boundary. Each fixture is held dark for `mask_beats` after the start while the wheel
    turns in, shows the base cues with `channel` set to the overlay's state, and is held
    dark for `mask_beats` before the end while it turns back; from the end it resumes
    whichever base step is in force then (`release` `resume_base`). The state is named:
    `state` in each fixture's profile, or the `channel` entry of the rig attribute preset
    `attribute_preset_id`; never a byte.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_beats: float = Field(ge=0, allow_inf_nan=False)
    end_beats: float = Field(allow_inf_nan=False)
    mask_beats: float = Field(gt=0, allow_inf_nan=False)
    channel: Literal["color", "gobo"]
    state: StateName | None = None
    attribute_preset_id: PresetId | None = None
    release: Literal["resume_base"] = "resume_base"

    @model_validator(mode="after")
    def _validate_overlay(self) -> "AttributeOverlay":
        if (self.state is None) == (self.attribute_preset_id is None):
            raise ValueError("an overlay names exactly one of state and attribute_preset_id")
        if self.end_beats - self.start_beats <= 2 * self.mask_beats:
            raise ValueError(
                "an overlay must outlast its two masks: end_beats - start_beats > 2 * mask_beats"
            )
        return self


class ComponentRefs(BaseModel):
    """Rig presets a physical step names, resolved per fixture from the fixture group.

    `position_id` supplies each start angle the step leaves unset; the attribute presets
    supply each held shutter, color, gobo or dimmer channel the step does not set
    itself. Two attribute presets may not both set a channel of one fixture.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    position_id: PresetId | None = None
    attribute_preset_ids: tuple[PresetId, ...] = ()

    @model_validator(mode="after")
    def _validate_refs(self) -> "ComponentRefs":
        if self.position_id is None and not self.attribute_preset_ids:
            raise ValueError("component_refs names no position or attribute preset")
        if len(set(self.attribute_preset_ids)) != len(self.attribute_preset_ids):
            raise ValueError("attribute_preset_ids names a preset more than once")
        return self


class Movement(BaseModel):
    """Movement specification for a template step.

    Defines how fixtures move over time (e.g., sweep, circle, nod).
    Movement is relative to the geometry baseline.

    Attributes:
        movement_id: Identifier for the movement handler (e.g., "SWEEP_LR").
        intensity: Movement intensity preset (e.g., "SMOOTH", "FAST").
        cycles: Number of movement cycles in the step duration.
        params: Additional parameters for the movement handler.
    """

    model_config = ConfigDict(extra="forbid")

    movement_type: MovementType = MovementType.NONE
    intensity: Intensity = Intensity.SMOOTH
    cycles: float = 1.0
    params: dict[str, Any] = Field(default_factory=dict)
    # Physical renderer only. Left out of dumps when absent so legacy template
    # fingerprints are unchanged.
    physical: PhysicalMovementSpec | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            removed = sorted(
                {"amplitude_override", "frequency_override", "center_offset_override"}
                & value.keys()
            )
            if removed:
                raise ValueError(
                    f"movement fields {removed} were removed because they never affected output"
                )
        return value


class Dimmer(BaseModel):
    """Dimmer specification for a template step.

    Defines the brightness/intensity pattern over time.

    Attributes:
        dimmer_id: Identifier for the dimmer handler (e.g., "PULSE", "FADE_IN").
        intensity: Dimmer intensity preset.
        min_norm: Minimum normalized brightness [0, 1].
        max_norm: Maximum normalized brightness [0, 1].
        cycles: Number of dimmer cycles in the step duration.
        params: Additional parameters for the dimmer handler.
    """

    model_config = ConfigDict(extra="forbid")

    dimmer_type: DimmerType = DimmerType.NONE
    intensity: Intensity = Intensity.SMOOTH
    min_norm: float = 0.0
    max_norm: float = 1.0
    params: dict[str, Any] = Field(default_factory=dict)
    # Physical renderer only; left out of dumps when absent.
    physical: PhysicalDimmerPulse | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict) and "cycles" in value:
            raise ValueError("dimmer field 'cycles' was removed because handlers ignored it")
        return value

    @model_validator(mode="after")
    def _validate_range(self) -> "Dimmer":
        """Validate max_norm >= min_norm."""
        if self.max_norm < self.min_norm:
            raise ValueError(f"max_norm ({self.max_norm}) < min_norm ({self.min_norm})")
        return self


class Color(BaseModel):
    """Discrete colour-wheel selection for a template step."""

    model_config = ConfigDict(extra="forbid")

    preset: ColorPreset

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict) and "params" in value:
            raise ValueError("color field 'params' was removed because no handler read it")
        return value


class Shutter(BaseModel):
    """Discrete or patterned shutter selection for a template step."""

    model_config = ConfigDict(extra="forbid")

    pattern: ShutterPattern

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict) and "params" in value:
            raise ValueError("shutter field 'params' was removed because no handler read it")
        return value


class Gobo(BaseModel):
    """Discrete gobo-wheel selection for a template step."""

    model_config = ConfigDict(extra="forbid")

    pattern: GoboPattern

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict) and "params" in value:
            raise ValueError("gobo field 'params' was removed because no handler read it")
        return value


class StepTiming(BaseModel):
    """Timing specification for a template step.

    Combines base timing with optional phase offset configuration.

    Attributes:
        base_timing: When the step starts and how long it lasts.
        phase_offset: Optional phase offset configuration.
    """

    model_config = ConfigDict(extra="forbid")

    base_timing: BaseTiming
    phase_offset: PhaseOffset = Field(
        default_factory=lambda: PhaseOffset(mode=PhaseOffsetMode.NONE)
    )


class TemplateStep(BaseModel):
    """A single step in a template.

    Steps are the atomic units of choreography. Each step defines:
    - Which fixtures to target
    - When it happens (timing)
    - The spatial formation (geometry)
    - How fixtures move (movement)
    - The brightness pattern (dimmer)

    Attributes:
        step_id: Unique identifier for this step within the template.
        target: Target group for this step (must exist in template groups).
        timing: When and how long this step runs.
        geometry: Spatial formation specification.
        movement: Motion specification.
        dimmer: Brightness specification.
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str
    target: SemanticGroupType = SemanticGroupType.ALL
    timing: StepTiming
    geometry: Geometry
    movement: Movement
    dimmer: Dimmer
    color: Color | None = None
    shutter: Shutter | None = None
    gobo: Gobo | None = None
    # Physical renderer only; left out of dumps when absent. Step-level because
    # `Shutter` requires a legacy pattern, which a physical step must not carry.
    physical_shutter: PhysicalShutterPulse | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    # Physical renderer only; left out of dumps when absent. Named profile states held
    # for the whole step, never a byte. A static shutter excludes the pulse form.
    physical_shutter_state: StateName | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    physical_color: StateName | None = Field(default=None, exclude_if=lambda value: value is None)
    physical_gobo: StateName | None = Field(default=None, exclude_if=lambda value: value is None)
    # Physical renderer only; left out of dumps when absent. The step's cues opt into
    # the run's `moving_heads.reposition_fallback` when it names the same mode.
    physical_reposition_fallback: Literal["preserve_aim", "drop_accent"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    # Physical renderer only; left out of dumps when absent. Named rig presets for the
    # start angles and held channels the step leaves unset.
    component_refs: ComponentRefs | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    # Physical renderer only; left out of dumps when empty. Phase spread over the rig
    # topology, each distribution over its own domains.
    physical_distribution: tuple[PhaseDistribution, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    # Physical renderer only; left out of dumps when absent. Lights only part of each
    # movement period and replaces the dimmer.
    physical_visibility: VisibilityEnvelope | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    # Physical renderer only; left out of dumps when absent. The beam angle on a
    # profile's zoom axis.
    physical_zoom: PhysicalZoomSpec | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @property
    def has_physical_data(self) -> bool:
        """Whether any component carries data for the physical renderer."""
        return (
            self.movement.physical is not None
            or self.dimmer.physical is not None
            or self.physical_shutter is not None
            or self.physical_shutter_state is not None
            or self.physical_color is not None
            or self.physical_gobo is not None
            or self.physical_reposition_fallback is not None
            or self.component_refs is not None
            or bool(self.physical_distribution)
            or self.physical_visibility is not None
            or self.physical_zoom is not None
        )

    @model_validator(mode="after")
    def _validate_physical_shutter(self) -> "TemplateStep":
        if self.physical_shutter is not None and self.physical_shutter_state is not None:
            raise ValueError("set physical_shutter_state or physical_shutter, not both")
        return self

    @model_validator(mode="after")
    def _validate_visibility(self) -> "TemplateStep":
        """An envelope needs a movement period, owns the dimmer, and reads one movement
        phase, so pan and tilt share their distribution offset."""
        envelope = self.physical_visibility
        if envelope is None:
            return self
        movement = self.movement.physical
        if movement is None or movement.period_beats is None:
            raise ValueError(
                f"step {self.step_id!r}: physical_visibility needs movement.physical with a "
                "period; a hold step has no movement phase to light"
            )
        if self.dimmer.physical is not None or self.physical_shutter is not None:
            raise ValueError(
                f"step {self.step_id!r}: physical_visibility replaces the dimmer and needs a "
                "static shutter; remove dimmer.physical and the physical_shutter pulse"
            )
        window_beats = exact_decimal(envelope.visible_phase_end) - exact_decimal(
            envelope.visible_phase_start
        )
        ramps = exact_decimal(envelope.attack_beats) + exact_decimal(envelope.release_beats)
        if ramps > window_beats * exact_decimal(movement.period_beats):
            raise ValueError(
                f"step {self.step_id!r}: attack_beats plus release_beats exceed the lit window "
                f"of {float(window_beats * exact_decimal(movement.period_beats)):g} beats"
            )
        if movement.mode == "finite" and envelope.visible_phase_end == 1 and envelope.release_beats:
            raise ValueError(
                f"step {self.step_id!r}: a finite movement's window ending at 1 stays lit "
                "through the terminal hold, so it takes no release_beats; end the window "
                "before 1 to fade out"
            )
        owners = [
            [ChannelName.PAN in spec.domains, ChannelName.TILT in spec.domains]
            for spec in self.physical_distribution
            if {ChannelName.PAN, ChannelName.TILT} & set(spec.domains)
        ]
        if owners and owners != [[True, True]]:
            raise ValueError(
                f"step {self.step_id!r}: physical_visibility reads the movement phase, so pan "
                "and tilt must be distributed together, by one distribution"
            )
        light = [
            domain.value
            for spec in self.physical_distribution
            for domain in spec.domains
            if domain in (ChannelName.DIMMER, ChannelName.SHUTTER)
        ]
        if light:
            raise ValueError(
                f"step {self.step_id!r}: physical_visibility follows the movement phase; "
                f"distributing {light} would do nothing"
            )
        return self

    @model_validator(mode="after")
    def _validate_zoom(self) -> "TemplateStep":
        """A zoom sine waves on the movement phase, so it needs a periodic movement."""
        zoom = self.physical_zoom
        movement = self.movement.physical
        if (
            zoom is not None
            and zoom.shape == "sine"
            and (movement is None or movement.mode != "periodic" or movement.period_beats is None)
        ):
            raise ValueError(
                f"step {self.step_id!r}: a physical_zoom sine waves on the movement phase, so "
                "it needs a periodic movement.physical with a period"
            )
        return self

    @model_validator(mode="after")
    def _validate_distribution(self) -> "TemplateStep":
        check_domain_ownership(self.physical_distribution)
        return self

    @model_validator(mode="after")
    def _validate_pose_source(self) -> "TemplateStep":
        """Each start angle is set on the step or supplied by a position reference."""
        movement = self.movement.physical
        if movement is None or (
            self.component_refs is not None and self.component_refs.position_id is not None
        ):
            return self
        for name in ("start_pan_deg", "start_tilt_deg"):
            if getattr(movement, name) is None:
                raise ValueError(
                    f"step {self.step_id!r} sets no movement.physical.{name} and no "
                    "component_refs.position_id: an axis nothing sets is never centered"
                )
        return self

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            removed = sorted(
                {"entry_transition", "exit_transition", "priority", "blend_mode"} & value.keys()
            )
            if removed:
                raise ValueError(
                    f"template-step fields {removed} were removed because they never affected output"
                )
        return value


# =============================================================================
# Template Structure Models
# =============================================================================


class TemplateMetadata(BaseModel):
    """Metadata for a template.

    Optional descriptive information about the template.

    Attributes:
        tags: Categorization tags (e.g., "energetic", "sweep").
        energy_range: Suggested energy level range (min, max) 0-100.
        description: Human-readable description.
    """

    model_config = ConfigDict(extra="forbid")

    tags: list[str] = Field(default_factory=list)
    recommended_sections: list[str] = Field(default_factory=list)
    energy_range: tuple[int, int] | None = None
    description: str | None = None


class StepPatch(BaseModel):
    """Patch to apply to a template step.

    Used by presets to override step properties.

    Attributes:
        geometry: Partial geometry overrides.
        movement: Partial movement overrides.
        dimmer: Partial dimmer overrides.
        timing: Partial timing overrides.
    """

    model_config = ConfigDict(extra="forbid")

    geometry: dict[str, Any] | None = None
    movement: dict[str, Any] | None = None
    dimmer: dict[str, Any] | None = None
    color: dict[str, Any] | None = None
    shutter: dict[str, Any] | None = None
    gobo: dict[str, Any] | None = None
    timing: dict[str, Any] | None = None


class TemplatePreset(BaseModel):
    """A named preset for a template.

    Presets allow variations of a template (e.g., "CHILL", "ENERGETIC")
    by overriding default values and step properties.

    Attributes:
        preset_id: Unique identifier for this preset.
        name: Human-readable name.
        defaults: Default value overrides.
        step_patches: Per-step property overrides.
    """

    model_config = ConfigDict(extra="forbid")

    preset_id: str
    name: str
    defaults: dict[str, Any] = Field(default_factory=dict)
    step_patches: dict[str, StepPatch] = Field(default_factory=dict)


class Template(BaseModel):
    """Complete template definition.

    Templates are portable choreography definitions that can be applied
    to any rig. They reference groups and roles, not fixture IDs.

    Attributes:
        template_id: Unique identifier for this template.
        version: Template version number.
        name: Human-readable name.
        category: Template category (e.g., "movement", "complex").
        roles: List of role names used by this template.
        groups: Mapping of group names to lists of roles.
        repeat: Repeat/loop configuration.
        defaults: Default parameter values.
        steps: List of template steps.
        metadata: Optional template metadata.
    """

    model_config = ConfigDict(extra="forbid")

    template_id: str
    version: int
    name: str
    category: TemplateCategory

    repeat: RepeatContract
    defaults: dict[str, Any] = Field(default_factory=dict)
    steps: list["TemplateStep"] = Field(default_factory=list)
    metadata: TemplateMetadata | None = None
    # Physical renderer only; left out of dumps when empty, refused by the legacy compile.
    physical_overlays: tuple[AttributeOverlay, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )

    @model_validator(mode="before")
    @classmethod
    def _set_default_metadata(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Set default metadata if not provided."""
        if isinstance(data, dict) and "roles" in data:
            raise ValueError(
                "template field 'roles' was removed because fixture context is the role authority"
            )
        if isinstance(data, dict) and data.get("metadata") is None:
            data["metadata"] = {}
        return data

    @model_validator(mode="after")
    def _validate_loop_steps_and_targets(self) -> "Template":
        """Validate loop_step_ids reference real steps and targets reference real groups."""
        step_ids = {s.step_id for s in self.steps}

        # Validate loop_step_ids reference existing steps
        for loop_step_id in self.repeat.loop_step_ids:
            if loop_step_id not in step_ids:
                raise ValueError(f"Loop step '{loop_step_id}' not found in template steps")

        # Validate step targets reference existing groups
        for step in self.steps:
            if step.target not in list(SemanticGroupType):
                raise ValueError(f"Step '{step.step_id}' targets unknown group: '{step.target}'")

        if self.repeat.mode is RepeatMode.ONCE:
            self._require_finite_steps()
        self._validate_overlays()
        return self

    def _validate_overlays(self) -> None:
        """Overlays on one channel may not overlap; a PING_PONG cycle mirrors its steps,
        which an overlay's offsets from the cycle start would not follow."""
        if not self.physical_overlays:
            return
        if self.repeat.mode is RepeatMode.PING_PONG:
            raise ValueError(
                "physical_overlays are offsets from the cycle start; repeat mode PING_PONG "
                "mirrors every other cycle, so use JOINER or ONCE"
            )
        for channel in ("color", "gobo"):
            spans = sorted(
                (overlay.start_beats, overlay.end_beats)
                for overlay in self.physical_overlays
                if overlay.channel == channel
            )
            for (_, end), (start, _) in pairwise(spans):
                if start < end:
                    raise ValueError(
                        f"two physical_overlays on {channel} overlap at beat {start:g}; an "
                        "overlay on a channel must end before the next starts"
                    )

    def _require_finite_steps(self) -> None:
        """A ONCE cycle ends in a terminal state its remainder holds, so each step must
        declare finite physical motion and no dimmer or shutter pulse below duty 1."""
        for step in self.steps:
            movement = step.movement.physical
            if movement is None or movement.mode != "finite":
                raise ValueError(
                    f"repeat mode ONCE needs every step finite, but step {step.step_id!r} "
                    "declares no finite movement.physical (mode 'finite')"
                )
            pulses = (
                ("dimmer.physical", step.dimmer.physical),
                ("physical_shutter", step.physical_shutter),
            )
            for name, pulse in pulses:
                if pulse is not None and pulse.duty_cycle != 1:
                    raise ValueError(
                        f"repeat mode ONCE needs every step finite, but step {step.step_id!r} "
                        f"pulses {name} with duty_cycle {pulse.duty_cycle}"
                    )


class TemplateDoc(BaseModel):
    """Complete template document with presets.

    This is the top-level structure for template files.

    Attributes:
        template: The template definition.
        presets: List of available presets.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    template: Template
    presets: list[TemplatePreset] = Field(default_factory=list)
