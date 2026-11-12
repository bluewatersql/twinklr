"""Anthropic Claude LLM provider implementation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import json
import logging
import threading
from typing import TYPE_CHECKING, Any, cast

from twinklr.core.agents.providers.base import (
    ImageBackground,
    ImageGenerationResponse,
    ImageOutputFormat,
    ImageQuality,
    ImageSize,
    LLMResponse,
    ProviderCapabilities,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
    unwrap_whole_response_fence,
)
from twinklr.core.agents.providers.conversation import Conversation
from twinklr.core.agents.providers.errors import LLMProviderError, RecoverableLLMProviderError
from twinklr.core.agents.schema_utils import response_schema_hash, strict_json_schema

if TYPE_CHECKING:
    from pydantic import BaseModel

# Lazy-imported at module level for type-checker friendliness.
# The actual import happens inside __init__ so the package is optional.
try:
    from anthropic import Anthropic, AsyncAnthropic
except ImportError:  # pragma: no cover
    Anthropic = cast("Any", None)  # type: ignore[misc,unused-ignore]
    AsyncAnthropic = cast("Any", None)  # type: ignore[misc,unused-ignore]

logger = logging.getLogger(__name__)

DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"

# Claude structured outputs reject numeric, string-length, and most array-size
# constraints.  They are moved into the description so the model still sees them,
# and Pydantic re-validates every response, so no constraint is lost.
_CLAUDE_UNSUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "default",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minLength",
        "minProperties",
        "minimum",
        "multipleOf",
        "pattern",
        "uniqueItems",
    }
)
_CLAUDE_SUPPORTED_STRING_FORMATS = frozenset(
    {"date-time", "time", "date", "duration", "email", "hostname", "uri", "ipv4", "ipv6", "uuid"}
)

# Models that accept the server-side refusal fallback ("default" routing form).
_SERVER_SIDE_FALLBACK_MODELS = frozenset(
    {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
)
_SERVER_SIDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Claude compiles each output schema into a grammar and rejects one that is too
# large with HTTP 400 before generating anything.  Every planner schema hits this
# (live probe 2026-11-12), so such requests are resent with the schema carried
# only by the prompt, which the runner validates and repairs like any response.
_SCHEMA_COMPLEXITY_REJECTION_MARKERS = (
    "compiled grammar is too large",
    "schema is too complex",
)


@dataclass(frozen=True)
class _ClaudeRequest:
    """One Messages request plus the context needed to resend and parse it."""

    params: dict[str, Any]
    response_model: type[BaseModel] | None
    schema_hash: str | None
    allow_prompt_only_fallback: bool

    @property
    def prompt_only(self) -> bool:
        """Whether a structured request carries its schema only in the prompt."""
        return self.response_model is not None and "format" not in self.params.get(
            "output_config", {}
        )


def claude_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Derive the Claude structured-output schema from Twinklr's strict schema."""
    return cast("dict[str, Any]", _claude_schema_node(strict_json_schema(model)))


def _claude_schema_node(value: Any) -> Any:
    if isinstance(value, list):
        return [_claude_schema_node(item) for item in value]
    if not isinstance(value, dict):
        return value

    node: dict[str, Any] = {}
    moved: dict[str, Any] = {}
    for key, child in value.items():
        if key in ("properties", "$defs"):
            node[key] = {name: _claude_schema_node(schema) for name, schema in child.items()}
        elif (key == "minItems" and child not in (0, 1)) or (
            key == "format" and child not in _CLAUDE_SUPPORTED_STRING_FORMATS
        ):
            moved[key] = child
        elif key in _CLAUDE_UNSUPPORTED_SCHEMA_KEYWORDS:
            if key != "default":
                moved[key] = child
        else:
            node[key] = _claude_schema_node(child)
    if moved and "$ref" not in node:
        constraint = ", ".join(f"{key}: {json.dumps(moved[key])}" for key in sorted(moved))
        description = node.get("description")
        node["description"] = (
            f"{description}\n\n{{{constraint}}}" if description else f"{{{constraint}}}"
        )
    return node


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
        default_model: str = DEFAULT_CLAUDE_MODEL,
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

        self._sync_client: Any = Anthropic(api_key=api_key, timeout=timeout)
        self._async_client: Any = AsyncAnthropic(api_key=api_key, timeout=timeout)
        self.default_model = default_model
        self.session_id = session_id or "default"

        # Thread-safe token tracking
        self._token_lock = threading.Lock()
        self._total_tokens = TokenUsage()

        # Conversation state
        self._conversations: dict[str, Conversation] = {}
        # (model, schema hash) pairs Claude refused to compile; later requests skip the 400.
        self._prompt_only_schemas: set[tuple[str, str]] = set()

    async def aclose(self) -> None:
        """Close the underlying Anthropic HTTP clients and their connection pools."""
        await self._async_client.close()
        self._sync_client.close()

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

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Anthropic does not use the OpenAI-compatible structured request path."""
        return ProviderCapabilities()

    @property
    def supports_image_generation(self) -> bool:
        """Anthropic does not expose the required generated-image capability."""
        return False

    async def generate_image_async(
        self,
        *,
        prompt: str,
        model: str,
        size: ImageSize,
        quality: ImageQuality,
        background: ImageBackground,
        output_format: ImageOutputFormat,
    ) -> ImageGenerationResponse:
        """Fail clearly if an image request is routed to Anthropic."""
        del prompt, model, size, quality, background, output_format
        raise LLMProviderError(
            "Asset image generation requires the OpenAI provider; configured provider is anthropic"
        )

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
        # The Messages API rejects a conversation whose first turn is the assistant's.
        while conversation and conversation[0]["role"] == "assistant":
            conversation.pop(0)

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

        Cached prompt tokens count as prompt tokens; thinking is billed inside
        ``output_tokens`` and is not reported separately.
        """
        if not hasattr(response, "usage") or response.usage is None:
            return TokenUsage()

        usage = response.usage
        input_tokens = sum(
            getattr(usage, field, 0) or 0
            for field in (
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
            )
        )
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        return TokenUsage(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )

    @staticmethod
    def _response_text(response: Any) -> str:
        """Join the response's text blocks, skipping thinking and fallback markers.

        After a mid-stream refusal fallback the partial text before the
        ``fallback`` block is the prefix the fallback model continues from, so
        every text block belongs to the final answer.
        """
        return "".join(
            block.text
            for block in getattr(response, "content", None) or []
            if getattr(block, "type", "text") == "text"
            and isinstance(getattr(block, "text", None), str)
        )

    def _build_request(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None,
        kwargs: dict[str, Any],
    ) -> _ClaudeRequest:
        """Translate Twinklr's portable request options into a Messages request."""
        response_model = kwargs.pop("response_model", None)
        if kwargs.pop("input_image_urls", None):
            raise LLMProviderError("Configured provider does not support vision image inputs")
        allow_prompt_only_fallback = kwargs.pop("allow_json_object_fallback", True)
        if not isinstance(allow_prompt_only_fallback, bool):
            raise LLMProviderError("allow_json_object_fallback must be a boolean")
        # OpenAI-only transport switch.
        kwargs.pop("provider_max_attempts", None)
        reasoning_effort = kwargs.pop("reasoning_effort", None)
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        max_tokens = kwargs.pop("max_tokens", 16000)
        if kwargs:
            raise LLMProviderError(
                f"Unsupported Anthropic request options: {', '.join(sorted(kwargs))}"
            )
        if temperature is not None:
            # Sampling parameters return HTTP 400 on every current Claude model.
            logger.debug("Dropping temperature=%s for Claude model %s", temperature, model)

        if not model.startswith("claude-"):
            raise LLMProviderError(
                f"Model {model!r} is not a Claude model; set every agent role's model "
                "in job_config.json to a claude-* id when llm_provider is anthropic"
            )

        system_text, conversation_messages = self._split_messages(messages)
        request_params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": conversation_messages,
        }
        if system_text:
            request_params["system"] = system_text
        output_config: dict[str, Any] = {}
        if reasoning_effort is not None:
            output_config["effort"] = reasoning_effort
        schema_hash: str | None = None
        if response_model is not None:
            if not hasattr(response_model, "model_json_schema"):
                raise LLMProviderError("response_model must be a Pydantic model class")
            schema_model = cast("type[BaseModel]", response_model)
            schema_hash = response_schema_hash(schema_model)
            if (model, schema_hash) not in self._prompt_only_schemas:
                output_config["format"] = {
                    "type": "json_schema",
                    "schema": claude_json_schema(schema_model),
                }
        if output_config:
            request_params["output_config"] = output_config
        if timeout_seconds is not None:
            request_params["timeout"] = timeout_seconds
        if model in _SERVER_SIDE_FALLBACK_MODELS:
            request_params["extra_headers"] = {"anthropic-beta": _SERVER_SIDE_FALLBACK_BETA}
            request_params["extra_body"] = {"fallbacks": "default"}
        return _ClaudeRequest(
            params=request_params,
            response_model=cast("type[BaseModel] | None", response_model),
            schema_hash=schema_hash,
            allow_prompt_only_fallback=allow_prompt_only_fallback,
        )

    def _prompt_only_request(
        self, request: _ClaudeRequest, error: Exception
    ) -> _ClaudeRequest | None:
        """Return the request without a schema Claude refused to compile, if allowed."""
        if (
            request.response_model is None
            or request.schema_hash is None
            or request.prompt_only
            or not request.allow_prompt_only_fallback
            or getattr(error, "status_code", None) != 400
        ):
            return None
        body = getattr(error, "body", None)
        detail = body.get("error") if isinstance(body, dict) else None
        message = detail.get("message") if isinstance(detail, dict) else None
        text = (message if isinstance(message, str) else str(error)).lower()
        if not any(marker in text for marker in _SCHEMA_COMPLEXITY_REJECTION_MARKERS):
            return None
        logger.warning(
            "Claude rejected the %s schema as too complex to compile; "
            "resending with the schema carried only by the prompt: %s",
            request.response_model.__name__,
            error,
        )
        model = request.params["model"]
        self._prompt_only_schemas.add((model, request.schema_hash))
        retry_params = {
            key: value for key, value in request.params.items() if key != "output_config"
        }
        retry_config = {
            key: value
            for key, value in request.params.get("output_config", {}).items()
            if key != "format"
        }
        if retry_config:
            retry_params["output_config"] = retry_config
        return replace(request, params=retry_params)

    @staticmethod
    def _decode_prompt_only_json(text: str) -> Any:
        """Decode the first JSON object in a reply that wraps it in prose or a fence."""
        start = text.find("{")
        if start < 0:
            raise json.JSONDecodeError("No JSON object in response", text, 0)
        value, _ = json.JSONDecoder().raw_decode(text, start)
        return value

    def _parse_message(self, response: Any, model: str, request: _ClaudeRequest) -> LLMResponse:
        """Classify the stop reason, account usage, and parse the JSON text."""
        token_usage = self._extract_token_usage(response)
        self._update_token_usage(
            prompt_tokens=token_usage.prompt_tokens,
            completion_tokens=token_usage.completion_tokens,
            total_tokens=token_usage.total_tokens,
        )
        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            raise RecoverableLLMProviderError(
                reason="refusal",
                message="Claude declined the request (refusal fallback chain exhausted)",
                token_usage=token_usage,
            )
        if stop_reason == "max_tokens":
            raise RecoverableLLMProviderError(
                reason="truncation",
                message="Claude response truncated at max_tokens",
                token_usage=token_usage,
            )

        # A prompt-only response may arrive wrapped in a Markdown fence.
        text = unwrap_whole_response_fence(self._response_text(response))
        if not text.strip():
            raise RecoverableLLMProviderError(
                reason="empty_response",
                message="Empty text in Anthropic response",
                token_usage=token_usage,
            )
        try:
            try:
                response_data = json.loads(text)
            except json.JSONDecodeError:
                # Without constrained decoding Claude may add a preamble or a
                # trailing note around the object; strict mode never does.
                if not request.prompt_only:
                    raise
                response_data = self._decode_prompt_only_json(text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Anthropic JSON response: %s", exc)
            raise RecoverableLLMProviderError(
                reason="json_decode",
                message=f"Failed to parse JSON response: {exc}",
                token_usage=token_usage,
            ) from exc

        actual_model = getattr(response, "model", None)
        return LLMResponse(
            content=response_data,
            metadata=ResponseMetadata(
                response_id=getattr(response, "id", None),
                token_usage=token_usage,
                model=actual_model if isinstance(actual_model, str) else model,
                actual_model_present=isinstance(actual_model, str),
                token_usage_is_explicit=getattr(response, "usage", None) is not None,
                finish_reason=stop_reason if isinstance(stop_reason, str) else None,
                structured_output_mode=(
                    None
                    if request.response_model is None
                    else "prompt_schema"
                    if request.prompt_only
                    else "json_schema"
                ),
                # A structured request only drops its schema after a complexity rejection.
                structured_output_fallback_reason=(
                    "schema_too_complex" if request.prompt_only else None
                ),
                response_schema_hash=request.schema_hash,
            ),
        )

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
            request = self._build_request(messages, model, temperature, kwargs)
            try:
                response = self._stream_sync(request.params)
            except Exception as exc:
                retry = self._prompt_only_request(request, exc)
                if retry is None:
                    raise
                request = retry
                response = self._stream_sync(request.params)
            return self._parse_message(response, model, request)

        except LLMProviderError:
            raise
        except Exception as exc:
            logger.error("Anthropic provider error: %s", exc)
            raise LLMProviderError(f"Provider error: {exc}") from exc

    def _stream_sync(self, request_params: dict[str, Any]) -> Any:
        # Streaming keeps large max_tokens requests inside HTTP timeouts.
        with self._sync_client.messages.stream(**request_params) as stream:
            return stream.get_final_message()

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
                metadata=replace(response.metadata, conversation_id=conversation_id),
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
            request = self._build_request(messages, model, temperature, kwargs)
            # The outer bound keeps timeout_seconds a limit on the whole call,
            # prompt-only resend included, since the HTTP timeout only bounds each
            # read of a stream that keeps pinging.
            async with asyncio.timeout(request.params.get("timeout")):
                try:
                    response = await self._stream_async(request.params)
                except Exception as exc:
                    retry = self._prompt_only_request(request, exc)
                    if retry is None:
                        raise
                    request = retry
                    response = await self._stream_async(request.params)
            return self._parse_message(response, model, request)

        except LLMProviderError:
            raise
        except TimeoutError as exc:
            message = f"request exceeded timeout_seconds={request.params.get('timeout')}"
            logger.error("Async Anthropic provider error: %s", message)
            raise LLMProviderError(f"Provider error: {message}") from exc
        except Exception as exc:
            logger.error("Async Anthropic provider error: %s", exc)
            raise LLMProviderError(f"Provider error: {exc}") from exc

    async def _stream_async(self, request_params: dict[str, Any]) -> Any:
        # Streaming keeps large max_tokens requests inside HTTP timeouts.
        async with self._async_client.messages.stream(**request_params) as stream:
            return await stream.get_final_message()

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
                metadata=replace(response.metadata, conversation_id=conversation_id),
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
