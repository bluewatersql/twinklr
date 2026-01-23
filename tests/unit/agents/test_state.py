"""Tests for agent state."""

from blinkb0t.core.agents.state import AgentState


def test_agent_state_init():
    """Test agent state initialization."""
    state = AgentState(name="test_agent")

    assert state.name == "test_agent"
    assert state.conversation_id is None
    assert state.attempt_count == 0
    assert state.metadata == {}


def test_agent_state_with_conversation():
    """Test agent state with conversation ID."""
    state = AgentState(
        name="planner",
        conversation_id="planner_iter1_abc123",
        attempt_count=2,
    )

    assert state.name == "planner"
    assert state.conversation_id == "planner_iter1_abc123"
    assert state.attempt_count == 2


def test_agent_state_with_metadata():
    """Test agent state with metadata."""
    metadata = {"last_error": "Schema validation failed", "retry_count": 1}

    state = AgentState(name="judge", metadata=metadata)

    assert state.metadata == metadata
    assert state.metadata["last_error"] == "Schema validation failed"


def test_agent_state_mutable():
    """Test agent state is mutable (for tracking)."""
    state = AgentState(name="test")

    # Should be able to update fields
    state.conversation_id = "new_conv_id"
    state.attempt_count = 5
    state.metadata["test"] = "data"

    assert state.conversation_id == "new_conv_id"
    assert state.attempt_count == 5
    assert state.metadata["test"] == "data"


def test_agent_state_increment_attempt():
    """Test incrementing attempt count."""
    state = AgentState(name="test")

    assert state.attempt_count == 0

    state.attempt_count += 1
    assert state.attempt_count == 1

    state.attempt_count += 1
    assert state.attempt_count == 2
