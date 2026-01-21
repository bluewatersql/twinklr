"""Template Models for the moving head sequencer.

This module defines all template-related models:
- Timing models: BaseTiming, PhaseOffset, RepeatContract
- Step components: Geometry, Movement, Dimmer, StepTiming, TemplateStep
- Template structure: Template, TemplatePreset, TemplateDoc

These models define how choreography is structured and executed.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RepeatMode(str, Enum):
    """How to repeat template sections.

    Attributes:
        PING_PONG: Alternate forward and backward through steps.
        JOINER: Play steps in sequence, then repeat from beginning.
    """

    PING_PONG = "PING_PONG"
    JOINER = "JOINER"


class RemainderPolicy(str, Enum):
    """What to do when template duration doesn't divide evenly into repeats.

    Attributes:
        HOLD_LAST_POSE: Maintain the final pose until window ends.
        FADE_OUT: Fade dimmer to zero over the remainder.
        TRUNCATE: Cut off abruptly at the end of the last complete cycle.
    """

    HOLD_LAST_POSE = "HOLD_LAST_POSE"
    FADE_OUT = "FADE_OUT"
    TRUNCATE = "TRUNCATE"


class PhaseOffsetMode(str, Enum):
    """How to apply phase offsets across fixtures.

    Attributes:
        NONE: No phase offset - all fixtures move in sync.
        GROUP_ORDER: Apply offsets based on fixture order in a group.
    """

    NONE = "NONE"
    GROUP_ORDER = "GROUP_ORDER"


class Distribution(str, Enum):
    """How to distribute phase offsets across fixtures.

    Attributes:
        LINEAR: Evenly distributed offsets (0, 0.25, 0.5, 0.75 for 4 fixtures).
    """

    LINEAR = "LINEAR"


class BaseTiming(BaseModel):
    """Base timing specification for a template element.

    Defines when an element starts (relative to parent) and how long it lasts.

    Attributes:
        start_offset_bars: When to start, in bars from parent start.
        duration_bars: How long the element lasts, in bars.

    Example:
        >>> timing = BaseTiming(start_offset_bars=0.0, duration_bars=4.0)
        >>> timing.duration_bars
        4.0
    """

    model_config = ConfigDict(extra="forbid")

    start_offset_bars: float = Field(..., ge=0.0)
    duration_bars: float = Field(..., gt=0.0)


class PhaseOffset(BaseModel):
    """Configuration for phase offset spreading across fixtures.

    Phase offsets create chase-like effects by starting each fixture's
    animation at a different point in the cycle.

    Attributes:
        mode: How to apply phase offsets.
        group: Which fixture group to apply offsets to (required for GROUP_ORDER).
        order: Chase order name (e.g., "LEFT_TO_RIGHT").
        spread_bars: Total spread across all fixtures, in bars.
        distribution: How to distribute offsets (currently only LINEAR).
        wrap: Whether to wrap offsets that exceed 1.0.

    Example:
        >>> offset = PhaseOffset(
        ...     mode=PhaseOffsetMode.GROUP_ORDER,
        ...     group="fronts",
        ...     spread_bars=0.5,
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    mode: PhaseOffsetMode
    group: str | None = Field(None)
    order: str | None = Field(None)  # ChaseOrder name
    spread_bars: float = Field(0.0, ge=0.0)
    distribution: Distribution = Field(Distribution.LINEAR)
    wrap: bool = Field(True)

    @model_validator(mode="after")
    def _validate_group_required(self) -> "PhaseOffset":
        """Validate group is required when mode=GROUP_ORDER."""
        if self.mode == PhaseOffsetMode.GROUP_ORDER and self.group is None:
            raise ValueError("group required when mode=GROUP_ORDER")
        return self


class RepeatContract(BaseModel):
    """Configuration for repeating template sections.

    Defines how a template section loops during playback.

    Attributes:
        repeatable: Whether this section can be repeated.
        mode: How to repeat (PING_PONG or JOINER).
        cycle_bars: Duration of one complete cycle, in bars.
        loop_step_ids: Which steps are included in the loop.
        remainder_policy: What to do with time remaining after last full cycle.

    Example:
        >>> contract = RepeatContract(
        ...     cycle_bars=4.0,
        ...     loop_step_ids=["step1", "step2"],
        ...     mode=RepeatMode.PING_PONG,
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    repeatable: bool = Field(True)
    mode: RepeatMode = Field(RepeatMode.PING_PONG)
    cycle_bars: float = Field(..., gt=0.0)
    loop_step_ids: list[str] = Field(..., min_length=1)
    remainder_policy: RemainderPolicy = Field(RemainderPolicy.HOLD_LAST_POSE)


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
        aim_zone: Target aim zone (e.g., "CROWD", "SKY").

    Example:
        >>> geo = Geometry(
        ...     geometry_id="ROLE_POSE",
        ...     pan_pose_by_role={"FRONT_LEFT": "LEFT", "FRONT_RIGHT": "RIGHT"},
        ...     aim_zone="CROWD",
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    geometry_id: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)

    # ROLE_POSE specific fields
    pan_pose_by_role: dict[str, str] | None = Field(None)
    tilt_pose: str | None = Field(None)
    aim_zone: str | None = Field(None)


class Movement(BaseModel):
    """Movement specification for a template step.

    Defines how fixtures move over time (e.g., sweep, circle, nod).
    Movement is relative to the geometry baseline.

    Attributes:
        movement_id: Identifier for the movement handler (e.g., "SWEEP_LR").
        intensity: Movement intensity preset (e.g., "SMOOTH", "FAST").
        cycles: Number of movement cycles in the step duration.
        params: Additional parameters for the movement handler.

    Example:
        >>> mov = Movement(
        ...     movement_id="SWEEP_LR",
        ...     intensity="FAST",
        ...     cycles=2.0,
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    movement_id: str = Field(..., min_length=1)
    intensity: str = Field("SMOOTH")
    cycles: float = Field(1.0, gt=0.0)
    params: dict[str, Any] = Field(default_factory=dict)


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

    Example:
        >>> dim = Dimmer(
        ...     dimmer_id="PULSE",
        ...     min_norm=0.2,
        ...     max_norm=1.0,
        ...     cycles=4.0,
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    dimmer_id: str = Field(..., min_length=1)
    intensity: str = Field("SMOOTH")
    min_norm: float = Field(0.0, ge=0.0, le=1.0)
    max_norm: float = Field(1.0, ge=0.0, le=1.0)
    cycles: float = Field(1.0, gt=0.0)
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_range(self) -> "Dimmer":
        """Validate max_norm >= min_norm."""
        if self.max_norm < self.min_norm:
            raise ValueError(f"max_norm ({self.max_norm}) < min_norm ({self.min_norm})")
        return self


class StepTiming(BaseModel):
    """Timing specification for a template step.

    Combines base timing with optional phase offset configuration.

    Attributes:
        base_timing: When the step starts and how long it lasts.
        phase_offset: Optional phase offset configuration.

    Example:
        >>> timing = StepTiming(
        ...     base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=4.0),
        ...     phase_offset=PhaseOffset(mode=PhaseOffsetMode.NONE),
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    base_timing: BaseTiming
    phase_offset: PhaseOffset | None = Field(None)


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

    Example:
        >>> step = TemplateStep(
        ...     step_id="main",
        ...     target="all_fixtures",
        ...     timing=StepTiming(
        ...         base_timing=BaseTiming(start_offset_bars=0.0, duration_bars=4.0),
        ...     ),
        ...     geometry=Geometry(geometry_id="FAN"),
        ...     movement=Movement(movement_id="SWEEP_LR"),
        ...     dimmer=Dimmer(dimmer_id="PULSE"),
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    timing: StepTiming
    geometry: Geometry
    movement: Movement
    dimmer: Dimmer


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

    Example:
        >>> meta = TemplateMetadata(
        ...     tags=["energetic", "movement"],
        ...     energy_range=(60, 100),
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    tags: list[str] = Field(default_factory=list)
    energy_range: tuple[int, int] | None = Field(None)
    description: str | None = Field(None)


class StepPatch(BaseModel):
    """Patch to apply to a template step.

    Used by presets to override step properties.

    Attributes:
        geometry: Partial geometry overrides.
        movement: Partial movement overrides.
        dimmer: Partial dimmer overrides.
        timing: Partial timing overrides.

    Example:
        >>> patch = StepPatch(
        ...     movement={"cycles": 3.0},
        ...     dimmer={"max_norm": 0.8},
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    geometry: dict[str, Any] | None = Field(None)
    movement: dict[str, Any] | None = Field(None)
    dimmer: dict[str, Any] | None = Field(None)
    timing: dict[str, Any] | None = Field(None)


class TemplatePreset(BaseModel):
    """A named preset for a template.

    Presets allow variations of a template (e.g., "CHILL", "ENERGETIC")
    by overriding default values and step properties.

    Attributes:
        preset_id: Unique identifier for this preset.
        name: Human-readable name.
        defaults: Default value overrides.
        step_patches: Per-step property overrides.

    Example:
        >>> preset = TemplatePreset(
        ...     preset_id="CHILL",
        ...     name="Chill",
        ...     defaults={"intensity": "SMOOTH"},
        ...     step_patches={"main": StepPatch(movement={"cycles": 1.0})},
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    preset_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
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

    Example:
        >>> template = Template(
        ...     template_id="fan_pulse",
        ...     version=1,
        ...     name="Fan Pulse",
        ...     category="movement",
        ...     roles=["FRONT_LEFT", "FRONT_RIGHT"],
        ...     groups={"all": ["FRONT_LEFT", "FRONT_RIGHT"]},
        ...     repeat=RepeatContract(cycle_bars=4.0, loop_step_ids=["main"]),
        ...     steps=[...],
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., min_length=1)
    version: int = Field(..., ge=1)
    name: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)

    roles: list[str] = Field(..., min_length=1)
    groups: dict[str, list[str]] = Field(..., min_length=1)

    repeat: RepeatContract
    defaults: dict[str, Any] = Field(default_factory=dict)
    steps: list["TemplateStep"] = Field(..., min_length=1)
    metadata: TemplateMetadata | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _set_default_metadata(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Set default metadata if not provided."""
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
            if step.target not in self.groups:
                raise ValueError(f"Step '{step.step_id}' targets unknown group: '{step.target}'")

        return self


class TemplateDoc(BaseModel):
    """Complete template document with presets.

    This is the top-level structure for template files.

    Attributes:
        template: The template definition.
        presets: List of available presets.

    Example:
        >>> doc = TemplateDoc(
        ...     template=template,
        ...     presets=[preset1, preset2],
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    template: Template
    presets: list[TemplatePreset] = Field(default_factory=list)
