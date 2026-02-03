"""Integration tests for agent learning system.

Tests the full integration of IssueRepository, FeedbackManager, and IterationController.
"""

from pathlib import Path
import tempfile

import pytest

from twinklr.core.agents.analytics.repository import IssueRepository
from twinklr.core.agents.issues import (
    Issue,
    IssueCategory,
    IssueEffort,
    IssueLocation,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
)
from twinklr.core.agents.shared.judge.controller import IterationConfig, StandardIterationController
from twinklr.core.agents.shared.judge.feedback import FeedbackManager
from twinklr.core.agents.shared.judge.models import JudgeVerdict, VerdictStatus


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_issues():
    """Create sample issues for testing."""
    return [
        Issue(
            issue_id="VARIETY_LOW_CHORUS",
            category=IssueCategory.VARIETY,
            severity=IssueSeverity.WARN,
            estimated_effort=IssueEffort.LOW,
            scope=IssueScope.SECTION,
            location=IssueLocation(section_id="chorus_1", bar_start=25, bar_end=33),
            rule="DON'T repeat templates 3+ times in high-energy sections",
            message="Chorus uses same template 3 times without variation",
            fix_hint="Use different geometry types or presets for variety",
            acceptance_test="Chorus sections use at least 2 different templates or presets",
            suggested_action=SuggestedAction.PATCH,
            generic_example="Repeated template usage without variation in high-energy sections",
        ),
        Issue(
            issue_id="MUSICALITY_ENERGY_MISMATCH",
            category=IssueCategory.MUSICALITY,
            severity=IssueSeverity.WARN,
            estimated_effort=IssueEffort.MEDIUM,
            scope=IssueScope.SECTION,
            location=IssueLocation(section_id="verse_1", bar_start=1, bar_end=8),
            rule="DON'T use high intensity in low-energy sections",
            message="Verse energy level too high for audio profile",
            fix_hint="Reduce intensity to match audio profile energy",
            acceptance_test="Verse intensity matches audio profile energy level",
            suggested_action=SuggestedAction.PATCH,
            generic_example="Energy mismatch between plan and audio profile",
        ),
    ]


def test_feedback_manager_records_to_repository(temp_storage, sample_issues):
    """Test FeedbackManager automatically records issues to repository."""
    # Create repository
    repo = IssueRepository(storage_dir=temp_storage, enabled=True)

    # Create feedback manager with repository
    feedback = FeedbackManager(
        max_entries=25,
        agent_name="test_judge",
        job_id="job_123",
        issue_repository=repo,
    )

    # Create verdict with issues
    verdict = JudgeVerdict(
        status=VerdictStatus.SOFT_FAIL,
        score=6.5,
        confidence=0.85,
        strengths=["Good timing", "Clear structure"],
        issues=sample_issues,
        overall_assessment="Good plan with some variety issues",
        feedback_for_planner="Address variety and energy concerns",
        score_breakdown={"musicality": 7.0, "variety": 6.0},
        iteration=1,
    )

    # Add verdict to feedback manager
    feedback.add_judge_verdict(verdict, iteration=1)

    # Check issues were recorded to repository
    file_path = temp_storage / "test_judge_issues.jsonl"
    assert file_path.exists()

    # Verify top issues
    top_issues = repo.get_top_issues("test_judge", top_n=5, min_occurrences=1)
    assert len(top_issues) == 2

    # Check categories
    categories = {cat for cat, _, _ in top_issues}
    assert IssueCategory.VARIETY in categories
    assert IssueCategory.MUSICALITY in categories


def test_resolution_tracking_across_iterations(temp_storage, sample_issues):
    """Test that issue resolution is tracked across multiple jobs."""
    repo = IssueRepository(storage_dir=temp_storage, enabled=True)

    # Simulate multiple jobs to get enough data for resolution tracking
    # Jobs 1-3: Both VARIETY and MUSICALITY issues
    for job_num in range(3):
        feedback = FeedbackManager(
            max_entries=25,
            agent_name="test_judge",
            job_id=f"job_{job_num}",
            issue_repository=repo,
        )
        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.85,
            strengths=[],
            issues=sample_issues,  # Both issues
            overall_assessment="Issues to address",
            feedback_for_planner="Fix variety and musicality",
            score_breakdown={},
            iteration=1,
        )
        feedback.add_judge_verdict(verdict, iteration=1)

    # Jobs 4-5: Only VARIETY issue (MUSICALITY resolved)
    for job_num in range(3, 5):
        feedback = FeedbackManager(
            max_entries=25,
            agent_name="test_judge",
            job_id=f"job_{job_num}",
            issue_repository=repo,
        )
        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.8,
            confidence=0.85,
            strengths=[],
            issues=[sample_issues[0]],  # Only VARIETY issue
            overall_assessment="Musicality fixed, variety remains",
            feedback_for_planner="Address remaining variety issue",
            score_breakdown={},
            iteration=1,
        )
        feedback.add_judge_verdict(verdict, iteration=1)

    # Check resolution rate
    # Old records (jobs 0-2): VARIETY + MUSICALITY = 6 issues
    # Recent records (jobs 3-4): VARIETY only = 2 issues
    # Issue IDs in old: {VARIETY_LOW_CHORUS, MUSICALITY_ENERGY_MISMATCH}
    # Issue IDs in recent: {VARIETY_LOW_CHORUS}
    # Resolved: MUSICALITY_ENERGY_MISMATCH
    # Resolution rate: 1/2 = 50%
    rate = repo.get_resolution_rate("test_judge")

    assert rate > 0.0  # At least MUSICALITY was resolved
    assert rate <= 1.0  # At most 100% resolved


def test_learning_context_formatting(temp_storage, sample_issues):
    """Test that learning context is properly formatted."""
    repo = IssueRepository(storage_dir=temp_storage, enabled=True)
    feedback = FeedbackManager(
        max_entries=25,
        agent_name="macro_planner_judge",
        job_id="job_123",
        issue_repository=repo,
    )

    # Simulate multiple jobs with recurring issues
    for job_num in range(3):
        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.5,
            confidence=0.85,
            strengths=[],
            issues=sample_issues,
            overall_assessment="Issues to address",
            feedback_for_planner="Fix variety and musicality",
            score_breakdown={},
            iteration=1,
        )
        feedback = FeedbackManager(
            max_entries=25,
            agent_name="macro_planner_judge",
            job_id=f"job_{job_num}",
            issue_repository=repo,
        )
        feedback.add_judge_verdict(verdict, iteration=1)

    # Get learning context
    learning_context = repo.format_learning_context(
        agent_name="macro_planner_judge",
        top_n=5,
        include_resolution_rate=True,
    )

    # Verify content
    assert "Historical Learning Context" in learning_context
    assert "VARIETY" in learning_context
    assert "MUSICALITY" in learning_context
    assert "occurred" in learning_context
    assert "Repeated template usage" in learning_context
    assert "Energy mismatch" in learning_context


def test_iteration_controller_creates_repository(temp_storage):
    """Test that IterationController creates repository automatically."""
    config = IterationConfig(
        max_iterations=3,
        enable_issue_tracking=True,
        issue_tracking_storage_dir=temp_storage,
    )

    controller = StandardIterationController(
        config=config,
        job_id="test_job",
    )

    # Check repository was created
    assert controller.issue_repository is not None
    assert controller.issue_repository.enabled is True
    assert controller.issue_repository.storage_dir == temp_storage


def test_iteration_controller_disabled_tracking(temp_storage):
    """Test that IterationController respects disabled tracking."""
    config = IterationConfig(
        max_iterations=3,
        enable_issue_tracking=False,
    )

    controller = StandardIterationController(
        config=config,
        job_id="test_job",
    )

    # Check repository was not created
    assert controller.issue_repository is None


def test_feedback_manager_with_learning_context(temp_storage, sample_issues):
    """Test FeedbackManager formats with learning context."""
    repo = IssueRepository(storage_dir=temp_storage, enabled=True)

    # Populate repository with historical data
    for i in range(3):
        feedback = FeedbackManager(
            max_entries=25,
            agent_name="test_judge",
            job_id=f"job_{i}",
            issue_repository=repo,
        )
        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.5,
            confidence=0.85,
            strengths=[],
            issues=sample_issues,
            overall_assessment="Issues to address",
            feedback_for_planner="Fix variety and musicality",
            score_breakdown={},
            iteration=1,
        )
        feedback.add_judge_verdict(verdict, iteration=1)

    # Create new feedback manager for new job
    feedback = FeedbackManager(
        max_entries=25,
        agent_name="test_judge",
        job_id="job_new",
        issue_repository=repo,
    )

    # Format with learning context
    formatted = feedback.format_with_learning_context(
        include_historical=True,
        top_n_historical=5,
    )

    # Should include historical learning context
    assert "Historical Learning Context" in formatted
    assert "VARIETY" in formatted


def test_multiple_agents_isolated_learning(temp_storage, sample_issues):
    """Test that different agents have isolated learning contexts."""
    repo = IssueRepository(storage_dir=temp_storage, enabled=True)

    # Agent 1: Record VARIETY issues
    feedback1 = FeedbackManager(
        max_entries=25,
        agent_name="agent_1",
        job_id="job_1",
        issue_repository=repo,
    )
    verdict1 = JudgeVerdict(
        status=VerdictStatus.SOFT_FAIL,
        score=6.5,
        confidence=0.85,
        strengths=[],
        issues=[sample_issues[0]],  # VARIETY only
        overall_assessment="Variety issue",
        feedback_for_planner="Fix variety",
        score_breakdown={},
        iteration=1,
    )
    feedback1.add_judge_verdict(verdict1, iteration=1)

    # Agent 2: Record MUSICALITY issues
    feedback2 = FeedbackManager(
        max_entries=25,
        agent_name="agent_2",
        job_id="job_2",
        issue_repository=repo,
    )
    verdict2 = JudgeVerdict(
        status=VerdictStatus.SOFT_FAIL,
        score=6.5,
        confidence=0.85,
        strengths=[],
        issues=[sample_issues[1]],  # MUSICALITY only
        overall_assessment="Musicality issue",
        feedback_for_planner="Fix musicality",
        score_breakdown={},
        iteration=1,
    )
    feedback2.add_judge_verdict(verdict2, iteration=1)

    # Get learning contexts
    context1 = repo.format_learning_context("agent_1", top_n=5)
    context2 = repo.format_learning_context("agent_2", top_n=5)

    # Agent 1 should only see VARIETY
    assert "VARIETY" in context1
    assert "MUSICALITY" not in context1

    # Agent 2 should only see MUSICALITY
    assert "MUSICALITY" in context2
    assert "VARIETY" not in context2


def test_generic_examples_in_learning_context(temp_storage):
    """Test that generic examples appear in learning context."""
    repo = IssueRepository(storage_dir=temp_storage, enabled=True)

    # Create issue with generic example
    issue_with_example = Issue(
        issue_id="TEST_ISSUE",
        category=IssueCategory.VARIETY,
        severity=IssueSeverity.WARN,
        estimated_effort=IssueEffort.LOW,
        scope=IssueScope.SECTION,
        location=IssueLocation(),
        rule="DON'T use repetitive patterns without variation",
        message="Specific message about section X",
        fix_hint="Fix section X",
        acceptance_test="Section X fixed",
        suggested_action=SuggestedAction.PATCH,
        generic_example="Generic pattern: insufficient variety in repeated sections",
    )

    # Record multiple times
    for i in range(3):
        feedback = FeedbackManager(
            max_entries=25,
            agent_name="test_judge",
            job_id=f"job_{i}",
            issue_repository=repo,
        )
        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.5,
            confidence=0.85,
            strengths=[],
            issues=[issue_with_example],
            overall_assessment="Test",
            feedback_for_planner="Test",
            score_breakdown={},
            iteration=1,
        )
        feedback.add_judge_verdict(verdict, iteration=1)

    # Get learning context
    context = repo.format_learning_context("test_judge", top_n=5)

    # Should include generic example, not specific message
    assert "Generic pattern: insufficient variety" in context
    assert "section X" not in context  # Specific details filtered out


def test_cross_job_learning_accumulation(temp_storage, sample_issues):
    """Test that learning accumulates across multiple jobs."""
    repo = IssueRepository(storage_dir=temp_storage, enabled=True)

    # Simulate 5 jobs, each with variety issues
    for job_num in range(5):
        feedback = FeedbackManager(
            max_entries=25,
            agent_name="test_judge",
            job_id=f"job_{job_num}",
            issue_repository=repo,
        )
        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.5,
            confidence=0.85,
            strengths=[],
            issues=[sample_issues[0]],  # VARIETY issue
            overall_assessment="Variety issue",
            feedback_for_planner="Fix variety",
            score_breakdown={},
            iteration=1,
        )
        feedback.add_judge_verdict(verdict, iteration=1)

    # Get stats
    stats = repo.get_stats("test_judge")

    assert stats["total_issues"] == 5
    assert stats["most_common_category"] == "VARIETY"

    # Get top issues
    top_issues = repo.get_top_issues("test_judge", top_n=5)
    assert len(top_issues) == 1
    assert top_issues[0][1] == 5  # Count should be 5
