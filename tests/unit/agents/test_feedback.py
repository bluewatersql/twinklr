"""Tests for feedback manager."""

from twinklr.core.agents.feedback import (
    FeedbackEntry,
    FeedbackManager,
    FeedbackType,
)


def test_feedback_manager_init():
    """Test feedback manager initialization."""
    manager = FeedbackManager(max_entries=2)

    assert manager.max_entries == 2
    assert manager.count() == 0
    assert manager.is_empty()


def test_add_validation_failure():
    """Test adding validation failure feedback."""
    manager = FeedbackManager(max_entries=5)

    manager.add_validation_failure(message="Duration too short", iteration=1)

    assert manager.count() == 1
    assert not manager.is_empty()

    entries = manager.get_all()
    assert len(entries) == 1
    assert entries[0].type == FeedbackType.VALIDATION_FAILURE
    assert entries[0].message == "Duration too short"
    assert entries[0].iteration == 1


def test_add_validation_failure_with_metadata():
    """Test adding validation failure with metadata."""
    manager = FeedbackManager()

    manager.add_validation_failure(
        message="Duration too short",
        iteration=1,
        metadata={"error_count": 3, "issues": ["issue1", "issue2"]},
    )

    entries = manager.get_all()
    assert entries[0].metadata["error_count"] == 3
    assert len(entries[0].metadata["issues"]) == 2


def test_add_judge_soft_failure():
    """Test adding judge soft failure feedback."""
    manager = FeedbackManager()

    manager.add_judge_soft_failure(
        message="Energy matching needs improvement", iteration=2, score=68.0
    )

    entries = manager.get_all()
    assert entries[0].type == FeedbackType.JUDGE_SOFT_FAILURE
    assert entries[0].metadata["score"] == 68.0


def test_add_judge_hard_failure():
    """Test adding judge hard failure feedback."""
    manager = FeedbackManager()

    manager.add_judge_hard_failure(message="Fundamental structural issues", iteration=2, score=52.0)

    entries = manager.get_all()
    assert entries[0].type == FeedbackType.JUDGE_HARD_FAILURE
    assert entries[0].metadata["score"] == 52.0


def test_automatic_trimming():
    """Test automatic trimming to max_entries."""
    manager = FeedbackManager(max_entries=2)

    # Add 3 entries (should trim to 2)
    manager.add_validation_failure("Issue 1", iteration=1)
    manager.add_validation_failure("Issue 2", iteration=2)
    manager.add_validation_failure("Issue 3", iteration=3)

    # Should only have 2 most recent
    assert manager.count() == 2

    entries = manager.get_all()
    assert entries[0].message == "Issue 2"
    assert entries[1].message == "Issue 3"


def test_get_by_type():
    """Test filtering feedback by type."""
    manager = FeedbackManager(max_entries=10)

    manager.add_validation_failure("Val 1", iteration=1)
    manager.add_judge_soft_failure("Judge 1", iteration=2, score=70.0)
    manager.add_validation_failure("Val 2", iteration=3)
    manager.add_judge_hard_failure("Judge 2", iteration=4, score=50.0)

    # Filter by validation
    val_entries = manager.get_by_type(FeedbackType.VALIDATION_FAILURE)
    assert len(val_entries) == 2
    assert all(e.type == FeedbackType.VALIDATION_FAILURE for e in val_entries)

    # Filter by judge soft
    judge_soft = manager.get_by_type(FeedbackType.JUDGE_SOFT_FAILURE)
    assert len(judge_soft) == 1

    # Filter by judge hard
    judge_hard = manager.get_by_type(FeedbackType.JUDGE_HARD_FAILURE)
    assert len(judge_hard) == 1


def test_format_for_prompt_empty():
    """Test formatting when no feedback."""
    manager = FeedbackManager()

    formatted = manager.format_for_prompt()

    assert formatted == "No feedback available."


def test_format_for_prompt():
    """Test feedback formatting for prompts."""
    manager = FeedbackManager(max_entries=5)

    manager.add_validation_failure(message="Duration too short: 180s < 220s minimum", iteration=1)

    manager.add_judge_soft_failure(
        message="Energy matching needs improvement", iteration=2, score=68.0
    )

    formatted = manager.format_for_prompt()

    assert "Iteration 1" in formatted
    assert "Iteration 2" in formatted
    assert "Duration too short" in formatted
    assert "Energy matching" in formatted
    assert "validation_failure" in formatted
    assert "judge_soft_failure" in formatted


def test_format_for_prompt_with_filter():
    """Test formatting with type filter."""
    manager = FeedbackManager(max_entries=10)  # Need larger max to keep all

    manager.add_validation_failure("Val 1", iteration=1)
    manager.add_judge_soft_failure("Judge 1", iteration=2, score=70.0)
    manager.add_validation_failure("Val 2", iteration=3)

    # Format only validation feedback
    formatted = manager.format_for_prompt(filter_type=FeedbackType.VALIDATION_FAILURE)

    assert "Val 1" in formatted
    assert "Val 2" in formatted
    assert "Judge 1" not in formatted


def test_clear():
    """Test clearing all feedback."""
    manager = FeedbackManager()

    manager.add_validation_failure("Test 1", iteration=1)
    manager.add_validation_failure("Test 2", iteration=2)

    assert manager.count() == 2

    manager.clear()

    assert manager.count() == 0
    assert manager.is_empty()


def test_feedback_entry_model():
    """Test FeedbackEntry model."""
    entry = FeedbackEntry(
        type=FeedbackType.VALIDATION_FAILURE,
        message="Test message",
        iteration=1,
        timestamp=1234567890.0,
        metadata={"test": "data"},
    )

    assert entry.type == FeedbackType.VALIDATION_FAILURE
    assert entry.message == "Test message"
    assert entry.iteration == 1
    assert entry.timestamp == 1234567890.0
    assert entry.metadata["test"] == "data"


def test_trimming_with_different_types():
    """Test trimming works correctly with mixed types."""
    manager = FeedbackManager(max_entries=2)

    manager.add_validation_failure("Val 1", iteration=1)
    manager.add_judge_soft_failure("Judge 1", iteration=2, score=70.0)
    manager.add_judge_hard_failure("Judge 2", iteration=3, score=50.0)

    # Should keep Judge 1 and Judge 2 (most recent 2)
    assert manager.count() == 2

    entries = manager.get_all()
    assert entries[0].message == "Judge 1"
    assert entries[1].message == "Judge 2"


def test_multiple_iterations_same_type():
    """Test multiple feedback entries of same type."""
    manager = FeedbackManager(max_entries=10)

    for i in range(5):
        manager.add_validation_failure(f"Issue {i + 1}", iteration=i + 1)

    assert manager.count() == 5

    entries = manager.get_by_type(FeedbackType.VALIDATION_FAILURE)
    assert len(entries) == 5
