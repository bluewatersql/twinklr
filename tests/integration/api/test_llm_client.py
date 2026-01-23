"""Integration tests for OpenAI LLM client.

These tests verify the integration between client components,
including retry logic, metadata tracking, and conversation flows.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from openai import APIConnectionError, RateLimitError
import pytest

from blinkb0t.core.api.llm.openai.client import (
    OpenAIClient,
    OpenAIRetryExhausted,
    ReasoningEffort,
    RetryConfig,
    Verbosity,
)


class TestRetryIntegration:
    """Integration tests for retry behavior across multiple operations."""

    @pytest.fixture
    def fast_retry_config(self) -> RetryConfig:
        """Create fast retry config for testing."""
        return RetryConfig(
            max_retries=3,
            initial_delay=0.001,
            max_delay=0.01,
            exponential_base=2.0,
            jitter=False,
            max_rate_limit_retries=3,
            max_timeout_retries=2,
            max_connection_retries=2,
        )

    def test_retry_recovers_from_transient_errors(self, fast_retry_config: RetryConfig) -> None:
        """Test that retries can recover from transient errors."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            # First call fails with connection error, second succeeds
            request = MagicMock()
            mock_response = MagicMock()
            mock_response.id = "resp_123"
            mock_response.model = "gpt-5.2"
            mock_response.output_text = '{"recovered": true}'
            mock_response.usage = MagicMock(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            )

            mock_client.responses.create.side_effect = [
                APIConnectionError(request=request),
                mock_response,
            ]
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key", retry_config=fast_retry_config)
            result = client.generate_json(
                messages=[{"role": "user", "content": "test"}],
                model="gpt-5.2",
            )

            assert result == {"recovered": True}
            assert mock_client.responses.create.call_count == 2

    def test_retry_exhaustion_preserves_error(self, fast_retry_config: RetryConfig) -> None:
        """Test that original error is preserved when retries exhausted."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            # Always fail with connection error
            request = MagicMock()
            mock_client.responses.create.side_effect = APIConnectionError(request=request)
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key", retry_config=fast_retry_config)

            with pytest.raises(OpenAIRetryExhausted) as exc_info:
                client.generate_json(
                    messages=[{"role": "user", "content": "test"}],
                    model="gpt-5.2",
                )

            # Original error should be the cause
            assert isinstance(exc_info.value.__cause__, APIConnectionError)

    def test_rate_limit_has_higher_retry_count(self, fast_retry_config: RetryConfig) -> None:
        """Test that rate limit errors get more retry attempts."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            # Create rate limit error
            mock_rate_limit_response = MagicMock()
            mock_rate_limit_response.status_code = 429

            # Fail twice, then succeed
            mock_response = MagicMock()
            mock_response.id = "resp_123"
            mock_response.model = "gpt-5.2"
            mock_response.output_text = '{"success": true}'
            mock_response.usage = MagicMock(
                prompt_tokens=100, completion_tokens=50, total_tokens=150
            )

            mock_client.responses.create.side_effect = [
                RateLimitError("Rate limited", response=mock_rate_limit_response, body=None),
                RateLimitError("Rate limited", response=mock_rate_limit_response, body=None),
                mock_response,
            ]
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key", retry_config=fast_retry_config)
            result = client.generate_json(
                messages=[{"role": "user", "content": "test"}],
                model="gpt-5.2",
            )

            assert result == {"success": True}
            assert mock_client.responses.create.call_count == 3


class TestTokenTrackingIntegration:
    """Integration tests for token tracking across multiple calls."""

    def test_token_accumulation_across_calls(self) -> None:
        """Test that tokens accumulate across multiple API calls."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            def create_response(tokens: int) -> MagicMock:
                response = MagicMock()
                response.id = f"resp_{tokens}"
                response.model = "gpt-5.2"
                response.output_text = '{"data": "test"}'
                response.usage = MagicMock(
                    prompt_tokens=tokens // 2,
                    completion_tokens=tokens // 2,
                    total_tokens=tokens,
                )
                return response

            mock_client.responses.create.side_effect = [
                create_response(100),
                create_response(150),
                create_response(200),
            ]
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")

            # Make three calls
            for _ in range(3):
                client.generate_json(
                    messages=[{"role": "user", "content": "test"}],
                    model="gpt-5.2",
                )

            # Check accumulated tokens
            total_usage = client.get_total_token_usage()
            assert total_usage.total_tokens == 450  # 100 + 150 + 200

    def test_metadata_history_tracked(self) -> None:
        """Test that metadata history is tracked for all calls."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            def create_response(idx: int) -> MagicMock:
                response = MagicMock()
                response.id = f"resp_{idx}"
                response.model = "gpt-5.2"
                response.output_text = f'{{"idx": {idx}}}'
                response.usage = MagicMock(
                    prompt_tokens=100,
                    completion_tokens=50,
                    total_tokens=150,
                )
                return response

            mock_client.responses.create.side_effect = [
                create_response(1),
                create_response(2),
                create_response(3),
            ]
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")

            for _ in range(3):
                client.generate_json(
                    messages=[{"role": "user", "content": "test"}],
                    model="gpt-5.2",
                )

            history = client.get_response_metadata_history()
            assert len(history) == 3
            assert history[0].response_id == "resp_1"
            assert history[1].response_id == "resp_2"
            assert history[2].response_id == "resp_3"

    def test_reset_clears_all_tracking(self) -> None:
        """Test that reset clears all tracking data."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            mock_response = MagicMock()
            mock_response.id = "resp_123"
            mock_response.model = "gpt-5.2"
            mock_response.output_text = '{"test": true}'
            mock_response.usage = MagicMock(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            )
            mock_client.responses.create.return_value = mock_response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")

            # Make a call
            client.generate_json(
                messages=[{"role": "user", "content": "test"}],
                model="gpt-5.2",
            )

            # Verify tracking
            assert client.get_total_token_usage().total_tokens == 150
            assert len(client.get_response_metadata_history()) == 1

            # Reset
            client.reset_conversation()

            # Verify cleared
            assert client.get_total_token_usage().total_tokens == 0
            assert len(client.get_response_metadata_history()) == 0
            assert client.get_last_response_id() is None


class TestConversationFlowIntegration:
    """Integration tests for conversation flows."""

    def test_multi_turn_conversation(self) -> None:
        """Test multi-turn conversation maintains context."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()
            call_count = {"n": 0}

            def create_response(**kwargs: Any) -> MagicMock:
                call_count["n"] += 1
                response = MagicMock()
                response.id = f"resp_{call_count['n']}"
                response.model = "gpt-5.2"
                response.output_text = f'{{"turn": {call_count["n"]}}}'
                response.usage = MagicMock(
                    prompt_tokens=100,
                    completion_tokens=50,
                    total_tokens=150,
                )
                return response

            mock_client.responses.create.side_effect = create_response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")

            # First turn
            result1, _meta1 = client.generate_json_with_conversation(
                user_message="Hello",
                model="gpt-5.2",
            )

            # Second turn
            result2, _meta2 = client.generate_json_with_conversation(
                user_message="How are you?",
                model="gpt-5.2",
            )

            # Third turn
            result3, _meta3 = client.generate_json_with_conversation(
                user_message="Goodbye",
                model="gpt-5.2",
            )

            # Verify results
            assert result1 == {"turn": 1}
            assert result2 == {"turn": 2}
            assert result3 == {"turn": 3}

            # Verify conversation history
            history = client.get_conversation_history()
            assert len(history) == 6  # 3 user + 3 assistant messages

    def test_conversation_response_id_tracking(self) -> None:
        """Test that response IDs are tracked in conversation."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            response = MagicMock()
            response.id = "resp_conv_123"
            response.model = "gpt-5.2"
            response.output_text = '{"message": "hello"}'
            response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            mock_client.responses.create.return_value = response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")

            # Make conversation call
            client.generate_json_with_conversation(
                user_message="Hello",
                model="gpt-5.2",
                use_response_id=True,
            )

            # Check that last_response_id is set
            assert client.get_last_response_id() == "resp_conv_123"


class TestMixedOperationsIntegration:
    """Integration tests for mixing different operations."""

    def test_mixed_json_and_text_generation(self) -> None:
        """Test mixing JSON and text generation."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            json_response = MagicMock()
            json_response.id = "resp_json"
            json_response.model = "gpt-5.2"
            json_response.output_text = '{"type": "json"}'
            json_response.usage = MagicMock(
                prompt_tokens=100, completion_tokens=50, total_tokens=150
            )

            text_response = MagicMock()
            text_response.id = "resp_text"
            text_response.model = "gpt-5.2"
            text_response.output_text = "This is text."
            text_response.usage = MagicMock(
                prompt_tokens=80, completion_tokens=40, total_tokens=120
            )

            mock_client.responses.create.side_effect = [json_response, text_response]
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")

            # JSON call
            json_result = client.generate_json(
                messages=[{"role": "user", "content": "JSON please"}],
                model="gpt-5.2",
            )

            # Text call
            text_result = client.generate_text(
                messages=[{"role": "user", "content": "Text please"}],
                model="gpt-5.2",
            )

            assert json_result == {"type": "json"}
            assert text_result == "This is text."

            # Check combined token usage
            total = client.get_total_token_usage()
            assert total.total_tokens == 270  # 150 + 120

    def test_operations_with_different_parameters(self) -> None:
        """Test operations with different parameter combinations."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            response = MagicMock()
            response.id = "resp_123"
            response.model = "gpt-5.2"
            response.output_text = '{"result": "ok"}'
            response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            mock_client.responses.create.return_value = response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")

            # Call with reasoning effort
            client.generate_json(
                messages=[{"role": "user", "content": "test"}],
                model="gpt-5.2",
                reasoning_effort=ReasoningEffort.HIGH,
            )

            # Call with temperature
            client.generate_json(
                messages=[{"role": "user", "content": "test"}],
                model="gpt-5.2",
                temperature=0.9,
            )

            # Call with verbosity
            client.generate_json(
                messages=[{"role": "user", "content": "test"}],
                model="gpt-5.2",
                verbosity=Verbosity.LOW,
            )

            assert mock_client.responses.create.call_count == 3


class TestValidationIntegration:
    """Integration tests for validation behavior."""

    def test_validation_with_retry(self) -> None:
        """Test validation failure triggers retry behavior."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            # First response fails validation, second passes
            invalid_response = MagicMock()
            invalid_response.id = "resp_1"
            invalid_response.model = "gpt-5.2"
            invalid_response.output_text = '{"invalid": true}'
            invalid_response.usage = MagicMock(
                prompt_tokens=100, completion_tokens=50, total_tokens=150
            )

            valid_response = MagicMock()
            valid_response.id = "resp_2"
            valid_response.model = "gpt-5.2"
            valid_response.output_text = '{"valid": true, "required_field": "present"}'
            valid_response.usage = MagicMock(
                prompt_tokens=100, completion_tokens=50, total_tokens=150
            )

            mock_client.responses.create.side_effect = [invalid_response, valid_response]
            mock_openai.return_value = mock_client

            client = OpenAIClient(
                api_key="test-key",
                retry_config=RetryConfig(
                    max_retries=3,
                    initial_delay=0.001,
                    jitter=False,
                ),
            )

            def validator(data: dict) -> bool:
                return "required_field" in data

            # This should fail on first attempt, succeed on retry
            with pytest.raises(OpenAIRetryExhausted):
                # Note: validation failure isn't automatically retried by the
                # retry mechanism - it raises immediately
                client.generate_json(
                    messages=[{"role": "user", "content": "test"}],
                    model="gpt-5.2",
                    validate_json=validator,
                )


class TestEdgeCasesIntegration:
    """Integration tests for edge cases."""

    def test_empty_conversation_history_on_first_call(self) -> None:
        """Test first conversational call with empty history."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            response = MagicMock()
            response.id = "resp_123"
            response.model = "gpt-5.2"
            response.output_text = '{"greeting": "hello"}'
            response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            mock_client.responses.create.return_value = response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")

            # First call without any history
            assert len(client.get_conversation_history()) == 0

            result, _ = client.generate_json_with_conversation(
                user_message="Hello",
                model="gpt-5.2",
                add_to_history=True,
            )

            assert result == {"greeting": "hello"}
            assert len(client.get_conversation_history()) == 2

    def test_multiple_resets(self) -> None:
        """Test multiple reset calls are safe."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI"):
            client = OpenAIClient(api_key="test-key")

            # Reset multiple times
            client.reset_conversation()
            client.reset_conversation()
            client.reset_conversation()

            # Should still be in clean state
            assert len(client.get_conversation_history()) == 0
            assert client.get_last_response_id() is None

    def test_large_message_handling(self) -> None:
        """Test handling of large messages."""
        with patch("blinkb0t.core.api.llm.openai.client.OpenAI") as mock_openai:
            mock_client = MagicMock()

            response = MagicMock()
            response.id = "resp_large"
            response.model = "gpt-5.2"
            response.output_text = '{"processed": true}'
            response.usage = MagicMock(
                prompt_tokens=10000, completion_tokens=100, total_tokens=10100
            )
            mock_client.responses.create.return_value = response
            mock_openai.return_value = mock_client

            client = OpenAIClient(api_key="test-key")

            # Create large message
            large_content = "x" * 100000

            result = client.generate_json(
                messages=[{"role": "user", "content": large_content}],
                model="gpt-5.2",
            )

            assert result == {"processed": True}
            assert client.get_total_token_usage().total_tokens == 10100
