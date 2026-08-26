"""OpenAI provider implementation."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import threading
from typing import TYPE_CHECKING, Any, cast

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

from twinklr.core.agents.providers.base import (
    ImageBackground,
    ImageGenerationResponse,
    ImageGenerationUsage,
    ImageOutputFormat,
    ImageQuality,
    ImageSize,
    LLMResponse,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
from twinklr.core.agents.providers.capabilities import normalized_openai_generation_config
from twinklr.core.agents.providers.conversation import Conversation
from twinklr.core.agents.providers.errors import (
    LLMProviderError,
    RecoverableLLMProviderError,
    RecoverableResponseReason,
)
from twinklr.core.agents.schema_utils import response_schema_hash, strict_response_format
from twinklr.core.api.llm.openai.client import OpenAIClient

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)

SDK_MAX_RETRIES = 0
PROVIDER_MAX_ATTEMPTS = 3
"""One logical strict call makes at most three HTTP requests.

The SDK retry layer is explicitly disabled, so these manual attempts do not
multiply by the SDK default.  A non-retryable strict-schema rejection may add
one compatibility request before the three-attempt json_object fallback.
"""


def _as_int(value: Any) -> int:
    """Normalize optional SDK usage fields without accepting mock objects as counts."""
    return value if isinstance(value, int) else 0


def _as_optional_int(value: Any) -> int | None:
    """Preserve absent image-usage detail instead of silently pricing it as zero."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


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
        self._async_client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout,
            base_url=base_url,
            max_retries=SDK_MAX_RETRIES,
        )
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

    @property
    def supports_image_generation(self) -> bool:
        """OpenAI exposes image generation through this provider instance."""
        return True

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
        """Generate one image without exposing the provider's SDK client."""
        response = await self._async_client.images.generate(
            model=model,
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
            output_format=output_format,
            background=background,
        )
        if not response.data or not response.data[0].b64_json:
            raise LLMProviderError("OpenAI image generation returned no image data")
        usage = None
        if response.usage is not None:
            input_details = response.usage.input_tokens_details
            output_details = response.usage.output_tokens_details
            usage = ImageGenerationUsage(
                input_tokens=_as_optional_int(response.usage.input_tokens),
                input_text_tokens=_as_optional_int(getattr(input_details, "text_tokens", None)),
                input_image_tokens=_as_optional_int(getattr(input_details, "image_tokens", None)),
                output_tokens=_as_optional_int(response.usage.output_tokens),
                output_text_tokens=_as_optional_int(getattr(output_details, "text_tokens", None)),
                output_image_tokens=_as_optional_int(getattr(output_details, "image_tokens", None)),
                total_tokens=_as_optional_int(response.usage.total_tokens),
            )
        return ImageGenerationResponse(
            image_bytes=base64.b64decode(response.data[0].b64_json),
            model=model,
            usage=usage,
        )

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
            generation_config = normalized_openai_generation_config(
                model=model,
                temperature=temperature,
                reasoning_effort=kwargs.pop("reasoning_effort", None),
            )
            response_data = self._sync_client.generate_json(
                messages=messages,
                model=model,
                temperature=generation_config.pop("temperature", None),
                **generation_config,
                **kwargs,
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
            generation_config = normalized_openai_generation_config(
                model=model,
                temperature=temperature,
                reasoning_effort=kwargs.pop("reasoning_effort", None),
            )
            response_data = self._sync_client.generate_json(
                messages=windowed,
                model=model,
                temperature=generation_config.pop("temperature", None),
                **generation_config,
                **kwargs,
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
        response_model = kwargs.pop("response_model", None)
        allow_json_object_fallback = kwargs.pop("allow_json_object_fallback", True)
        provider_max_attempts = kwargs.pop("provider_max_attempts", PROVIDER_MAX_ATTEMPTS)
        input_image_urls = kwargs.pop("input_image_urls", None)
        if not isinstance(allow_json_object_fallback, bool):
            raise LLMProviderError("allow_json_object_fallback must be a boolean")
        if (
            not isinstance(provider_max_attempts, int)
            or isinstance(provider_max_attempts, bool)
            or not 1 <= provider_max_attempts <= PROVIDER_MAX_ATTEMPTS
        ):
            raise LLMProviderError(
                f"provider_max_attempts must be between 1 and {PROVIDER_MAX_ATTEMPTS}"
            )
        schema_hash: str | None = None
        if response_model is not None:
            if not hasattr(response_model, "model_json_schema"):
                raise LLMProviderError("response_model must be a Pydantic model class")
            schema_hash = response_schema_hash(cast("type[BaseModel]", response_model))

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
            response_format: dict[str, Any]
            if response_model is None:
                response_format = {"type": "json_object"}
            else:
                response_format = strict_response_format(cast("type[BaseModel]", response_model))
            request_params: dict[str, Any] = {
                "model": model,
                "input": self._attach_input_images(messages, input_image_urls),
                "text": {"format": response_format},
            }

            allowed_kwargs = {
                key: value for key, value in kwargs.items() if key in allowed_request_kwargs
            }
            reasoning_effort = allowed_kwargs.pop("reasoning_effort", None)
            normalized_generation = normalized_openai_generation_config(
                model=model,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
            )
            normalized_reasoning_effort = normalized_generation.pop("reasoning_effort", None)
            if normalized_reasoning_effort is not None:
                request_params["reasoning"] = {"effort": normalized_reasoning_effort}
            request_params.update(normalized_generation)
            max_tokens = allowed_kwargs.pop("max_tokens", None)
            if max_tokens is not None and "max_output_tokens" not in allowed_kwargs:
                allowed_kwargs["max_output_tokens"] = max_tokens
            timeout_seconds = allowed_kwargs.pop("timeout_seconds", None)
            if timeout_seconds is not None:
                allowed_kwargs["timeout"] = timeout_seconds
            request_params.update(allowed_kwargs)

            # SDK retries are disabled at client construction.  Therefore the
            # only transient layer is this bounded loop: at most three HTTP
            # requests for one logical call (not the former implicit 3 x 3).
            fallback_reason: str | None = None
            try:
                response = await self._create_response_with_retries(
                    request_params, max_attempts=provider_max_attempts
                )
            except APIStatusError as error:
                fallback_reason = self._strict_rejection_reason(error)
                if (
                    response_model is None
                    or fallback_reason is None
                    or not allow_json_object_fallback
                ):
                    raise
                logger.warning(
                    "OpenAI model %s rejected strict json_schema; falling back to json_object: %s",
                    model,
                    fallback_reason,
                )
                request_params["text"] = {"format": {"type": "json_object"}}
                response = await self._create_response_with_retries(
                    request_params, max_attempts=provider_max_attempts
                )

            # Usage belongs to this completed HTTP response even when refusal,
            # truncation, filtering, empty content, or JSON decoding makes the
            # logical attempt recoverable. Extract and account it before any
            # response classification so the runner can attribute every attempt.
            token_usage = self._extract_response_token_usage(response)
            self._update_token_usage(
                prompt_tokens=token_usage.prompt_tokens,
                reasoning_tokens=token_usage.reasoning_tokens,
                completion_tokens=token_usage.completion_tokens,
                total_tokens=token_usage.total_tokens,
            )

            recoverable = self._recoverable_response_error(response, token_usage)
            if recoverable is not None:
                raise recoverable

            # Extract response content
            content = response.output_text
            if not content:
                raise RecoverableLLMProviderError(
                    reason="empty_response",
                    message="Empty response from OpenAI API",
                    token_usage=token_usage,
                )

            # Parse JSON
            try:
                response_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise RecoverableLLMProviderError(
                    reason="json_decode",
                    message=f"Failed to parse JSON response: {e}",
                    token_usage=token_usage,
                ) from e

            return LLMResponse(
                content=response_data,
                metadata=ResponseMetadata(
                    response_id=getattr(response, "id", None),
                    token_usage=token_usage,
                    model=(
                        response.model
                        if isinstance(getattr(response, "model", None), str) and response.model
                        else model
                    ),
                    actual_model_present=(
                        isinstance(getattr(response, "model", None), str) and bool(response.model)
                    ),
                    token_usage_is_explicit=self._has_explicit_response_token_usage(response),
                    finish_reason=getattr(response, "status", None),
                    structured_output_mode=(
                        "json_object_fallback"
                        if fallback_reason is not None
                        else "json_schema"
                        if response_model is not None
                        else "json_object"
                    ),
                    structured_output_fallback_reason=fallback_reason,
                    response_schema_hash=schema_hash,
                ),
            )

        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"Async OpenAI provider error: {e}")
            raise LLMProviderError(f"Provider error: {e}") from e

    @staticmethod
    def _attach_input_images(
        messages: list[dict[str, str]], input_image_urls: object
    ) -> list[dict[str, Any]]:
        """Attach image inputs to the final user turn without bypassing the provider."""
        copied: list[dict[str, Any]] = [dict(message) for message in messages]
        if input_image_urls is None:
            return copied
        if not isinstance(input_image_urls, list) or not all(
            isinstance(url, str) and url.startswith("data:image/") for url in input_image_urls
        ):
            raise LLMProviderError("input_image_urls must be data:image URLs")
        if not input_image_urls:
            return copied
        user_index = next(
            (index for index in range(len(copied) - 1, -1, -1) if copied[index]["role"] == "user"),
            None,
        )
        if user_index is None:
            raise LLMProviderError("Vision requests require a user message")
        text = copied[user_index].get("content")
        if not isinstance(text, str):
            raise LLMProviderError("Vision user message content must be text before attachment")
        copied[user_index]["content"] = [
            {"type": "input_text", "text": text},
            *(
                {"type": "input_image", "image_url": url, "detail": "low"}
                for url in input_image_urls
            ),
        ]
        return copied

    async def _create_response_with_retries(
        self, request_params: dict[str, Any], *, max_attempts: int
    ) -> Any:
        """Create one response with the single explicit transient retry layer."""
        for attempt in range(max_attempts):
            try:
                return await self._async_client.responses.create(**request_params)
            except Exception as error:
                if not self._should_retry_async_error(error, attempt, max_attempts):
                    raise
                await asyncio.sleep(0.5 * (2**attempt))
        raise LLMProviderError("No response received from OpenAI API")

    @staticmethod
    def _strict_rejection_reason(error: APIStatusError) -> str | None:
        """Return an observable reason only for a strict-format capability rejection."""
        if error.status_code != 400:
            return None
        body = getattr(error, "body", None)
        text = f"{error} {body}".lower()
        invalid_schema_markers = (
            "invalid schema",
            "schema is invalid",
            "schema validation",
            "is not permitted",
            "unsupported schema keyword",
        )
        if any(marker in text for marker in invalid_schema_markers):
            return None
        capability_patterns = (
            "unsupported text.format",
            "unsupported response_format",
            "does not support json_schema",
            "doesn't support json_schema",
            "json_schema is unsupported",
            "json_schema is not supported",
            "structured outputs are not supported",
            "structured output is not supported",
        )
        return str(error) if any(pattern in text for pattern in capability_patterns) else None

    @staticmethod
    def _recoverable_response_error(
        response: Any, token_usage: TokenUsage
    ) -> RecoverableLLMProviderError | None:
        """Classify response-level outcomes that merit another logical call."""
        status = getattr(response, "status", None)
        details = getattr(response, "incomplete_details", None)
        detail_reason = str(getattr(details, "reason", "") or "").lower()
        if status == "incomplete":
            reason: RecoverableResponseReason = (
                "content_filter" if "content_filter" in detail_reason else "truncation"
            )
            return RecoverableLLMProviderError(
                reason=reason,
                message=f"OpenAI response incomplete: {detail_reason or 'unknown reason'}",
                token_usage=token_usage,
            )

        for item in getattr(response, "output", ()) or ():
            for content in getattr(item, "content", ()) or ():
                if getattr(content, "type", None) == "refusal" or getattr(content, "refusal", None):
                    return RecoverableLLMProviderError(
                        reason="refusal",
                        message="OpenAI refused the structured response",
                        token_usage=token_usage,
                    )
        return None

    @staticmethod
    def _extract_response_token_usage(response: Any) -> TokenUsage:
        """Normalize one Responses API result's exact token attribution."""
        usage = getattr(response, "usage", None)
        if not usage:
            return TokenUsage()
        prompt_tokens = _as_int(getattr(usage, "prompt_tokens", None))
        completion_tokens = _as_int(getattr(usage, "completion_tokens", None))
        total_tokens = _as_int(getattr(usage, "total_tokens", None))
        # Responses API variants expose input/output token names.
        if prompt_tokens == 0:
            prompt_tokens = _as_int(getattr(usage, "input_tokens", 0))
        if completion_tokens == 0:
            completion_tokens = _as_int(getattr(usage, "output_tokens", 0))
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        output_details = getattr(usage, "output_tokens_details", None)
        reasoning_tokens = _as_int(getattr(output_details, "reasoning_tokens", 0))
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            reasoning_tokens=reasoning_tokens,
            completion_tokens=max(0, completion_tokens - reasoning_tokens),
            total_tokens=total_tokens,
        )

    @staticmethod
    def _has_explicit_response_token_usage(response: Any) -> bool:
        usage = getattr(response, "usage", None)
        if usage is None:
            return False
        prompt = getattr(usage, "prompt_tokens", None)
        if not isinstance(prompt, int):
            prompt = getattr(usage, "input_tokens", None)
        completion = getattr(usage, "completion_tokens", None)
        if not isinstance(completion, int):
            completion = getattr(usage, "output_tokens", None)
        total = getattr(usage, "total_tokens", None)
        details = getattr(usage, "output_tokens_details", None)
        reasoning = getattr(details, "reasoning_tokens", None) if details is not None else None
        return all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in (prompt, completion, reasoning, total)
        )

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
                    model=response.metadata.model or model,
                    actual_model_present=response.metadata.actual_model_present,
                    token_usage_is_explicit=response.metadata.token_usage_is_explicit,
                    conversation_id=conversation_id,
                    finish_reason=response.metadata.finish_reason,
                    structured_output_mode=response.metadata.structured_output_mode,
                    structured_output_fallback_reason=(
                        response.metadata.structured_output_fallback_reason
                    ),
                    response_schema_hash=response.metadata.response_schema_hash,
                ),
            )

        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"Async OpenAI provider error: {e}")
            raise LLMProviderError(f"Provider error: {e}") from e
