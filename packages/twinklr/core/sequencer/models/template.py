"""Template Models for the moving head sequencer.

This module defines all template-related models:
- Timing models: BaseTiming, PhaseOffset, RepeatContract
- Step components: Geometry, Movement, Dimmer, StepTiming, TemplateStep
- Physical renderer step data: PhysicalMovementSpec, PhysicalPulseSpec and its
  dimmer and shutter forms
- Template structure: Template, TemplatePreset, TemplateDoc

These models define how choreography is structured and executed.
"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.config.poses import PanPose, TiltPose
from twinklr.core.sequencer.models.enum import (
    AimZone,
    ChaseOrder,
    Intensity,
    QuantizeMode,
    SemanticGroupType,
    TemplateCategory,
    TemplateRole,
    TimingMode,
)
from twinklr.core.sequencer.moving_heads.libraries.color import ColorPreset
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType
from twinklr.core.sequencer.moving_heads.libraries.shutter import ShutterPattern


class RepeatMode(StrEnum):
    PING_PONG = "PING_PONG"
    JOINER = "JOINER"


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
        mode: How to repeat (PING_PONG or JOINER).
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


class PhysicalMovementSpec(BaseModel):
    """Physical motion of a step for the physical renderer, in fixture-local degrees.

    Template-owned renderer data, never an LLM control. Reach (`*_extent_deg`) and
    rate (`period_beats`) are independent. Kernels: `hold` keeps the start pose;
    `sine_pan`/`sine_tilt` add the selected extent times sin(2*pi*phase) and are
    periodic; `linear` moves from start to start plus extent over one period, then
    holds, and is finite.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    shape: Literal["hold", "sine_pan", "sine_tilt", "linear"]
    mode: Literal["periodic", "finite"]
    start_pan_deg: float = Field(allow_inf_nan=False)
    start_tilt_deg: float = Field(allow_inf_nan=False)
    pan_extent_deg: float = Field(default=0.0, allow_inf_nan=False)
    tilt_extent_deg: float = Field(default=0.0, allow_inf_nan=False)
    period_beats: float | None = Field(
        default=None,
        ge=MIN_PHYSICAL_PERIOD_BEATS,
        allow_inf_nan=False,
        description="Required unless shape is hold",
    )

    @model_validator(mode="after")
    def _validate_kernel(self) -> "PhysicalMovementSpec":
        if self.shape == "linear" and self.mode != "finite":
            raise ValueError("linear motion is finite; periodic linear is not supported")
        if self.shape in ("sine_pan", "sine_tilt") and self.mode != "periodic":
            raise ValueError(f"{self.shape} is periodic; finite sine is not supported")
        if self.shape == "hold":
            if self.pan_extent_deg or self.tilt_extent_deg or self.period_beats is not None:
                raise ValueError("hold takes no extent or period")
            return self
        if self.period_beats is None:
            raise ValueError(f"{self.shape} needs period_beats")
        unused = {"sine_pan": self.tilt_extent_deg, "sine_tilt": self.pan_extent_deg}
        if unused.get(self.shape):
            raise ValueError(f"{self.shape} moves one axis; the other extent must be zero")
        return self


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

    low_state: str = Field(min_length=1)
    high_state: str = Field(min_length=1)


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

    @property
    def has_physical_data(self) -> bool:
        """Whether any component carries data for the physical renderer."""
        return (
            self.movement.physical is not None
            or self.dimmer.physical is not None
            or self.physical_shutter is not None
        )

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

        return self


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
