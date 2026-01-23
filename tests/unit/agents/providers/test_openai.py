"""Tests for OpenAI provider."""

from unittest.mock import MagicMock, patch

import pytest

from blinkb0t.core.agents.providers.base import ProviderType, TokenUsage
from blinkb0t.core.agents.providers.conversation import generate_conversation_id
from blinkb0t.core.agents.providers.errors import LLMProviderError
from blinkb0t.core.agents.providers.openai import OpenAIProvider


@pytest.fixture
def mock_openai_client():
    """Mock OpenAIClient for testing."""
    client = MagicMock()

    # Mock token usage
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    usage.total_tokens = 150
    client.get_total_token_usage.return_value = usage

    # Mock successful response
    client.generate_json.return_value = {"test": "response", "success": True}

    return client


def test_openai_provider_type():
    """Test provider type is OPENAI."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient"):
        provider = OpenAIProvider(api_key="test-key")
        assert provider.provider_type == ProviderType.OPENAI


def test_openai_provider_init(mock_openai_client):
    """Test provider initialization."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key", timeout=60.0)

        assert provider._client == mock_openai_client
        assert provider._conversations == {}


def test_generate_json_success(mock_openai_client):
    """Test successful JSON generation."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        messages = [
            {"role": "developer", "content": "You are helpful."},
            {"role": "user", "content": "Generate plan."},
        ]

        response = provider.generate_json(messages=messages, model="gpt-4", temperature=0.7)

        # Verify client was called correctly
        mock_openai_client.generate_json.assert_called_once_with(
            messages=messages, model="gpt-4", temperature=0.7
        )

        # Verify response format
        assert response.content == {"test": "response", "success": True}
        assert response.metadata.token_usage.total_tokens == 150
        assert response.metadata.token_usage.prompt_tokens == 100
        assert response.metadata.token_usage.completion_tokens == 50
        assert response.metadata.model == "gpt-4"


def test_generate_json_error(mock_openai_client):
    """Test error handling in generate_json."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        # Make client raise error
        mock_openai_client.generate_json.side_effect = Exception("API Error")

        messages = [{"role": "user", "content": "test"}]

        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_json(messages=messages, model="gpt-4")

        assert "Provider error" in str(exc_info.value)


def test_generate_json_with_conversation_new(mock_openai_client):
    """Test creating new conversation."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        conv_id = generate_conversation_id("planner", 1)

        response = provider.generate_json_with_conversation(
            user_message="Hello",
            conversation_id=conv_id,
            model="gpt-4",
            system_prompt="You are helpful.",
        )

        # Verify conversation was created
        assert conv_id in provider._conversations
        conversation = provider._conversations[conv_id]

        # Should have developer + user + assistant messages
        assert len(conversation.messages) == 3
        assert conversation.messages[0]["role"] == "developer"
        assert conversation.messages[0]["content"] == "You are helpful."
        assert conversation.messages[1]["role"] == "user"
        assert conversation.messages[1]["content"] == "Hello"
        assert conversation.messages[2]["role"] == "assistant"

        # Verify response
        assert response.content == {"test": "response", "success": True}
        assert response.metadata.conversation_id == conv_id


def test_generate_json_with_conversation_existing(mock_openai_client):
    """Test continuing existing conversation."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        conv_id = generate_conversation_id("planner", 1)

        # First message
        provider.generate_json_with_conversation(
            user_message="Hello",
            conversation_id=conv_id,
            model="gpt-4",
            system_prompt="You are helpful.",
        )

        # Second message (should reuse conversation)
        _response = provider.generate_json_with_conversation(
            user_message="How are you?", conversation_id=conv_id, model="gpt-4"
        )

        conversation = provider._conversations[conv_id]

        # Should have: developer, user1, assistant1, user2, assistant2 = 5 messages
        assert len(conversation.messages) == 5
        assert conversation.messages[3]["role"] == "user"
        assert conversation.messages[3]["content"] == "How are you?"
        assert conversation.messages[4]["role"] == "assistant"


def test_add_message_to_conversation(mock_openai_client):
    """Test adding message to conversation."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        conv_id = generate_conversation_id("test", 1)

        # Create conversation
        provider.generate_json_with_conversation(
            user_message="Hello", conversation_id=conv_id, model="gpt-4"
        )

        # Add message
        provider.add_message_to_conversation(
            conversation_id=conv_id, role="user", content="Additional message"
        )

        history = provider.get_conversation_history(conv_id)
        assert history[-1]["role"] == "user"
        assert history[-1]["content"] == "Additional message"


def test_add_message_to_nonexistent_conversation(mock_openai_client):
    """Test adding message to nonexistent conversation."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        with pytest.raises(ValueError) as exc_info:
            provider.add_message_to_conversation(
                conversation_id="nonexistent", role="user", content="test"
            )

        assert "not found" in str(exc_info.value)


def test_get_conversation_history(mock_openai_client):
    """Test getting conversation history."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        conv_id = generate_conversation_id("test", 1)

        # Create conversation
        provider.generate_json_with_conversation(
            user_message="Hello",
            conversation_id=conv_id,
            model="gpt-4",
            system_prompt="Test",
        )

        # Get history
        history = provider.get_conversation_history(conv_id)

        assert isinstance(history, list)
        assert len(history) >= 2
        assert all(isinstance(m, dict) for m in history)
        assert all("role" in m and "content" in m for m in history)


def test_get_conversation_history_nonexistent(mock_openai_client):
    """Test getting history for nonexistent conversation."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        with pytest.raises(ValueError) as exc_info:
            provider.get_conversation_history("nonexistent")

        assert "not found" in str(exc_info.value)


def test_get_token_usage(mock_openai_client):
    """Test getting token usage."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        usage = provider.get_token_usage()

        assert isinstance(usage, TokenUsage)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150


def test_reset_token_tracking(mock_openai_client):
    """Test resetting token tracking."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        provider.reset_token_tracking()

        mock_openai_client.reset_conversation.assert_called_once()


def test_conversation_without_system_prompt(mock_openai_client):
    """Test conversation without system prompt."""
    with patch("blinkb0t.core.api.llm.openai.client.OpenAIClient", return_value=mock_openai_client):
        provider = OpenAIProvider(api_key="test-key")

        conv_id = generate_conversation_id("test", 1)

        _response = provider.generate_json_with_conversation(
            user_message="Hello", conversation_id=conv_id, model="gpt-4"
        )

        conversation = provider._conversations[conv_id]

        # Should only have user + assistant (no developer)
        assert len(conversation.messages) == 2
        assert conversation.messages[0]["role"] == "user"
        assert conversation.messages[1]["role"] == "assistant"
