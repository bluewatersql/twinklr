"""Template Models for the moving head sequencer.

This module defines all template-related models:
- Timing models: BaseTiming, RepeatContract
- Step components: Movement and its PathTransform, PulseSpec and its dimmer and
  shutter forms, named shutter, color and gobo states, ComponentRefs,
  PhaseDistribution, the VisibilityEnvelope, the ZoomSpec, StepTiming and TemplateStep
- Template structure: Template (with its AttributeOverlays), TemplatePreset,
  TemplateDoc

These models define how choreography is structured and executed.
"""

from enum import StrEnum
from itertools import pairwise
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from twinklr.core.config.fixtures.presets import PresetId, StateName
from twinklr.core.sequencer.models.enum import (
    ChannelName,
    QuantizeMode,
    SemanticGroupType,
    TemplateCategory,
    TimingMode,
)
from twinklr.core.sequencer.models.moving_heads.topology import (
    PhaseDistribution,
    check_domain_ownership,
)
from twinklr.core.sequencer.timing.musical_phase import exact_decimal


class RepeatMode(StrEnum):
    PING_PONG = "PING_PONG"
    JOINER = "JOINER"
    # One cycle, never repeated; see `RepeatContract`.
    ONCE = "ONCE"


class RemainderPolicy(StrEnum):
    HOLD_LAST_POSE = "HOLD_LAST_POSE"
    FADE_OUT = "FADE_OUT"
    TRUNCATE = "TRUNCATE"


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


class RepeatContract(BaseModel):
    """Configuration for repeating template sections.

    Defines how a template section loops during playback.

    Attributes:
        mode: How to repeat (PING_PONG or JOINER), or ONCE: the renderer plays
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


MIN_PERIOD_BEATS = 1 / 64
"""Shortest period: 1/64 beat is under 8 ms at 120 BPM, already far below one
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


class Movement(BaseModel):
    """Movement of a template step, in fixture-local degrees.

    Template-owned renderer data, never an LLM control. Reach (`*_extent_deg`) and
    rate (`period_beats`) are independent. Kernels: `hold` keeps the start pose;
    `sine_pan`/`sine_tilt` add the selected extent times sin(2*pi*phase) and are
    periodic; `linear` moves from start to start plus extent over one period, then
    holds, and is finite. `circle`, `lissajous` (periodic) and `sweep` (periodic or
    finite) move about the start pose; each extent is that axis's maximum signed
    displacement before rotation, and `transform` rotates, shifts or reverses them
    (`evaluate_path` states each formula). `lissajous_ratio` is the pan and
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
        ge=MIN_PERIOD_BEATS,
        allow_inf_nan=False,
        description="Required unless shape is hold",
    )
    # Left out of dumps when absent.
    lissajous_ratio: tuple[PositiveInt, PositiveInt] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    transform: PathTransform | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        _reject_removed_movement_fields(value)
        return value

    @model_validator(mode="after")
    def _validate_kernel(self) -> "Movement":
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


class PulseSpec(BaseModel):
    """A musical-phase pulse: high while the fractional phase is in `[0, duty_cycle)`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    period_beats: float = Field(ge=MIN_PERIOD_BEATS, allow_inf_nan=False)
    duty_cycle: float = Field(gt=0, le=1)
    phase_cycles: float = Field(default=0.0, allow_inf_nan=False)


class DimmerPulse(PulseSpec):
    """A dimmer pulse between explicit normalized levels; duty 1 holds `high`."""

    low: float = Field(ge=0, le=1)
    high: float = Field(ge=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        _reject_removed_dimmer_fields(value)
        return value


class ShutterPulse(PulseSpec):
    """A shutter pulse between named profile states."""

    low_state: StateName
    high_state: StateName


class VisibilityEnvelope(BaseModel):
    """Where along its movement a step is lit; dark everywhere else.

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


class ZoomSpec(BaseModel):
    """The beam angle of a step on the fixture's zoom axis, in degrees.

    Template-owned renderer data, never an LLM control. `hold` keeps `start_deg`;
    `sine` adds `extent_deg * sin(2*pi*phase)`, where the phase is the step's movement
    phase (`movement.period_beats`) at the head's pan distribution offset, so
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
    def _validate_kernel(self) -> "ZoomSpec":
        if self.shape == "hold" and self.extent_deg:
            raise ValueError("a zoom hold takes no extent_deg")
        if self.shape == "sine" and not self.extent_deg:
            raise ValueError("a zoom sine needs a nonzero extent_deg")
        return self


class AttributeOverlay(BaseModel):
    """A temporary wheel state over part of every cycle of a template.

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
    """Rig presets a step names, resolved per fixture from the fixture group.

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


def _reject_removed_movement_fields(value: object) -> None:
    if isinstance(value, dict) and "physical" in value:
        raise ValueError(
            "movement field 'physical' was flattened into movement: move its keys (shape, "
            "mode, start angles, extents, period_beats, ...) up into movement itself"
        )
    if isinstance(value, dict):
        removed = sorted(
            {"amplitude_override", "frequency_override", "center_offset_override"} & value.keys()
        )
        if removed:
            raise ValueError(
                f"movement fields {removed} were removed because they never affected output"
            )
        removed = sorted({"movement_type", "intensity", "cycles", "params"} & value.keys())
        if removed:
            raise ValueError(
                f"movement fields {removed} were removed with the old moving-head "
                "renderer, their only reader; delete them and state the motion in "
                "movement (shape, mode, start angles, extents and period_beats)"
            )


def _reject_removed_dimmer_fields(value: object) -> None:
    if isinstance(value, dict) and "physical" in value:
        if value["physical"] is None:
            raise ValueError(
                "dimmer field 'physical' was flattened into dimmer, and a null pulse is no "
                "pulse: leave dimmer out"
            )
        raise ValueError(
            "dimmer field 'physical' was flattened into dimmer: move its keys (period_beats, "
            "duty_cycle, phase_cycles, low, high) up into dimmer itself"
        )
    if isinstance(value, dict) and "cycles" in value:
        raise ValueError("dimmer field 'cycles' was removed because handlers ignored it")
    if isinstance(value, dict):
        removed = sorted(
            {"dimmer_type", "intensity", "min_norm", "max_norm", "params"} & value.keys()
        )
        if removed:
            raise ValueError(
                f"dimmer fields {removed} were removed with the old moving-head "
                "renderer, their only reader; delete them and state the pulse in "
                "dimmer (period_beats, duty_cycle, phase_cycles, low and high)"
            )


def _reject_removed_timing_fields(value: object) -> None:
    if isinstance(value, dict) and "phase_offset" in value:
        raise ValueError(
            "timing field 'phase_offset' was removed with the old moving-head renderer, its "
            "only reader; delete it and spread phase with distribution"
        )


class StepTiming(BaseModel):
    """Timing specification for a template step.

    Attributes:
        base_timing: When the step starts and how long it lasts.
    """

    model_config = ConfigDict(extra="forbid")

    base_timing: BaseTiming

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        _reject_removed_timing_fields(value)
        return value


RENAMED_STEP_FIELDS = {
    "physical_shutter": "shutter",
    "physical_shutter_state": "shutter_state",
    "physical_color": "color",
    "physical_gobo": "gobo",
    "physical_reposition_fallback": "reposition_fallback",
    "physical_distribution": "distribution",
    "physical_visibility": "visibility",
    "physical_zoom": "zoom",
}
"""Template-step keys renamed when the moving-head renderer became the only one: each is
refused by name with its new key."""


class TemplateStep(BaseModel):
    """A single step in a template.

    Steps are the atomic units of choreography. Each step defines:
    - Which fixtures to target
    - When it happens (timing)
    - How fixtures move (movement)
    - The brightness pattern (a dimmer pulse, or a visibility envelope)
    - The shutter, color, gobo and zoom it holds or plays

    Attributes:
        step_id: Unique identifier for this step within the template.
        target: Target group for this step (must exist in template groups).
        timing: When and how long this step runs.
        movement: Motion specification.
        dimmer: A pulse between normalized levels, or none (held by a component
            reference, or replaced by a visibility envelope).
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str
    target: SemanticGroupType = SemanticGroupType.ALL
    timing: StepTiming
    movement: Movement
    # Left out of dumps when absent.
    dimmer: DimmerPulse | None = Field(default=None, exclude_if=lambda value: value is None)
    # Left out of dumps when absent.
    shutter: ShutterPulse | None = Field(default=None, exclude_if=lambda value: value is None)
    # Left out of dumps when absent. Named profile states held
    # for the whole step, never a byte. A static shutter excludes the pulse form.
    shutter_state: StateName | None = Field(default=None, exclude_if=lambda value: value is None)
    color: StateName | None = Field(default=None, exclude_if=lambda value: value is None)
    gobo: StateName | None = Field(default=None, exclude_if=lambda value: value is None)
    # Left out of dumps when absent. The step's cues opt into
    # the run's `moving_heads.reposition_fallback` when it names the same mode.
    reposition_fallback: Literal["preserve_aim", "drop_accent"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    # Left out of dumps when absent. Named rig presets for the
    # start angles and held channels the step leaves unset.
    component_refs: ComponentRefs | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    # Left out of dumps when empty. Phase spread over the rig
    # topology, each distribution over its own domains.
    distribution: tuple[PhaseDistribution, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    # Left out of dumps when absent. Lights only part of each
    # movement period and replaces the dimmer.
    visibility: VisibilityEnvelope | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    # Left out of dumps when absent. The beam angle on a
    # profile's zoom axis.
    zoom: ZoomSpec | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def _validate_shutter(self) -> "TemplateStep":
        if self.shutter is not None and self.shutter_state is not None:
            raise ValueError("set shutter_state or shutter, not both")
        return self

    @model_validator(mode="after")
    def _validate_visibility(self) -> "TemplateStep":
        """An envelope needs a movement period, owns the dimmer, and reads one movement
        phase, so pan and tilt share their distribution offset."""
        envelope = self.visibility
        if envelope is None:
            return self
        movement = self.movement
        if movement.period_beats is None:
            raise ValueError(
                f"step {self.step_id!r}: visibility needs a movement with a period; a hold "
                "step has no movement phase to light"
            )
        if self.dimmer is not None or self.shutter is not None:
            raise ValueError(
                f"step {self.step_id!r}: visibility replaces the dimmer and needs a static "
                "shutter; remove the dimmer and the shutter pulse"
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
            for spec in self.distribution
            if {ChannelName.PAN, ChannelName.TILT} & set(spec.domains)
        ]
        if owners and owners != [[True, True]]:
            raise ValueError(
                f"step {self.step_id!r}: visibility reads the movement phase, so pan "
                "and tilt must be distributed together, by one distribution"
            )
        light = [
            domain.value
            for spec in self.distribution
            for domain in spec.domains
            if domain in (ChannelName.DIMMER, ChannelName.SHUTTER)
        ]
        if light:
            raise ValueError(
                f"step {self.step_id!r}: visibility follows the movement phase; "
                f"distributing {light} would do nothing"
            )
        return self

    @model_validator(mode="after")
    def _validate_zoom(self) -> "TemplateStep":
        """A zoom sine waves on the movement phase, so it needs a periodic movement."""
        zoom = self.zoom
        movement = self.movement
        if (
            zoom is not None
            and zoom.shape == "sine"
            and (movement.mode != "periodic" or movement.period_beats is None)
        ):
            raise ValueError(
                f"step {self.step_id!r}: a zoom sine waves on the movement phase, so it needs "
                "a periodic movement with a period"
            )
        return self

    @model_validator(mode="after")
    def _validate_distribution(self) -> "TemplateStep":
        check_domain_ownership(self.distribution)
        return self

    @model_validator(mode="after")
    def _validate_pose_source(self) -> "TemplateStep":
        """Each start angle is set on the step or supplied by a position reference."""
        movement = self.movement
        if self.component_refs is not None and self.component_refs.position_id is not None:
            return self
        for name in ("start_pan_deg", "start_tilt_deg"):
            if getattr(movement, name) is None:
                raise ValueError(
                    f"step {self.step_id!r} sets no movement.{name} and no "
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
            if "geometry" in value:
                raise ValueError(
                    "template-step field 'geometry' was removed with the old moving-head "
                    "renderer, its only reader; delete it and state the step's aim in "
                    "movement or component_refs"
                )
            renamed = [key for key in RENAMED_STEP_FIELDS if key in value]
            if renamed:
                raise ValueError(
                    "template-step fields were renamed: "
                    + ", ".join(f"{key!r} is now {RENAMED_STEP_FIELDS[key]!r}" for key in renamed)
                )
            if value.get("dimmer") == {}:
                raise ValueError(
                    "an empty dimmer object no longer means no pulse: leave dimmer out instead"
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
        movement: Partial movement overrides.
        dimmer: Partial dimmer overrides.
        timing: Partial timing overrides.
    """

    model_config = ConfigDict(extra="forbid")

    movement: dict[str, Any] | None = None
    dimmer: dict[str, Any] | None = None
    timing: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            if "geometry" in value:
                raise ValueError(
                    "step-patch field 'geometry' was removed with the old moving-head "
                    "renderer, its only reader; delete it and patch movement, dimmer or timing"
                )
            step_keys = sorted({"color", "shutter", "gobo"} & value.keys())
            if step_keys:
                raise ValueError(
                    f"a step patch sets only movement, dimmer or timing; set {step_keys} on "
                    "the step itself"
                )
        return value


def _reject_removed_patch_fields(preset_id: object, step_id: str, patch: object) -> None:
    """Refuse a step patch whose movement, dimmer or timing names a removed field when
    the preset loads, naming the preset and step, rather than when it is applied."""
    parts = patch.model_dump() if isinstance(patch, StepPatch) else patch
    if not isinstance(parts, dict):
        return
    checks = (
        ("movement", _reject_removed_movement_fields),
        ("dimmer", _reject_removed_dimmer_fields),
        ("timing", _reject_removed_timing_fields),
    )
    for name, check in checks:
        try:
            check(parts.get(name))
        except ValueError as error:
            raise ValueError(f"preset {preset_id!r}, step patch {step_id!r}: {error}") from None


class TemplatePreset(BaseModel):
    """A named preset for a template.

    Presets allow variations of a template (e.g., "narrow", "slow") by overriding
    step properties.

    Attributes:
        preset_id: Unique identifier for this preset.
        step_patches: Per-step property overrides.
    """

    model_config = ConfigDict(extra="forbid")

    preset_id: str
    step_patches: dict[str, StepPatch] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            removed = sorted({"name", "defaults"} & value.keys())
            if removed:
                raise ValueError(
                    f"preset fields {removed} were removed with the old moving-head renderer, "
                    "their only reader; delete them"
                )
            for step_id, patch in (value.get("step_patches") or {}).items():
                _reject_removed_patch_fields(value.get("preset_id"), step_id, patch)
        return value


class Template(BaseModel):
    """Complete template definition.

    Templates are portable choreography definitions that can be applied
    to any rig. They reference groups and roles, not fixture IDs.

    Attributes:
        template_id: Unique identifier for this template.
        version: Template version number.
        name: Human-readable name.
        category: Template category (e.g., "movement", "complex").
        repeat: Repeat/loop configuration.
        steps: List of template steps.
        metadata: Optional template metadata.
    """

    model_config = ConfigDict(extra="forbid")

    template_id: str
    version: int
    name: str
    category: TemplateCategory

    repeat: RepeatContract
    steps: list["TemplateStep"] = Field(default_factory=list)
    metadata: TemplateMetadata | None = None
    # Left out of dumps when empty.
    overlays: tuple[AttributeOverlay, ...] = Field(default=(), exclude_if=lambda value: not value)

    @model_validator(mode="before")
    @classmethod
    def _set_default_metadata(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Set default metadata if not provided."""
        if isinstance(data, dict) and "roles" in data:
            raise ValueError(
                "template field 'roles' was removed because fixture context is the role authority"
            )
        if isinstance(data, dict) and "physical_overlays" in data:
            raise ValueError("template field 'physical_overlays' was renamed: it is now 'overlays'")
        if isinstance(data, dict) and "defaults" in data:
            raise ValueError(
                "template field 'defaults' was removed with the old moving-head renderer, its "
                "only reader; delete it"
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
        if not self.overlays:
            return
        if self.repeat.mode is RepeatMode.PING_PONG:
            raise ValueError(
                "overlays are offsets from the cycle start; repeat mode PING_PONG "
                "mirrors every other cycle, so use JOINER or ONCE"
            )
        for channel in ("color", "gobo"):
            spans = sorted(
                (overlay.start_beats, overlay.end_beats)
                for overlay in self.overlays
                if overlay.channel == channel
            )
            for (_, end), (start, _) in pairwise(spans):
                if start < end:
                    raise ValueError(
                        f"two overlays on {channel} overlap at beat {start:g}; an "
                        "overlay on a channel must end before the next starts"
                    )

    def _require_finite_steps(self) -> None:
        """A ONCE cycle ends in a terminal state its remainder holds, so each step must
        declare finite motion and no dimmer or shutter pulse below duty 1."""
        for step in self.steps:
            if step.movement.mode != "finite":
                raise ValueError(
                    f"repeat mode ONCE needs every step finite, but step {step.step_id!r} "
                    "declares no finite movement (mode 'finite')"
                )
            pulses = (
                ("dimmer", step.dimmer),
                ("shutter", step.shutter),
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
