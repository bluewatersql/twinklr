"""Shared judge models for agent iteration and quality control.

This module provides standardized models for judge evaluation, revision requests,
and iteration state management across all V2 agents.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.agents.issues import Issue, IssueSeverity


class VerdictStatus(str, Enum):
    """Judge verdict status.

    Determines whether plan is accepted or requires revision.
    - APPROVE: Ready for next stage (score >= 7.0)
    - SOFT_FAIL: Minor issues, refine (score 5.0-6.9)
    - HARD_FAIL: Major issues, revise (score < 5.0)
    """

    APPROVE = "APPROVE"
    SOFT_FAIL = "SOFT_FAIL"
    HARD_FAIL = "HARD_FAIL"

    @property
    def requires_revision(self) -> bool:
        """Check if verdict requires revision.

        Returns:
            True if status is SOFT_FAIL or HARD_FAIL
        """
        return self in (VerdictStatus.SOFT_FAIL, VerdictStatus.HARD_FAIL)

    @property
    def is_blocking(self) -> bool:
        """Check if verdict is blocking (HARD_FAIL).

        Returns:
            True if status is HARD_FAIL
        """
        return self == VerdictStatus.HARD_FAIL


class JudgeVerdict(BaseModel):
    """Judge evaluation verdict.

    Comprehensive evaluation result from judge agent, including structured
    feedback for iterative refinement.

    This is the standardized judge output across all V2 agents.

    Attributes:
        status: Approve, soft fail, or hard fail
        score: Overall quality score (0-10)
        confidence: Judge confidence in evaluation (0-1)
        strengths: What the plan does well (2-5 items)
        issues: Detailed issues to address
        overall_assessment: Overall assessment summary (2-4 sentences)
        feedback_for_planner: Concise feedback for next iteration (2-4 sentences)
        score_breakdown: Named dimension scores (e.g., musicality: 8.5)
        iteration: Iteration number when verdict issued
    """

    # Core verdict
    status: VerdictStatus = Field(description="Approve, soft fail, or hard fail")
    score: float = Field(ge=0.0, le=10.0, description="Overall quality score (0-10)")
    confidence: float = Field(ge=0.0, le=1.0, description="Judge confidence in evaluation (0-1)")

    # Structured feedback
    strengths: list[str] = Field(
        description="What the plan does well (2-5 items)",
        default_factory=list,
    )
    issues: list[Issue] = Field(
        description="Detailed issues to address",
        default_factory=list,
    )

    # Narrative feedback
    overall_assessment: str = Field(description="Overall assessment summary (2-4 sentences)")
    feedback_for_planner: str = Field(
        description="Concise feedback for next iteration (2-4 sentences)"
    )

    # Transparency
    score_breakdown: dict[str, float] = Field(
        description="Named dimension scores (e.g., musicality: 8.5, variety: 7.0)",
        default_factory=dict,
    )

    # Metadata
    iteration: int = Field(ge=0, description="Iteration number when verdict issued")

    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)

    @model_validator(mode="after")
    def enforce_status_matches_score(self) -> "JudgeVerdict":
        """Enforce that status matches score thresholds.

        The prompts instruct judges to set status based on score thresholds:
        - APPROVE: score >= 7.0
        - SOFT_FAIL: score 5.0-6.9
        - HARD_FAIL: score < 5.0

        This validator overrides status if it doesn't match, ensuring consistent
        behavior and improving first-iteration approval rates when plans score >= 7.0.

        Returns:
            JudgeVerdict with corrected status if needed
        """
        expected_status = self._expected_status_for_score(self.score)

        if self.status != expected_status:
            # Override status to match score threshold
            # Use object.__setattr__ because model is frozen
            object.__setattr__(self, "status", expected_status)

        return self

    @staticmethod
    def _expected_status_for_score(score: float) -> VerdictStatus:
        """Determine expected status for a given score.

        Args:
            score: Quality score (0-10)

        Returns:
            Expected VerdictStatus based on score thresholds
        """
        if score >= 7.0:
            return VerdictStatus.APPROVE
        elif score >= 5.0:
            return VerdictStatus.SOFT_FAIL
        else:
            return VerdictStatus.HARD_FAIL

    @property
    def requires_revision(self) -> bool:
        """Check if verdict requires revision.

        Returns:
            True if status requires revision
        """
        return self.status.requires_revision

    @property
    def critical_issues(self) -> list[Issue]:
        """Get ERROR severity issues only.

        Returns:
            List of issues with ERROR severity
        """
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    @property
    def has_blocking_issues(self) -> bool:
        """Check if verdict has blocking (ERROR) issues.

        Returns:
            True if any issues have ERROR severity
        """
        return len(self.critical_issues) > 0


class RevisionPriority(str, Enum):
    """Revision priority level.

    - CRITICAL: Must fix (blocks APPROVE)
    - HIGH: Should fix (impacts score significantly)
    - MEDIUM: Nice to fix (minor impact)
    - LOW: Optional (polish)
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RevisionRequest(BaseModel):
    """Structured revision request for next iteration.

    Provides actionable guidance for planner refinement based on
    judge verdict and validation failures.

    Attributes:
        priority: Revision priority level
        focus_areas: Key areas to focus on (2-5 items)
        specific_fixes: Specific actionable fixes (3-8 items)
        avoid: What NOT to change (preserve strengths)
        context_for_planner: Additional context to guide revision
    """

    priority: RevisionPriority = Field(description="Revision priority")
    focus_areas: list[str] = Field(
        description="Key areas to focus on (2-5 items)",
        min_length=1,
        max_length=10,
    )
    specific_fixes: list[str] = Field(
        description="Specific actionable fixes (3-8 items, max 25 for complex cases)",
        min_length=1,
        max_length=25,
    )
    avoid: list[str] = Field(
        description="What NOT to change (preserve strengths)",
        default_factory=list,
        max_length=5,
    )
    context_for_planner: str = Field(
        description="Additional context to guide revision (1-3 sentences)",
    )

    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)

    @classmethod
    def from_verdict(
        cls,
        verdict: JudgeVerdict,
        validation_errors: list[str] | None = None,
    ) -> "RevisionRequest":
        """Create revision request from judge verdict.

        Args:
            verdict: Judge verdict
            validation_errors: Optional validation errors to prepend

        Returns:
            RevisionRequest with priority and guidance
        """
        # Determine priority
        if verdict.status == VerdictStatus.HARD_FAIL or verdict.has_blocking_issues:
            priority = RevisionPriority.CRITICAL
        elif verdict.status == VerdictStatus.SOFT_FAIL:
            priority = RevisionPriority.HIGH if verdict.score < 6.0 else RevisionPriority.MEDIUM
        else:
            priority = RevisionPriority.LOW

        # Extract focus areas from issues (unique categories)
        focus_areas = list({issue.category.value for issue in verdict.issues[:5]})
        if not focus_areas:
            focus_areas = ["Quality improvement"]

        # Extract specific fixes — prefer structured actions over free-text hints
        specific_fixes: list[str] = []
        for issue in verdict.issues[:8]:
            if issue.targeted_actions:
                specific_fixes.extend(action.description for action in issue.targeted_actions)
            elif issue.fix_hint:
                specific_fixes.append(issue.fix_hint)

        # Prepend validation errors if provided
        if validation_errors:
            specific_fixes = list(validation_errors[:3]) + specific_fixes

        # Ensure at least one fix
        if not specific_fixes:
            specific_fixes = [verdict.feedback_for_planner]

        # Preserve strengths
        avoid = [f"Keep: {s}" for s in verdict.strengths[:3]]

        return cls(
            priority=priority,
            focus_areas=focus_areas,
            specific_fixes=specific_fixes,
            avoid=avoid,
            context_for_planner=verdict.feedback_for_planner,
        )


class IterationState(str, Enum):
    """State of iteration loop.

    Tracks progression through judge iteration cycle.
    """

    # Initial states
    NOT_STARTED = "NOT_STARTED"
    PLANNING = "PLANNING"

    # Validation states
    VALIDATING = "VALIDATING"
    VALIDATION_FAILED = "VALIDATION_FAILED"

    # Judging states
    JUDGING = "JUDGING"
    JUDGE_APPROVED = "JUDGE_APPROVED"
    JUDGE_SOFT_FAIL = "JUDGE_SOFT_FAIL"
    JUDGE_HARD_FAIL = "JUDGE_HARD_FAIL"

    # Terminal states
    MAX_ITERATIONS_REACHED = "MAX_ITERATIONS_REACHED"
    TOKEN_BUDGET_EXCEEDED = "TOKEN_BUDGET_EXCEEDED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        """Check if state is terminal.

        Returns:
            True if state is a terminal state
        """
        return self in (
            IterationState.MAX_ITERATIONS_REACHED,
            IterationState.TOKEN_BUDGET_EXCEEDED,
            IterationState.COMPLETE,
            IterationState.FAILED,
        )

    @property
    def is_success(self) -> bool:
        """Check if state represents success.

        Returns:
            True if state is COMPLETE
        """
        return self == IterationState.COMPLETE

    @property
    def requires_revision(self) -> bool:
        """Check if state requires revision.

        Returns:
            True if state indicates need for revision
        """
        return self in (
            IterationState.VALIDATION_FAILED,
            IterationState.JUDGE_SOFT_FAIL,
            IterationState.JUDGE_HARD_FAIL,
        )
