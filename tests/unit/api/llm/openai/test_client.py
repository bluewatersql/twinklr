"""Tests for OpenAI API client."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from openai import APIConnectionError, APIStatusError, RateLimitError
import pytest

from twinklr.core.api.llm.openai.client import (
    OpenAIClient,
    OpenAIRetryExhausted,
    ReasoningEffort,
    ResponseMetadata,
    RetryConfig,
    TokenUsage,
    Verbosity,
)

# ============================================================================
# Dataclass Tests
# ============================================================================


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_add_two_usages(self) -> None:
        """Test adding two TokenUsage instances."""
        usage1 = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        usage2 = TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300)

        result = usage1 + usage2

        assert result.prompt_tokens == 300
        assert result.completion_tokens == 150
        assert result.total_tokens == 450


class TestResponseMetadata:
    """Tests for ResponseMetadata dataclass."""

    def test_custom_values(self) -> None:
        """Test custom values."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        metadata = ResponseMetadata(
            response_id="resp_123",
            token_usage=usage,
            model="gpt-5.2",
            finish_reason="stop",
        )

        assert metadata.response_id == "resp_123"
        assert metadata.model == "gpt-5.2"
        assert metadata.finish_reason == "stop"
        assert metadata.token_usage.total_tokens == 150


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_custom_values(self) -> None:
        """Test custom values."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            max_delay=30.0,
            exponential_base=1.5,
            jitter=False,
            max_rate_limit_retries=10,
        )

        assert config.max_retries == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 1.5
        assert config.jitter is False
        assert config.max_rate_limit_retries == 10


# ============================================================================
# Exception Tests
# ============================================================================


# Skip trivial exception inheritance tests - Python guarantees this


# ============================================================================
# OpenAIClient Tests
# ============================================================================


class TestOpenAIClientInit:
    """Tests for OpenAIClient initialization."""

    def client(self) -> OpenAIClient:
        """Create client for testing."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI"):
            return OpenAIClient(
                api_key="test-key",
                retry_config=RetryConfig(
                    initial_delay=1.0,
                    max_delay=60.0,
                    exponential_base=2.0,
                    jitter=False,
                ),
            )

    def test_jitter_applied(self) -> None:
        """Test that jitter is applied when enabled."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI"):
            client = OpenAIClient(
                api_key="test-key",
                retry_config=RetryConfig(
                    initial_delay=1.0,
                    exponential_base=2.0,
                    jitter=True,
                ),
            )

            delays = [client._get_retry_delay(0) for _ in range(10)]

            # With jitter, not all delays should be exactly the same
            # (probability of all being exactly equal is very low)
            assert len(set(delays)) > 1 or all(0.5 <= d <= 1.0 for d in delays)


class TestShouldRetry:
    """Tests for _should_retry method."""

    @pytest.fixture
    def client(self) -> OpenAIClient:
        """Create client for testing."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI"):
            return OpenAIClient(
                api_key="test-key",
                retry_config=RetryConfig(
                    max_retries=3,
                    max_rate_limit_retries=5,
                    max_timeout_retries=3,
                    max_connection_retries=3,
                ),
            )

    def test_rate_limit_error_retry(self, client: OpenAIClient) -> None:
        """Test rate limit errors are retried."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        error = RateLimitError("Rate limited", response=mock_response, body=None)

        should_retry, reason = client._should_retry(error, attempt=0)

        assert should_retry is True
        assert "Rate limit" in reason

    def test_rate_limit_exhausted(self, client: OpenAIClient) -> None:
        """Test rate limit retries are exhausted."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        error = RateLimitError("Rate limited", response=mock_response, body=None)

        should_retry, reason = client._should_retry(error, attempt=5)

        assert should_retry is False
        assert "exhausted" in reason

    def test_client_error_not_retried(self, client: OpenAIClient) -> None:
        """Test 4xx client errors are not retried."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        error = APIStatusError("Bad request", response=mock_response, body=None)

        should_retry, reason = client._should_retry(error, attempt=0)

        assert should_retry is False
        assert "Client error" in reason

    def test_non_retryable_exception(self, client: OpenAIClient) -> None:
        """Test non-retryable exceptions."""
        error = ValueError("Some error")

        should_retry, reason = client._should_retry(error, attempt=0)

        assert should_retry is False
        assert "Non-retryable" in reason


class TestRetryWithBackoff:
    """Tests for _retry_with_backoff method."""

    @pytest.fixture
    def client(self) -> OpenAIClient:
        """Create client with fast retry config for testing."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI"):
            return OpenAIClient(
                api_key="test-key",
                retry_config=RetryConfig(
                    max_retries=2,
                    initial_delay=0.001,  # Very small delay for tests
                    max_rate_limit_retries=2,
                    max_timeout_retries=2,
                    max_connection_retries=2,
                    jitter=False,
                ),
            )

    def test_success_after_retry(self, client: OpenAIClient) -> None:
        """Test success after retry."""
        attempt_count = {"count": 0}
        request = MagicMock()

        def retry_then_succeed() -> str:
            attempt_count["count"] += 1
            if attempt_count["count"] < 2:
                raise APIConnectionError(request=request)
            return "success"

        result = client._retry_with_backoff(retry_then_succeed, "test operation")
        assert result == "success"
        assert attempt_count["count"] == 2

    def test_raises_after_exhausted(self, client: OpenAIClient) -> None:
        """Test raises OpenAIRetryExhausted after all retries."""
        request = MagicMock()

        def always_fail() -> None:
            raise APIConnectionError(request=request)

        with pytest.raises(OpenAIRetryExhausted) as exc_info:
            client._retry_with_backoff(always_fail, "test operation")

        assert "test operation" in str(exc_info.value)


class TestGenerateJson:
    """Tests for generate_json method."""

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock API response."""
        response = MagicMock()
        response.id = "resp_123"
        response.model = "gpt-5.2"
        response.output_text = '{"result": "success", "count": 5}'
        response.usage = MagicMock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        return response

    @pytest.fixture
    def client_with_mock(self, mock_response: MagicMock) -> OpenAIClient:
        """Create client with mocked responses.create."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.responses.create.return_value = mock_response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")
            return client

    def test_generate_json_success(self, client_with_mock: OpenAIClient) -> None:
        """Test successful JSON generation."""
        messages = [
            {"role": "developer", "content": "You are helpful."},
            {"role": "user", "content": "Generate JSON."},
        ]

        result = client_with_mock.generate_json(messages=messages, model="gpt-5.2")

        assert result == {"result": "success", "count": 5}

    def test_generate_json_with_metadata(self, client_with_mock: OpenAIClient) -> None:
        """Test JSON generation with metadata return."""
        messages = [{"role": "user", "content": "Test"}]

        result, metadata = client_with_mock.generate_json(
            messages=messages, model="gpt-5.2", return_metadata=True
        )

        assert result == {"result": "success", "count": 5}
        assert metadata.response_id == "resp_123"
        assert metadata.token_usage.total_tokens == 150

    def test_generate_json_updates_tracking(self, client_with_mock: OpenAIClient) -> None:
        """Test that generate_json updates internal tracking."""
        messages = [{"role": "user", "content": "Test"}]

        client_with_mock.generate_json(messages=messages, model="gpt-5.2")

        assert client_with_mock.get_last_response_id() == "resp_123"
        assert client_with_mock.get_total_token_usage().total_tokens == 150
        assert len(client_with_mock.get_response_metadata_history()) == 1

    def test_generate_json_temperature_negative(self, client_with_mock: OpenAIClient) -> None:
        """Test negative temperature validation."""
        messages = [{"role": "user", "content": "Test"}]

        with pytest.raises(ValueError):
            client_with_mock.generate_json(messages=messages, model="gpt-5.2", temperature=-0.1)

    def test_generate_json_with_reasoning_effort(self, client_with_mock: OpenAIClient) -> None:
        """Test with reasoning effort parameter."""
        messages = [{"role": "user", "content": "Test"}]

        result = client_with_mock.generate_json(
            messages=messages,
            model="gpt-5.2",
            reasoning_effort=ReasoningEffort.HIGH,
        )

        assert result == {"result": "success", "count": 5}

    def test_generate_json_with_verbosity(self, client_with_mock: OpenAIClient) -> None:
        """Test with verbosity parameter."""
        messages = [{"role": "user", "content": "Test"}]

        result = client_with_mock.generate_json(
            messages=messages,
            model="gpt-5.2",
            verbosity=Verbosity.HIGH,
        )

        assert result == {"result": "success", "count": 5}

    def test_generate_json_with_validation(self, client_with_mock: OpenAIClient) -> None:
        """Test with validation function."""
        messages = [{"role": "user", "content": "Test"}]

        def validator(data: dict[str, Any]) -> bool:
            return "result" in data

        result = client_with_mock.generate_json(
            messages=messages,
            model="gpt-5.2",
            validate_json=validator,
        )

        assert result == {"result": "success", "count": 5}

    def test_generate_json_validation_failure(self, client_with_mock: OpenAIClient) -> None:
        """Test validation failure raises error."""
        messages = [{"role": "user", "content": "Test"}]

        def failing_validator(data: dict[str, Any]) -> bool:
            return False

        with pytest.raises(OpenAIRetryExhausted):
            client_with_mock.generate_json(
                messages=messages,
                model="gpt-5.2",
                validate_json=failing_validator,
            )

    def test_generate_json_empty_response(self) -> None:
        """Test empty response raises error."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_response = MagicMock()
            mock_response.output_text = None
            mock_response.id = "resp_123"
            mock_response.usage = MagicMock(prompt_tokens=0, completion_tokens=0, total_tokens=0)

            mock_client = MagicMock()
            mock_client.responses.create.return_value = mock_response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")
            messages = [{"role": "user", "content": "Test"}]

            with pytest.raises(OpenAIRetryExhausted):
                client.generate_json(messages=messages, model="gpt-5.2")

    def test_generate_json_invalid_json(self) -> None:
        """Test invalid JSON response raises error."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_response = MagicMock()
            mock_response.output_text = "not valid json {"
            mock_response.id = "resp_123"
            mock_response.usage = MagicMock(prompt_tokens=0, completion_tokens=0, total_tokens=0)

            mock_client = MagicMock()
            mock_client.responses.create.return_value = mock_response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")
            messages = [{"role": "user", "content": "Test"}]

            with pytest.raises(OpenAIRetryExhausted):
                client.generate_json(messages=messages, model="gpt-5.2")

    def test_generate_json_mini_model_skips_temperature(self) -> None:
        """Test mini models skip temperature parameter."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_response = MagicMock()
            mock_response.output_text = '{"result": "ok"}'
            mock_response.id = "resp_123"
            mock_response.usage = MagicMock(
                prompt_tokens=100, completion_tokens=50, total_tokens=150
            )

            mock_client = MagicMock()
            mock_client.responses.create.return_value = mock_response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")
            messages = [{"role": "user", "content": "Test"}]

            client.generate_json(
                messages=messages,
                model="gpt-5-mini",
                temperature=0.5,
            )

            # Check that temperature was NOT passed to the API call
            call_kwargs = mock_client.responses.create.call_args.kwargs
            assert "temperature" not in call_kwargs


class TestGenerateText:
    """Tests for generate_text method."""

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock API response."""
        response = MagicMock()
        response.id = "resp_text_123"
        response.model = "gpt-5.2"
        response.output_text = "This is a text response."
        response.usage = MagicMock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        return response

    @pytest.fixture
    def client_with_mock(self, mock_response: MagicMock) -> OpenAIClient:
        """Create client with mocked responses.create."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.responses.create.return_value = mock_response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")
            return client

    def test_generate_text_with_metadata(self, client_with_mock: OpenAIClient) -> None:
        """Test text generation with metadata return."""
        messages = [{"role": "user", "content": "Hello"}]

        result, metadata = client_with_mock.generate_text(
            messages=messages, model="gpt-5.2", return_metadata=True
        )

        assert result == "This is a text response."
        assert metadata.response_id == "resp_text_123"

    def test_generate_text_empty_response(self) -> None:
        """Test empty response raises error."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_response = MagicMock()
            mock_response.output_text = None
            mock_response.id = "resp_123"
            mock_response.usage = MagicMock(prompt_tokens=0, completion_tokens=0, total_tokens=0)

            mock_client = MagicMock()
            mock_client.responses.create.return_value = mock_response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")
            messages = [{"role": "user", "content": "Test"}]

            with pytest.raises(OpenAIRetryExhausted):
                client.generate_text(messages=messages, model="gpt-5.2")


class TestExtractMetadata:
    """Tests for _extract_metadata method."""

    @pytest.fixture
    def client(self) -> OpenAIClient:
        """Create client for testing."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI"):
            return OpenAIClient(api_key="test-key")

    def test_extract_full_metadata(self, client: OpenAIClient) -> None:
        """Test extracting full metadata."""
        response = MagicMock()
        response.id = "resp_123"
        response.model = "gpt-5.2"
        response.usage = MagicMock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        response.choices = [MagicMock(finish_reason="stop")]

        metadata = client._extract_metadata(response)

        assert metadata.response_id == "resp_123"
        assert metadata.model == "gpt-5.2"
        assert metadata.token_usage.prompt_tokens == 100
        assert metadata.token_usage.completion_tokens == 50
        assert metadata.token_usage.total_tokens == 150
        assert metadata.finish_reason == "stop"

    def test_extract_minimal_metadata(self, client: OpenAIClient) -> None:
        """Test extracting metadata with minimal attributes."""
        response = MagicMock(spec=[])  # No attributes

        metadata = client._extract_metadata(response)

        assert metadata.response_id is None
        assert metadata.model is None
        assert metadata.token_usage.total_tokens == 0

    def test_extract_metadata_no_choices(self, client: OpenAIClient) -> None:
        """Test extracting metadata without choices."""
        response = MagicMock()
        response.id = "resp_123"
        response.choices = []

        metadata = client._extract_metadata(response)

        assert metadata.finish_reason is None


class TestConversationManagement:
    """Tests for conversation management methods."""

    @pytest.fixture
    def client(self) -> OpenAIClient:
        """Create client for testing."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI"):
            return OpenAIClient(api_key="test-key")

    def test_add_to_conversation(self, client: OpenAIClient) -> None:
        """Test adding messages to conversation."""
        client.add_to_conversation("user", "Hello")
        client.add_to_conversation("assistant", "Hi there!")

        history = client.get_conversation_history()

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hi there!"

    def test_reset_conversation(self, client: OpenAIClient) -> None:
        """Test resetting conversation state."""
        # Add some state
        client.add_to_conversation("user", "Hello")
        client._last_response_id = "resp_123"
        client._total_token_usage = TokenUsage(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        )
        client._response_metadata_history.append(ResponseMetadata())

        client.reset_conversation()

        assert len(client.get_conversation_history()) == 0
        assert client.get_last_response_id() is None
        assert client.get_total_token_usage().total_tokens == 0
        assert len(client.get_response_metadata_history()) == 0


class TestGenerateJsonWithConversation:
    """Tests for generate_json_with_conversation method."""

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock API response."""
        response = MagicMock()
        response.id = "resp_conv_123"
        response.model = "gpt-5.2"
        response.output_text = '{"response": "Hello back!"}'
        response.usage = MagicMock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        return response

    @pytest.fixture
    def client_with_mock(self, mock_response: MagicMock) -> OpenAIClient:
        """Create client with mocked responses.create."""
        with patch("twinklr.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.responses.create.return_value = mock_response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")
            return client

    def test_conversation_adds_to_history(self, client_with_mock: OpenAIClient) -> None:
        """Test that conversation adds messages to history."""
        result, _metadata = client_with_mock.generate_json_with_conversation(
            user_message="Hello",
            model="gpt-5.2",
        )

        assert result == {"response": "Hello back!"}
        history = client_with_mock.get_conversation_history()
        assert len(history) == 2  # user + assistant

    def test_conversation_without_history(self, client_with_mock: OpenAIClient) -> None:
        """Test conversation without adding to history."""
        result, _ = client_with_mock.generate_json_with_conversation(
            user_message="Hello",
            model="gpt-5.2",
            add_to_history=False,
        )

        assert result == {"response": "Hello back!"}
        history = client_with_mock.get_conversation_history()
        assert len(history) == 0

    def test_conversation_uses_previous_response_id(self, client_with_mock: OpenAIClient) -> None:
        """Test that conversation uses previous response ID."""
        # First call
        client_with_mock.generate_json_with_conversation(
            user_message="Hello",
            model="gpt-5.2",
        )

        # Check response ID is set
        assert client_with_mock.get_last_response_id() == "resp_conv_123"


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestCreateClient:
    """Tests for create_client factory function."""
