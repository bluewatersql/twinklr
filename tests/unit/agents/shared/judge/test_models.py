"""Unit tests for shared judge models."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.issues import (
    Issue,
    IssueCategory,
    IssueEffort,
    IssueLocation,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
)
from twinklr.core.agents.shared.judge.models import (
    IterationState,
    JudgeVerdict,
    RevisionPriority,
    RevisionRequest,
    VerdictStatus,
)


class TestVerdictStatus:
    """Tests for VerdictStatus enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert VerdictStatus.APPROVE == "APPROVE"
        assert VerdictStatus.SOFT_FAIL == "SOFT_FAIL"
        assert VerdictStatus.HARD_FAIL == "HARD_FAIL"

    def test_requires_revision_approve(self):
        """Test requires_revision for APPROVE."""
        assert VerdictStatus.APPROVE.requires_revision is False

    def test_requires_revision_soft_fail(self):
        """Test requires_revision for SOFT_FAIL."""
        assert VerdictStatus.SOFT_FAIL.requires_revision is True

    def test_requires_revision_hard_fail(self):
        """Test requires_revision for HARD_FAIL."""
        assert VerdictStatus.HARD_FAIL.requires_revision is True

    def test_is_blocking_approve(self):
        """Test is_blocking for APPROVE."""
        assert VerdictStatus.APPROVE.is_blocking is False

    def test_is_blocking_soft_fail(self):
        """Test is_blocking for SOFT_FAIL."""
        assert VerdictStatus.SOFT_FAIL.is_blocking is False

    def test_is_blocking_hard_fail(self):
        """Test is_blocking for HARD_FAIL."""
        assert VerdictStatus.HARD_FAIL.is_blocking is True


class TestJudgeVerdict:
    """Tests for JudgeVerdict model."""

    def test_valid_verdict_minimal(self):
        """Test creating valid verdict with minimal fields."""
        verdict = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.5,
            confidence=0.9,
            overall_assessment="Plan looks good",
            feedback_for_planner="Good work",
            iteration=1,
        )
        assert verdict.status == VerdictStatus.APPROVE
        assert verdict.score == 8.5
        assert verdict.confidence == 0.9
        assert verdict.iteration == 1

    def test_valid_verdict_full(self):
        """Test creating valid verdict with all fields."""
        issue = Issue(
            issue_id="TEST_001",
            category=IssueCategory.TIMING,
            severity=IssueSeverity.ERROR,
            estimated_effort=IssueEffort.MEDIUM,
            scope=IssueScope.SECTION,
            location=IssueLocation(),
            message="Test issue",
            fix_hint="Fix the timing",
            acceptance_test="Timing is correct",
            suggested_action=SuggestedAction.PATCH,
        )

        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.5,
            confidence=0.85,
            strengths=["Good variety", "Nice energy match"],
            issues=[issue],
            overall_assessment="Needs minor improvements",
            feedback_for_planner="Adjust timing",
            score_breakdown={"musicality": 7.0, "variety": 6.0},
            iteration=2,
        )

        assert len(verdict.strengths) == 2
        assert len(verdict.issues) == 1
        assert len(verdict.score_breakdown) == 2

    def test_score_validation_min(self):
        """Test score validation - too low."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeVerdict(
                status=VerdictStatus.APPROVE,
                score=-1.0,
                confidence=0.9,
                overall_assessment="Test",
                feedback_for_planner="Test",
                iteration=1,
            )
        assert "score" in str(exc_info.value).lower()

    def test_score_validation_max(self):
        """Test score validation - too high."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeVerdict(
                status=VerdictStatus.APPROVE,
                score=11.0,
                confidence=0.9,
                overall_assessment="Test",
                feedback_for_planner="Test",
                iteration=1,
            )
        assert "score" in str(exc_info.value).lower()

    def test_confidence_validation_min(self):
        """Test confidence validation - too low."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeVerdict(
                status=VerdictStatus.APPROVE,
                score=8.0,
                confidence=-0.1,
                overall_assessment="Test",
                feedback_for_planner="Test",
                iteration=1,
            )
        assert "confidence" in str(exc_info.value).lower()

    def test_confidence_validation_max(self):
        """Test confidence validation - too high."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeVerdict(
                status=VerdictStatus.APPROVE,
                score=8.0,
                confidence=1.1,
                overall_assessment="Test",
                feedback_for_planner="Test",
                iteration=1,
            )
        assert "confidence" in str(exc_info.value).lower()

    def test_frozen_immutable(self):
        """Test verdict is frozen (immutable)."""
        verdict = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.0,
            confidence=0.9,
            overall_assessment="Test",
            feedback_for_planner="Test",
            iteration=1,
        )

        with pytest.raises(ValidationError):
            verdict.score = 9.0

    def test_extra_forbid(self):
        """Test extra fields are forbidden."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeVerdict(
                status=VerdictStatus.APPROVE,
                score=8.0,
                confidence=0.9,
                overall_assessment="Test",
                feedback_for_planner="Test",
                iteration=1,
                extra_field="not allowed",
            )
        assert "extra" in str(exc_info.value).lower()

    def test_requires_revision_property(self):
        """Test requires_revision property."""
        approve = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.0,
            confidence=0.9,
            overall_assessment="Test",
            feedback_for_planner="Test",
            iteration=1,
        )
        assert approve.requires_revision is False

        soft_fail = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.9,
            overall_assessment="Test",
            feedback_for_planner="Test",
            iteration=1,
        )
        assert soft_fail.requires_revision is True

    def test_critical_issues_property(self):
        """Test critical_issues property filters ERROR severity."""
        error_issue = Issue(
            issue_id="ERR_001",
            category=IssueCategory.TIMING,
            severity=IssueSeverity.ERROR,
            estimated_effort=IssueEffort.HIGH,
            scope=IssueScope.SECTION,
            location=IssueLocation(),
            message="Critical error",
            fix_hint="Fix immediately",
            acceptance_test="Error resolved",
            suggested_action=SuggestedAction.REPLAN_SECTION,
        )
        warn_issue = Issue(
            issue_id="WARN_001",
            category=IssueCategory.VARIETY,
            severity=IssueSeverity.WARN,
            estimated_effort=IssueEffort.LOW,
            scope=IssueScope.GLOBAL,
            location=IssueLocation(),
            message="Warning",
            fix_hint="Add variety",
            acceptance_test="Variety improved",
            suggested_action=SuggestedAction.PATCH,
        )

        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.9,
            issues=[error_issue, warn_issue],
            overall_assessment="Test",
            feedback_for_planner="Test",
            iteration=1,
        )

        critical = verdict.critical_issues
        assert len(critical) == 1
        assert critical[0].severity == IssueSeverity.ERROR

    def test_has_blocking_issues_true(self):
        """Test has_blocking_issues with ERROR issues."""
        error_issue = Issue(
            issue_id="ERR_001",
            category=IssueCategory.TIMING,
            severity=IssueSeverity.ERROR,
            estimated_effort=IssueEffort.HIGH,
            scope=IssueScope.SECTION,
            location=IssueLocation(),
            message="Critical error",
            fix_hint="Fix immediately",
            acceptance_test="Error resolved",
            suggested_action=SuggestedAction.REPLAN_SECTION,
        )

        verdict = JudgeVerdict(
            status=VerdictStatus.HARD_FAIL,
            score=4.0,
            confidence=0.9,
            issues=[error_issue],
            overall_assessment="Test",
            feedback_for_planner="Test",
            iteration=1,
        )

        assert verdict.has_blocking_issues is True

    def test_has_blocking_issues_false(self):
        """Test has_blocking_issues without ERROR issues."""
        warn_issue = Issue(
            issue_id="WARN_001",
            category=IssueCategory.VARIETY,
            severity=IssueSeverity.WARN,
            estimated_effort=IssueEffort.LOW,
            scope=IssueScope.GLOBAL,
            location=IssueLocation(),
            message="Warning",
            fix_hint="Add variety",
            acceptance_test="Variety improved",
            suggested_action=SuggestedAction.PATCH,
        )

        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.9,
            issues=[warn_issue],
            overall_assessment="Test",
            feedback_for_planner="Test",
            iteration=1,
        )

        assert verdict.has_blocking_issues is False


class TestRevisionRequest:
    """Tests for RevisionRequest model."""

    def test_valid_revision_request(self):
        """Test creating valid revision request."""
        request = RevisionRequest(
            priority=RevisionPriority.HIGH,
            focus_areas=["Timing", "Variety"],
            specific_fixes=["Fix section overlap", "Add more variety"],
            avoid=["Keep current energy"],
            context_for_planner="Focus on timing issues",
        )

        assert request.priority == RevisionPriority.HIGH
        assert len(request.focus_areas) == 2
        assert len(request.specific_fixes) == 2
        assert len(request.avoid) == 1

    def test_focus_areas_min_length(self):
        """Test focus_areas requires at least 1 item."""
        with pytest.raises(ValidationError) as exc_info:
            RevisionRequest(
                priority=RevisionPriority.HIGH,
                focus_areas=[],
                specific_fixes=["Fix something"],
                context_for_planner="Test",
            )
        assert "focus_areas" in str(exc_info.value).lower()

    def test_specific_fixes_min_length(self):
        """Test specific_fixes requires at least 1 item."""
        with pytest.raises(ValidationError) as exc_info:
            RevisionRequest(
                priority=RevisionPriority.HIGH,
                focus_areas=["Timing"],
                specific_fixes=[],
                context_for_planner="Test",
            )
        assert "specific_fixes" in str(exc_info.value).lower()

    def test_from_verdict_hard_fail(self):
        """Test from_verdict with HARD_FAIL."""
        error_issue = Issue(
            issue_id="ERR_001",
            category=IssueCategory.TIMING,
            severity=IssueSeverity.ERROR,
            estimated_effort=IssueEffort.HIGH,
            scope=IssueScope.SECTION,
            location=IssueLocation(),
            message="Critical timing error",
            fix_hint="Fix the timing issues",
            acceptance_test="Timing is correct",
            suggested_action=SuggestedAction.REPLAN_SECTION,
        )

        verdict = JudgeVerdict(
            status=VerdictStatus.HARD_FAIL,
            score=3.0,
            confidence=0.9,
            strengths=["Good energy"],
            issues=[error_issue],
            overall_assessment="Major issues",
            feedback_for_planner="Fix timing problems",
            iteration=1,
        )

        request = RevisionRequest.from_verdict(verdict)

        assert request.priority == RevisionPriority.CRITICAL
        assert "TIMING" in request.focus_areas
        assert len(request.specific_fixes) > 0

    def test_from_verdict_soft_fail_low_score(self):
        """Test from_verdict with SOFT_FAIL and score < 6.0."""
        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=5.5,
            confidence=0.9,
            strengths=["Good variety"],
            issues=[],
            overall_assessment="Needs improvement",
            feedback_for_planner="Improve quality",
            iteration=1,
        )

        request = RevisionRequest.from_verdict(verdict)

        assert request.priority == RevisionPriority.HIGH

    def test_from_verdict_soft_fail_high_score(self):
        """Test from_verdict with SOFT_FAIL and score >= 6.0."""
        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.5,
            confidence=0.9,
            strengths=["Good variety"],
            issues=[],
            overall_assessment="Minor improvements needed",
            feedback_for_planner="Polish a bit",
            iteration=1,
        )

        request = RevisionRequest.from_verdict(verdict)

        assert request.priority == RevisionPriority.MEDIUM

    def test_from_verdict_with_validation_errors(self):
        """Test from_verdict with both verdict issues and validation errors."""
        issue = Issue(
            issue_id="TEST_001",
            category=IssueCategory.SCHEMA,
            severity=IssueSeverity.ERROR,
            estimated_effort=IssueEffort.MEDIUM,
            scope=IssueScope.FIELD,
            location=IssueLocation(),
            message="Schema validation failed",
            fix_hint="Fix the schema",
            acceptance_test="Schema validates",
            suggested_action=SuggestedAction.PATCH,
        )

        verdict = JudgeVerdict(
            status=VerdictStatus.HARD_FAIL,
            score=4.0,
            confidence=0.9,
            strengths=["Good energy"],
            issues=[issue],
            overall_assessment="Major issues",
            feedback_for_planner="Fix schema and timing",
            iteration=1,
        )

        validation_errors = ["Missing required field", "Invalid bar range"]
        request = RevisionRequest.from_verdict(verdict, validation_errors)

        assert request.priority == RevisionPriority.CRITICAL
        # Validation errors should be at the beginning
        assert "Missing required field" in request.specific_fixes[0]
        assert "Invalid bar range" in request.specific_fixes[1]

    def test_from_verdict_preserves_strengths(self):
        """Test from_verdict preserves strengths in avoid list."""
        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.9,
            strengths=["Excellent variety", "Great energy match", "Good timing"],
            issues=[],
            overall_assessment="Minor improvements",
            feedback_for_planner="Polish details",
            iteration=1,
        )

        request = RevisionRequest.from_verdict(verdict)

        # Should preserve up to 3 strengths
        assert len(request.avoid) <= 3
        assert all("Keep:" in item for item in request.avoid)


class TestIterationState:
    """Tests for IterationState enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert IterationState.NOT_STARTED == "NOT_STARTED"
        assert IterationState.PLANNING == "PLANNING"
        assert IterationState.VALIDATING == "VALIDATING"
        assert IterationState.VALIDATION_FAILED == "VALIDATION_FAILED"
        assert IterationState.JUDGING == "JUDGING"
        assert IterationState.JUDGE_APPROVED == "JUDGE_APPROVED"
        assert IterationState.JUDGE_SOFT_FAIL == "JUDGE_SOFT_FAIL"
        assert IterationState.JUDGE_HARD_FAIL == "JUDGE_HARD_FAIL"
        assert IterationState.MAX_ITERATIONS_REACHED == "MAX_ITERATIONS_REACHED"
        assert IterationState.TOKEN_BUDGET_EXCEEDED == "TOKEN_BUDGET_EXCEEDED"
        assert IterationState.COMPLETE == "COMPLETE"
        assert IterationState.FAILED == "FAILED"

    def test_is_terminal_true(self):
        """Test is_terminal for terminal states."""
        assert IterationState.MAX_ITERATIONS_REACHED.is_terminal is True
        assert IterationState.TOKEN_BUDGET_EXCEEDED.is_terminal is True
        assert IterationState.COMPLETE.is_terminal is True
        assert IterationState.FAILED.is_terminal is True

    def test_is_terminal_false(self):
        """Test is_terminal for non-terminal states."""
        assert IterationState.NOT_STARTED.is_terminal is False
        assert IterationState.PLANNING.is_terminal is False
        assert IterationState.VALIDATING.is_terminal is False
        assert IterationState.JUDGING.is_terminal is False
        assert IterationState.JUDGE_SOFT_FAIL.is_terminal is False

    def test_is_success_true(self):
        """Test is_success for successful completion."""
        assert IterationState.COMPLETE.is_success is True

    def test_is_success_false(self):
        """Test is_success for non-successful states."""
        assert IterationState.MAX_ITERATIONS_REACHED.is_success is False
        assert IterationState.FAILED.is_success is False
        assert IterationState.PLANNING.is_success is False

    def test_requires_revision_true(self):
        """Test requires_revision for states needing revision."""
        assert IterationState.VALIDATION_FAILED.requires_revision is True
        assert IterationState.JUDGE_SOFT_FAIL.requires_revision is True
        assert IterationState.JUDGE_HARD_FAIL.requires_revision is True

    def test_requires_revision_false(self):
        """Test requires_revision for states not needing revision."""
        assert IterationState.PLANNING.requires_revision is False
        assert IterationState.JUDGE_APPROVED.requires_revision is False
        assert IterationState.COMPLETE.requires_revision is False
