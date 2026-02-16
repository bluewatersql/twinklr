"""Shared issue tracking models for agent feedback and validation.

These models provide structured issue reporting across all agents,
enabling consistent feedback tracking, resolution verification, and
iterative improvement.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class IssueCategory(str, Enum):
    """Category of identified issue.

    Categorizes issues by domain for better organization and filtering.
    """

    SCHEMA = "SCHEMA"  # Schema validation or structure issues
    TIMING = "TIMING"  # Timing, bar range, or alignment issues
    COVERAGE = "COVERAGE"  # Missing sections or gaps in coverage
    TEMPLATES = "TEMPLATES"  # Template selection or availability issues
    LAYERING = "LAYERING"  # Fixture group layering or coordination issues
    COORDINATION = "COORDINATION"  # Group coordination or transition issues
    SPATIAL = "SPATIAL"  # Spatial positioning or geometry issues
    VARIETY = "VARIETY"  # Lack of variety or repetition issues
    MUSICALITY = "MUSICALITY"  # Music synchronization or energy matching issues
    COMPLEXITY = "COMPLEXITY"  # Over/under-complexity issues
    STYLE = "STYLE"  # Style consistency or coherence issues
    PALETTE = "PALETTE"  # Palette selection, overuse, or coherence issues
    MOTIF_COHESION = "MOTIF_COHESION"  # Motif reuse, overreliance, or identity issues
    CONTRAST_DYNAMICS = "CONTRAST_DYNAMICS"  # Energy contrast or headroom issues
    DATA_QUALITY = "DATA_QUALITY"  # Input data quality or completeness issues
    LOGIC = "LOGIC"  # Logical consistency or contradiction issues
    CONSTRAINT = "CONSTRAINT"  # Constraint violation issues


class IssueSeverity(str, Enum):
    """Severity level of identified issue.

    Determines urgency and whether issue blocks progression.
    """

    ERROR = "ERROR"  # Must be fixed (blocks progression)
    WARN = "WARN"  # Should be fixed (quality improvement)
    NIT = "NIT"  # Nice to fix (minor improvement)


class IssueEffort(str, Enum):
    """Estimated effort to fix issue.

    Helps prioritize fixes and set expectations.
    """

    LOW = "LOW"  # Minor adjustment (quick fix)
    MEDIUM = "MEDIUM"  # Moderate changes (some rework)
    HIGH = "HIGH"  # Significant revision (major rework)


class IssueScope(str, Enum):
    """Scope of identified issue.

    Indicates how localized or widespread the issue is.
    """

    GLOBAL = "GLOBAL"  # Affects entire plan/output
    SECTION = "SECTION"  # Affects specific section
    LANE = "LANE"  # Affects specific lane (BASE/RHYTHM/ACCENT)
    GROUP = "GROUP"  # Affects fixture group or logical grouping
    PLACEMENT = "PLACEMENT"  # Affects specific placement within a lane
    EFFECT = "EFFECT"  # Affects specific effect or element
    BAR_RANGE = "BAR_RANGE"  # Affects specific bar range
    FIELD = "FIELD"  # Affects specific field or value


class SuggestedAction(str, Enum):
    """Suggested action to resolve issue.

    Guides the agent on how to address the issue in next iteration.
    """

    PATCH = "PATCH"  # Minor adjustment to existing plan
    REPLAN_SECTION = "REPLAN_SECTION"  # Replan specific section/component
    REPLAN_GLOBAL = "REPLAN_GLOBAL"  # Replan entire output
    IGNORE = "IGNORE"  # Can be safely ignored (informational)
    RETRY = "RETRY"  # Retry with same approach (transient error)


class IssueLocation(BaseModel):
    """Location of identified issue.

    Provides structured location information for precise issue tracking.
    All fields are optional to support various granularities.
    """

    section_id: str | None = Field(default=None, description="Section identifier")
    group_id: str | None = Field(default=None, description="Group identifier")
    effect_id: str | None = Field(default=None, description="Effect identifier")
    bar_start: int | None = Field(default=None, description="Start bar of issue location")
    bar_end: int | None = Field(default=None, description="End bar of issue location")
    field_path: str | None = Field(
        default=None, description="Dot-notation field path (e.g., 'sections.0.template_id')"
    )

    model_config = ConfigDict(frozen=True)


class Issue(BaseModel):
    """Detailed issue identified by validator or judge.

    Provides comprehensive issue tracking with stable IDs for resolution
    verification across iterations.

    Example:
        Issue(
            issue_id="VARIETY_LOW_CHORUS",
            category=IssueCategory.VARIETY,
            severity=IssueSeverity.WARN,
            estimated_effort=IssueEffort.LOW,
            scope=IssueScope.SECTION,
            location=IssueLocation(section_id="chorus_1", bar_start=25, bar_end=33),
            rule="DON'T repeat the same template 3+ times in high-energy sections without variation",
            message="Chorus uses same template 3 times without variation",
            fix_hint="Use different geometry types or presets for variety",
            acceptance_test="Chorus sections use at least 2 different templates or presets",
            suggested_action=SuggestedAction.PATCH,
            generic_example="Repeated template usage without variation in high-energy sections",
        )
    """

    issue_id: str = Field(
        description="Stable identifier for tracking across iterations (e.g., 'TIMING_OVERLAP')"
    )
    category: IssueCategory = Field(description="Issue category")
    severity: IssueSeverity = Field(description="Severity level")
    estimated_effort: IssueEffort = Field(description="Estimated effort to fix")
    scope: IssueScope = Field(description="Scope of issue")
    location: IssueLocation = Field(description="Location details")
    rule: str = Field(
        max_length=150,
        description="Generic guideline (<150 chars, 'DON'T...' format, no specific names)",
    )
    message: str = Field(description="Human-readable issue description")
    fix_hint: str = Field(description="One sentence, actionable fix suggestion")
    acceptance_test: str = Field(
        description="Deterministic check the next output must satisfy to resolve this issue"
    )
    suggested_action: SuggestedAction = Field(description="Suggested action to resolve")
    generic_example: str | None = Field(
        default=None,
        description=(
            "Optional generic example for learning context. "
            "Should be abstract/pattern-based to avoid biasing future judgments. "
            "Good: 'Repeated template usage without variation in high-energy sections' "
            "Bad: 'Section chorus_1 uses sweep_fan 3 times' (too specific)"
        ),
    )

    model_config = ConfigDict(frozen=True)

    def matches_location(self, section_id: str | None = None, bar: int | None = None) -> bool:
        """Check if issue matches given location criteria.

        Args:
            section_id: Optional section ID to match
            bar: Optional bar number to check if within issue's bar range

        Returns:
            True if issue matches location criteria
        """
        if section_id and self.location.section_id != section_id:
            return False

        if bar and self.location.bar_start and self.location.bar_end:
            if not (self.location.bar_start <= bar <= self.location.bar_end):
                return False

        return True
