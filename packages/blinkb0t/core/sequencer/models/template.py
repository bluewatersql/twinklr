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

from blinkb0t.core.config.poses import PanPose, TiltPose
from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.sequencer.models.enum import (
    AimZone,
    BlendMode,
    ChaseOrder,
    Intensity,
    QuantizeMode,
    SemanticGroupType,
    TemplateCategory,
    TemplateRole,
    TimingMode,
    TransitionMode,
)
from blinkb0t.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from blinkb0t.core.sequencer.moving_heads.libraries.geometry import GeometryType
from blinkb0t.core.sequencer.moving_heads.libraries.movement import MovementType


class RepeatMode(str, Enum):
    PING_PONG = "PING_PONG"
    JOINER = "JOINER"


class RemainderPolicy(str, Enum):
    HOLD_LAST_POSE = "HOLD_LAST_POSE"
    FADE_OUT = "FADE_OUT"
    TRUNCATE = "TRUNCATE"


class PhaseOffsetMode(str, Enum):
    NONE = "NONE"
    GROUP_ORDER = "GROUP_ORDER"


class Distribution(str, Enum):
    LINEAR = "LINEAR"


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
    mode: TimingMode = TimingMode.MUSICAL
    quantize_type: QuantizeMode = QuantizeMode.DOWNBEAT
    start_offset_bars: float
    duration_bars: float


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
    """

    model_config = ConfigDict(extra="forbid")

    mode: PhaseOffsetMode = PhaseOffsetMode.NONE
    group: SemanticGroupType = SemanticGroupType.ALL
    order: ChaseOrder = ChaseOrder.LEFT_TO_RIGHT
    spread_bars: float = 0.0
    distribution: Distribution = Distribution.LINEAR
    wrap: bool = True

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
        loop_step_ids: Which steps are included in the loop (required when repeatable=True).
        remainder_policy: What to do with time remaining after last full cycle.
    """

    model_config = ConfigDict(extra="forbid")

    repeatable: bool = True
    mode: RepeatMode = RepeatMode.PING_PONG
    cycle_bars: float
    loop_step_ids: list[str] = Field(default_factory=list)
    remainder_policy: RemainderPolicy = RemainderPolicy.HOLD_LAST_POSE

    @model_validator(mode="after")
    def _validate_loop_step_ids(self) -> "RepeatContract":
        """Validate loop_step_ids has at least 1 item when repeatable=True."""
        if self.repeatable and len(self.loop_step_ids) == 0:
            raise ValueError("loop_step_ids must have at least 1 item when repeatable=True")
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


class Movement(BaseModel):
    """Movement specification for a template step.

    Defines how fixtures move over time (e.g., sweep, circle, nod).
    Movement is relative to the geometry baseline.

    Attributes:
        movement_id: Identifier for the movement handler (e.g., "SWEEP_LR").
        intensity: Movement intensity preset (e.g., "SMOOTH", "FAST").
        cycles: Number of movement cycles in the step duration.
        params: Additional parameters for the movement handler.
        amplitude_override: Optional amplitude override [0, 1].
        frequency_override: Optional frequency override [0, 10].
        center_offset_override: Optional center offset override [0, 1].
    """

    model_config = ConfigDict(extra="forbid")

    movement_type: MovementType = MovementType.NONE
    intensity: Intensity = Intensity.SMOOTH
    cycles: float = 1.0
    params: dict[str, Any] = Field(default_factory=dict)

    # Categorical parameter overrides
    amplitude_override: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_override: float | None = Field(default=None, ge=0.0, le=10.0)
    center_offset_override: float | None = Field(default=None, ge=0.0, le=1.0)

    def get_categorical_params(self, curve_id: "CurveLibrary") -> Any:
        """Get categorical parameters for this movement, applying any overrides.

        Args:
            curve_id: Curve identifier to get base params for

        Returns:
            Categorical parameters with overrides applied

        Example:
            >>> from blinkb0t.core.curves.library import CurveLibrary
            >>> movement = Movement(
            ...     movement_type=MovementType.SWEEP_LR,
            ...     intensity=Intensity.SMOOTH,
            ...     amplitude_override=0.8,
            ... )
            >>> params = movement.get_categorical_params(CurveLibrary.MOVEMENT_SINE)
            >>> params.amplitude
            0.8
        """
        # Import here to avoid circular dependency
        from blinkb0t.core.sequencer.moving_heads.libraries.movement import (
            MovementCategoricalParams,
            get_curve_categorical_params,
        )

        # Get base params from curve and intensity
        base_params = get_curve_categorical_params(curve_id, self.intensity)

        # Apply overrides
        return MovementCategoricalParams(
            amplitude=self.amplitude_override
            if self.amplitude_override is not None
            else base_params.amplitude,
            frequency=self.frequency_override
            if self.frequency_override is not None
            else base_params.frequency,
            center_offset=self.center_offset_override
            if self.center_offset_override is not None
            else base_params.center_offset,
        )


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
    cycles: float = 1.0
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
    """

    model_config = ConfigDict(extra="forbid")

    base_timing: BaseTiming
    phase_offset: PhaseOffset = Field(
        default_factory=lambda: PhaseOffset(mode=PhaseOffsetMode.NONE)
    )


class Transition(BaseModel):
    """Transition specification for a template step.

    Defines how to transition between steps.

    Attributes:
        mode: Transition mode (e.g., "CROSSFADE", "SNAP").
        duration_bars: Transition duration in bars.
        curve: Transition curve (e.g., "sine", "linear").
    """

    model_config = ConfigDict(extra="forbid")

    mode: TransitionMode = TransitionMode.CROSSFADE
    duration_bars: float = 0.0
    curve: CurveLibrary = CurveLibrary.LINEAR


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
        entry_transition: Transition when entering this step.
        exit_transition: Transition when exiting this step.
        priority: Priority for conflict resolution.
        blend_mode: How to blend this step with others.
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str
    target: SemanticGroupType = SemanticGroupType.ALL
    timing: StepTiming
    geometry: Geometry
    movement: Movement
    dimmer: Dimmer
    entry_transition: Transition | None = None
    exit_transition: Transition | None = None
    priority: int = 0
    blend_mode: BlendMode = BlendMode.OVERRIDE


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

    roles: list[TemplateRole] = Field(default_factory=list)
    repeat: RepeatContract
    defaults: dict[str, Any] = Field(default_factory=dict)
    steps: list["TemplateStep"] = Field(default_factory=list)
    metadata: TemplateMetadata | None = None

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
