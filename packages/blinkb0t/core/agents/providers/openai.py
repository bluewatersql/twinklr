"""OpenAI provider implementation."""

from __future__ import annotations

import json
import logging
from typing import Any

from blinkb0t.core.agents.providers.base import (
    LLMResponse,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
from blinkb0t.core.agents.providers.conversation import Conversation
from blinkb0t.core.agents.providers.errors import LLMProviderError

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI provider implementation wrapping existing OpenAIClient.

    Responsibilities:
    - Wrap existing OpenAIClient from core/api/llm/openai/client.py
    - Manage conversation state (new functionality)
    - Convert responses to standard format

    Does NOT:
    - Reimplement SDK calls (uses existing client)
    - Reimplement retry logic (existing client handles this)
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 120.0,
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (uses env var if not provided)
            timeout: Request timeout
        """
        # Use existing OpenAIClient from core/api/llm
        from blinkb0t.core.api.llm.openai.client import OpenAIClient

        self._client = OpenAIClient(api_key=api_key, timeout=timeout)
        self._conversations: dict[str, Conversation] = {}

    @property
    def provider_type(self) -> ProviderType:
        """Provider type identifier."""
        return ProviderType.OPENAI

    def generate_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate JSON using existing OpenAI client.

        Note: The existing OpenAIClient already handles:
        - Retry logic with exponential backoff
        - OpenAI SDK calls
        - JSON parsing
        - Error handling

        We just wrap it and convert to standard format.
        """
        try:
            # Call existing OpenAI client (handles retries, SDK calls, parsing)
            response_data = self._client.generate_json(
                messages=messages, model=model, temperature=temperature, **kwargs
            )

            # Get token usage from existing client
            usage = self._client.get_total_token_usage()

            # Convert to standardized format
            return LLMResponse(
                content=response_data,  # Already parsed JSON dict
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
            # Existing client already handled retries
            # Any exception here is unrecoverable
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
        """Generate JSON with conversation support."""
        try:
            # Get or create conversation
            if conversation_id in self._conversations:
                conversation = self._conversations[conversation_id]
                # Add user message
                conversation.messages.append({"role": "user", "content": user_message})
            else:
                # Create new conversation
                messages = []
                if system_prompt:
                    messages.append({"role": "developer", "content": system_prompt})
                messages.append({"role": "user", "content": user_message})

                conversation = Conversation(id=conversation_id, messages=messages)
                self._conversations[conversation_id] = conversation

            # Call OpenAI (handles retries)
            response_data = self._client.generate_json(
                messages=conversation.messages, model=model, temperature=temperature, **kwargs
            )

            # Add assistant response to conversation
            conversation.messages.append(
                {"role": "assistant", "content": json.dumps(response_data)}
            )

            # Get token usage
            usage = self._client.get_total_token_usage()

            # Convert metadata
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
        """Get cumulative token usage."""
        usage = self._client.get_total_token_usage()
        return TokenUsage(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )

    def reset_token_tracking(self) -> None:
        """Reset token tracking."""
        self._client.reset_conversation()
