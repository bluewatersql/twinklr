"""Tests for OpenAI API client."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
import pytest

from blinkb0t.core.api.llm.openai.client import (
    OpenAIClient,
    OpenAIClientError,
    OpenAIResponseParseError,
    OpenAIRetryExhausted,
    ReasoningEffort,
    ResponseMetadata,
    RetryConfig,
    TokenUsage,
    Verbosity,
    create_client,
)

# ============================================================================
# Enum Tests
# ============================================================================


class TestReasoningEffort:
    """Tests for ReasoningEffort enum."""

    def test_low_value(self) -> None:
        """Test LOW enum value."""
        assert ReasoningEffort.LOW.value == "low"

    def test_medium_value(self) -> None:
        """Test MEDIUM enum value."""
        assert ReasoningEffort.MEDIUM.value == "medium"

    def test_high_value(self) -> None:
        """Test HIGH enum value."""
        assert ReasoningEffort.HIGH.value == "high"

    def test_is_string_enum(self) -> None:
        """Test that ReasoningEffort is a string enum."""
        assert isinstance(ReasoningEffort.LOW, str)
        assert ReasoningEffort.LOW == "low"


class TestVerbosity:
    """Tests for Verbosity enum."""

    def test_low_value(self) -> None:
        """Test LOW enum value."""
        assert Verbosity.LOW.value == "low"

    def test_medium_value(self) -> None:
        """Test MEDIUM enum value."""
        assert Verbosity.MEDIUM.value == "medium"

    def test_high_value(self) -> None:
        """Test HIGH enum value."""
        assert Verbosity.HIGH.value == "high"

    def test_is_string_enum(self) -> None:
        """Test that Verbosity is a string enum."""
        assert isinstance(Verbosity.LOW, str)
        assert Verbosity.LOW == "low"


# ============================================================================
# Dataclass Tests
# ============================================================================


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_default_values(self) -> None:
        """Test default values are zero."""
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0

    def test_custom_values(self) -> None:
        """Test custom values."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150

    def test_add_two_usages(self) -> None:
        """Test adding two TokenUsage instances."""
        usage1 = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        usage2 = TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300)

        result = usage1 + usage2

        assert result.prompt_tokens == 300
        assert result.completion_tokens == 150
        assert result.total_tokens == 450

    def test_add_preserves_original(self) -> None:
        """Test that addition does not modify original instances."""
        usage1 = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        usage2 = TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300)

        _ = usage1 + usage2

        # Originals should be unchanged
        assert usage1.prompt_tokens == 100
        assert usage2.prompt_tokens == 200

    def test_str_representation(self) -> None:
        """Test string representation."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        result = str(usage)

        assert "TokenUsage" in result
        assert "prompt=100" in result
        assert "completion=50" in result
        assert "total=150" in result


class TestResponseMetadata:
    """Tests for ResponseMetadata dataclass."""

    def test_default_values(self) -> None:
        """Test default values."""
        metadata = ResponseMetadata()

        assert metadata.response_id is None
        assert metadata.model is None
        assert metadata.finish_reason is None
        assert isinstance(metadata.token_usage, TokenUsage)
        assert metadata.token_usage.total_tokens == 0

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

    def test_str_representation(self) -> None:
        """Test string representation."""
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        metadata = ResponseMetadata(
            response_id="resp_123",
            token_usage=usage,
            model="gpt-5.2",
        )
        result = str(metadata)

        assert "ResponseMetadata" in result
        assert "resp_123" in result
        assert "gpt-5.2" in result


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert config.max_rate_limit_retries == 5
        assert config.max_timeout_retries == 3
        assert config.max_connection_retries == 3

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


class TestExceptions:
    """Tests for custom exceptions."""

    def test_openai_client_error_is_exception(self) -> None:
        """Test OpenAIClientError inherits from Exception."""
        error = OpenAIClientError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_openai_retry_exhausted_inherits_client_error(self) -> None:
        """Test OpenAIRetryExhausted inherits from OpenAIClientError."""
        error = OpenAIRetryExhausted("Retries exhausted")
        assert isinstance(error, OpenAIClientError)
        assert isinstance(error, Exception)

    def test_openai_response_parse_error_inherits_client_error(self) -> None:
        """Test OpenAIResponseParseError inherits from OpenAIClientError."""
        error = OpenAIResponseParseError("Parse failed")
        assert isinstance(error, OpenAIClientError)
        assert isinstance(error, Exception)


# ============================================================================
# OpenAIClient Tests
# ============================================================================


class TestOpenAIClientInit:
    """Tests for OpenAIClient initialization."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with default values."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            client = OpenAIClient(api_key="test-key")

            mock_openai.assert_called_once_with(api_key="test-key", timeout=120.0)
            assert client.retry_config is not None
            assert client.max_tokens is None

    def test_init_with_custom_retry_config(self) -> None:
        """Test initialization with custom retry config."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
            config = RetryConfig(max_retries=5)
            client = OpenAIClient(api_key="test-key", retry_config=config)

            assert client.retry_config.max_retries == 5

    def test_init_with_custom_timeout(self) -> None:
        """Test initialization with custom timeout."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            OpenAIClient(api_key="test-key", timeout=60.0)

            mock_openai.assert_called_once_with(api_key="test-key", timeout=60.0)

    def test_init_with_max_tokens(self) -> None:
        """Test initialization with max_tokens."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
            client = OpenAIClient(api_key="test-key", max_tokens=4096)

            assert client.max_tokens == 4096

    def test_init_conversation_state(self) -> None:
        """Test conversation state is initialized."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
            client = OpenAIClient(api_key="test-key")

            assert client._conversation_history == []
            assert client._last_response_id is None
            assert client._total_token_usage.total_tokens == 0
            assert client._response_metadata_history == []


class TestGetRetryDelay:
    """Tests for _get_retry_delay method."""

    @pytest.fixture
    def client(self) -> OpenAIClient:
        """Create client for testing."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
            return OpenAIClient(
                api_key="test-key",
                retry_config=RetryConfig(
                    initial_delay=1.0,
                    max_delay=60.0,
                    exponential_base=2.0,
                    jitter=False,
                ),
            )

    def test_first_attempt_delay(self, client: OpenAIClient) -> None:
        """Test delay for first attempt (0-indexed)."""
        delay = client._get_retry_delay(0)
        assert delay == 1.0

    def test_second_attempt_delay(self, client: OpenAIClient) -> None:
        """Test delay for second attempt."""
        delay = client._get_retry_delay(1)
        assert delay == 2.0

    def test_third_attempt_delay(self, client: OpenAIClient) -> None:
        """Test delay for third attempt."""
        delay = client._get_retry_delay(2)
        assert delay == 4.0

    def test_max_delay_cap(self, client: OpenAIClient) -> None:
        """Test that delay is capped at max_delay."""
        delay = client._get_retry_delay(10)  # Would be 1024 without cap
        assert delay == 60.0

    def test_custom_base_delay(self, client: OpenAIClient) -> None:
        """Test with custom base delay."""
        delay = client._get_retry_delay(0, base_delay=2.0)
        assert delay == 2.0

    def test_jitter_applied(self) -> None:
        """Test that jitter is applied when enabled."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
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
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
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

    def test_timeout_error_retry(self, client: OpenAIClient) -> None:
        """Test timeout errors are retried."""
        request = MagicMock()
        error = APITimeoutError(request=request)

        should_retry, reason = client._should_retry(error, attempt=0)

        assert should_retry is True
        assert "Timeout" in reason

    def test_timeout_exhausted(self, client: OpenAIClient) -> None:
        """Test timeout retries are exhausted."""
        request = MagicMock()
        error = APITimeoutError(request=request)

        should_retry, reason = client._should_retry(error, attempt=3)

        assert should_retry is False
        assert "exhausted" in reason

    def test_connection_error_retry(self, client: OpenAIClient) -> None:
        """Test connection errors are retried."""
        request = MagicMock()
        error = APIConnectionError(request=request)

        should_retry, reason = client._should_retry(error, attempt=0)

        assert should_retry is True
        assert "Connection" in reason

    def test_connection_exhausted(self, client: OpenAIClient) -> None:
        """Test connection retries are exhausted."""
        request = MagicMock()
        error = APIConnectionError(request=request)

        should_retry, reason = client._should_retry(error, attempt=3)

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
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
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

    def test_success_on_first_try(self, client: OpenAIClient) -> None:
        """Test successful execution on first try."""

        def success_func() -> str:
            return "success"

        result = client._retry_with_backoff(success_func, "test operation")
        assert result == "success"

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
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
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

    def test_generate_json_temperature_validation(self, client_with_mock: OpenAIClient) -> None:
        """Test temperature parameter validation."""
        messages = [{"role": "user", "content": "Test"}]

        with pytest.raises(ValueError) as exc_info:
            client_with_mock.generate_json(messages=messages, model="gpt-5.2", temperature=3.0)

        assert "temperature must be between" in str(exc_info.value)

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
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
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
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
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
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
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
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.responses.create.return_value = mock_response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")
            return client

    def test_generate_text_success(self, client_with_mock: OpenAIClient) -> None:
        """Test successful text generation."""
        messages = [{"role": "user", "content": "Hello"}]

        result = client_with_mock.generate_text(messages=messages, model="gpt-5.2")

        assert result == "This is a text response."

    def test_generate_text_with_metadata(self, client_with_mock: OpenAIClient) -> None:
        """Test text generation with metadata return."""
        messages = [{"role": "user", "content": "Hello"}]

        result, metadata = client_with_mock.generate_text(
            messages=messages, model="gpt-5.2", return_metadata=True
        )

        assert result == "This is a text response."
        assert metadata.response_id == "resp_text_123"

    def test_generate_text_updates_tracking(self, client_with_mock: OpenAIClient) -> None:
        """Test that generate_text updates internal tracking."""
        messages = [{"role": "user", "content": "Hello"}]

        client_with_mock.generate_text(messages=messages, model="gpt-5.2")

        assert client_with_mock.get_last_response_id() == "resp_text_123"

    def test_generate_text_empty_response(self) -> None:
        """Test empty response raises error."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
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
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
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
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
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

    def test_get_conversation_history_returns_copy(self, client: OpenAIClient) -> None:
        """Test that get_conversation_history returns a copy."""
        client.add_to_conversation("user", "Hello")

        history1 = client.get_conversation_history()
        history2 = client.get_conversation_history()

        assert history1 is not history2

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

    def test_get_last_response_id(self, client: OpenAIClient) -> None:
        """Test getting last response ID."""
        assert client.get_last_response_id() is None

        client._last_response_id = "resp_123"

        assert client.get_last_response_id() == "resp_123"

    def test_get_response_metadata_history_returns_copy(self, client: OpenAIClient) -> None:
        """Test that get_response_metadata_history returns a copy."""
        client._response_metadata_history.append(ResponseMetadata())

        history1 = client.get_response_metadata_history()
        history2 = client.get_response_metadata_history()

        assert history1 is not history2


class TestMessageConversion:
    """Tests for message conversion methods."""

    @pytest.fixture
    def client(self) -> OpenAIClient:
        """Create client for testing."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
            return OpenAIClient(api_key="test-key")

    def test_get_messages_from_simple(self, client: OpenAIClient) -> None:
        """Test converting simple messages to OpenAI format."""
        simple_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        result = client.get_messages_from_simple(simple_messages)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_get_messages_from_simple_defaults(self, client: OpenAIClient) -> None:
        """Test converting simple messages with missing fields."""
        simple_messages = [
            {"content": "Hello"},  # Missing role
            {"role": "user"},  # Missing content
        ]

        result = client.get_messages_from_simple(simple_messages)

        assert result[0]["role"] == "user"  # Default
        assert result[1]["content"] == ""  # Default

    def test_get_simple_messages(self, client: OpenAIClient) -> None:
        """Test converting OpenAI format to simple messages."""
        openai_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        result = client.get_simple_messages(openai_messages)

        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi"}

    def test_get_simple_messages_list_content(self, client: OpenAIClient) -> None:
        """Test converting messages with list content."""
        openai_messages = [
            {"role": "user", "content": ["part1", "part2"]},
        ]

        result = client.get_simple_messages(openai_messages)

        assert result[0]["content"] == "['part1', 'part2']"


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
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
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

    def test_create_client_defaults(self) -> None:
        """Test create_client with defaults."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            client = create_client(api_key="test-key")

            mock_openai.assert_called_once_with(api_key="test-key", timeout=120.0)
            assert client.retry_config.max_retries == 3

    def test_create_client_custom_retries(self) -> None:
        """Test create_client with custom max_retries."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
            client = create_client(api_key="test-key", max_retries=5)

            assert client.retry_config.max_retries == 5

    def test_create_client_custom_timeout(self) -> None:
        """Test create_client with custom timeout."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            create_client(api_key="test-key", timeout=60.0)

            mock_openai.assert_called_once_with(api_key="test-key", timeout=60.0)
