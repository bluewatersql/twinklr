"""Provider factory for LLM provider dispatch."""

from __future__ import annotations

from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.config.models import AppConfig


def create_llm_provider(app_config: AppConfig, session_id: str) -> LLMProvider:
    """Create configured LLM provider for the session."""
    provider_name = app_config.llm_provider.lower().strip()

    if provider_name == "openai":
        return OpenAIProvider(
            api_key=app_config.llm_api_key,
            session_id=session_id,
            base_url=app_config.llm_base_url,
        )

    raise ValueError(f"Unknown LLM provider configured: {app_config.llm_provider}")
