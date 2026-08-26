"""Base types and protocol for LLM providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal, Protocol

ImageSize = Literal["auto", "1024x1024", "1024x1536", "1536x1024"]
ImageQuality = Literal["low", "medium", "high"]
ImageBackground = Literal["transparent", "opaque", "auto"]
ImageOutputFormat = Literal["png", "jpeg", "webp"]


class ProviderType(StrEnum):
    """Supported provider types."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass(frozen=True)
class TokenUsage:
    """Standardized token usage."""

    prompt_tokens: int = 0
    reasoning_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ImageGenerationUsage:
    """Provider-reported image token usage, when the API supplies it."""

    input_tokens: int | None = None
    input_text_tokens: int | None = None
    input_image_tokens: int | None = None
    output_tokens: int | None = None
    output_text_tokens: int | None = None
    output_image_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ImageGenerationResponse:
    """Provider-neutral bytes and metadata for one generated image."""

    image_bytes: bytes
    model: str
    usage: ImageGenerationUsage | None = None


@dataclass(frozen=True)
class ResponseMetadata:
    """Standardized response metadata."""

    response_id: str | None = None
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    model: str | None = None
    actual_model_present: bool = False
    token_usage_is_explicit: bool = False
    finish_reason: str | None = None
    conversation_id: str | None = None
    structured_output_mode: str | None = None
    structured_output_fallback_reason: str | None = None
    response_schema_hash: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Standardized LLM response."""

    content: Any  # Parsed JSON dict
    metadata: ResponseMetadata


class LLMProvider(Protocol):
    """Generic protocol for LLM providers.

    Implementations must handle:
    - Provider-level retries (network errors, rate limits, 5xx)
    - Conversation state management
    - Token usage tracking
    - JSON response parsing

    Phase 0 Note: This protocol now includes async methods.
    Sync methods are provided for backward compatibility and
    should be thin wrappers around async implementations.
    """

    @property
    def provider_type(self) -> ProviderType:
        """Provider type identifier."""
        ...

    def generate_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate JSON response from messages.

        Provider handles retries for:
        - Network errors (ConnectionError, TimeoutError)
        - Rate limits (429)
        - Server errors (500, 502, 503, 529)

        Strict-output response failures (refusal, truncation, content filtering,
        malformed fallback JSON) are surfaced as recoverable errors for the
        agent runner's single bounded logical retry. Transport retries remain
        provider-owned.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with parsed JSON content and metadata

        Raises:
            LLMProviderError: On unrecoverable errors after retries
        """
        ...

    def generate_json_with_conversation(
        self,
        user_message: str,
        conversation_id: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate JSON response in conversation context.

        Provider manages conversation state internally.

        Args:
            user_message: User's message
            conversation_id: Conversation ID (created if doesn't exist)
            model: Model identifier
            system_prompt: System prompt (only used for new conversations)
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with parsed JSON content and metadata
            (metadata.conversation_id will contain the conversation ID)

        Raises:
            LLMProviderError: On unrecoverable errors
        """
        ...

    def add_message_to_conversation(self, conversation_id: str, role: str, content: str) -> None:
        """Add message to existing conversation.

        Args:
            conversation_id: Conversation identifier
            role: Message role ('user', 'assistant', 'system')
            content: Message content

        Raises:
            ValueError: If conversation not found
        """
        ...

    def get_conversation_history(self, conversation_id: str) -> list[dict[str, str]]:
        """Get conversation history.

        Args:
            conversation_id: Conversation identifier

        Returns:
            List of message dicts

        Raises:
            ValueError: If conversation not found
        """
        ...

    def get_token_usage(self) -> TokenUsage:
        """Get cumulative token usage across all calls.

        Returns:
            TokenUsage with total tokens used
        """
        ...

    def reset_token_tracking(self) -> None:
        """Reset token usage tracking."""
        ...

    # =========================================================================
    # Async Methods (Phase 0)
    # =========================================================================

    async def generate_json_async(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate JSON response from messages asynchronously.

        This is the primary implementation method. The sync version
        `generate_json` should be a thin wrapper using asyncio.run().

        Provider handles retries for:
        - Network errors (ConnectionError, TimeoutError)
        - Rate limits (429)
        - Server errors (500, 502, 503, 529)

        Strict-output response failures are surfaced to the agent runner for
        its single bounded logical retry; transport retries remain here.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with parsed JSON content and metadata

        Raises:
            LLMProviderError: On unrecoverable errors after retries
        """
        ...

    async def generate_json_with_conversation_async(
        self,
        user_message: str,
        conversation_id: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate JSON response in conversation context asynchronously.

        This is the primary implementation method. The sync version
        should be a thin wrapper using asyncio.run().

        Provider manages conversation state internally.

        Args:
            user_message: User's message
            conversation_id: Conversation ID (created if doesn't exist)
            model: Model identifier
            system_prompt: System prompt (only used for new conversations)
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with parsed JSON content and metadata
            (metadata.conversation_id will contain the conversation ID)

        Raises:
            LLMProviderError: On unrecoverable errors
        """
        ...

    @property
    def supports_image_generation(self) -> bool:
        """Whether this provider implements the image-generation capability."""
        ...

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
        """Generate one image through the provider's public capability."""
        ...
