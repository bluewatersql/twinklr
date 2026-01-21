"""Template and pattern step models for multi-step choreography."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from .timing import MusicalTiming, TimingMode


class FixtureTarget(str, Enum):
    """Fixture targeting options."""

    ALL = "ALL"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    INNER = "INNER"
    OUTER = "OUTER"
    ODD = "ODD"
    EVEN = "EVEN"
    # Individual fixtures: MH1, MH2, etc. (handled as strings in template)


class TransitionMode(str, Enum):
    """Transition blending modes."""

    SNAP = "snap"  # Instant cut (no blend)
    CROSSFADE = "crossfade"  # Linear blend between steps
    FADE_THROUGH_BLACK = "fade_through_black"  # Dim out, snap, dim in


class BlendMode(str, Enum):
    """DMX channel blending modes for overlapping steps."""

    OVERRIDE = "override"  # Later step overrides earlier
    ADD = "add"  # Add DMX values (clamped to 255)
    MULTIPLY = "multiply"  # Multiply DMX values (normalized)
    MAX = "max"  # Take maximum value


class TransitionConfig(BaseModel):
    """Transition configuration between pattern steps."""

    mode: TransitionMode = TransitionMode.SNAP

    duration_bars: float = Field(
        default=0.0, ge=0.0, description="Transition duration in bars (0 for SNAP)"
    )

    curve: str | None = Field(
        default=None, description="Easing curve for transition (e.g., 'LINEAR', 'EASE_IN_OUT')"
    )

    @model_validator(mode="after")
    def validate_transition_settings(self) -> TransitionConfig:
        """Validate transition settings."""
        if self.mode == TransitionMode.SNAP and self.duration_bars > 0:
            raise ValueError("SNAP transitions must have duration_bars=0")

        if self.mode != TransitionMode.SNAP and self.duration_bars == 0:
            raise ValueError(f"{self.mode} transitions require duration_bars > 0")

        return self


class PatternStepTiming(BaseModel):
    """Domain-specific timing for pattern steps (moving heads).

    Extends universal MusicalTiming with domain-specific features like
    looping and per-fixture timing offsets.
    """

    base_timing: MusicalTiming = Field(description="Universal musical timing")

    loop: bool = Field(default=False, description="Whether pattern loops within duration")

    per_fixture_offsets: list[float] | None = Field(
        default=None, description="Per-fixture timing offsets in bars (for chase/canon effects)"
    )


class PatternStep(BaseModel):
    """Single step in a multi-step template.

    A pattern step references movement/geometry/dimmer patterns from
    Python libraries (type-safe enums) and provides parameters.
    """

    step_id: str = Field(description="Unique identifier for this step within the template")

    target: str = Field(
        default="ALL", description="Fixture target (ALL, LEFT, RIGHT, etc. or fixture ID)"
    )

    timing: PatternStepTiming = Field(description="Timing specification for this step")

    # References to library items (validated against Python enums at runtime)
    movement_id: str = Field(description="Movement pattern ID from movement library")

    geometry_id: str | None = Field(
        default=None, description="Geometry transform ID from geometry library (optional)"
    )

    dimmer_id: str = Field(description="Dimmer pattern ID from dimmer library")

    # Parameters - categorical or numeric
    movement_params: dict[str, str | float] = Field(
        default_factory=dict,
        description="Parameters for movement pattern (e.g., {'intensity': 'DRAMATIC'})",
    )

    geometry_params: dict[str, str | float] = Field(
        default_factory=dict,
        description="Parameters for geometry transform (e.g., {'pan_spread_deg': 30})",
    )

    dimmer_params: dict[str, str | float] = Field(
        default_factory=dict,
        description="Parameters for dimmer pattern (e.g., {'intensity': 'INTENSE'})",
    )

    # Transitions
    entry_transition: TransitionConfig = Field(
        default_factory=lambda: TransitionConfig(mode=TransitionMode.SNAP),
        description="Transition when entering this step",
    )

    exit_transition: TransitionConfig = Field(
        default_factory=lambda: TransitionConfig(mode=TransitionMode.SNAP),
        description="Transition when exiting this step",
    )

    # Conflict resolution (when steps overlap)
    priority: int = Field(
        default=0, ge=0, description="Priority for conflict resolution (higher = wins)"
    )

    blend_mode: BlendMode = Field(
        default=BlendMode.OVERRIDE, description="How to blend with overlapping steps"
    )


class TemplateCategory(str, Enum):
    """Template categorization for organization and selection."""

    LOW_ENERGY = "low_energy"
    MEDIUM_ENERGY = "medium_energy"
    HIGH_ENERGY = "high_energy"
    BUILD = "build"
    BREAKDOWN = "breakdown"
    ACCENT = "accent"
    TRANSITION = "transition"
    AMBIENT = "ambient"


class TemplateMetadata(BaseModel):
    """Metadata about a template for LLM context and selection."""

    description: str = Field(default="", description="What this template does and when to use it")

    recommended_sections: list[str] = Field(
        default_factory=list, description="Recommended song sections (e.g., ['verse', 'prechorus'])"
    )

    energy_range: tuple[int, int] = Field(
        default=(0, 100), description="Recommended energy range [0-100] for this template"
    )

    tags: list[str] = Field(
        default_factory=list,
        description="Tags for searching/filtering (e.g., ['smooth', 'building', 'symmetric'])",
    )


class TemplateTiming(BaseModel):
    """Template-level timing configuration."""

    mode: TimingMode = TimingMode.MUSICAL

    default_duration_bars: float = Field(
        default=8.0, gt=0.0, description="Default duration if not specified in plan"
    )


class Template(BaseModel):
    """Multi-step template definition.

    A template is a pre-composed choreography sequence that combines
    movement patterns, geometry transforms, and dimmer patterns from
    core libraries into a cohesive multi-step performance.
    """

    template_id: str = Field(description="Unique template identifier")

    name: str = Field(description="Human-readable template name")

    category: TemplateCategory = Field(description="Template category for organization")

    timing: TemplateTiming = Field(
        default_factory=TemplateTiming, description="Template-level timing configuration"
    )

    steps: list[PatternStep] = Field(min_length=1, description="Ordered sequence of pattern steps")

    metadata: TemplateMetadata = Field(
        default_factory=TemplateMetadata, description="Metadata for template selection and usage"
    )

    @model_validator(mode="after")
    def validate_template_structure(self) -> Template:
        """Validate template structure."""
        # Check step_ids are unique
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("All step_ids must be unique within a template")

        return self
