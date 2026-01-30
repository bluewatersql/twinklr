"""Pydantic models for MacroPlanner agent V2 (design spec compliant).

This module implements the MacroPlan schema as specified in:
changes/vnext/agents/core/04_macro_planner_agent_full_spec.md

Key changes from V1:
- Added GlobalStory (theme, motifs, pacing, color_story)
- Added display group selection (primary_focus_groups, secondary_groups)
- Added choreography_style (imagery|abstract|hybrid)
- Added motion_density (SPARSE|MED|BUSY)
- Replaced template selection with LayerIntent (suggestions, not selections)
- Removed template-specific fields (moved to GroupPlanner)
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from twinklr.core.agents.audio.profile.models import Issue, Provenance


class EnergyTarget(str, Enum):
    """Target energy level for a section."""

    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
    BUILD = "BUILD"
    RELEASE = "RELEASE"
    PEAK = "PEAK"


class ChoreographyStyle(str, Enum):
    """Visual approach for choreography."""

    IMAGERY = "imagery"  # Literal, recognizable patterns
    ABSTRACT = "abstract"  # Mood-driven, non-representational
    HYBRID = "hybrid"  # Mix of both


class MotionDensity(str, Enum):
    """Overall activity level."""

    SPARSE = "SPARSE"  # Minimal movement, focused accents
    MED = "MED"  # Balanced activity, rhythmic coordination
    BUSY = "BUSY"  # High activity, complex patterns


class LayerUsage(str, Enum):
    """Strategy for how layers are used across the plan."""

    UNIFIED = "unified"  # All groups coordinated
    COMPLEMENTARY = "complementary"  # Layers support each other
    INDEPENDENT = "independent"  # Layers work separately


class LayerTransitions(str, Enum):
    """Strategy for transitions between layers."""

    SMOOTH = "smooth"  # Gradual changes
    ABRUPT = "abrupt"  # Sudden changes
    EVOLVING = "evolving"  # Continuous development


class GlobalStory(BaseModel):
    """High-level theme and creative direction for the entire show.

    Defines the overarching narrative, motifs, pacing, and color story
    that guide the entire choreography plan.
    """

    theme: str = Field(
        description=(
            "Overarching theme (e.g., 'Joyful celebration', 'Elegant sophistication', "
            "'Playful energy', 'Nostalgic warmth')"
        )
    )

    motifs: list[str] = Field(
        description=(
            "Key recurring motifs (e.g., ['Rising intensity', 'Call-and-response', "
            "'Synchronized bursts', 'Wave patterns'])"
        )
    )

    pacing_notes: str = Field(
        description=(
            "How energy and intensity evolve across the song "
            "(e.g., 'Gradual build to peak at chorus, then controlled descent')"
        )
    )

    color_story: str = Field(
        description=(
            "Color palette and transitions "
            "(e.g., 'Traditional red/green with white accents', 'Cool blues building to warm golds')"
        )
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class LayerIntent(BaseModel):
    """Intent for one layer in a section.

    Describes WHAT a layer should accomplish, not HOW to implement it.
    Provides suggestions for templates/assets, but GroupPlanner makes final selections.
    """

    layer_index: int = Field(ge=1, le=3, description="Layer number (1, 2, or 3)")

    intent: str = Field(
        description=(
            "What this layer should accomplish "
            "(e.g., 'Provide rhythmic punctuation on downbeats', "
            "'Create ambient mood bed', 'Accent peak moments')"
        )
    )

    preferred_templates: list[str] = Field(
        default_factory=list,
        description=(
            "Suggested template types (e.g., ['chase', 'pulse']) - suggestions only, "
            "GroupPlanner makes final selection"
        ),
    )

    preferred_assets: list[str] = Field(
        default_factory=list,
        description="Suggested assets (e.g., ['sparkle', 'glow']) - suggestions only",
    )

    blend_mode: str = Field(
        default="normal",
        description="Suggested blend mode (e.g., 'normal', 'additive', 'multiply')",
    )

    intensity: float = Field(
        ge=0.0, le=1.0, default=0.7, description="Suggested intensity level (0.0-1.0)"
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class LayeringPlan(BaseModel):
    """Layer strategy for a section."""

    layers: list[LayerIntent] = Field(description="Layer intents for this section (1-3 layers)")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("layers")
    @classmethod
    def validate_layer_count(cls, v: list[LayerIntent]) -> list[LayerIntent]:
        """Validate layer count is 1-3."""
        if not (1 <= len(v) <= 3):
            raise ValueError(f"Must have 1-3 layers, got {len(v)}")
        return v

    @field_validator("layers")
    @classmethod
    def validate_unique_layer_indices(cls, v: list[LayerIntent]) -> list[LayerIntent]:
        """Validate layer indices are unique."""
        indices = [layer.layer_index for layer in v]
        if len(indices) != len(set(indices)):
            raise ValueError(f"Layer indices must be unique, got {indices}")
        return v


class MacroSectionPlan(BaseModel):
    """High-level plan for one song section.

    Defines strategic direction for a section: which display groups to use,
    what choreography style, motion density, and layer intents.
    Does NOT specify exact effects or templates - that's GroupPlanner's job.
    """

    # Section Identity
    section_id: str = Field(description="Unique section identifier (links to AudioProfile)")

    section_name: str = Field(description="Section name (e.g., 'verse_1', 'chorus', 'bridge')")

    start_ms: int = Field(ge=0, description="Section start time in milliseconds")

    end_ms: int = Field(gt=0, description="Section end time in milliseconds")

    # Energy and Mood
    energy_target: EnergyTarget = Field(
        description="Target energy level (LOW, MED, HIGH, BUILD, RELEASE, PEAK)"
    )

    # Display Group Selection
    primary_focus_groups: list[str] = Field(
        description=(
            "Primary display groups to feature (e.g., ['mega_tree', 'roofline', 'matrix']). "
            "These are the main visual elements for this section."
        )
    )

    secondary_groups: list[str] = Field(
        default_factory=list,
        description=(
            "Secondary/supporting display groups (e.g., ['windows', 'arches', 'spinners']). "
            "These provide accents and support."
        ),
    )

    # Choreography Style
    choreography_style: ChoreographyStyle = Field(
        description="Visual approach (imagery, abstract, or hybrid)"
    )

    motion_density: MotionDensity = Field(description="Overall activity level (SPARSE, MED, BUSY)")

    # Layer Strategy
    layering_plan: LayeringPlan = Field(description="Layer intents and strategy for this section")

    # Transitions
    transition_in: str | None = Field(
        default=None,
        description="How to transition INTO this section (e.g., 'Fade from previous', 'Abrupt cut')",
    )

    transition_out: str | None = Field(
        default=None,
        description="How to transition OUT of this section (e.g., 'Smooth fade', 'Build to next')",
    )

    # Additional Guidance
    objectives: list[str] = Field(
        default_factory=list,
        description="What this section should achieve (e.g., 'Build anticipation', 'Maximum impact')",
    )

    avoid: list[str] = Field(
        default_factory=list,
        description="What to avoid (e.g., 'Overly busy patterns', 'Clashing colors')",
    )

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("end_ms")
    @classmethod
    def validate_end_after_start(cls, v: int, info: Any) -> int:
        """Validate that end_ms > start_ms."""
        if "start_ms" in info.data and v <= info.data["start_ms"]:
            raise ValueError(f"end_ms ({v}) must be > start_ms ({info.data['start_ms']})")
        return v

    @field_validator("primary_focus_groups")
    @classmethod
    def validate_has_focus_groups(cls, v: list[str]) -> list[str]:
        """Validate at least one focus group."""
        if not v:
            raise ValueError("Must have at least one primary focus group")
        return v


class GlobalConstraints(BaseModel):
    """Global constraints and policies for the plan."""

    max_layers: int = Field(ge=1, le=3, default=3, description="Maximum layers allowed (1-3)")

    default_blend_mode: str = Field(default="normal", description="Default blend mode for layers")

    intensity_policy: str = Field(
        default="dynamic",
        description=("Intensity management policy (e.g., 'dynamic', 'conservative', 'aggressive')"),
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class MacroPlan(BaseModel):
    """High-level choreography plan for the entire song.

    Generated by the MacroPlanner agent from AudioProfileModel.
    Defines global story, strategic direction, and section-level plans.
    Does NOT specify exact effects or templates - that's GroupPlanner's job.

    This schema matches the design spec in:
    changes/vnext/agents/core/04_macro_planner_agent_full_spec.md
    """

    # Metadata
    schema_version: str = Field(default="2.0", description="Schema version")

    agent_id: str = Field(default="macro_planner.v2", description="Agent identifier")

    run_id: str = Field(description="Unique run identifier")

    iteration: int = Field(ge=1, description="Which iteration produced this plan")

    provenance: Provenance = Field(description="Metadata about how this plan was generated")

    warnings: list[Issue] = Field(
        default_factory=list, description="Non-blocking validation warnings"
    )

    # Global Story (NEW)
    global_story: GlobalStory = Field(
        description="High-level theme, motifs, pacing, and color story"
    )

    # Section Plans (REFACTORED)
    section_plans: list[MacroSectionPlan] = Field(
        description="Section-level strategic plans (one per song section)"
    )

    # Asset Requirements (NEW)
    asset_requirements: list[str] = Field(
        default_factory=list,
        description=(
            "Assets needed for this plan (e.g., ['sparkle_texture', 'glow_shader']). "
            "GroupPlanner will use these when selecting effects."
        ),
    )

    # Global Constraints (NEW)
    global_constraints: GlobalConstraints = Field(description="Global constraints and policies")

    # Quality Metadata (from judge)
    judge_score: float | None = Field(
        default=None, ge=0.0, le=10.0, description="Judge evaluation score (0-10)"
    )

    judge_feedback: str | None = Field(default=None, description="Judge feedback and assessment")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("section_plans")
    @classmethod
    def validate_has_sections(cls, v: list[MacroSectionPlan]) -> list[MacroSectionPlan]:
        """Validate at least one section."""
        if not v:
            raise ValueError("MacroPlan must contain at least one section")
        return v
