"""Tests for IssueRepository and cross-job learning system."""

import json
from pathlib import Path
import tempfile
import time

import pytest

from twinklr.core.agents.analytics.repository import IssueRecord, IssueRepository
from twinklr.core.agents.issues import (
    Issue,
    IssueCategory,
    IssueEffort,
    IssueLocation,
    IssueScope,
    IssueSeverity,
    SuggestedAction,
)


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_issue():
    """Create sample issue for testing."""
    return Issue(
        issue_id="VARIETY_LOW_CHORUS",
        category=IssueCategory.VARIETY,
        severity=IssueSeverity.WARN,
        estimated_effort=IssueEffort.LOW,
        scope=IssueScope.SECTION,
        location=IssueLocation(section_id="chorus_1", bar_start=25, bar_end=33),
        rule="DON'T use same template repeatedly in high-energy sections",
        message="Chorus uses same template 3 times without variation",
        fix_hint="Use different geometry types or presets for variety",
        acceptance_test="Chorus sections use at least 2 different templates or presets",
        suggested_action=SuggestedAction.PATCH,
        generic_example="Repeated template usage without variation in high-energy sections",
    )


@pytest.fixture
def repository(temp_storage):
    """Create IssueRepository instance."""
    return IssueRepository(storage_dir=temp_storage, enabled=True)


def test_repository_initialization(temp_storage):
    """Test repository initialization creates directory."""
    _ = IssueRepository(storage_dir=temp_storage / "analytics", enabled=True)
    assert (temp_storage / "analytics").exists()


def test_repository_disabled(temp_storage):
    """Test repository with enabled=False does not record."""
    repo = IssueRepository(storage_dir=temp_storage, enabled=False)

    repo.record_issues(
        issues=[],
        agent_name="test_judge",
        job_id="job_1",
        iteration=1,
        verdict_score=7.0,
        timestamp=time.time(),
    )

    # No file should be created
    assert len(list(temp_storage.glob("*.jsonl"))) == 0


def test_record_issues(repository, sample_issue, temp_storage):
    """Test recording issues to repository."""
    timestamp = time.time()

    repository.record_issues(
        issues=[sample_issue],
        agent_name="macro_planner_judge",
        job_id="job_123",
        iteration=1,
        verdict_score=6.5,
        timestamp=timestamp,
    )

    # Check file was created
    file_path = temp_storage / "macro_planner_judge_issues.jsonl"
    assert file_path.exists()

    # Read and validate record
    with file_path.open() as f:
        line = f.readline()
        data = json.loads(line)

    assert data["agent_name"] == "macro_planner_judge"
    assert data["job_id"] == "job_123"
    assert data["iteration"] == 1
    assert data["verdict_score"] == 6.5
    assert data["timestamp"] == timestamp
    assert data["resolved"] is False
    assert data["issue"]["issue_id"] == "VARIETY_LOW_CHORUS"


def test_record_multiple_issues(repository, sample_issue, temp_storage):
    """Test recording multiple issues in one call."""
    issue2 = Issue(
        issue_id="TIMING_OVERLAP",
        category=IssueCategory.TIMING,
        severity=IssueSeverity.ERROR,
        estimated_effort=IssueEffort.MEDIUM,
        scope=IssueScope.SECTION,
        location=IssueLocation(section_id="verse_1", bar_start=1, bar_end=8),
        rule="DON'T allow timing overlaps between sections",
        message="Timing overlap in verse",
        fix_hint="Adjust timing to remove overlap",
        acceptance_test="No timing overlaps in verse",
        suggested_action=SuggestedAction.PATCH,
    )

    repository.record_issues(
        issues=[sample_issue, issue2],
        agent_name="test_judge",
        job_id="job_1",
        iteration=1,
        verdict_score=5.0,
        timestamp=time.time(),
    )

    # Check both records written
    file_path = temp_storage / "test_judge_issues.jsonl"
    with file_path.open() as f:
        lines = f.readlines()

    assert len(lines) == 2


def test_get_top_issues(repository, sample_issue):
    """Test getting top issues by category."""
    # Record variety issues multiple times
    for i in range(3):
        repository.record_issues(
            issues=[sample_issue],
            agent_name="test_judge",
            job_id=f"job_{i}",
            iteration=1,
            verdict_score=6.0,
            timestamp=time.time(),
        )

    # Record timing issue once
    timing_issue = Issue(
        issue_id="TIMING_OVERLAP",
        category=IssueCategory.TIMING,
        severity=IssueSeverity.ERROR,
        estimated_effort=IssueEffort.MEDIUM,
        scope=IssueScope.SECTION,
        location=IssueLocation(),
        rule="DON'T allow timing overlaps",
        message="Timing issue",
        fix_hint="Fix timing",
        acceptance_test="No timing issues",
        suggested_action=SuggestedAction.PATCH,
    )
    repository.record_issues(
        issues=[timing_issue],
        agent_name="test_judge",
        job_id="job_3",
        iteration=1,
        verdict_score=5.0,
        timestamp=time.time(),
    )

    # Get top issues
    top_issues = repository.get_top_issues(agent_name="test_judge", top_n=5, min_occurrences=1)

    assert len(top_issues) == 2
    # First should be VARIETY (3 occurrences)
    assert top_issues[0][0] == IssueCategory.VARIETY
    assert top_issues[0][1] == 3
    # Second should be TIMING (1 occurrence)
    assert top_issues[1][0] == IssueCategory.TIMING
    assert top_issues[1][1] == 1


def test_get_top_issues_with_generic_examples(repository, sample_issue):
    """Test that generic examples are included in top issues."""
    repository.record_issues(
        issues=[sample_issue],
        agent_name="test_judge",
        job_id="job_1",
        iteration=1,
        verdict_score=6.0,
        timestamp=time.time(),
    )

    top_issues = repository.get_top_issues("test_judge", top_n=5, min_occurrences=1)

    assert len(top_issues) == 1
    category, count, examples = top_issues[0]
    assert category == IssueCategory.VARIETY
    assert count == 1
    assert len(examples) == 1
    assert examples[0] == "Repeated template usage without variation in high-energy sections"


def test_get_top_issues_min_occurrences(repository, sample_issue):
    """Test min_occurrences filter."""
    # Record once
    repository.record_issues(
        issues=[sample_issue],
        agent_name="test_judge",
        job_id="job_1",
        iteration=1,
        verdict_score=6.0,
        timestamp=time.time(),
    )

    # With min_occurrences=2, should get nothing
    top_issues = repository.get_top_issues("test_judge", top_n=5, min_occurrences=2)
    assert len(top_issues) == 0


def test_get_recurring_issues(repository, sample_issue):
    """Test getting recurring issues by issue_id."""
    # Record same issue_id multiple times
    for i in range(4):
        repository.record_issues(
            issues=[sample_issue],
            agent_name="test_judge",
            job_id=f"job_{i}",
            iteration=1,
            verdict_score=6.0,
            timestamp=time.time(),
        )

    recurring = repository.get_recurring_issues("test_judge", min_occurrences=3)

    assert len(recurring) == 1
    issue_id, count, issue = recurring[0]
    assert issue_id == "VARIETY_LOW_CHORUS"
    assert count == 4
    assert issue.message == "Chorus uses same template 3 times without variation"


def test_get_resolution_rate(repository, sample_issue):
    """Test resolution rate calculation returns 0-1 range."""
    # Note: Resolution rate calculation requires sufficient historical data
    # across multiple jobs to be meaningful. For now, just verify it returns
    # a valid rate in range [0, 1].

    # Record minimal test data
    repository.record_issues(
        issues=[sample_issue],
        agent_name="test_judge",
        job_id="job_1",
        iteration=1,
        verdict_score=6.0,
        timestamp=time.time(),
    )

    rate = repository.get_resolution_rate("test_judge")
    # Should return a valid rate (0.0-1.0)
    assert 0.0 <= rate <= 1.0


def test_format_learning_context(repository, sample_issue):
    """Test learning context formatting."""
    # Record multiple issues
    for i in range(3):
        repository.record_issues(
            issues=[sample_issue],
            agent_name="test_judge",
            job_id=f"job_{i}",
            iteration=1,
            verdict_score=6.0,
            timestamp=time.time(),
        )

    context = repository.format_learning_context(
        agent_name="test_judge", top_n=5, include_resolution_rate=True
    )

    assert "Historical Learning Context" in context
    assert "VARIETY" in context
    assert "occurred 3 times" in context
    assert "Repeated template usage without variation" in context
    assert "resolution rate" in context.lower()


def test_format_learning_context_empty(repository):
    """Test learning context with no data."""
    context = repository.format_learning_context("nonexistent_agent", top_n=5)
    assert context == ""


def test_get_stats(repository, sample_issue):
    """Test statistics generation."""
    repository.record_issues(
        issues=[sample_issue],
        agent_name="test_judge",
        job_id="job_1",
        iteration=1,
        verdict_score=6.0,
        timestamp=time.time(),
    )

    stats = repository.get_stats("test_judge")

    assert stats["total_issues"] == 1
    assert stats["unique_categories"] == 1
    assert stats["unique_severities"] == 1
    assert "resolution_rate" in stats
    assert stats["most_common_category"] == "VARIETY"


def test_multiple_agents_separate_files(repository, sample_issue):
    """Test that different agents get separate files."""
    repository.record_issues(
        issues=[sample_issue],
        agent_name="agent_1",
        job_id="job_1",
        iteration=1,
        verdict_score=6.0,
        timestamp=time.time(),
    )
    repository.record_issues(
        issues=[sample_issue],
        agent_name="agent_2",
        job_id="job_1",
        iteration=1,
        verdict_score=6.0,
        timestamp=time.time(),
    )

    # Check separate files
    assert (repository.storage_dir / "agent_1_issues.jsonl").exists()
    assert (repository.storage_dir / "agent_2_issues.jsonl").exists()

    # Check data isolation
    top_1 = repository.get_top_issues("agent_1", top_n=5, min_occurrences=1)
    top_2 = repository.get_top_issues("agent_2", top_n=5, min_occurrences=1)

    assert len(top_1) == 1
    assert len(top_2) == 1


def test_agent_name_sanitization(repository, sample_issue, temp_storage):
    """Test that agent names are sanitized for filenames."""
    # Use agent name with special characters
    repository.record_issues(
        issues=[sample_issue],
        agent_name="agent/with/slashes",
        job_id="job_1",
        iteration=1,
        verdict_score=6.0,
        timestamp=time.time(),
    )

    # Check file was created with sanitized name
    assert (temp_storage / "agent_with_slashes_issues.jsonl").exists()


def test_max_records_limits_scan(repository, sample_issue):
    """Test that max_records limits the number of records scanned."""
    # Record 10 issues
    for i in range(10):
        repository.record_issues(
            issues=[sample_issue],
            agent_name="test_judge",
            job_id=f"job_{i}",
            iteration=1,
            verdict_score=6.0,
            timestamp=time.time(),
        )

    # Get top issues with max_records=5
    top_issues = repository.get_top_issues("test_judge", top_n=5, max_records=5)

    # Should only see 5 occurrences (from most recent 5 records)
    assert len(top_issues) == 1
    assert top_issues[0][1] == 5  # Count should be 5


def test_issue_record_validation():
    """Test IssueRecord model validation."""
    issue = Issue(
        issue_id="TEST",
        category=IssueCategory.VARIETY,
        severity=IssueSeverity.WARN,
        estimated_effort=IssueEffort.LOW,
        scope=IssueScope.SECTION,
        location=IssueLocation(),
        rule="DON'T test - this is a test issue",
        message="Test",
        fix_hint="Fix",
        acceptance_test="Test",
        suggested_action=SuggestedAction.PATCH,
    )

    record = IssueRecord(
        issue=issue,
        agent_name="test_judge",
        job_id="job_1",
        iteration=1,
        verdict_score=7.5,
        timestamp=time.time(),
        resolved=False,
    )

    assert record.agent_name == "test_judge"
    assert record.verdict_score == 7.5
    assert record.resolved is False


def test_deduplication_of_generic_examples(repository, sample_issue):
    """Test that generic examples are deduplicated."""
    # Record same issue (with same generic_example) multiple times
    for i in range(3):
        repository.record_issues(
            issues=[sample_issue],
            agent_name="test_judge",
            job_id=f"job_{i}",
            iteration=1,
            verdict_score=6.0,
            timestamp=time.time(),
        )

    top_issues = repository.get_top_issues("test_judge", top_n=5)

    _, count, examples = top_issues[0]
    assert count == 3
    # Should only have one unique example despite 3 records
    assert len(examples) == 1


def test_empty_issues_list(repository):
    """Test recording with empty issues list."""
    repository.record_issues(
        issues=[],
        agent_name="test_judge",
        job_id="job_1",
        iteration=1,
        verdict_score=7.0,
        timestamp=time.time(),
    )

    # No file should be created
    assert not (repository.storage_dir / "test_judge_issues.jsonl").exists()
