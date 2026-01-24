"""Response models for moving heads agents."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ============================================================================
# Planner Models
# ============================================================================


class PlanSegment(BaseModel):
    """LLM selection for a contiguous sub-range within a section."""

    segment_id: str = Field(description="Short id within the section (e.g., 'A', 'B', 'C')")
    start_bar: int = Field(ge=1, description="Start bar (1-indexed)")
    end_bar: int = Field(ge=1, description="End bar (1-indexed, inclusive)")

    template_id: str = Field(description="Template ID to use for this segment")
    preset_id: str | None = Field(None, description="Optional preset ID")
    modifiers: dict[str, str] = Field(default_factory=dict, description="Optional modifiers")
    reasoning: str = Field(default="", description="Why this segment choice was made")

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_bar_range(self) -> PlanSegment:
        if self.end_bar < self.start_bar:
            raise ValueError(f"end_bar ({self.end_bar}) must be >= start_bar ({self.start_bar})")
        return self


class PlanSection(BaseModel):
    """LLM selection for a single song section.

    The LLM selects which template + preset to use for each section.
    Templates already define the choreography; the LLM just makes categorical choices.
    """

    # Section context (where in the song)
    section_name: str = Field(description="Section name (e.g., 'verse_1', 'chorus_1')")
    start_bar: int = Field(ge=1, description="Start bar (1-indexed)")
    end_bar: int = Field(ge=1, description="End bar (1-indexed, inclusive)")

    # Optional context
    section_role: str | None = Field(
        None, description="Section role (verse, chorus, bridge, build, drop, etc.)"
    )
    energy_level: int | None = Field(None, ge=0, le=100, description="Energy level 0-100")

    # Template selection (the LLM's choice)
    template_id: str | None = Field(
        None,
        description="Template ID to use when not providing segments",
    )
    preset_id: str | None = Field(None, description="Optional preset ID")
    modifiers: dict[str, str] = Field(default_factory=dict, description="Optional modifiers")
    reasoning: str = Field(default="", description="Why this template/preset was chosen")

    # New: optional segmented plan
    segments: list[PlanSegment] | None = Field(
        None,
        description="Optional 1–3 contiguous segments that partition this section",
        min_length=1,
        max_length=3,
    )

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_section(self) -> PlanSection:
        if self.end_bar < self.start_bar:
            raise ValueError(f"end_bar ({self.end_bar}) must be >= start_bar ({self.start_bar})")

        has_segments = bool(self.segments)
        has_single = bool(self.template_id)

        # Require exactly one of: segments OR single template
        if has_segments and has_single:
            raise ValueError("Provide either 'segments' OR 'template_id', not both.")
        if not has_segments and not has_single:
            raise ValueError("Must provide either 'segments' or 'template_id'.")

        # If segmented, enforce full coverage + contiguity + within section bounds
        if self.segments:
            segs = sorted(self.segments, key=lambda s: (s.start_bar, s.end_bar))

            if segs[0].start_bar != self.start_bar:
                raise ValueError("First segment must start at section start_bar.")
            if segs[-1].end_bar != self.end_bar:
                raise ValueError("Last segment must end at section end_bar.")

            for i in range(len(segs) - 1):
                if segs[i].end_bar + 1 != segs[i + 1].start_bar:
                    raise ValueError("Segments must be contiguous and non-overlapping.")

            for s in segs:
                if s.start_bar < self.start_bar or s.end_bar > self.end_bar:
                    raise ValueError("Segment bar range must be within the section bar range.")

        return self


class ChoreographyPlan(BaseModel):
    """Complete choreography plan from planner agent.

    The LLM outputs a list of section selections - one template selection per section.
    """

    sections: list[PlanSection] = Field(
        description="Section selections (template choices per section)", min_length=1
    )
    overall_strategy: str = Field(
        default="", description="High-level choreography strategy description"
    )

    model_config = ConfigDict(frozen=True)


# ============================================================================
# Judge Models
# ============================================================================


class JudgeDecision(str, Enum):
    """Judge decision enum."""

    APPROVE = "APPROVE"  # Ready to render (score >= 7.0)
    SOFT_FAIL = "SOFT_FAIL"  # Needs minor improvements (5.0-6.9)
    HARD_FAIL = "HARD_FAIL"  # Needs major revision (< 5.0)


class JudgeIssue(BaseModel):
    """Quality issue identified by judge."""

    severity: str = Field(description="Severity: 'minor', 'moderate', 'critical'")
    location: str = Field(description="Location of issue")
    issue: str = Field(description="Issue description")
    suggestion: str = Field(description="Suggested improvement")

    model_config = ConfigDict(frozen=True)


class JudgeResponse(BaseModel):
    """Judge evaluation result."""

    decision: JudgeDecision = Field(description="Approve, soft fail, or hard fail")
    score: float = Field(ge=0.0, le=10.0, description="Quality score (0-10)")
    strengths: list[str] = Field(description="What the plan does well", default_factory=list)
    issues: list[JudgeIssue] = Field(description="Issues to address", default_factory=list)
    feedback_for_planner: str = Field(description="Concise feedback for next iteration")
    overall_assessment: str = Field(description="Overall assessment summary")

    model_config = ConfigDict(frozen=True)
