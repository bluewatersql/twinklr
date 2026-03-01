"""Tests for OpenAI provider."""

from unittest.mock import AsyncMock, MagicMock, patch

from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
import pytest

from twinklr.core.agents.providers.base import ProviderType, TokenUsage
from twinklr.core.agents.providers.conversation import generate_conversation_id
from twinklr.core.agents.providers.errors import LLMProviderError
from twinklr.core.agents.providers.openai import OpenAIProvider


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
    with patch("twinklr.core.agents.providers.openai.OpenAIClient"):
        provider = OpenAIProvider(api_key="test-key")
        assert provider.provider_type == ProviderType.OPENAI


def test_openai_provider_init(mock_openai_client):
    """Test provider initialization."""
    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI"),
    ):
        provider = OpenAIProvider(api_key="test-key", timeout=60.0)

        assert provider._sync_client == mock_openai_client
        assert provider._conversations == {}


def test_generate_json_success(mock_openai_client):
    """Test successful JSON generation."""
    with patch(
        "twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client
    ):
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
    """Test error handling in generate_json wraps OpenAI API errors."""
    with patch(
        "twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client
    ):
        provider = OpenAIProvider(api_key="test-key")

        # Make client raise an OpenAI APIError (which IS caught and wrapped)
        mock_request = MagicMock()
        mock_openai_client.generate_json.side_effect = APIError(
            "API Error", request=mock_request, body=None
        )

        messages = [{"role": "user", "content": "test"}]

        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_json(messages=messages, model="gpt-4")

        assert "Provider error" in str(exc_info.value)


def test_generate_json_with_conversation_new(mock_openai_client):
    """Test creating new conversation."""
    with patch(
        "twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client
    ):
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
    with patch(
        "twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client
    ):
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
    with patch(
        "twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client
    ):
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
    with patch(
        "twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client
    ):
        provider = OpenAIProvider(api_key="test-key")

        with pytest.raises(ValueError) as exc_info:
            provider.add_message_to_conversation(
                conversation_id="nonexistent", role="user", content="test"
            )

        assert "not found" in str(exc_info.value)


def test_get_conversation_history(mock_openai_client):
    """Test getting conversation history."""
    with patch(
        "twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client
    ):
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
    with patch(
        "twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client
    ):
        provider = OpenAIProvider(api_key="test-key")

        with pytest.raises(ValueError) as exc_info:
            provider.get_conversation_history("nonexistent")

        assert "not found" in str(exc_info.value)


def test_get_token_usage(mock_openai_client):
    """Test getting token usage after making calls."""
    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI"),
    ):
        provider = OpenAIProvider(api_key="test-key")

        # Token usage starts at 0 before any calls
        usage_before = provider.get_token_usage()
        assert usage_before.total_tokens == 0

        # Make a call to accumulate tokens
        provider.generate_json(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4",
        )

        # Now get token usage - should reflect accumulated tokens
        usage = provider.get_token_usage()

        assert isinstance(usage, TokenUsage)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150


def test_reset_token_tracking(mock_openai_client):
    """Test resetting token tracking."""
    with patch(
        "twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client
    ):
        provider = OpenAIProvider(api_key="test-key")

        provider.reset_token_tracking()

        mock_openai_client.reset_conversation.assert_called_once()


def test_conversation_without_system_prompt(mock_openai_client):
    """Test conversation without system prompt."""
    with patch(
        "twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_openai_client
    ):
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


@pytest.mark.asyncio
async def test_generate_json_async_passes_supported_kwargs() -> None:
    """Async JSON generation should pass supported kwargs through to API request."""
    response = MagicMock()
    response.output_text = '{"ok": true}'
    response.id = "resp_1"
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=2, total_tokens=12)

    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient"),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI") as mock_async_openai,
    ):
        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(return_value=response)
        mock_async_openai.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")

        result = await provider.generate_json_async(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-5",
            top_p=0.9,
            max_output_tokens=120,
        )

    assert result.content["ok"] is True
    request_kwargs = mock_client.responses.create.call_args.kwargs
    assert request_kwargs["top_p"] == 0.9
    assert request_kwargs["max_output_tokens"] == 120


@pytest.mark.asyncio
async def test_generate_json_async_retries_transient_errors() -> None:
    """Async path should retry transient OpenAI API errors before succeeding."""
    mock_request = MagicMock()
    first_error = APIConnectionError(request=mock_request)
    response = MagicMock()
    response.output_text = '{"ok": true}'
    response.id = "resp_2"
    response.usage = None

    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient"),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI") as mock_async_openai,
        patch("twinklr.core.agents.providers.openai.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(side_effect=[first_error, response])
        mock_async_openai.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")

        result = await provider.generate_json_async(
            messages=[{"role": "user", "content": "hello"}], model="gpt-5"
        )

    assert result.content["ok"] is True
    assert mock_client.responses.create.await_count == 2


# =========================================================================
# PERF-10: Conversation Windowing Tests
# =========================================================================


class TestWindowMessages:
    """Tests for OpenAIProvider._window_messages sliding window."""

    def _make_provider(self) -> OpenAIProvider:
        """Create an OpenAIProvider with mocked clients."""
        with (
            patch("twinklr.core.agents.providers.openai.OpenAIClient"),
            patch("twinklr.core.agents.providers.openai.AsyncOpenAI"),
        ):
            return OpenAIProvider(api_key="test-key")

    def test_short_conversation_all_messages_kept(self) -> None:
        """Short conversation (within window) keeps all messages."""
        provider = self._make_provider()
        messages = [
            {"role": "developer", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        result = provider._window_messages(messages, window_size=2)

        # All messages should be preserved (1 system + 2 conversation = 3)
        assert len(result) == 3
        assert result[0]["role"] == "developer"
        assert result[1]["role"] == "user"
        assert result[2]["role"] == "assistant"

    def test_long_conversation_only_last_n_pairs_plus_system(self) -> None:
        """Long conversation trims to last N exchange pairs, keeping system."""
        provider = self._make_provider()
        messages = [
            {"role": "developer", "content": "System prompt"},
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Message 3"},
            {"role": "assistant", "content": "Response 3"},
        ]

        result = provider._window_messages(messages, window_size=2)

        # Should keep: developer + last 2 pairs (4 conversation msgs)
        assert len(result) == 5
        assert result[0]["role"] == "developer"
        assert result[0]["content"] == "System prompt"
        assert result[1]["content"] == "Message 2"
        assert result[2]["content"] == "Response 2"
        assert result[3]["content"] == "Message 3"
        assert result[4]["content"] == "Response 3"

    def test_system_message_always_preserved(self) -> None:
        """System and developer messages are never dropped regardless of window."""
        provider = self._make_provider()
        messages = [
            {"role": "system", "content": "System message"},
            {"role": "developer", "content": "Developer message"},
            {"role": "user", "content": "Msg 1"},
            {"role": "assistant", "content": "Reply 1"},
            {"role": "user", "content": "Msg 2"},
            {"role": "assistant", "content": "Reply 2"},
            {"role": "user", "content": "Msg 3"},
            {"role": "assistant", "content": "Reply 3"},
        ]

        result = provider._window_messages(messages, window_size=1)

        # Should keep: system + developer + last 1 pair (2 conversation msgs)
        assert len(result) == 4
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "System message"
        assert result[1]["role"] == "developer"
        assert result[1]["content"] == "Developer message"
        assert result[2]["content"] == "Msg 3"
        assert result[3]["content"] == "Reply 3"

    def test_window_size_one_keeps_most_recent_exchange(self) -> None:
        """Window size=1 keeps only the most recent user-assistant pair."""
        provider = self._make_provider()
        messages = [
            {"role": "developer", "content": "System"},
            {"role": "user", "content": "Old question"},
            {"role": "assistant", "content": "Old answer"},
            {"role": "user", "content": "New question"},
            {"role": "assistant", "content": "New answer"},
        ]

        result = provider._window_messages(messages, window_size=1)

        # developer + last 1 pair
        assert len(result) == 3
        assert result[0]["role"] == "developer"
        assert result[1]["content"] == "New question"
        assert result[2]["content"] == "New answer"

    def test_empty_conversation_returns_system_only(self) -> None:
        """Empty conversation (no user/assistant) returns only system messages."""
        provider = self._make_provider()
        messages = [
            {"role": "developer", "content": "System prompt"},
            {"role": "system", "content": "Additional system"},
        ]

        result = provider._window_messages(messages, window_size=2)

        # Only system messages, no conversation
        assert len(result) == 2
        assert result[0]["role"] == "developer"
        assert result[1]["role"] == "system"


# =========================================================================
# CQ-05: Exception Handling Tests
# =========================================================================


class TestShouldRetryAsyncError:
    """Tests for _should_retry_async_error() — CQ-05 narrow exception handling."""

    def test_runtime_error_is_not_retried(self) -> None:
        """RuntimeError must NOT be retried (it is a programming/internal error)."""
        error = RuntimeError("internal error")
        result = OpenAIProvider._should_retry_async_error(error, attempt=0, max_attempts=3)
        assert result is False

    def test_rate_limit_error_is_retried(self) -> None:
        """RateLimitError must be retried on first attempts."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        error = RateLimitError("rate limited", response=mock_response, body=None)
        result = OpenAIProvider._should_retry_async_error(error, attempt=0, max_attempts=3)
        assert result is True

    def test_api_error_is_retried(self) -> None:
        """APIError must be retried on first attempts."""
        mock_request = MagicMock()
        error = APIError("server error", request=mock_request, body=None)
        result = OpenAIProvider._should_retry_async_error(error, attempt=0, max_attempts=3)
        assert result is True

    def test_api_timeout_error_is_retried(self) -> None:
        """APITimeoutError must be retried on first attempts."""
        mock_request = MagicMock()
        error = APITimeoutError(request=mock_request)
        result = OpenAIProvider._should_retry_async_error(error, attempt=0, max_attempts=3)
        assert result is True

    def test_api_connection_error_is_retried(self) -> None:
        """APIConnectionError must be retried on first attempts."""
        mock_request = MagicMock()
        error = APIConnectionError(request=mock_request)
        result = OpenAIProvider._should_retry_async_error(error, attempt=0, max_attempts=3)
        assert result is True

    def test_value_error_is_not_retried(self) -> None:
        """ValueError (programming error) must NOT be caught or retried."""
        error = ValueError("bad argument")
        result = OpenAIProvider._should_retry_async_error(error, attempt=0, max_attempts=3)
        assert result is False

    def test_no_retry_on_last_attempt(self) -> None:
        """Retryable errors must not be retried when max attempts are exhausted."""
        mock_request = MagicMock()
        error = APIConnectionError(request=mock_request)
        # attempt == max_attempts - 1 means we are on the last attempt
        result = OpenAIProvider._should_retry_async_error(error, attempt=2, max_attempts=3)
        assert result is False


class TestGenerateJsonExceptionNarrowing:
    """Tests that generate_json and generate_json_with_conversation propagate
    non-OpenAI errors (e.g. ValueError) without wrapping them in LLMProviderError.
    """

    def _make_provider(self, mock_client: MagicMock) -> OpenAIProvider:
        with patch("twinklr.core.agents.providers.openai.OpenAIClient", return_value=mock_client):
            return OpenAIProvider(api_key="test-key")

    def test_generate_json_propagates_value_error(self) -> None:
        """ValueError from the sync client must propagate, not be wrapped."""
        mock_client = MagicMock()
        mock_client.generate_json.side_effect = ValueError("bad input")
        provider = self._make_provider(mock_client)

        with pytest.raises(ValueError, match="bad input"):
            provider.generate_json(messages=[{"role": "user", "content": "test"}], model="gpt-4")

    def test_generate_json_wraps_api_error(self) -> None:
        """OpenAI APIError from the sync client must be wrapped in LLMProviderError."""
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_client.generate_json.side_effect = APIError(
            "server error", request=mock_request, body=None
        )
        provider = self._make_provider(mock_client)

        with pytest.raises(LLMProviderError):
            provider.generate_json(messages=[{"role": "user", "content": "test"}], model="gpt-4")

    def test_generate_json_with_conversation_propagates_value_error(self) -> None:
        """ValueError must propagate out of generate_json_with_conversation."""
        mock_client = MagicMock()
        mock_client.generate_json.side_effect = ValueError("bad input")
        provider = self._make_provider(mock_client)

        with pytest.raises(ValueError, match="bad input"):
            provider.generate_json_with_conversation(
                user_message="hello",
                conversation_id="conv-1",
                model="gpt-4",
            )

    def test_generate_json_with_conversation_wraps_api_error(self) -> None:
        """OpenAI APIError must be wrapped in LLMProviderError."""
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_client.generate_json.side_effect = APIError(
            "server error", request=mock_request, body=None
        )
        provider = self._make_provider(mock_client)

        with pytest.raises(LLMProviderError):
            provider.generate_json_with_conversation(
                user_message="hello",
                conversation_id="conv-1",
                model="gpt-4",
            )
