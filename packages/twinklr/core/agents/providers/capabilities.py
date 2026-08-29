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

# The GPT-5 reasoning line reports `temperature` as unsupported (a terminal HTTP 400):
# first seen on the 5.6 family (sol/terra/luna; P3-T4 attempt 2), then on a job-config
# planner override onto a 5.2-line sibling during the first live moving-head run.
# `temperature` and a reasoning effort are mutually exclusive for these models, so match
# the whole line by the "gpt-5" prefix and every shipped reasoning role — planner, profile,
# lyrics, refinement, judge, asset-enricher, vision judge — plus any operator override onto
# a sibling reasoning model has temperature stripped while `reasoning_effort` is preserved.
# Non-reasoning models (gpt-4.1/gpt-4o) keep temperature via the explicit map above.
_TEMPERATURE_UNSUPPORTED_PREFIXES = ("gpt-5",)


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
    """Return only model-supported optional generation parameters.

    The GPT-5 reasoning line reports `temperature` as unsupported (a terminal HTTP 400),
    so the per-model policy strips it for that whole prefix while preserving
    `reasoning_effort`. Non-reasoning models keep `temperature`.
    """
    capabilities = _capabilities_for(model)
    config: dict[str, Any] = {}
    if capabilities.supports_temperature and temperature is not None:
        config["temperature"] = temperature
    if reasoning_effort is not None:
        config["reasoning_effort"] = reasoning_effort
    return config
