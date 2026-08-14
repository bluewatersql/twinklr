"""Shared issue tracking models for agent feedback and validation.

These models provide structured issue reporting across all agents,
enabling consistent feedback tracking, resolution verification, and
iterative improvement.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IssueCategory(StrEnum):
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


class IssueSeverity(StrEnum):
    """Severity level of identified issue.

    Determines urgency and whether issue blocks progression.
    """

    ERROR = "ERROR"  # Must be fixed (blocks progression)
    WARN = "WARN"  # Should be fixed (quality improvement)
    NIT = "NIT"  # Nice to fix (minor improvement)


class IssueEffort(StrEnum):
    """Estimated effort to fix issue.

    Helps prioritize fixes and set expectations.
    """

    LOW = "LOW"  # Minor adjustment (quick fix)
    MEDIUM = "MEDIUM"  # Moderate changes (some rework)
    HIGH = "HIGH"  # Significant revision (major rework)


class IssueScope(StrEnum):
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


class SuggestedAction(StrEnum):
    """Suggested action to resolve issue.

    Guides the agent on how to address the issue in next iteration.
    """

    PATCH = "PATCH"  # Minor adjustment to existing plan
    REPLAN_SECTION = "REPLAN_SECTION"  # Replan specific section/component
    REPLAN_GLOBAL = "REPLAN_GLOBAL"  # Replan entire output
    IGNORE = "IGNORE"  # Can be safely ignored (informational)
    RETRY = "RETRY"  # Retry with same approach (transient error)


class ActionType(StrEnum):
    """Type of targeted fix action.

    Categorizes plan mutations for structured feedback.
    """

    ADD_TARGET = "ADD_TARGET"
    REMOVE_TARGET = "REMOVE_TARGET"
    ADD_PLACEMENT = "ADD_PLACEMENT"
    REMOVE_PLACEMENT = "REMOVE_PLACEMENT"
    SWAP_TEMPLATE = "SWAP_TEMPLATE"
    CHANGE_PALETTE = "CHANGE_PALETTE"
    CHANGE_THEME = "CHANGE_THEME"
    ADD_MOTIF = "ADD_MOTIF"
    REMOVE_MOTIF = "REMOVE_MOTIF"
    ADJUST_TIMING = "ADJUST_TIMING"
    REORDER_GROUPS = "REORDER_GROUPS"
    OTHER = "OTHER"


class TargetedAction(BaseModel):
    """A specific, directly actionable fix instruction.

    Shared by section judge (Issue) and holistic judge (CrossSectionIssue).
    Each action is a single mutation that can be applied to a
    SectionCoordinationPlan without further interpretation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_type: ActionType = Field(description="What kind of mutation to apply")
    section_id: str = Field(description="Target section")
    lane: str | None = Field(
        description="Lane kind (BASE, RHYTHM, ACCENT, BURST) if applicable",
    )
    target: str | None = Field(
        description="Target reference (e.g. 'group:ARCHES', 'zone:HOUSE')",
    )
    template_id: str | None = Field(
        description="Template to add, swap to, or remove",
    )
    replacement_template_id: str | None = Field(
        description="For SWAP_TEMPLATE: the template to replace with",
    )
    palette_id: str | None = Field(
        description="Palette reference (e.g. 'core.peppermint')",
    )
    bar: int | None = Field(ge=1, description="Bar number if applicable, or null")
    beat: int | None = Field(ge=1, description="Beat number if applicable, or null")
    bar_end: int | None = Field(ge=1, description="End bar for range-based actions, or null")
    description: str = Field(
        description="Human-readable explanation of the action",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        """Fill nullable action arms for existing deterministic constructors."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for key in (
            "lane",
            "target",
            "template_id",
            "replacement_template_id",
            "palette_id",
            "bar",
            "beat",
            "bar_end",
        ):
            normalized.setdefault(key, None)
        return normalized

    @model_validator(mode="after")
    def validate_fields_for_action_type(self) -> TargetedAction:
        """Ensure required fields are populated per action_type.

        Validation is intentionally lenient for fields that may be omitted
        when the action expresses removal intent (e.g. CHANGE_PALETTE
        without palette_id means "remove the current override").
        """
        at = self.action_type
        if at == ActionType.SWAP_TEMPLATE and (
            not self.template_id or not self.replacement_template_id
        ):
            raise ValueError("SWAP_TEMPLATE requires template_id and replacement_template_id")
        elif at in (ActionType.ADD_TARGET, ActionType.REMOVE_TARGET) and (
            not self.lane or not self.target
        ):
            raise ValueError(f"{at.value} requires lane and target")
        return self


class IssueLocation(BaseModel):
    """Location of identified issue.

    Provides structured location information for precise issue tracking.
    All fields are optional to support various granularities.
    """

    section_id: str | None = Field(description="Section identifier, or null")
    group_id: str | None = Field(description="Group identifier, or null")
    effect_id: str | None = Field(description="Effect identifier, or null")
    bar_start: int | None = Field(description="Start bar of issue location, or null")
    bar_end: int | None = Field(description="End bar of issue location, or null")
    field_path: str | None = Field(
        description="Dot-notation field path (e.g., 'sections.0.template_id'), or null"
    )

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        """Fill nullable coordinates for legacy partial locations."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for key in ("section_id", "group_id", "effect_id", "bar_start", "bar_end", "field_path"):
            normalized.setdefault(key, None)
        return normalized


class Issue(BaseModel):
    """Detailed issue identified by validator or judge.

    Provides comprehensive issue tracking with stable IDs for resolution
    verification across iterations.

    Example:
        Issue(
            issue_id="VARIETY_LOW_CHORUS",
            category=IssueCategory.VARIETY,
            severity=IssueSeverity.WARN,
            location=IssueLocation(section_id="chorus_1", bar_start=25, bar_end=33),
            rule="DON'T repeat the same template 3+ times in high-energy sections without variation",
            message="Chorus uses same template 3 times without variation",
            fix_hint="Use different geometry types or presets for variety",
            acceptance_test="Chorus sections use at least 2 different templates or presets",
            generic_example="Repeated template usage without variation in high-energy sections",
        )
    """

    issue_id: str = Field(
        description="Stable identifier for tracking across iterations (e.g., 'TIMING_OVERLAP')"
    )
    category: IssueCategory = Field(description="Issue category")
    severity: IssueSeverity = Field(description="Severity level")
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
    generic_example: str | None = Field(
        description=(
            "Optional generic example for learning context. "
            "Should be abstract/pattern-based to avoid biasing future judgments. "
            "Good: 'Repeated template usage without variation in high-energy sections' "
            "Bad: 'Section chorus_1 uses sweep_fan 3 times' (too specific)"
        ),
    )
    targeted_actions: list[TargetedAction] = Field(
        description=(
            "Structured fix actions (preferred over fix_hint when non-empty). "
            "Each action is a single mutation referencing concrete identifiers."
        ),
    )

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_input(cls, value: object) -> object:
        """Retain historical optional issue detail defaults for internal callers."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("generic_example", None)
        normalized.setdefault("targeted_actions", [])
        return normalized

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

        return not (
            bar
            and self.location.bar_start
            and self.location.bar_end
            and not (self.location.bar_start <= bar <= self.location.bar_end)
        )
