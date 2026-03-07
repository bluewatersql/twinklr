"""Anthropic Claude LLM provider implementation."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from twinklr.core.agents.providers.base import (
    LLMResponse,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
from twinklr.core.agents.providers.conversation import Conversation
from twinklr.core.agents.providers.errors import LLMProviderError

# Lazy-imported at module level for type-checker friendliness.
# The actual import happens inside __init__ so the package is optional.
try:
    from anthropic import Anthropic, AsyncAnthropic
except ImportError:  # pragma: no cover
    Anthropic = None
    AsyncAnthropic = None

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Anthropic Claude LLM provider.

    Implements the LLMProvider protocol with both sync and async paths.

    Key design decisions:
    - Anthropic API requires system messages as a separate ``system`` parameter,
      not inside the ``messages`` list.  This class extracts any message with
      role ``"system"`` or ``"developer"`` and passes its content as ``system``.
    - Thread-safe cumulative token tracking via ``threading.Lock``.
    - Conversation windowing mirrors the OpenAI provider (``_window_messages``).
    - The ``anthropic`` package is imported lazily so it remains an optional
      dependency; callers that never use this provider pay no import cost.
    """

    _DEFAULT_WINDOW_SIZE: int = 2  # Keep last 2 exchange pairs

    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_model: str = "claude-sonnet-4-20250514",
        session_id: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        """Initialize AnthropicProvider.

        Args:
            api_key: Anthropic API key.  Falls back to ``ANTHROPIC_API_KEY``
                environment variable when ``None``.
            default_model: Default Claude model identifier.
            session_id: Optional session identifier for tracking.
            timeout: HTTP request timeout in seconds.
        """
        if Anthropic is None:  # pragma: no cover
            raise ImportError(
                "The 'anthropic' package is required to use AnthropicProvider. "
                "Install it with: pip install 'twinklr-core[anthropic]'"
            )

        self._sync_client: Anthropic = Anthropic(api_key=api_key, timeout=timeout)
        self._async_client: AsyncAnthropic = AsyncAnthropic(api_key=api_key, timeout=timeout)
        self.default_model = default_model
        self.session_id = session_id or "default"

        # Thread-safe token tracking
        self._token_lock = threading.Lock()
        self._total_tokens = TokenUsage()

        # Conversation state
        self._conversations: dict[str, Conversation] = {}

    # =========================================================================
    # Protocol: provider_type
    # =========================================================================

    @property
    def provider_type(self) -> ProviderType:
        """Provider type identifier.

        Returns:
            ProviderType.ANTHROPIC
        """
        return ProviderType.ANTHROPIC

    # =========================================================================
    # Internal helpers
    # =========================================================================

    @staticmethod
    def _split_messages(
        messages: list[dict[str, str]],
    ) -> tuple[str | None, list[dict[str, str]]]:
        """Extract system/developer content from a messages list.

        Anthropic requires system instructions as a top-level ``system``
        parameter rather than inside the ``messages`` array.  OpenAI uses
        ``"role": "developer"`` for the same purpose, so both roles are
        treated equivalently here.

        Args:
            messages: Full list of message dicts with ``role`` and ``content``.

        Returns:
            A two-tuple ``(system_text, filtered_messages)`` where
            ``system_text`` is the concatenated text of all system/developer
            messages (or ``None`` if absent) and ``filtered_messages`` is the
            remaining list with only ``"user"`` and ``"assistant"`` roles.
        """
        system_parts: list[str] = []
        conversation: list[dict[str, str]] = []

        for msg in messages:
            if msg["role"] in ("system", "developer"):
                system_parts.append(msg["content"])
            else:
                conversation.append(msg)

        system_text = "\n\n".join(system_parts) if system_parts else None
        return system_text, conversation

    def _window_messages(
        self,
        messages: list[dict[str, str]],
        window_size: int | None = None,
    ) -> list[dict[str, str]]:
        """Apply a sliding window to conversation messages.

        Keeps system/developer messages and the last ``window_size``
        user-assistant exchange pairs to prevent quadratic token growth in
        planner-judge-retry loops.

        Args:
            messages: Full conversation history.
            window_size: Number of recent exchange pairs to retain.
                Defaults to ``_DEFAULT_WINDOW_SIZE``.

        Returns:
            Windowed message list with system messages preserved at the front.
        """
        if window_size is None:
            window_size = self._DEFAULT_WINDOW_SIZE

        system_msgs = [m for m in messages if m["role"] in ("system", "developer")]
        conversation = [m for m in messages if m["role"] in ("user", "assistant")]

        max_msgs = window_size * 2
        if len(conversation) > max_msgs:
            conversation = conversation[-max_msgs:]

        return system_msgs + conversation

    def _update_token_usage(
        self, prompt_tokens: int, completion_tokens: int, total_tokens: int
    ) -> None:
        """Thread-safe accumulation of token usage.

        Args:
            prompt_tokens: Input tokens for this call.
            completion_tokens: Output tokens for this call.
            total_tokens: Total tokens for this call.
        """
        with self._token_lock:
            self._total_tokens = TokenUsage(
                prompt_tokens=self._total_tokens.prompt_tokens + prompt_tokens,
                completion_tokens=self._total_tokens.completion_tokens + completion_tokens,
                total_tokens=self._total_tokens.total_tokens + total_tokens,
            )

    @staticmethod
    def _extract_token_usage(response: Any) -> TokenUsage:
        """Extract token usage from an Anthropic API response.

        Args:
            response: Raw response object from ``anthropic.messages.create``.

        Returns:
            Populated ``TokenUsage`` dataclass.
        """
        if not hasattr(response, "usage") or response.usage is None:
            return TokenUsage()

        input_tokens = getattr(response.usage, "input_tokens", 0) or 0
        output_tokens = getattr(response.usage, "output_tokens", 0) or 0
        return TokenUsage(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )

    @staticmethod
    def _parse_response_text(response: Any) -> Any:
        """Extract and JSON-parse the text content from an Anthropic response.

        Args:
            response: Raw response object from ``anthropic.messages.create``.

        Returns:
            Parsed Python object (dict, list, etc.).

        Raises:
            LLMProviderError: If the response has no text content or the text
                is not valid JSON.
        """
        if not response.content:
            raise LLMProviderError("Empty response from Anthropic API")

        text = response.content[0].text
        if not text:
            raise LLMProviderError("Empty text block in Anthropic response")

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Anthropic JSON response: %s", exc)
            raise LLMProviderError(f"Failed to parse JSON response: {exc}") from exc

    # =========================================================================
    # Sync Methods
    # =========================================================================

    def generate_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a JSON response synchronously.

        Args:
            messages: List of message dicts with ``role`` and ``content``.
                Roles ``"system"`` and ``"developer"`` are extracted and
                forwarded as the Anthropic ``system`` parameter.
            model: Claude model identifier (e.g. ``"claude-sonnet-4-20250514"``).
            temperature: Sampling temperature.  Passed only when provided.
            **kwargs: Additional parameters forwarded to the Anthropic API.

        Returns:
            ``LLMResponse`` with parsed JSON ``content`` and populated
            ``metadata`` (token usage, model).

        Raises:
            LLMProviderError: On API errors or JSON parse failures.
        """
        try:
            system_text, conversation_messages = self._split_messages(messages)

            request_params: dict[str, Any] = {
                "model": model,
                "max_tokens": kwargs.pop("max_tokens", 4096),
                "messages": conversation_messages,
            }
            if system_text:
                request_params["system"] = system_text
            if temperature is not None:
                request_params["temperature"] = temperature

            response = self._sync_client.messages.create(**request_params, **kwargs)

            response_data = self._parse_response_text(response)
            token_usage = self._extract_token_usage(response)
            self._update_token_usage(
                prompt_tokens=token_usage.prompt_tokens,
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
        except Exception as exc:
            logger.error("Anthropic provider error: %s", exc)
            raise LLMProviderError(f"Provider error: {exc}") from exc

    def generate_json_with_conversation(
        self,
        user_message: str,
        conversation_id: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a JSON response with conversation state management (sync).

        Args:
            user_message: The user's message content.
            conversation_id: Conversation identifier; created automatically if
                it does not already exist.
            model: Claude model identifier.
            system_prompt: System instruction text used when creating a new
                conversation.  Ignored when the conversation already exists.
            temperature: Sampling temperature.
            **kwargs: Additional parameters forwarded to the Anthropic API.

        Returns:
            ``LLMResponse`` with ``metadata.conversation_id`` populated.

        Raises:
            LLMProviderError: On API errors or JSON parse failures.
        """
        try:
            if conversation_id in self._conversations:
                conversation = self._conversations[conversation_id]
                conversation.messages.append({"role": "user", "content": user_message})
            else:
                messages: list[dict[str, str]] = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": user_message})
                conversation = Conversation(id=conversation_id, messages=messages)
                self._conversations[conversation_id] = conversation

            windowed = self._window_messages(conversation.messages)
            response = self.generate_json(
                messages=windowed, model=model, temperature=temperature, **kwargs
            )

            conversation.messages.append(
                {"role": "assistant", "content": json.dumps(response.content)}
            )

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
        except Exception as exc:
            logger.error("Anthropic provider error: %s", exc)
            raise LLMProviderError(f"Provider error: {exc}") from exc

    # =========================================================================
    # Async Methods
    # =========================================================================

    async def generate_json_async(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a JSON response asynchronously.

        Args:
            messages: List of message dicts with ``role`` and ``content``.
                Roles ``"system"`` and ``"developer"`` are extracted and
                forwarded as the Anthropic ``system`` parameter.
            model: Claude model identifier.
            temperature: Sampling temperature.  Passed only when provided.
            **kwargs: Additional parameters forwarded to the Anthropic API.

        Returns:
            ``LLMResponse`` with parsed JSON ``content`` and populated
            ``metadata``.

        Raises:
            LLMProviderError: On API errors or JSON parse failures.
        """
        try:
            system_text, conversation_messages = self._split_messages(messages)

            request_params: dict[str, Any] = {
                "model": model,
                "max_tokens": kwargs.pop("max_tokens", 4096),
                "messages": conversation_messages,
            }
            if system_text:
                request_params["system"] = system_text
            if temperature is not None:
                request_params["temperature"] = temperature

            response = await self._async_client.messages.create(**request_params, **kwargs)

            response_data = self._parse_response_text(response)
            token_usage = self._extract_token_usage(response)
            self._update_token_usage(
                prompt_tokens=token_usage.prompt_tokens,
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
        except Exception as exc:
            logger.error("Async Anthropic provider error: %s", exc)
            raise LLMProviderError(f"Provider error: {exc}") from exc

    async def generate_json_with_conversation_async(
        self,
        user_message: str,
        conversation_id: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a JSON response with conversation state management (async).

        Args:
            user_message: The user's message content.
            conversation_id: Conversation identifier; created automatically if
                it does not already exist.
            model: Claude model identifier.
            system_prompt: System instruction text for new conversations.
            temperature: Sampling temperature.
            **kwargs: Additional parameters forwarded to the Anthropic API.

        Returns:
            ``LLMResponse`` with ``metadata.conversation_id`` populated.

        Raises:
            LLMProviderError: On API errors or JSON parse failures.
        """
        try:
            if conversation_id in self._conversations:
                conversation = self._conversations[conversation_id]
                conversation.messages.append({"role": "user", "content": user_message})
            else:
                messages: list[dict[str, str]] = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": user_message})
                conversation = Conversation(id=conversation_id, messages=messages)
                self._conversations[conversation_id] = conversation

            windowed = self._window_messages(conversation.messages)
            response = await self.generate_json_async(
                messages=windowed, model=model, temperature=temperature, **kwargs
            )

            conversation.messages.append(
                {"role": "assistant", "content": json.dumps(response.content)}
            )

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
        except Exception as exc:
            logger.error("Async Anthropic provider error: %s", exc)
            raise LLMProviderError(f"Provider error: {exc}") from exc

    # =========================================================================
    # Token / conversation accessors
    # =========================================================================

    def add_message_to_conversation(self, conversation_id: str, role: str, content: str) -> None:
        """Append a message to an existing conversation.

        Args:
            conversation_id: Identifier of an existing conversation.
            role: Message role (e.g. ``"user"`` or ``"assistant"``).
            content: Message text.

        Raises:
            ValueError: If ``conversation_id`` does not exist.
        """
        if conversation_id not in self._conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
        self._conversations[conversation_id].messages.append({"role": role, "content": content})

    def get_conversation_history(self, conversation_id: str) -> list[dict[str, str]]:
        """Return a copy of the conversation message history.

        Args:
            conversation_id: Identifier of an existing conversation.

        Returns:
            Shallow copy of the messages list.

        Raises:
            ValueError: If ``conversation_id`` does not exist.
        """
        if conversation_id not in self._conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
        return self._conversations[conversation_id].messages.copy()

    def get_token_usage(self) -> TokenUsage:
        """Return cumulative token usage (thread-safe).

        Returns:
            ``TokenUsage`` dataclass with accumulated counts.
        """
        with self._token_lock:
            return self._total_tokens

    def reset_token_tracking(self) -> None:
        """Reset cumulative token usage to zero (thread-safe)."""
        with self._token_lock:
            self._total_tokens = TokenUsage()
