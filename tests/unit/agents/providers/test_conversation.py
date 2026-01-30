"""Tests for conversation utilities."""

import re

from twinklr.core.agents.providers.conversation import Conversation, generate_conversation_id


def test_generate_conversation_id_format():
    """Test conversation ID format."""
    conv_id = generate_conversation_id("planner", 1)

    # Should match pattern: {agent_name}_iter{iteration}_{uuid}
    pattern = r"^planner_iter1_[a-f0-9]{8}$"
    assert re.match(pattern, conv_id), f"ID {conv_id} doesn't match pattern"


def test_generate_conversation_id_uniqueness():
    """Test that IDs are unique."""
    id1 = generate_conversation_id("planner", 1)
    id2 = generate_conversation_id("planner", 1)

    assert id1 != id2, "IDs should be unique"


def test_generate_conversation_id_different_iterations():
    """Test IDs for different iterations."""
    id1 = generate_conversation_id("planner", 1)
    id2 = generate_conversation_id("planner", 2)

    assert "iter1" in id1
    assert "iter2" in id2
    assert id1 != id2


def test_generate_conversation_id_different_agents():
    """Test IDs for different agents."""
    id1 = generate_conversation_id("planner", 1)
    id2 = generate_conversation_id("judge", 1)

    assert "planner" in id1
    assert "judge" in id2
    assert id1 != id2


def test_conversation_dataclass():
    """Test Conversation dataclass."""
    conv = Conversation(id="test_id")

    assert conv.id == "test_id"
    assert conv.messages == []
    assert conv.created_at > 0


def test_conversation_with_messages():
    """Test Conversation with messages."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    conv = Conversation(id="test_id", messages=messages)

    assert conv.id == "test_id"
    assert len(conv.messages) == 2
    assert conv.messages[0]["role"] == "user"
