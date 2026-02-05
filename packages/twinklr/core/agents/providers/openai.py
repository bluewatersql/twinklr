"""OpenAI provider implementation."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from twinklr.core.agents.providers.base import (
    LLMResponse,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
from twinklr.core.agents.providers.conversation import Conversation
from twinklr.core.agents.providers.errors import LLMProviderError
from twinklr.core.api.llm.openai.client import OpenAIClient

if TYPE_CHECKING:
    from twinklr.core.caching import Cache

logger = logging.getLogger(__name__)

# LLM cache TTL (1 hour) - short-lived, transient cache for deduplication
LLM_CACHE_TTL_SECONDS = 3600.0


class CachedLLMResponse(BaseModel):
    """Cacheable LLM response wrapper.

    Wraps response data and metadata for caching LLM calls.
    Separate from LLMResponse to avoid coupling provider interface to cache.
    """

    content: dict[str, Any]
    response_id: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str
    conversation_id: str | None = None


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

    def __init__(
        self,
        *,
        api_key: str | None = None,
        session_id: str | None = None,
        timeout: float = 300.0,
        llm_cache: Cache | None = None,
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (uses env var if not provided)
            timeout: Request timeout
            llm_cache: Optional short-lived cache for LLM call deduplication
        """
        # Async client for async-first implementation
        self._async_client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._sync_client = OpenAIClient(api_key=api_key, timeout=timeout)

        self.session_id = session_id or "default"

        # LLM call cache (transparent, short-lived)
        self.llm_cache = llm_cache

        # Thread-safe token tracking
        self._token_lock = threading.Lock()
        self._total_tokens = TokenUsage()

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

            usage = self._sync_client.get_total_token_usage()

            # Update thread-safe token tracking
            self._update_token_usage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )

            return LLMResponse(
                content=response_data,
                metadata=ResponseMetadata(
                    token_usage=TokenUsage(
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        total_tokens=usage.total_tokens,
                    ),
                    model=model,
                ),
            )

        except Exception as e:
            logger.error(f"OpenAI provider error: {e}")
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

            response_data = self._sync_client.generate_json(
                messages=conversation.messages, model=model, temperature=temperature, **kwargs
            )

            conversation.messages.append(
                {"role": "assistant", "content": json.dumps(response_data)}
            )

            usage = self._sync_client.get_total_token_usage()

            self._update_token_usage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )

            response_metadata = ResponseMetadata(
                token_usage=TokenUsage(
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                ),
                model=model,
                conversation_id=conversation_id,
            )

            return LLMResponse(content=response_data, metadata=response_metadata)

        except Exception as e:
            logger.error(f"OpenAI provider error: {e}")
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
        self._sync_client.reset_conversation()

    def _update_token_usage(
        self, prompt_tokens: int, completion_tokens: int, total_tokens: int
    ) -> None:
        """Thread-safe token usage update."""
        with self._token_lock:
            self._total_tokens = TokenUsage(
                prompt_tokens=self._total_tokens.prompt_tokens + prompt_tokens,
                completion_tokens=self._total_tokens.completion_tokens + completion_tokens,
                total_tokens=self._total_tokens.total_tokens + total_tokens,
            )

    def _build_llm_cache_key(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None,
    ) -> str:
        """Build cache key from LLM call parameters.

        Cache key includes all parameters that affect output:
        - Full message history (for multi-turn conversations)
        - Model identifier
        - Temperature setting
        - Response format (always JSON for this provider)

        Returns:
            SHA256 hash of canonical call parameters
        """
        cache_data = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "format": "json",
        }

        # Canonical JSON encoding for stable hashing
        canonical = json.dumps(
            cache_data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

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
        """Generate JSON response asynchronously with transparent caching.

        This is the primary async implementation using AsyncOpenAI.
        Automatically caches identical calls to avoid redundant LLM requests.

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
        # Check LLM cache (transparent, short-lived)
        if self.llm_cache:
            try:
                cache_key_hash = self._build_llm_cache_key(messages, model, temperature)
                from twinklr.core.caching import CacheKey

                cache_key = CacheKey(
                    domain="llm",
                    session_id=self.session_id,
                    step_id="llm.openai.json",
                    step_version="1",
                    input_fingerprint=cache_key_hash,
                )

                cached_response = await self.llm_cache.load(
                    cache_key, CachedLLMResponse, ttl_seconds=LLM_CACHE_TTL_SECONDS
                )
                if cached_response:
                    logger.debug(f"LLM cache hit (model={model}, temp={temperature})")
                    # Update token tracking from cached response
                    self._update_token_usage(
                        prompt_tokens=cached_response.prompt_tokens,
                        completion_tokens=cached_response.completion_tokens,
                        total_tokens=cached_response.total_tokens,
                    )
                    return LLMResponse(
                        content=cached_response.content,
                        metadata=ResponseMetadata(
                            response_id=cached_response.response_id,
                            token_usage=TokenUsage(
                                prompt_tokens=cached_response.prompt_tokens,
                                completion_tokens=cached_response.completion_tokens,
                                total_tokens=cached_response.total_tokens,
                            ),
                            model=cached_response.model,
                            conversation_id=cached_response.conversation_id,
                        ),
                    )
            except Exception as e:
                logger.warning(f"LLM cache check failed: {e}")

        try:
            # Build request parameters
            request_params: dict[str, Any] = {
                "model": model,
                "input": messages,
                "text": {"format": {"type": "json_object"}},
            }

            # Add temperature if provided and model supports it
            is_mini_model = "mini" in model.lower()
            if temperature is not None and not is_mini_model:
                request_params["temperature"] = temperature

            # Make async API call
            response = await self._async_client.responses.create(**request_params)

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
                token_usage = TokenUsage(
                    prompt_tokens=getattr(response.usage, "prompt_tokens", 0),
                    completion_tokens=getattr(response.usage, "completion_tokens", 0),
                    total_tokens=getattr(response.usage, "total_tokens", 0),
                )
                self._update_token_usage(
                    prompt_tokens=token_usage.prompt_tokens,
                    completion_tokens=token_usage.completion_tokens,
                    total_tokens=token_usage.total_tokens,
                )

            llm_response = LLMResponse(
                content=response_data,
                metadata=ResponseMetadata(
                    response_id=getattr(response, "id", None),
                    token_usage=token_usage,
                    model=model,
                ),
            )

            # Store in LLM cache
            if self.llm_cache:
                try:
                    cached_resp = CachedLLMResponse(
                        content=response_data,
                        response_id=llm_response.metadata.response_id,
                        prompt_tokens=token_usage.prompt_tokens,
                        completion_tokens=token_usage.completion_tokens,
                        total_tokens=token_usage.total_tokens,
                        model=model,
                    )
                    await self.llm_cache.store(
                        cache_key, cached_resp, ttl_seconds=LLM_CACHE_TTL_SECONDS
                    )
                    logger.debug(
                        f"LLM response cached with TTL={LLM_CACHE_TTL_SECONDS}s "
                        f"(model={model}, temp={temperature})"
                    )
                except Exception as e:
                    logger.warning(f"LLM cache store failed: {e}")

            return llm_response

        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"Async OpenAI provider error: {e}")
            raise LLMProviderError(f"Provider error: {e}") from e

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

            # Use async method
            response = await self.generate_json_async(
                messages=conversation.messages,
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
