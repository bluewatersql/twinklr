"""Provider factory for LLM provider dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.config.models import AppConfig

if TYPE_CHECKING:
    import httpx


def validate_llm_provider_config(app_config: AppConfig) -> None:
    """Fail before execution when a remote provider has no configured credential."""
    if app_config.llm_provider in {"openai", "anthropic"}:
        api_key = app_config.llm_api_key.get_secret_value()
        if not api_key:
            raise ValueError(f"{app_config.llm_provider.title()} provider requires an API key")


def create_llm_provider(
    app_config: AppConfig,
    session_id: str,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> LLMProvider:
    """Create a configured LLM provider for the session.

    Args:
        app_config: Application configuration containing provider name and
            API key.
        session_id: Session identifier forwarded to the provider.

    Returns:
        An object that satisfies the ``LLMProvider`` protocol.

    Raises:
        ValueError: If the configured provider name is not recognised.
    """
    provider_name = app_config.llm_provider.lower().strip()
    api_key = app_config.llm_api_key.get_secret_value()
    validate_llm_provider_config(app_config)

    if provider_name == "openai":
        return OpenAIProvider(
            api_key=api_key,
            session_id=session_id,
            base_url=app_config.llm_base_url,
            http_client=http_client,
        )

    if provider_name == "anthropic":
        from twinklr.core.agents.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            api_key=api_key,
            session_id=session_id,
        )

    if provider_name == "ollama":
        from twinklr.core.agents.providers.ollama import OllamaProvider

        return OllamaProvider(
            base_url=app_config.llm_base_url,
            session_id=session_id,
            http_client=http_client,
        )

    raise ValueError(f"Unknown LLM provider configured: {app_config.llm_provider}")
