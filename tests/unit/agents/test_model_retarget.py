"""Regression tests for configuration-driven GPT-5.6 agent requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from twinklr.core.agents.assets.prompt_enricher import build_enricher_spec
from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.audio.lyrics.spec import get_lyrics_spec
from twinklr.core.agents.audio.profile.spec import get_audio_profile_spec
from twinklr.core.agents.providers.base import LLMResponse, ProviderType, ResponseMetadata
from twinklr.core.agents.sequencer.group_planner.holistic import get_holistic_judge_spec
from twinklr.core.agents.sequencer.group_planner.specs import (
    get_holistic_corrector_spec,
    get_section_judge_spec,
)
from twinklr.core.agents.sequencer.group_planner.specs import (
    get_planner_spec as get_group_planner_spec,
)
from twinklr.core.agents.sequencer.macro_planner.specs import (
    get_judge_spec as get_macro_judge_spec,
)
from twinklr.core.agents.sequencer.macro_planner.specs import (
    get_planner_spec as get_macro_planner_spec,
)
from twinklr.core.agents.sequencer.moving_heads.specs import (
    get_judge_spec as get_mh_judge_spec,
)
from twinklr.core.agents.sequencer.moving_heads.specs import (
    get_planner_spec as get_mh_planner_spec,
)
from twinklr.core.config.models import AgentConfig, AgentOrchestrationConfig


class RecordingProvider:
    """Provider fake that records the payload sent by the runner."""

    provider_type = ProviderType.OPENAI

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_json_async(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        return LLMResponse(content={}, metadata=ResponseMetadata())

    async def generate_json_with_conversation_async(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        return LLMResponse(content={}, metadata=ResponseMetadata())


def _role_specs(config: AgentOrchestrationConfig):
    return (
        get_audio_profile_spec(config=config.profile_agent),
        get_lyrics_spec(config=config.lyrics_agent),
        get_macro_planner_spec(config=config.plan_agent),
        get_mh_planner_spec(config=config.plan_agent),
        get_group_planner_spec(config=config.plan_agent),
        get_holistic_corrector_spec(config=config.refinement_agent),
        get_holistic_judge_spec(config=config.judge_agent),
        build_enricher_spec(config=config.asset_enricher_agent),
        get_macro_judge_spec(config=config.judge_agent),
        get_mh_judge_spec(config=config.judge_agent),
        get_section_judge_spec(config=config.judge_agent),
    )


@pytest.mark.asyncio
async def test_every_agent_role_sends_explicit_reasoning_effort(tmp_path) -> None:
    """The runner must never rely on the provider's GPT-5.6 default effort."""
    provider = RecordingProvider()
    runner = AsyncAgentRunner(provider=provider, prompt_base_path=tmp_path)

    for spec in _role_specs(AgentOrchestrationConfig()):
        await runner._call_oneshot_async(spec, [{"role": "user", "content": "test"}])

    assert len(provider.calls) == 11
    assert all(call["reasoning_effort"] in {"low", "medium", "high"} for call in provider.calls)


@pytest.mark.asyncio
async def test_runner_normalizes_sampling_options_for_openai_model(tmp_path: Path) -> None:
    provider = RecordingProvider()
    runner = AsyncAgentRunner(provider=provider, prompt_base_path=tmp_path)
    sol_spec = get_macro_planner_spec(
        config=AgentConfig(model=AgentConfig().model, temperature=0.7, reasoning_effort="high")
    )
    supported_spec = get_macro_planner_spec(
        config=AgentConfig(model="gpt-4.1", temperature=0.4, reasoning_effort="medium")
    )

    await runner._call_oneshot_async(sol_spec, [{"role": "user", "content": "test"}])
    await runner._call_oneshot_async(supported_spec, [{"role": "user", "content": "test"}])

    assert "temperature" not in provider.calls[0]
    assert provider.calls[0]["reasoning_effort"] == "high"
    assert provider.calls[1]["temperature"] == 0.4
    assert provider.calls[1]["reasoning_effort"] == "medium"


def test_model_id_comes_from_config() -> None:
    """Each role factory uses the model supplied by its role configuration."""
    custom = AgentConfig(
        model="configured-model",
        reasoning_effort="high",
        max_tokens=1234,
        timeout_seconds=17,
    )

    assert get_audio_profile_spec(config=custom).model == "configured-model"
    assert get_lyrics_spec(config=custom).model == "configured-model"
    assert get_macro_planner_spec(config=custom).model == "configured-model"
    assert get_mh_planner_spec(config=custom).model == "configured-model"
    assert get_group_planner_spec(config=custom).model == "configured-model"
    assert get_holistic_corrector_spec(config=custom).model == "configured-model"
    assert get_macro_judge_spec(config=custom).model == "configured-model"
    assert get_mh_judge_spec(config=custom).model == "configured-model"
    assert get_section_judge_spec(config=custom).model == "configured-model"
    assert get_holistic_judge_spec(config=custom).model == "configured-model"
    assert build_enricher_spec(config=custom).model == "configured-model"
    assert get_macro_planner_spec(config=custom).max_tokens == 1234
    assert get_macro_planner_spec(config=custom).timeout_seconds == 17


def test_agent_config_allows_model_policy_to_omit_temperature() -> None:
    config = AgentConfig(temperature=None)
    assert config.temperature is None
    assert get_macro_planner_spec(config=config).temperature is None


@pytest.mark.asyncio
async def test_configured_model_reaches_fake_provider(tmp_path) -> None:
    """A configured role model is the one sent on every provider request."""
    provider = RecordingProvider()
    runner = AsyncAgentRunner(provider=provider, prompt_base_path=tmp_path)
    limits = {"max_tokens": 1234, "timeout_seconds": 17}
    config = AgentOrchestrationConfig(
        plan_agent=AgentConfig(model="configured-model", reasoning_effort="high", **limits),
        judge_agent=AgentConfig(model="configured-model", reasoning_effort="low", **limits),
        refinement_agent=AgentConfig(model="configured-model", reasoning_effort="medium", **limits),
        profile_agent=AgentConfig(model="configured-model", reasoning_effort="medium", **limits),
        lyrics_agent=AgentConfig(model="configured-model", reasoning_effort="medium", **limits),
        asset_enricher_agent=AgentConfig(
            model="configured-model",
            reasoning_effort="low",
            **limits,
        ),
    )

    for spec in _role_specs(config):
        await runner._call_oneshot_async(spec, [{"role": "user", "content": "test"}])

    assert [call["model"] for call in provider.calls] == ["configured-model"] * 11
    assert all(call["max_tokens"] == 1234 for call in provider.calls)
    assert all(call["timeout_seconds"] == 17 for call in provider.calls)


def test_role_defaults_choose_current_models_and_deliberate_effort() -> None:
    """Planner roles optimize quality, while judges use the lower-cost evaluator."""
    config = AgentOrchestrationConfig()

    assert config.plan_agent.model == "gpt-5.6-sol"
    assert config.profile_agent.model == "gpt-5.6-sol"
    assert config.lyrics_agent.model == "gpt-5.6-sol"
    assert config.judge_agent.model == "gpt-5.6-terra"
    assert config.plan_agent.reasoning_effort == "high"
    assert config.judge_agent.reasoning_effort == "low"


def test_recipe_generation_docs_match_central_default() -> None:
    """Both published guides report the configured recipe-generation tier and effort."""
    root = Path(__file__).parents[3]
    recipe_config = AgentOrchestrationConfig().recipe_generation_agent
    expected = f"`{recipe_config.model}`, {recipe_config.reasoning_effort} reasoning"

    assert expected in (root / "docs/developer-guide.md").read_text()
    assert expected in (root / "docs/user-guide.md").read_text()


def test_no_hardcoded_legacy_model_literals() -> None:
    """A future retarget grep finds no live legacy model selections."""
    root = Path(__file__).parents[3]
    legacy_ids = ("gpt-5.2", "gpt-5-mini", "gpt-4o-mini", "gpt-image-1.5")
    for directory in (root / "packages", root / "scripts"):
        for path in directory.rglob("*.py"):
            assert not any(model_id in path.read_text() for model_id in legacy_ids), path


def test_current_model_literals_are_centralized() -> None:
    """Current model IDs have a single Python source of truth in config models."""
    root = Path(__file__).parents[3]
    current_ids = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-image-2")
    allowed = root / "packages/twinklr/core/config/models.py"
    duplicates: list[Path] = []
    for directory in (root / "packages", root / "scripts"):
        for path in directory.rglob("*.py"):
            if path != allowed and any(model_id in path.read_text() for model_id in current_ids):
                duplicates.append(path)
    assert duplicates == []


def test_normalization_has_no_inert_agent_config_or_stale_retarget_note() -> None:
    """Normalization keeps configuration at its actual caller and documents current behavior."""
    root = Path(__file__).parents[3]
    feature_config = root / "packages/twinklr/core/feature_engineering/config.py"
    llm_review = root / "packages/twinklr/core/feature_engineering/normalization/llm_review.py"

    assert "normalization_review_agent" not in feature_config.read_text()
    review_source = llm_review.read_text()
    assert "not yet retargeted" not in review_source
    assert "later model-retarget task" not in review_source
