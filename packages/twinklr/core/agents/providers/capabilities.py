"""Explicit provider model-capability policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenAIModelCapabilities:
    """Request parameters supported by one OpenAI model identity."""

    supports_temperature: bool


_DEFAULT_OPENAI_CAPABILITIES = OpenAIModelCapabilities(supports_temperature=True)
_OPENAI_MODEL_CAPABILITIES = {
    "gpt-4.1": OpenAIModelCapabilities(supports_temperature=True),
    "gpt-4o": OpenAIModelCapabilities(supports_temperature=True),
}

# The GPT-5.6 reasoning family (sol/terra/luna and future siblings) rejects `temperature`
# with a terminal HTTP 400 (see P3-T4 attempt 2). Match the whole family by prefix so every
# shipped role — planner (sol), judge/asset-enricher (terra), vision judge (luna) — has
# temperature stripped, not just the enumerated default.
_TEMPERATURE_UNSUPPORTED_PREFIXES = ("gpt-5.6",)


def _capabilities_for(model: str) -> OpenAIModelCapabilities:
    if model in _OPENAI_MODEL_CAPABILITIES:
        return _OPENAI_MODEL_CAPABILITIES[model]
    if any(model.startswith(prefix) for prefix in _TEMPERATURE_UNSUPPORTED_PREFIXES):
        return OpenAIModelCapabilities(supports_temperature=False)
    return _DEFAULT_OPENAI_CAPABILITIES


def normalized_openai_generation_config(
    *,
    model: str,
    temperature: float | None,
    reasoning_effort: str | None,
) -> dict[str, Any]:
    """Return only model-supported optional generation parameters."""
    capabilities = _capabilities_for(model)
    config: dict[str, Any] = {}
    if capabilities.supports_temperature and temperature is not None:
        config["temperature"] = temperature
    if reasoning_effort is not None:
        config["reasoning_effort"] = reasoning_effort
    return config
