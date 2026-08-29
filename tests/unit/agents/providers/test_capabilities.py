"""Model-capability policy for OpenAI optional generation parameters.

The GPT-5.6 reasoning family rejects `temperature` (P3-T4 attempt 2 was a terminal
HTTP 400 for exactly this reason on `gpt-5.6-sol`). Every shipped GPT-5.6 role — the
`sol` planner/profile/lyrics/refinement default, the `terra` judge/asset-enricher, and
the `luna` vision judge — must therefore have `temperature` stripped, while
`reasoning_effort` is preserved. Non-reasoning models (gpt-4.1/gpt-4o) keep temperature.
"""

from __future__ import annotations

import pytest

from twinklr.core.agents.providers.capabilities import normalized_openai_generation_config
from twinklr.core.config.models import AgentConfig

_SOL = AgentConfig.model_fields["model"].default  # shipped planner/profile/lyrics default


@pytest.mark.parametrize("model", [_SOL, "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"])
def test_gpt_56_family_strips_temperature_but_keeps_reasoning(model: str) -> None:
    config = normalized_openai_generation_config(
        model=model, temperature=0.7, reasoning_effort="medium"
    )
    assert "temperature" not in config
    assert config["reasoning_effort"] == "medium"


@pytest.mark.parametrize("model", ["gpt-5", "gpt-5.2", "gpt-5-mini", "gpt-5.1"])
def test_gpt5_line_strips_temperature(model: str) -> None:
    """The whole GPT-5 reasoning line rejects `temperature`, not just the 5.6 family.

    A job-config planner override onto the `gpt-5.2` line hit a terminal HTTP 400
    ("temperature is not supported with this model") during the first live moving-head run,
    because the temperature strip was scoped to the `gpt-5.6` prefix only. The policy now
    covers the `gpt-5` prefix so every sibling reasoning model has temperature stripped
    while `reasoning_effort` is preserved.
    """
    config = normalized_openai_generation_config(
        model=model, temperature=0.7, reasoning_effort="high"
    )
    assert "temperature" not in config
    assert config["reasoning_effort"] == "high"


@pytest.mark.parametrize("model", ["gpt-4.1", "gpt-4o"])
def test_non_reasoning_models_keep_temperature(model: str) -> None:
    config = normalized_openai_generation_config(
        model=model, temperature=0.3, reasoning_effort=None
    )
    assert config["temperature"] == 0.3
    assert "reasoning_effort" not in config


def test_unknown_model_defaults_to_sending_temperature() -> None:
    config = normalized_openai_generation_config(
        model="some-future-model", temperature=0.5, reasoning_effort=None
    )
    assert config["temperature"] == 0.5


def test_none_temperature_is_never_emitted() -> None:
    assert (
        normalized_openai_generation_config(
            model="gpt-4.1", temperature=None, reasoning_effort=None
        )
        == {}
    )
