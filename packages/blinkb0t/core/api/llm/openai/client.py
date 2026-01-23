"""OpenAI API Client with retry logic and error handling"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)
from openai.types.responses import ResponseInputItemParam, ResponseTextConfigParam
from openai.types.shared_params import Reasoning

logger = logging.getLogger(__name__)


class ReasoningEffort(str, Enum):
    """Reasoning effort levels for API requests"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Verbosity(str, Enum):
    """Response verbosity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class TokenUsage:
    """Token usage information from API response"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        """Add token counts from multiple responses"""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    def __str__(self) -> str:
        return (
            f"TokenUsage(prompt={self.prompt_tokens}, "
            f"completion={self.completion_tokens}, "
            f"total={self.total_tokens})"
        )


@dataclass
class ResponseMetadata:
    """Metadata from API response including response_id and token usage"""

    response_id: str | None = None
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    model: str | None = None
    finish_reason: str | None = None

    def __str__(self) -> str:
        return (
            f"ResponseMetadata(id={self.response_id}, "
            f"model={self.model}, "
            f"tokens={self.token_usage})"
        )


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

    # Specific retry counts for different error types
    max_rate_limit_retries: int = 5
    max_timeout_retries: int = 3
    max_connection_retries: int = 3


class OpenAIClientError(Exception):
    """Base exception for OpenAI client errors"""

    pass


class OpenAIRetryExhausted(OpenAIClientError):
    """Raised when all retry attempts are exhausted"""

    pass


class OpenAIResponseParseError(OpenAIClientError):
    """Raised when response cannot be parsed"""

    pass


class OpenAIClient:
    def __init__(
        self,
        api_key: str | None = None,
        retry_config: RetryConfig | None = None,
        timeout: float = 120.0,
        max_tokens: int | None = None,
    ):
        """
        Initialize OpenAI client with retry capabilities

        Args:
            api_key: OpenAI API key (uses env var if not provided)
            retry_config: Configuration for retry behavior
            timeout: Request timeout in seconds
            max_tokens: Maximum tokens for completion (optional)
        """
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.retry_config = retry_config or RetryConfig()
        self.max_tokens = max_tokens

        # Conversation state tracking
        self._conversation_history: list[ResponseInputItemParam] = []
        self._last_response_id: str | None = None
        self._total_token_usage = TokenUsage()
        self._response_metadata_history: list[ResponseMetadata] = []

    def _get_retry_delay(self, attempt: int, base_delay: float | None = None) -> float:
        """
        Calculate retry delay with exponential backoff and optional jitter

        Args:
            attempt: Current attempt number (0-indexed)
            base_delay: Override base delay (uses config default if None)

        Returns:
            Delay in seconds
        """
        if base_delay is None:
            base_delay = self.retry_config.initial_delay

        delay = min(
            base_delay * (self.retry_config.exponential_base**attempt), self.retry_config.max_delay
        )

        if self.retry_config.jitter:
            import random

            delay = delay * (0.5 + random.random() * 0.5)

        return delay

    def _should_retry(self, error: Exception, attempt: int) -> tuple[bool, str]:
        """
        Determine if request should be retried based on error type

        Args:
            error: The exception that occurred
            attempt: Current attempt number (0-indexed)

        Returns:
            Tuple of (should_retry, reason)
        """
        # Rate limit errors - always retry with more attempts
        if isinstance(error, RateLimitError):
            if attempt < self.retry_config.max_rate_limit_retries:
                return (
                    True,
                    f"Rate limit hit (attempt {attempt + 1}/{self.retry_config.max_rate_limit_retries})",
                )
            return False, "Rate limit retry attempts exhausted"

        # Timeout errors
        if isinstance(error, APITimeoutError):
            if attempt < self.retry_config.max_timeout_retries:
                return (
                    True,
                    f"Timeout (attempt {attempt + 1}/{self.retry_config.max_timeout_retries})",
                )
            return False, "Timeout retry attempts exhausted"

        # Connection errors
        if isinstance(error, APIConnectionError):
            if attempt < self.retry_config.max_connection_retries:
                return (
                    True,
                    f"Connection error (attempt {attempt + 1}/{self.retry_config.max_connection_retries})",
                )
            return False, "Connection retry attempts exhausted"

        # Generic API errors - use standard retry count
        if isinstance(error, APIError):
            # Don't retry 4xx errors except rate limits (handled above)
            # Use APIStatusError for status_code access
            if isinstance(error, APIStatusError) and 400 <= error.status_code < 500:
                # Log the full error details for debugging
                logger.error(f"Client error {error.status_code} details: {error}")
                return False, f"Client error {error.status_code} - not retrying"

            if attempt < self.retry_config.max_retries:
                return True, f"API error (attempt {attempt + 1}/{self.retry_config.max_retries})"
            return False, "API error retry attempts exhausted"

        # Don't retry other exceptions
        return False, f"Non-retryable error: {type(error).__name__}"

    def _retry_with_backoff(self, func: Callable[[], Any], operation_name: str = "API call") -> Any:
        """
        Execute function with retry logic and exponential backoff

        Args:
            func: Function to execute
            operation_name: Name of operation for logging

        Returns:
            Result from func

        Raises:
            OpenAIRetryExhausted: When all retries are exhausted
        """
        last_exception = None

        for attempt in range(
            max(
                self.retry_config.max_retries,
                self.retry_config.max_rate_limit_retries,
                self.retry_config.max_timeout_retries,
                self.retry_config.max_connection_retries,
            )
            + 1
        ):
            try:
                return func()

            except Exception as e:
                last_exception = e
                should_retry, reason = self._should_retry(e, attempt)

                if not should_retry:
                    logger.error(f"{operation_name} failed: {reason}")
                    raise OpenAIRetryExhausted(
                        f"{operation_name} failed after retries: {reason}"
                    ) from e

                delay = self._get_retry_delay(attempt)
                logger.warning(
                    f"{operation_name} failed: {reason}. Retrying in {delay:.2f}s... Error: {e}"
                )
                time.sleep(delay)

        # Should never reach here, but just in case
        raise OpenAIRetryExhausted(f"{operation_name} failed after all retries") from last_exception

    def generate_json(
        self,
        messages: list[dict[str, str]],
        model: str = "gpt-5.2",
        *,
        reasoning_effort: ReasoningEffort | None = None,
        temperature: float | None = None,
        verbosity: Verbosity = Verbosity.MEDIUM,
        validate_json: Callable[[Any], bool] | None = None,
        return_metadata: bool = False,
    ) -> Any | tuple[Any, ResponseMetadata]:
        """
        Generate JSON response with retry logic

        Args:
            messages: Input messages as simple dicts with 'role' and 'content' keys
            model: Model to use
            reasoning_effort: Reasoning effort level (ReasoningEffort enum or low/medium/high string)
            temperature: Sampling temperature
            verbosity: Response verbosity (Verbosity enum or low/medium/high string)
            validate_json: Optional validation function for parsed JSON
            return_metadata: If True, return (data, metadata) tuple

        Returns:
            Parsed JSON response, or tuple of (parsed_json, metadata) if return_metadata=True

        Raises:
            OpenAIRetryExhausted: When all retries are exhausted
            OpenAIResponseParseError: When response cannot be parsed or validated
            ValueError: When parameter validation fails
        """
        # Defensive parameter validation
        if temperature is not None and not (0.0 <= temperature <= 2.0):
            raise ValueError(f"temperature must be between 0.0 and 2.0, got {temperature}")

        if reasoning_effort is not None and temperature is not None:
            logger.debug(
                f"Both reasoning_effort ({reasoning_effort}) and temperature ({temperature}) "
                "specified. Using both parameters - note that reasoning models may ignore temperature."
            )

        # Convert enums to strings if needed
        effort = reasoning_effort.value if isinstance(reasoning_effort, ReasoningEffort) else None

        # Convert simple messages to OpenAI format
        openai_messages = self.get_messages_from_simple(messages)

        def _make_request() -> tuple[Any, ResponseMetadata]:
            logger.debug(f"Making OpenAI API call with model={model}")

            # Build text parameter with format and verbosity
            text_param: ResponseTextConfigParam = {
                "format": {"type": "json_object"},
                "verbosity": verbosity.value,  # type: ignore[typeddict-item]
            }

            # Build request parameters
            request_params: dict[str, Any] = {
                "model": model,
                "input": openai_messages,  # type: ignore[arg-type]
                "text": text_param,
            }

            # Mini models (gpt-5-mini, gpt-4o-mini, etc.) don't support temperature or reasoning
            is_mini_model = "mini" in model.lower()

            # Add temperature as top-level parameter if provided and supported
            if temperature is not None and not is_mini_model:
                request_params["temperature"] = temperature
            elif temperature is not None and is_mini_model:
                logger.debug(f"Model {model} does not support temperature parameter, skipping")

            # Only add reasoning if effort is specified AND model supports it
            if effort is not None and not is_mini_model:
                reasoning_param: Reasoning = {"effort": effort}  # type: ignore[typeddict-item]
                request_params["reasoning"] = reasoning_param
            elif effort is not None and is_mini_model:
                logger.debug(f"Model {model} does not support reasoning parameter, skipping")

            response = self.client.responses.create(**request_params)

            # Extract metadata
            metadata = self._extract_metadata(response)

            # Update tracking
            self._last_response_id = metadata.response_id
            self._total_token_usage += metadata.token_usage
            self._response_metadata_history.append(metadata)

            content = response.output_text

            if not content:
                raise OpenAIResponseParseError("Empty response from OpenAI API")

            try:
                response_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response content: {content[:500]}...")  # Log first 500 chars
                raise OpenAIResponseParseError(f"Failed to parse JSON response: {e}") from e

            # Optional validation
            if validate_json and not validate_json(response_data):
                raise OpenAIResponseParseError("Response JSON failed validation")

            logger.debug(
                f"Successfully parsed JSON response. "
                f"Response ID: {metadata.response_id}, "
                f"Tokens: {metadata.token_usage}"
            )
            return response_data, metadata

        result, metadata = self._retry_with_backoff(_make_request, "JSON generation")

        if return_metadata:
            return result, metadata
        return result

    def _extract_metadata(self, response: Any) -> ResponseMetadata:
        """
        Extract metadata from API response

        Args:
            response: Raw API response object

        Returns:
            ResponseMetadata with response_id and token usage
        """
        metadata = ResponseMetadata()

        # Extract response ID
        if hasattr(response, "id"):
            metadata.response_id = response.id

        # Extract model
        if hasattr(response, "model"):
            metadata.model = response.model

        # Extract token usage
        if hasattr(response, "usage"):
            usage = response.usage
            metadata.token_usage = TokenUsage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0),
                completion_tokens=getattr(usage, "completion_tokens", 0),
                total_tokens=getattr(usage, "total_tokens", 0),
            )

        # Extract finish reason (if available)
        if hasattr(response, "choices") and response.choices:
            finish_reason = getattr(response.choices[0], "finish_reason", None)
            metadata.finish_reason = finish_reason

        return metadata

    def get_last_response_id(self) -> str | None:
        """Get the response_id from the last API call"""
        return self._last_response_id

    def get_total_token_usage(self) -> TokenUsage:
        """Get cumulative token usage across all calls in this session"""
        return self._total_token_usage

    def get_response_metadata_history(self) -> list[ResponseMetadata]:
        """Get metadata history for all responses in this session"""
        return self._response_metadata_history.copy()

    def reset_conversation(self):
        """Reset conversation state and token tracking"""
        self._conversation_history.clear()
        self._last_response_id = None
        self._total_token_usage = TokenUsage()
        self._response_metadata_history.clear()
        logger.info("Conversation state reset")

    def get_conversation_history(self) -> list[ResponseInputItemParam]:
        """Get the current conversation history"""
        return self._conversation_history.copy()

    def get_messages_from_simple(
        self, simple_messages: list[dict[str, str]]
    ) -> list[ResponseInputItemParam]:
        """Convert list of dict[str, str] to list of ResponseInputItemParam"""
        messages: list[ResponseInputItemParam] = []
        for m in simple_messages:
            role = m.get("role", "user")
            content = m.get("content", "")

            # Cast to ResponseInputItemParam to satisfy type checker
            message = cast(ResponseInputItemParam, {"role": role, "content": content})
            messages.append(message)

        return messages

    def get_simple_messages(self, messages: list[ResponseInputItemParam]) -> list[dict[str, str]]:
        """Convert list of ResponseInputItemParam to list of dict[str, str]"""
        simple_messages = []
        for m in messages:
            role = str(m.get("role", ""))
            content = m.get("content", "")
            # Convert content to string if it's not already
            if isinstance(content, str):
                content_str = content
            else:
                # Handle list/iterable content types
                content_str = str(content) if content else ""
            simple_messages.append({"role": role, "content": content_str})

        return simple_messages

    def add_to_conversation(
        self,
        role: str,
        content: str,
    ) -> None:
        """
        Add a message to the conversation history

        Args:
            role: Message role (e.g., 'user', 'assistant')
            content: Message content
        """
        message: ResponseInputItemParam = {  # type: ignore[assignment,misc]
            "type": "message",
            "role": role,  # type: ignore[typeddict-item]
            "content": content,
        }
        self._conversation_history.append(message)
        logger.debug(f"Added {role} message to conversation history")

    def generate_json_with_conversation(
        self,
        user_message: str,
        model: str = "gpt-5.2",
        reasoning_effort: ReasoningEffort | str = ReasoningEffort.MEDIUM,
        verbosity: Verbosity | str = Verbosity.LOW,
        validate_json: Callable[[Any], bool] | None = None,
        use_response_id: bool = True,
        add_to_history: bool = True,
    ) -> tuple[Any, ResponseMetadata]:
        """
        Generate JSON response as part of an ongoing conversation

        Args:
            user_message: User's message
            model: Model to use
            reasoning_effort: Reasoning effort level (ReasoningEffort enum or low/medium/high string)
            verbosity: Response verbosity (Verbosity enum or low/medium/high string)
            validate_json: Optional validation function
            use_response_id: Include previous response_id for conversation continuity
            add_to_history: Add this exchange to conversation history

        Returns:
            Tuple of (parsed_json, response_metadata)
        """
        # Add user message to history
        if add_to_history:
            self.add_to_conversation("user", user_message)

        # Build messages - use history or single message
        messages = (
            self._conversation_history.copy()
            if self._conversation_history
            else [
                {
                    "type": "message",
                    "role": "user",
                    "content": user_message,
                }
            ]
        )

        # Convert enums to strings if needed
        effort_str = (
            reasoning_effort.value
            if isinstance(reasoning_effort, ReasoningEffort)
            else reasoning_effort
        )
        verbosity_str = verbosity.value if isinstance(verbosity, Verbosity) else verbosity

        def _make_request() -> tuple[Any, ResponseMetadata]:
            logger.debug(
                f"Making conversational API call with model={model}, "
                f"effort={effort_str}, history_length={len(self._conversation_history)}"
            )

            # Build proper type-safe parameters
            reasoning_param: Reasoning = {"effort": effort_str}  # type: ignore[typeddict-item]
            text_param: ResponseTextConfigParam = {
                "format": {"type": "json_object"},
                "verbosity": verbosity_str,  # type: ignore[typeddict-item]
            }

            # Build request parameters
            request_params: dict[str, Any] = {
                "model": model,
                "input": messages,  # type: ignore[arg-type]
                "reasoning": reasoning_param,
                "text": text_param,
            }

            # Include previous response_id for conversation continuity
            if use_response_id and self._last_response_id:
                request_params["previous_response_id"] = self._last_response_id
                logger.debug(f"Using previous_response_id: {self._last_response_id}")

            response = self.client.responses.create(**request_params)

            # Extract metadata
            metadata = self._extract_metadata(response)

            # Update state
            self._last_response_id = metadata.response_id
            self._total_token_usage += metadata.token_usage
            self._response_metadata_history.append(metadata)

            content = response.output_text

            if not content:
                raise OpenAIResponseParseError("Empty response from OpenAI API")

            try:
                response_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response content: {content[:500]}...")
                raise OpenAIResponseParseError(f"Failed to parse JSON response: {e}") from e

            # Optional validation
            if validate_json and not validate_json(response_data):
                raise OpenAIResponseParseError("Response JSON failed validation")

            # Add assistant response to history
            if add_to_history:
                self.add_to_conversation("assistant", content)

            logger.debug(
                f"Successfully parsed JSON response. "
                f"Response ID: {metadata.response_id}, "
                f"Tokens: {metadata.token_usage}"
            )

            return response_data, metadata

        result, metadata = self._retry_with_backoff(_make_request, "Conversational JSON generation")
        return result, metadata  # type: ignore[no-any-return]

    def generate_text(
        self,
        messages: list[dict[str, str]],
        model: str = "gpt-5.2",
        reasoning_effort: ReasoningEffort | str = ReasoningEffort.MEDIUM,
        verbosity: Verbosity | str = Verbosity.MEDIUM,
        return_metadata: bool = False,
    ) -> str | tuple[str, ResponseMetadata]:
        """
        Generate text response with retry logic

        Args:
            messages: Input messages as simple dicts with 'role' and 'content' keys
            model: Model to use
            reasoning_effort: Reasoning effort level (ReasoningEffort enum or low/medium/high string)
            verbosity: Response verbosity (Verbosity enum or low/medium/high string)
            return_metadata: If True, return (text, metadata) tuple

        Returns:
            Text response, or tuple of (text, metadata) if return_metadata=True

        Raises:
            OpenAIRetryExhausted: When all retries are exhausted
        """
        # Convert enums to strings if needed
        effort_str = (
            reasoning_effort.value
            if isinstance(reasoning_effort, ReasoningEffort)
            else reasoning_effort
        )
        verbosity_str = verbosity.value if isinstance(verbosity, Verbosity) else verbosity

        # Convert simple messages to OpenAI format
        openai_messages = self.get_messages_from_simple(messages)

        def _make_request() -> tuple[str, ResponseMetadata]:
            logger.debug(f"Making OpenAI API call with model={model}, effort={effort_str}")

            # Build proper type-safe parameters
            reasoning_param: Reasoning = {"effort": effort_str}  # type: ignore[typeddict-item]
            text_param: ResponseTextConfigParam = {
                "verbosity": verbosity_str,  # type: ignore[typeddict-item]
            }

            response = self.client.responses.create(
                model=model,
                input=openai_messages,  # type: ignore[arg-type]
                reasoning=reasoning_param,
                text=text_param,
            )

            # Extract metadata
            metadata = self._extract_metadata(response)

            # Update tracking
            self._last_response_id = metadata.response_id
            self._total_token_usage += metadata.token_usage
            self._response_metadata_history.append(metadata)

            content = response.output_text

            if not content:
                raise OpenAIClientError("Empty response from OpenAI API")

            logger.debug(
                f"Successfully received text response ({len(content)} chars). "
                f"Response ID: {metadata.response_id}, "
                f"Tokens: {metadata.token_usage}"
            )
            return content, metadata

        result, metadata = self._retry_with_backoff(_make_request, "Text generation")

        if return_metadata:
            return result, metadata  # type: ignore[no-any-return]
        return result  # type: ignore[no-any-return]


# Convenience function for quick usage
def create_client(
    api_key: str | None = None,
    max_retries: int = 3,
    timeout: float = 120.0,
) -> OpenAIClient:
    """
    Create OpenAI client with default retry configuration

    Args:
        api_key: OpenAI API key
        max_retries: Maximum number of retries
        timeout: Request timeout in seconds

    Returns:
        Configured OpenAIClient instance
    """
    retry_config = RetryConfig(max_retries=max_retries)
    return OpenAIClient(
        api_key=api_key,
        retry_config=retry_config,
        timeout=timeout,
    )
