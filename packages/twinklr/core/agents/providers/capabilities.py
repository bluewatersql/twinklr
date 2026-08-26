"""Explicit provider model-capability policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from twinklr.core.config.models import AgentConfig


@dataclass(frozen=True)
class OpenAIModelCapabilities:
    """Request parameters supported by one OpenAI model identity."""

    supports_temperature: bool


_DEFAULT_OPENAI_CAPABILITIES = OpenAIModelCapabilities(supports_temperature=True)
_OPENAI_MODEL_CAPABILITIES = {
    AgentConfig.model_fields["model"].default: OpenAIModelCapabilities(supports_temperature=False),
    "gpt-4.1": OpenAIModelCapabilities(supports_temperature=True),
    "gpt-4o": OpenAIModelCapabilities(supports_temperature=True),
}


def normalized_openai_generation_config(
    *,
    model: str,
    temperature: float | None,
    reasoning_effort: str | None,
) -> dict[str, Any]:
    """Return only model-supported optional generation parameters."""
    capabilities = _OPENAI_MODEL_CAPABILITIES.get(model, _DEFAULT_OPENAI_CAPABILITIES)
    config: dict[str, Any] = {}
    if capabilities.supports_temperature and temperature is not None:
        config["temperature"] = temperature
    if reasoning_effort is not None:
        config["reasoning_effort"] = reasoning_effort
    return config
