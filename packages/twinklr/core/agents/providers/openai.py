"""OpenAI provider implementation."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

from twinklr.core.agents.providers.base import (
    LLMResponse,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
from twinklr.core.agents.providers.conversation import Conversation
from twinklr.core.agents.providers.errors import LLMProviderError
from twinklr.core.api.llm.openai.client import OpenAIClient

logger = logging.getLogger(__name__)


def _as_int(value: Any) -> int:
    """Normalize optional SDK usage fields without accepting mock objects as counts."""
    return value if isinstance(value, int) else 0


class OpenAIProvider:
    """OpenAI provider implementation with async-first design.

    Phase 0 Architecture:
    - Primary implementation uses AsyncOpenAI for async methods
    - Sync methods are thin wrappers using asyncio.run()
    - Maintains backward compatibility with existing code
    - Thread-safe token tracking

    Responsibilities:
    - Async-first LLM API calls
    - Manage conversation state
    - Convert responses to standard format
    - Thread-safe token tracking
    """

    _DEFAULT_WINDOW_SIZE: int = 2  # Keep last 2 exchanges

    def __init__(
        self,
        *,
        api_key: str | None = None,
        session_id: str | None = None,
        timeout: float = 300.0,
        base_url: str | None = None,
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (uses env var if not provided)
            session_id: Session identifier for tracking
            timeout: Request timeout
        """
        # Async client for async-first implementation
        self._async_client = AsyncOpenAI(api_key=api_key, timeout=timeout, base_url=base_url)
        self._sync_client = OpenAIClient(api_key=api_key, timeout=timeout)

        self.session_id = session_id or "default"

        # Thread-safe token tracking
        self._token_lock = threading.Lock()
        self._total_tokens = TokenUsage()
        self._sync_usage_snapshot = TokenUsage()

        # Conversation state
        self._conversations: dict[str, Conversation] = {}

    @property
    def provider_type(self) -> ProviderType:
        """Provider type identifier."""
        return ProviderType.OPENAI

    # =========================================================================
    # Sync Methods (Backward Compatible - use sync client)
    # =========================================================================

    def generate_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate JSON using sync client (backward compatible).

        Note: The existing OpenAIClient already handles:
        - Retry logic with exponential backoff
        - OpenAI SDK calls
        - JSON parsing
        - Error handling
        """
        try:
            response_data = self._sync_client.generate_json(
                messages=messages, model=model, temperature=temperature, **kwargs
            )

            cumulative_usage = self._sync_client.get_total_token_usage()
            usage = self._sync_usage_delta(cumulative_usage)

            # Update thread-safe token tracking
            self._update_token_usage(
                prompt_tokens=usage.prompt_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )

            return LLMResponse(
                content=response_data,
                metadata=ResponseMetadata(
                    token_usage=TokenUsage(
                        prompt_tokens=usage.prompt_tokens,
                        reasoning_tokens=usage.reasoning_tokens,
                        completion_tokens=usage.completion_tokens,
                        total_tokens=usage.total_tokens,
                    ),
                    model=model,
                ),
            )

        except (APIError, RateLimitError, APIConnectionError, APITimeoutError, APIStatusError) as e:
            logger.error(f"OpenAI API error: {e}")
            raise LLMProviderError(f"Provider error: {e}") from e

    def generate_json_with_conversation(
        self,
        user_message: str,
        conversation_id: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate JSON with conversation support (sync)."""
        try:
            if conversation_id in self._conversations:
                conversation = self._conversations[conversation_id]
                conversation.messages.append({"role": "user", "content": user_message})
            else:
                messages: list[dict[str, str]] = []
                if system_prompt:
                    messages.append({"role": "developer", "content": system_prompt})
                messages.append({"role": "user", "content": user_message})

                conversation = Conversation(id=conversation_id, messages=messages)
                self._conversations[conversation_id] = conversation

            windowed = self._window_messages(conversation.messages)
            response_data = self._sync_client.generate_json(
                messages=windowed, model=model, temperature=temperature, **kwargs
            )

            conversation.messages.append(
                {"role": "assistant", "content": json.dumps(response_data)}
            )

            cumulative_usage = self._sync_client.get_total_token_usage()
            usage = self._sync_usage_delta(cumulative_usage)

            self._update_token_usage(
                prompt_tokens=usage.prompt_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )

            response_metadata = ResponseMetadata(
                token_usage=TokenUsage(
                    prompt_tokens=usage.prompt_tokens,
                    reasoning_tokens=usage.reasoning_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                ),
                model=model,
                conversation_id=conversation_id,
            )

            return LLMResponse(content=response_data, metadata=response_metadata)

        except (APIError, RateLimitError, APIConnectionError, APITimeoutError, APIStatusError) as e:
            logger.error(f"OpenAI API error: {e}")
            raise LLMProviderError(f"Provider error: {e}") from e

    def add_message_to_conversation(self, conversation_id: str, role: str, content: str) -> None:
        """Add message to conversation."""
        if conversation_id not in self._conversations:
            raise ValueError(f"Conversation {conversation_id} not found")

        self._conversations[conversation_id].messages.append({"role": role, "content": content})

    def get_conversation_history(self, conversation_id: str) -> list[dict[str, str]]:
        """Get conversation history."""
        if conversation_id not in self._conversations:
            raise ValueError(f"Conversation {conversation_id} not found")

        return self._conversations[conversation_id].messages.copy()

    def get_token_usage(self) -> TokenUsage:
        """Get cumulative token usage (thread-safe)."""
        with self._token_lock:
            return self._total_tokens

    def reset_token_tracking(self) -> None:
        """Reset token tracking (thread-safe)."""
        with self._token_lock:
            self._total_tokens = TokenUsage()
            self._sync_usage_snapshot = TokenUsage()
        self._sync_client.reset_conversation()

    def _sync_usage_delta(self, cumulative: Any) -> TokenUsage:
        """Return the current sync call's usage from the client's cumulative totals."""
        current = TokenUsage(
            prompt_tokens=_as_int(getattr(cumulative, "prompt_tokens", 0)),
            reasoning_tokens=_as_int(getattr(cumulative, "reasoning_tokens", 0)),
            completion_tokens=_as_int(getattr(cumulative, "completion_tokens", 0)),
            total_tokens=_as_int(getattr(cumulative, "total_tokens", 0)),
        )
        previous = self._sync_usage_snapshot
        delta = TokenUsage(
            prompt_tokens=max(0, current.prompt_tokens - previous.prompt_tokens),
            reasoning_tokens=max(0, current.reasoning_tokens - previous.reasoning_tokens),
            completion_tokens=max(0, current.completion_tokens - previous.completion_tokens),
            total_tokens=max(0, current.total_tokens - previous.total_tokens),
        )
        self._sync_usage_snapshot = current
        return delta

    def _update_token_usage(
        self, prompt_tokens: int, reasoning_tokens: int, completion_tokens: int, total_tokens: int
    ) -> None:
        """Thread-safe token usage update."""
        with self._token_lock:
            self._total_tokens = TokenUsage(
                prompt_tokens=self._total_tokens.prompt_tokens + prompt_tokens,
                reasoning_tokens=self._total_tokens.reasoning_tokens + reasoning_tokens,
                completion_tokens=self._total_tokens.completion_tokens + completion_tokens,
                total_tokens=self._total_tokens.total_tokens + total_tokens,
            )

    def _window_messages(
        self,
        messages: list[dict[str, str]],
        window_size: int | None = None,
    ) -> list[dict[str, str]]:
        """Apply sliding window to conversation messages.

        Keeps system/developer messages and the last ``window_size``
        user-assistant exchange pairs.  This prevents quadratic token
        growth in planner-judge-retry loops.

        Args:
            messages: Full conversation history.
            window_size: Number of recent exchange pairs to keep.
                Defaults to ``_DEFAULT_WINDOW_SIZE``.

        Returns:
            Windowed message list with system messages preserved.
        """
        if window_size is None:
            window_size = self._DEFAULT_WINDOW_SIZE

        system_msgs = [m for m in messages if m["role"] in ("system", "developer")]
        conversation = [m for m in messages if m["role"] in ("user", "assistant")]

        max_msgs = window_size * 2
        if len(conversation) > max_msgs:
            conversation = conversation[-max_msgs:]

        return system_msgs + conversation

    # =========================================================================
    # Async Methods (Phase 0 - Primary Implementation)
    # =========================================================================

    async def generate_json_async(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate JSON response asynchronously.

        This is the primary async implementation using AsyncOpenAI.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with parsed JSON content and metadata

        Raises:
            LLMProviderError: On unrecoverable errors
        """
        allowed_request_kwargs = {
            "max_output_tokens",
            "max_tokens",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "reasoning",
            "reasoning_effort",
            "metadata",
            "timeout_seconds",
        }

        try:
            # Build request parameters
            request_params: dict[str, Any] = {
                "model": model,
                "input": messages,
                "text": {"format": {"type": "json_object"}},
            }

            # GPT-5.6 supports temperature.  We intentionally send it for every
            # configured model instead of guessing from a substring in its name.
            if temperature is not None:
                request_params["temperature"] = temperature

            allowed_kwargs = {
                key: value for key, value in kwargs.items() if key in allowed_request_kwargs
            }
            reasoning_effort = allowed_kwargs.pop("reasoning_effort", None)
            if reasoning_effort is not None:
                request_params["reasoning"] = {"effort": reasoning_effort}
            max_tokens = allowed_kwargs.pop("max_tokens", None)
            if max_tokens is not None and "max_output_tokens" not in allowed_kwargs:
                allowed_kwargs["max_output_tokens"] = max_tokens
            timeout_seconds = allowed_kwargs.pop("timeout_seconds", None)
            if timeout_seconds is not None:
                allowed_kwargs["timeout"] = timeout_seconds
            request_params.update(allowed_kwargs)

            # Make async API call with transient retry handling
            response = None
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    response = await self._async_client.responses.create(**request_params)
                    break
                except Exception as error:
                    if not self._should_retry_async_error(error, attempt, max_attempts):
                        raise
                    await asyncio.sleep(0.5 * (2**attempt))

            if response is None:
                raise LLMProviderError("No response received from OpenAI API")

            # Extract response content
            content = response.output_text
            if not content:
                raise LLMProviderError("Empty response from OpenAI API")

            # Parse JSON
            try:
                response_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise LLMProviderError(f"Failed to parse JSON response: {e}") from e

            # Extract token usage
            token_usage = TokenUsage()
            if hasattr(response, "usage") and response.usage:
                prompt_tokens = _as_int(getattr(response.usage, "prompt_tokens", None))
                completion_tokens = _as_int(getattr(response.usage, "completion_tokens", None))
                total_tokens = _as_int(getattr(response.usage, "total_tokens", None))
                # Responses API variants may expose input/output token names instead.
                if prompt_tokens in (None, 0):
                    prompt_tokens = _as_int(getattr(response.usage, "input_tokens", 0))
                if completion_tokens in (None, 0):
                    completion_tokens = _as_int(getattr(response.usage, "output_tokens", 0))
                if total_tokens in (None, 0):
                    total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
                output_details = getattr(response.usage, "output_tokens_details", None)
                reasoning_tokens = _as_int(getattr(output_details, "reasoning_tokens", 0))
                completion_without_reasoning = max(0, (completion_tokens or 0) - reasoning_tokens)
                token_usage = TokenUsage(
                    prompt_tokens=prompt_tokens or 0,
                    reasoning_tokens=reasoning_tokens,
                    completion_tokens=completion_without_reasoning,
                    total_tokens=total_tokens or 0,
                )
                self._update_token_usage(
                    prompt_tokens=token_usage.prompt_tokens,
                    reasoning_tokens=token_usage.reasoning_tokens,
                    completion_tokens=token_usage.completion_tokens,
                    total_tokens=token_usage.total_tokens,
                )

            return LLMResponse(
                content=response_data,
                metadata=ResponseMetadata(
                    response_id=getattr(response, "id", None),
                    token_usage=token_usage,
                    model=model,
                ),
            )

        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"Async OpenAI provider error: {e}")
            raise LLMProviderError(f"Provider error: {e}") from e

    @staticmethod
    def _should_retry_async_error(error: Exception, attempt: int, max_attempts: int) -> bool:
        """Determine whether async request should be retried."""
        if attempt >= max_attempts - 1:
            return False

        if (
            isinstance(error, APIStatusError)
            and 400 <= error.status_code < 500
            and error.status_code != 429
        ):
            return False

        retryable_types = (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
            APIError,
            TimeoutError,
            ConnectionError,
        )
        return isinstance(error, retryable_types)

    async def generate_json_with_conversation_async(
        self,
        user_message: str,
        conversation_id: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate JSON with conversation support asynchronously.

        Args:
            user_message: User's message
            conversation_id: Conversation ID (created if doesn't exist)
            model: Model identifier
            system_prompt: System prompt (only used for new conversations)
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with parsed JSON content and metadata

        Raises:
            LLMProviderError: On unrecoverable errors
        """
        try:
            if conversation_id in self._conversations:
                conversation = self._conversations[conversation_id]
                conversation.messages.append({"role": "user", "content": user_message})
            else:
                messages: list[dict[str, str]] = []
                if system_prompt:
                    messages.append({"role": "developer", "content": system_prompt})
                messages.append({"role": "user", "content": user_message})

                conversation = Conversation(id=conversation_id, messages=messages)
                self._conversations[conversation_id] = conversation

            # Apply sliding window to limit token growth
            windowed = self._window_messages(conversation.messages)

            # Use async method
            response = await self.generate_json_async(
                messages=windowed,
                model=model,
                temperature=temperature,
                **kwargs,
            )

            # Add assistant response to conversation
            conversation.messages.append(
                {"role": "assistant", "content": json.dumps(response.content)}
            )

            # Return with conversation_id in metadata
            return LLMResponse(
                content=response.content,
                metadata=ResponseMetadata(
                    response_id=response.metadata.response_id,
                    token_usage=response.metadata.token_usage,
                    model=model,
                    conversation_id=conversation_id,
                ),
            )

        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"Async OpenAI provider error: {e}")
            raise LLMProviderError(f"Provider error: {e}") from e
