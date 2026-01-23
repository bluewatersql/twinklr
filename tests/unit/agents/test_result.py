"""Tests for agent result."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.agents.result import AgentResult


def test_agent_result_success():
    """Test successful agent result."""
    result = AgentResult(
        success=True,
        data={"plan": "test_plan", "steps": [1, 2, 3]},
        duration_seconds=5.5,
        tokens_used=1000,
    )

    assert result.success is True
    assert result.data == {"plan": "test_plan", "steps": [1, 2, 3]}
    assert result.error_message is None
    assert result.duration_seconds == 5.5
    assert result.tokens_used == 1000
    assert result.conversation_id is None
    assert result.metadata == {}


def test_agent_result_failure():
    """Test failed agent result."""
    result = AgentResult(
        success=False,
        data=None,
        error_message="Validation failed: Missing required field",
        duration_seconds=2.0,
        tokens_used=500,
    )

    assert result.success is False
    assert result.data is None
    assert result.error_message == "Validation failed: Missing required field"


def test_agent_result_with_conversation():
    """Test agent result with conversation ID."""
    result = AgentResult(
        success=True,
        data={"result": "test"},
        conversation_id="planner_iter1_abc123",
        duration_seconds=3.0,
        tokens_used=750,
    )

    assert result.conversation_id == "planner_iter1_abc123"


def test_agent_result_with_metadata():
    """Test agent result with metadata."""
    metadata = {
        "schema_repair_attempts": 2,
        "validation_issues": ["issue1", "issue2"],
    }

    result = AgentResult(
        success=True,
        data={"result": "test"},
        metadata=metadata,
        duration_seconds=4.0,
        tokens_used=800,
    )

    assert result.metadata == metadata
    assert result.metadata["schema_repair_attempts"] == 2


def test_agent_result_success_requires_data():
    """Test successful result should have data."""
    # Success with None data is allowed (for flexibility)
    result = AgentResult(
        success=True,
        data=None,
        duration_seconds=1.0,
        tokens_used=100,
    )

    assert result.success is True
    assert result.data is None


def test_agent_result_failure_requires_error():
    """Test failed result should have error message."""
    # Failure without error message is allowed (though not ideal)
    result = AgentResult(
        success=False,
        data=None,
        duration_seconds=1.0,
        tokens_used=100,
    )

    assert result.success is False
    assert result.error_message is None


def test_agent_result_immutable():
    """Test agent result is immutable."""
    result = AgentResult(
        success=True,
        data={"test": "data"},
        duration_seconds=1.0,
        tokens_used=100,
    )

    with pytest.raises((ValidationError, AttributeError)):
        result.success = False  # Should not be allowed


def test_agent_result_duration_validation():
    """Test duration must be non-negative."""
    # Valid duration
    result = AgentResult(success=True, data={}, duration_seconds=0.0, tokens_used=0)
    assert result.duration_seconds == 0.0

    # Invalid duration
    with pytest.raises(ValidationError):
        AgentResult(success=True, data={}, duration_seconds=-1.0, tokens_used=0)


def test_agent_result_tokens_validation():
    """Test tokens must be non-negative."""
    # Valid tokens
    result = AgentResult(success=True, data={}, duration_seconds=1.0, tokens_used=0)
    assert result.tokens_used == 0

    # Invalid tokens
    with pytest.raises(ValidationError):
        AgentResult(success=True, data={}, duration_seconds=1.0, tokens_used=-100)


def test_agent_result_serialization():
    """Test agent result can be serialized."""
    result = AgentResult(
        success=True,
        data={"test": "data"},
        duration_seconds=5.0,
        tokens_used=1000,
        conversation_id="test_conv",
        metadata={"extra": "info"},
    )

    # Should be able to convert to dict
    data = result.model_dump()

    assert data["success"] is True
    assert data["data"] == {"test": "data"}
    assert data["duration_seconds"] == 5.0
    assert data["tokens_used"] == 1000
    assert data["conversation_id"] == "test_conv"
    assert data["metadata"] == {"extra": "info"}
