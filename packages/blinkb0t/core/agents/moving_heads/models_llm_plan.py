"""LLM Choreography Plan Models.

This module defines the simplified LLM response schema for template-based
choreography. The LLM selects templates + presets + modifiers for each section
rather than generating raw implementation details.

The new paradigm:
- Templates define choreography (geometry, movement, dimmer patterns)
- Presets provide variations (CHILL, ENERGETIC, etc.)
- Modifiers are optional categorical knobs (intensity, speed, variation)
- LLM makes categorical selections, not raw plan generation
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SectionSelection(BaseModel):
    """LLM selection for a single song section.

    The LLM selects which template + preset + modifiers to use for each section.
    Templates already define the choreography; the LLM just makes categorical choices.

    Attributes:
        section_name: Name of the section (e.g., 'verse_1', 'chorus_1').
        start_bar: Starting bar number (1-indexed, inclusive).
        end_bar: Ending bar number (1-indexed, inclusive).
        section_role: Optional section role context (verse, chorus, bridge, etc.).
        energy_level: Optional energy level context (0-100).
        template_id: ID of the template to use.
        preset_id: Optional preset to apply to the template.
        modifiers: Optional categorical modifiers (e.g., {'intensity': 'HIGH'}).
        reasoning: Optional reasoning for the selection (helps LLM explain choices).

    Example:
        >>> selection = SectionSelection(
        ...     section_name="chorus_1",
        ...     start_bar=17,
        ...     end_bar=32,
        ...     template_id="sweep_pulse",
        ...     preset_id="ENERGETIC",
        ...     modifiers={"intensity": "HIGH"},
        ...     reasoning="High energy chorus needs dramatic sweeping motion",
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    # Section context (where in the song)
    section_name: str = Field(..., min_length=1)
    start_bar: int = Field(..., ge=1, description="Start bar (1-indexed)")
    end_bar: int = Field(..., ge=1, description="End bar (1-indexed, inclusive)")

    # Optional context for LLM reasoning
    section_role: str | None = Field(
        None, description="Section role (verse, chorus, bridge, build, drop, etc.)"
    )
    energy_level: int | None = Field(None, ge=0, le=100, description="Energy level 0-100")

    # Template selection (the LLM's choice)
    template_id: str = Field(..., min_length=1, description="Template ID to use")
    preset_id: str | None = Field(None, description="Optional preset ID")
    modifiers: dict[str, str] = Field(
        default_factory=dict,
        description="Categorical modifiers (e.g., {'intensity': 'HIGH'})",
    )

    # Reasoning (helps LLM explain its choices)
    reasoning: str = Field(
        default="",
        description="Why this template/preset/modifiers were chosen",
    )

    @model_validator(mode="after")
    def _validate_bar_range(self) -> SectionSelection:
        """Validate end_bar >= start_bar."""
        if self.end_bar < self.start_bar:
            raise ValueError(f"end_bar ({self.end_bar}) must be >= start_bar ({self.start_bar})")
        return self


class LLMChoreographyPlan(BaseModel):
    """Complete LLM-generated choreography plan.

    The LLM outputs a list of section selections - one template selection per section.
    This replaces the previous complex plan with raw implementation details.

    Attributes:
        sections: List of section selections (template choices per section).
        overall_strategy: High-level choreography strategy description.
        template_variety_notes: Optional notes on template variety/contrast.

    Example:
        >>> plan = LLMChoreographyPlan(
        ...     sections=[
        ...         SectionSelection(
        ...             section_name="verse_1",
        ...             start_bar=1,
        ...             end_bar=16,
        ...             template_id="fan_pulse",
        ...             preset_id="CHILL",
        ...         ),
        ...         SectionSelection(
        ...             section_name="chorus_1",
        ...             start_bar=17,
        ...             end_bar=32,
        ...             template_id="sweep_pulse",
        ...             preset_id="ENERGETIC",
        ...         ),
        ...     ],
        ...     overall_strategy="Build energy from verse to chorus",
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    sections: list[SectionSelection] = Field(
        ..., min_length=1, description="Section selections (one per section)"
    )
    overall_strategy: str = Field(..., min_length=1, description="High-level choreography strategy")
    template_variety_notes: str | None = Field(
        None, description="Notes on template variety and contrast"
    )
