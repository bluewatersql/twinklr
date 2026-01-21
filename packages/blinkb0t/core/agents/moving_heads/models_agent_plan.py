"""Agent plan models

These models represent the LLM-generated strategic plans (template-based).
Extended inwith channel specifications.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from blinkb0t.core.domains.sequencing.models.channels import ChannelSpecification


class SectionPlan(BaseModel):
    """Plan for a single section (template-based).

    Stage 1 output: Strategic template selection only.
    The planner selects MULTIPLE templates for each section.
    The implementation agent (Stage 3) decides targeting and layering.

    Extended into include channel specifications (shutter, color, gobo).
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(description="Section name (e.g., 'verse_1', 'chorus_1')")
    start_bar: int = Field(description="Starting bar number (1-indexed)", ge=1)
    end_bar: int = Field(description="Ending bar number (inclusive)", ge=1)
    section_role: str = Field(
        description="Section role (verse, chorus, bridge, build, drop, transition)"
    )
    energy_level: int = Field(description="Energy level 0-100", ge=0, le=100)

    # Stage 1: Planner selects MULTIPLE templates (1:M relationship with sections)
    # The implementation agent (Stage 3) creates one ImplementationSection per template
    templates: list[str] = Field(
        description="List of template IDs from library for this section (enables layering)",
    )

    params: dict[str, str] = Field(
        default_factory=dict,
        description="Template parameters (e.g., {'intensity': 'SMOOTH'}) - Optional, can be set by implementation agent",
    )
    base_pose: str = Field(
        default="AUDIENCE_CENTER",
        description="Base pose ID (e.g., 'AUDIENCE_CENTER') - Optional, can be refined by implementation agent",
    )
    reasoning: str = Field(description="Why these templates were chosen")

    # Channel specifications (optional for backward compatibility)
    channels: ChannelSpecification = Field(
        default_factory=ChannelSpecification,
        description="Channel specifications (shutter, color, gobo) -addition",
    )


class AgentPlan(BaseModel):
    """Complete agent-generated plan with all sections."""

    model_config = ConfigDict(extra="ignore")

    sections: list[SectionPlan] = Field(description="List of section plans")
    overall_strategy: str = Field(description="High-level choreography strategy")
    template_variety_score: int = Field(description="Self-assessed variety (0-10)", ge=0, le=10)
    energy_alignment_score: int = Field(
        description="Self-assessed energy match (0-10)", ge=0, le=10
    )


class TransitionSpec(BaseModel):
    """Transition specification.

    DEPRECATED: Transitions are now determined by the renderer, not the agent.
    This model is kept for backward compatibility with old pipeline only.

    DO NOT USE in new code (renderer_v2 or agent output).
    """

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(description="Transition mode (snap, crossfade, fade_through_black)")
    duration_ms: float = Field(description="Transition duration in milliseconds", ge=0)


class ImplementationSection(BaseModel):
    """Implementation section with bar-level timing.

    Agent works in MUSICAL UNITS (bars), not milliseconds.
    Renderer converts bars→ms using BeatGrid (single source of truth).
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(description="Section name")
    plan_section_name: str = Field(
        description="Original section name from plan (for traceability and notes track)"
    )
    start_bar: int = Field(description="Start bar number (1-indexed)", ge=1)
    end_bar: int = Field(description="End bar number (inclusive, 1-indexed)", ge=1)
    template_id: str = Field(description="Template ID")
    params: dict[str, str] = Field(description="Template parameters")
    base_pose: str = Field(description="Base pose ID")
    targets: list[str] = Field(description="Target fixture groups (choreographic decision)")
    layer_priority: int = Field(default=0, description="Layer priority (0=base, 1+=layers)", ge=0)

    # Narrative/reasoning (preserves strategic intent from plan)
    reasoning: str = Field(
        default="",
        description="Why this implementation was chosen (targeting, layering rationale)",
    )

    # REMOVED (renderer determines these):
    # - start_ms / end_ms (renderer converts bars→ms using BeatGrid)
    # - transition_in / transition_out (renderer determines based on boundaries)

    @field_validator("params")
    @classmethod
    def validate_intensity_param(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate that intensity parameter uses proper enum values."""
        if "intensity" in v:
            intensity = v["intensity"]
            valid_intensities = {"SMOOTH", "DRAMATIC", "INTENSE"}
            if intensity not in valid_intensities:
                raise ValueError(
                    f"Invalid intensity value '{intensity}'. "
                    f"Must be one of: {', '.join(sorted(valid_intensities))}"
                )
        return v


class AgentImplementation(BaseModel):
    """Detailed implementation with bar-level timing.

    Agent works in bars (musical units).
    Renderer converts to milliseconds after alignment.
    """

    model_config = ConfigDict(extra="ignore")

    sections: list[ImplementationSection] = Field(description="List of implementation sections")
    total_duration_bars: int = Field(description="Total duration in bars", ge=1)
    quantization_applied: bool = Field(description="Whether beat quantization was applied")
    timing_precision: str = Field(description="Timing precision (beat_aligned, bar_aligned, raw)")

    # Narrative fields (preserve strategic narrative from plan)
    overall_strategy: str = Field(
        default="",
        description="High-level choreography strategy from plan (preserved for context)",
    )
    implementation_approach: str = Field(
        default="",
        description="How the plan was implemented (layering strategy, targeting choices)",
    )


class ChannelScoring(BaseModel):
    """Scoring for channel usage (extension).

    Evaluates the quality of shutter, color, and gobo selections
    in relation to section energy and musical context.
    """

    model_config = ConfigDict(extra="ignore")

    shutter_appropriateness: int = Field(ge=1, le=10, description="Shutter usage quality (1-10)")
    shutter_issues: list[str] = Field(default_factory=list, description="Issues with shutter usage")

    color_appropriateness: int = Field(ge=1, le=10, description="Color usage quality (1-10)")
    color_issues: list[str] = Field(default_factory=list, description="Issues with color usage")

    gobo_appropriateness: int = Field(ge=1, le=10, description="Gobo usage quality (1-10)")
    gobo_issues: list[str] = Field(default_factory=list, description="Issues with gobo usage")

    visual_impact: int = Field(ge=1, le=10, description="Overall visual impact (1-10)")
    visual_impact_issues: list[str] = Field(
        default_factory=list, description="Issues with visual impact"
    )
