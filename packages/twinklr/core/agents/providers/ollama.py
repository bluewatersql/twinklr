"""Ollama's OpenAI-compatible local structured-output adapter."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from twinklr.core.agents.providers.base import (
    LLMResponse,
    ProviderCapabilities,
    ProviderType,
)
from twinklr.core.agents.providers.openai import OpenAIProvider

if TYPE_CHECKING:
    import httpx


class OllamaProvider(OpenAIProvider):
    """Route strict schemas through Ollama's documented Chat Completions surface."""

    def __init__(
        self,
        *,
        base_url: str,
        session_id: str | None = None,
        timeout: float = 300.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key="ollama",
            session_id=session_id,
            timeout=timeout,
            base_url=base_url,
            http_client=http_client,
        )

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OLLAMA

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_responses_structured_output=False,
            supports_openai_request_options=True,
            supports_vision_inputs=False,
        )

    @property
    def supports_image_generation(self) -> bool:
        return False

    def _window_messages(
        self,
        messages: list[dict[str, str]],
        window_size: int | None = None,
    ) -> list[dict[str, str]]:
        """Apply the shared bound without producing an assistant-first transcript."""
        windowed = super()._window_messages(messages, window_size)
        prefix = [message for message in windowed if message["role"] in ("system", "developer")]
        conversation = [message for message in windowed if message["role"] in ("user", "assistant")]
        while conversation and conversation[0]["role"] == "assistant":
            conversation.pop(0)
        return prefix + conversation

    def generate_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return asyncio.run(
            self.generate_json_async(
                messages=messages,
                model=model,
                temperature=temperature,
                **kwargs,
            )
        )

    def generate_json_with_conversation(
        self,
        user_message: str,
        conversation_id: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return asyncio.run(
            self.generate_json_with_conversation_async(
                user_message=user_message,
                conversation_id=conversation_id,
                model=model,
                system_prompt=system_prompt,
                temperature=temperature,
                **kwargs,
            )
        )
