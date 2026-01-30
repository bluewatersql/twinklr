"""Tests for shared judge feedback manager."""

from twinklr.core.agents.issues import (
    Issue,
    IssueCategory,
    IssueEffort,
    IssueLocation,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
)
from twinklr.core.agents.shared.judge.feedback import (
    FeedbackManager,
    FeedbackType,
)
from twinklr.core.agents.shared.judge.models import JudgeVerdict, VerdictStatus


class TestFeedbackManagerJudgeVerdictIntegration:
    """Tests for add_judge_verdict() integration method."""

    def test_add_judge_verdict_soft_fail(self):
        """Test add_judge_verdict with SOFT_FAIL status."""
        manager = FeedbackManager(max_entries=10)

        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.5,
            confidence=0.8,
            overall_assessment="Needs improvement",
            feedback_for_planner="Add more variety to the choreography",
            iteration=1,
        )

        manager.add_judge_verdict(verdict=verdict, iteration=1)

        # Verify entry was added
        assert manager.count() == 1

        entries = manager.get_all()
        assert entries[0].type == FeedbackType.JUDGE_SOFT_FAILURE
        assert entries[0].message == "Add more variety to the choreography"
        assert entries[0].iteration == 1
        assert entries[0].metadata["score"] == 6.5

    def test_add_judge_verdict_hard_fail(self):
        """Test add_judge_verdict with HARD_FAIL status."""
        manager = FeedbackManager(max_entries=10)

        verdict = JudgeVerdict(
            status=VerdictStatus.HARD_FAIL,
            score=3.5,
            confidence=0.9,
            overall_assessment="Fundamental issues",
            feedback_for_planner="Completely revise the structure",
            iteration=2,
        )

        manager.add_judge_verdict(verdict=verdict, iteration=2)

        # Verify entry was added
        assert manager.count() == 1

        entries = manager.get_all()
        assert entries[0].type == FeedbackType.JUDGE_HARD_FAILURE
        assert entries[0].message == "Completely revise the structure"
        assert entries[0].iteration == 2
        assert entries[0].metadata["score"] == 3.5

    def test_add_judge_verdict_approve(self):
        """Test add_judge_verdict with APPROVE status (no-op)."""
        manager = FeedbackManager(max_entries=10)

        verdict = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.5,
            confidence=0.95,
            overall_assessment="Excellent plan",
            feedback_for_planner="Great work",
            iteration=1,
        )

        manager.add_judge_verdict(verdict=verdict, iteration=1)

        # APPROVE should not add feedback (no refinement needed)
        assert manager.count() == 0
        assert manager.is_empty()

    def test_add_judge_verdict_with_issues(self):
        """Test add_judge_verdict with structured issues."""
        manager = FeedbackManager(max_entries=10)

        issue = Issue(
            issue_id="timing-001",
            category=IssueCategory.TIMING,
            severity=IssueSeverity.WARN,
            message="Section timing mismatch",
            estimated_effort=IssueEffort.MEDIUM,
            scope=IssueScope.SECTION,
            location=IssueLocation(section_id="section-2"),
            fix_hint="Adjust section boundaries",
            acceptance_test="Section timing matches beat grid",
            suggested_action=SuggestedAction.PATCH,
        )

        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.85,
            overall_assessment="Timing issues",
            feedback_for_planner="Fix timing",
            issues=[issue],
            iteration=1,
        )

        manager.add_judge_verdict(verdict=verdict, iteration=1)

        entries = manager.get_all()
        assert len(entries[0].issues) == 1
        assert entries[0].issues[0].category == IssueCategory.TIMING

    def test_add_judge_verdict_includes_verdict_in_metadata(self):
        """Test that verdict is included in metadata."""
        manager = FeedbackManager(max_entries=10)

        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.5,
            confidence=0.8,
            overall_assessment="Needs work",
            feedback_for_planner="Improve",
            iteration=1,
        )

        manager.add_judge_verdict(verdict=verdict, iteration=1)

        entries = manager.get_all()
        assert "verdict" in entries[0].metadata
        assert entries[0].metadata["verdict"]["status"] == VerdictStatus.SOFT_FAIL
        assert entries[0].metadata["verdict"]["score"] == 6.5

    def test_add_judge_verdict_multiple_verdicts(self):
        """Test adding multiple verdicts across iterations."""
        manager = FeedbackManager(max_entries=10)

        verdict1 = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.8,
            overall_assessment="First attempt",
            feedback_for_planner="Improve variety",
            iteration=0,
        )

        verdict2 = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.8,
            confidence=0.85,
            overall_assessment="Better but still needs work",
            feedback_for_planner="Add more dynamics",
            iteration=1,
        )

        manager.add_judge_verdict(verdict=verdict1, iteration=0)
        manager.add_judge_verdict(verdict=verdict2, iteration=1)

        assert manager.count() == 2

        entries = manager.get_all()
        assert entries[0].iteration == 0
        assert entries[1].iteration == 1
        assert entries[0].metadata["score"] == 6.0
        assert entries[1].metadata["score"] == 6.8


class TestFeedbackManagerBackwardCompatibility:
    """Tests to ensure existing functionality still works."""

    def test_existing_add_methods_still_work(self):
        """Test that existing add_* methods are unchanged."""
        manager = FeedbackManager(max_entries=10)

        # Test all existing methods
        manager.add_validation_failure("Validation error", iteration=0)
        manager.add_judge_soft_failure("Soft fail", iteration=1, score=6.5)
        manager.add_judge_hard_failure("Hard fail", iteration=2, score=4.0)

        assert manager.count() == 3

        entries = manager.get_all()
        assert entries[0].type == FeedbackType.VALIDATION_FAILURE
        assert entries[1].type == FeedbackType.JUDGE_SOFT_FAILURE
        assert entries[2].type == FeedbackType.JUDGE_HARD_FAILURE

    def test_format_for_prompt_still_works(self):
        """Test that format_for_prompt is unchanged."""
        manager = FeedbackManager(max_entries=10)

        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.5,
            confidence=0.8,
            overall_assessment="Needs work",
            feedback_for_planner="Improve variety",
            iteration=1,
        )

        manager.add_judge_verdict(verdict=verdict, iteration=1)

        formatted = manager.format_for_prompt()

        assert "Feedback 1" in formatted
        assert "Improve variety" in formatted
        assert "iteration 1" in formatted
        assert "judge_soft_failure" in formatted
