"""Strict structured-output contracts for the agent/provider framework."""

from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from openai import APITimeoutError, BadRequestError
from pydantic import BaseModel, ConfigDict, ValidationError
import pytest

from twinklr.core.agents._paths import AGENTS_BASE_PATH
from twinklr.core.agents.assets.prompt_enricher import build_enricher_spec
from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.audio.lyrics.spec import get_lyrics_spec
from twinklr.core.agents.audio.profile.spec import get_audio_profile_spec
from twinklr.core.agents.prompts import spec_prompt_hash
from twinklr.core.agents.providers.base import LLMResponse, ResponseMetadata, TokenUsage
from twinklr.core.agents.providers.errors import (
    LLMProviderError,
    RecoverableLLMProviderError,
    RecoverableResponseReason,
)
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.agents.schema_utils import (
    STRICT_SCHEMA_ENUM_LIMIT,
    STRICT_SCHEMA_MAX_DEPTH,
    STRICT_SCHEMA_PROPERTY_LIMIT,
    _normalize_supported_schema,
    response_schema_hash,
    strict_json_schema,
    strict_response_format,
    strict_schema_stats,
)
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
from twinklr.core.agents.sequencer.moving_heads.models import ColorIntent
from twinklr.core.agents.sequencer.moving_heads.specs import (
    get_judge_spec as get_moving_head_judge_spec,
)
from twinklr.core.agents.sequencer.moving_heads.specs import (
    get_planner_spec as get_moving_head_planner_spec,
)
from twinklr.core.agents.spec import AgentSpec
from twinklr.core.sequencer.planning.group_plan import (
    CoordinationPlanResponse,
    CorrectionResponse,
    GroupPlacementResponse,
    LanePlanResponse,
    ParameterOverrideEntry,
    PlacementWindowResponse,
    SectionCoordinationResponse,
)
from twinklr.core.sequencer.planning.models import MacroPlan
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    GPBlendMode,
    GPTimingDriver,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
    TargetType,
    TimingHint,
)


class StrictSample(BaseModel):
    """Small strict root used to pin exact request identity."""

    model_config = ConfigDict(extra="forbid")

    result: str
    count: int


def _walk_json(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _extract_json_objects(text: str) -> Iterator[dict[str, Any]]:
    """Extract full or embedded JSON objects from assistant coaching prose."""
    decoder = json.JSONDecoder()
    cursor = 0
    while True:
        start = text.find("{", cursor)
        if start < 0:
            return
        try:
            value, consumed = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            cursor = start + 1
            continue
        cursor = start + consumed
        if isinstance(value, dict):
            yield value


def _registered_specs() -> tuple[AgentSpec, ...]:
    return (
        build_enricher_spec(),
        get_audio_profile_spec(),
        get_lyrics_spec(),
        get_group_planner_spec(),
        get_section_judge_spec(),
        get_holistic_corrector_spec(),
        get_holistic_judge_spec(),
        get_moving_head_planner_spec(),
        get_moving_head_judge_spec(),
        get_macro_planner_spec(),
        get_macro_judge_spec(),
    )


def test_all_registered_response_roots_are_strict_compatible() -> None:
    """Every live AgentSpec root must be accepted by OpenAI strict mode."""
    for model in {spec.response_model for spec in _registered_specs()}:
        schema = model.model_json_schema()
        assert schema.get("type") == "object", model.__name__
        for node in _walk_json(schema):
            assert "allOf" not in node, (model.__name__, node)
            if node.get("type") != "object":
                continue
            properties = node.get("properties", {})
            assert node.get("additionalProperties") is False, (model.__name__, node)
            assert set(node.get("required", ())) == set(properties), (model.__name__, node)


def test_all_registered_strict_roots_have_bare_ref_nodes() -> None:
    """OpenAI rejects a $ref that carries even annotation siblings."""
    for model in {spec.response_model for spec in _registered_specs()}:
        for node in _walk_json(strict_json_schema(model)):
            if "$ref" in node:
                assert set(node) == {"$ref"}, (model.__name__, node)


def test_ref_normalization_fails_loud_on_semantic_siblings() -> None:
    with pytest.raises(ValueError, match=r"\$ref.*minLength"):
        _normalize_supported_schema(
            {"$ref": "#/$defs/NamedValue", "description": "annotation", "minLength": 1}
        )


def test_machine_derived_schema_normalizes_discriminated_union_to_supported_anyof() -> None:
    raw_schema = get_moving_head_planner_spec().response_model.model_json_schema()
    assert any("oneOf" in node for node in _walk_json(raw_schema))
    assert any("discriminator" in node for node in _walk_json(raw_schema))

    schema = strict_json_schema(get_moving_head_planner_spec().response_model)
    assert not any("oneOf" in node for node in _walk_json(schema))
    assert not any("discriminator" in node for node in _walk_json(schema))
    assert any("anyOf" in node for node in _walk_json(schema))

    with pytest.raises(ValidationError):
        ColorIntent.model_validate(
            {
                "selection": {
                    "kind": "PALETTE_ROLE",
                    "palette_role": None,
                    "explicit_color": "RED",
                }
            }
        )


def test_all_registered_strict_roots_stay_within_openai_schema_ceilings() -> None:
    for model in {spec.response_model for spec in _registered_specs()}:
        stats = strict_schema_stats(strict_json_schema(model))
        assert stats.property_count <= STRICT_SCHEMA_PROPERTY_LIMIT, (model.__name__, stats)
        assert stats.max_depth <= STRICT_SCHEMA_MAX_DEPTH, (model.__name__, stats)
        assert stats.enum_value_count <= STRICT_SCHEMA_ENUM_LIMIT, (model.__name__, stats)


def test_shipped_full_response_examples_match_registered_strict_models() -> None:
    """Few-shot response examples must contain every server-required DTO key."""
    jsonl_contracts = {
        AGENTS_BASE_PATH / "sequencer/group_planner/prompts/planner/examples.jsonl": (
            get_group_planner_spec().response_model
        ),
        AGENTS_BASE_PATH / "sequencer/macro_planner/prompts/planner/examples.jsonl": (
            get_macro_planner_spec().response_model
        ),
    }
    audio_examples = sorted(
        (AGENTS_BASE_PATH / "audio/profile/prompts/audio_profile/examples").glob("*.json")
    )
    shipped_example_files = set(AGENTS_BASE_PATH.glob("**/examples.jsonl")) | set(
        AGENTS_BASE_PATH.glob("**/examples/*.json")
    )
    assert shipped_example_files == set(jsonl_contracts) | set(audio_examples)

    validated_jsonl_examples: dict[Path, int] = {}
    validated_override_contracts: dict[Path, int] = {}
    for path, response_model in jsonl_contracts.items():
        validated = 0
        override_contracts = 0
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            message = json.loads(line)
            if message["role"] != "assistant":
                continue

            for embedded in _extract_json_objects(message["content"]):
                for node in _walk_json(embedded):
                    override_fields = {"param_override_keys", "param_overrides"}
                    if override_fields.isdisjoint(node):
                        continue
                    assert override_fields.issubset(node), (
                        f"{path}:{line_number} must pair param_override_keys with param_overrides"
                    )
                    keys = node["param_override_keys"]
                    values = node["param_overrides"]
                    assert isinstance(keys, list) and isinstance(values, list)
                    assert len(keys) == len(values), (
                        f"{path}:{line_number} override key/value lengths differ"
                    )
                    node_keys = list(node)
                    assert node_keys.index("param_override_keys") < node_keys.index(
                        "param_overrides"
                    ), f"{path}:{line_number} override keys must precede values"
                    if {
                        "placement_id",
                        "target",
                        "template_id",
                        "start",
                        "duration",
                        "intensity",
                    }.issubset(node):
                        GroupPlacementResponse.model_validate(node)
                    elif {"start", "end", "template_id", "intensity"}.issubset(node):
                        PlacementWindowResponse.model_validate(node)
                    override_contracts += 1

            try:
                raw_response = json.loads(message["content"])
            except json.JSONDecodeError:
                # Coaching examples are prose, sometimes with partial JSON snippets.
                continue
            if not isinstance(raw_response, dict):
                continue
            parsed = response_model.model_validate(raw_response)
            assert parsed.model_dump(mode="json") == raw_response, (
                f"{path}:{line_number} relies on model defaults and is not an exact "
                "strict-schema example"
            )
            validated += 1
        validated_jsonl_examples[path] = validated
        validated_override_contracts[path] = override_contracts

    assert validated_jsonl_examples == {
        AGENTS_BASE_PATH / "sequencer/group_planner/prompts/planner/examples.jsonl": 3,
        AGENTS_BASE_PATH / "sequencer/macro_planner/prompts/planner/examples.jsonl": 0,
    }
    assert validated_override_contracts == {
        AGENTS_BASE_PATH / "sequencer/group_planner/prompts/planner/examples.jsonl": 20,
        AGENTS_BASE_PATH / "sequencer/macro_planner/prompts/planner/examples.jsonl": 0,
    }

    assert len(audio_examples) == 2
    audio_model = get_audio_profile_spec().response_model
    for path in audio_examples:
        raw_response = json.loads(path.read_text())["expected_output"]
        parsed = audio_model.model_validate(raw_response)
        assert parsed.model_dump(mode="json") == raw_response, (
            f"{path} relies on model defaults and is not an exact strict-schema example"
        )


@pytest.mark.asyncio
async def test_agent_calls_use_machine_derived_strict_json_schema() -> None:
    response = MagicMock(
        output_text='{"result": "ok", "count": 1}',
        id="resp_strict",
        status="completed",
        usage=None,
    )

    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient"),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI") as async_openai,
    ):
        client = MagicMock()
        client.responses.create = AsyncMock(return_value=response)
        async_openai.return_value = client
        provider = OpenAIProvider(api_key="test-key")

        result = await provider.generate_json_async(
            messages=[{"role": "user", "content": "respond"}],
            model="gpt-5.6-sol",
            response_model=StrictSample,
        )

    request = client.responses.create.call_args.kwargs
    assert request["text"]["format"] == strict_response_format(StrictSample)
    for node in _walk_json(request["text"]["format"]["schema"]):
        if "$ref" in node:
            assert set(node) == {"$ref"}
    assert result.metadata.response_schema_hash == response_schema_hash(StrictSample)
    assert result.metadata.structured_output_mode == "json_schema"
    assert result.metadata.response_schema_hash is not None


@pytest.mark.asyncio
async def test_provider_sends_exact_normalized_macro_schema() -> None:
    response = MagicMock(
        output_text="{}",
        id="resp_macro_schema",
        model="gpt-5.6-sol",
        status="completed",
        usage=None,
    )

    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient"),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI") as async_openai,
    ):
        client = MagicMock()
        client.responses.create = AsyncMock(return_value=response)
        async_openai.return_value = client
        provider = OpenAIProvider(api_key="test-key")
        result = await provider.generate_json_async(
            messages=[{"role": "user", "content": "plan"}],
            model="gpt-5.6-sol",
            response_model=MacroPlan,
            provider_max_attempts=1,
            allow_json_object_fallback=False,
        )

    sent = client.responses.create.call_args.kwargs["text"]["format"]
    assert sent == strict_response_format(MacroPlan)
    assert sent["schema"]["$defs"]["ThemeRef"]["properties"]["scope"] == {
        "$ref": "#/$defs/ThemeScope"
    }
    assert result.metadata.response_schema_hash == response_schema_hash(MacroPlan)


@pytest.mark.asyncio
async def test_strict_rejection_falls_back_to_json_object_and_records_it() -> None:
    error_response = MagicMock(status_code=400, headers={})
    rejection = BadRequestError(
        "Unsupported text.format json_schema",
        response=error_response,
        body={"error": {"message": "json_schema is unsupported for this model"}},
    )
    response = MagicMock(
        output_text='{"result": "ok", "count": 2}',
        id="resp_fallback",
        status="completed",
        usage=None,
    )

    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient"),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI") as async_openai,
    ):
        client = MagicMock()
        client.responses.create = AsyncMock(side_effect=[rejection, response])
        async_openai.return_value = client
        provider = OpenAIProvider(api_key="test-key")

        result = await provider.generate_json_async(
            messages=[{"role": "user", "content": "respond"}],
            model="gpt-5.6-sol",
            response_model=StrictSample,
        )

    calls = client.responses.create.call_args_list
    assert calls[0].kwargs["text"]["format"]["type"] == "json_schema"
    assert calls[1].kwargs["text"]["format"] == {"type": "json_object"}
    assert result.metadata.structured_output_mode == "json_object_fallback"
    assert "json_schema" in (result.metadata.structured_output_fallback_reason or "")


@pytest.mark.asyncio
async def test_strict_rejection_does_not_fallback_when_disabled() -> None:
    """A one-request role must not turn a capability rejection into request two."""
    error_response = MagicMock(status_code=400, headers={})
    rejection = BadRequestError(
        "Unsupported text.format json_schema",
        response=error_response,
        body={"error": {"message": "json_schema is unsupported for this model"}},
    )

    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient"),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI") as async_openai,
    ):
        client = MagicMock()
        client.responses.create = AsyncMock(side_effect=rejection)
        async_openai.return_value = client
        provider = OpenAIProvider(api_key="test-key")

        with pytest.raises(LLMProviderError, match=r"Unsupported text\.format"):
            await provider.generate_json_async(
                messages=[{"role": "user", "content": "respond"}],
                model="configured-vision-model",
                response_model=StrictSample,
                provider_max_attempts=1,
                allow_json_object_fallback=False,
            )

    assert client.responses.create.await_count == 1


@pytest.mark.asyncio
async def test_invalid_strict_schema_400_propagates_without_fallback() -> None:
    error_response = MagicMock(status_code=400, headers={})
    rejection = BadRequestError(
        "Invalid schema for response_format StrictSample: oneOf is not permitted",
        response=error_response,
        body={
            "error": {
                "message": (
                    "Invalid schema for response_format StrictSample: oneOf is not permitted"
                )
            }
        },
    )

    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient"),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI") as async_openai,
    ):
        client = MagicMock()
        client.responses.create = AsyncMock(side_effect=rejection)
        async_openai.return_value = client
        provider = OpenAIProvider(api_key="test-key")

        with pytest.raises(LLMProviderError, match="Invalid schema"):
            await provider.generate_json_async(
                messages=[{"role": "user", "content": "respond"}],
                model="gpt-5.6-sol",
                response_model=StrictSample,
            )

    assert client.responses.create.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason", ["json_decode", "refusal", "truncation", "content_filter", "empty_response"]
)
async def test_recoverable_response_failures_are_retried(
    reason: RecoverableResponseReason, tmp_path
) -> None:
    provider = MagicMock()
    provider.provider_type.value = "openai"
    provider.generate_json_async = AsyncMock(
        side_effect=[
            RecoverableLLMProviderError(
                reason=reason,
                message=f"recoverable {reason}",
                token_usage=TokenUsage(
                    prompt_tokens=10,
                    reasoning_tokens=2,
                    completion_tokens=3,
                    total_tokens=15,
                ),
            ),
            LLMResponse(
                content={"result": "fixed", "count": 3},
                metadata=ResponseMetadata(
                    structured_output_mode="json_schema",
                    token_usage=TokenUsage(
                        prompt_tokens=20,
                        reasoning_tokens=1,
                        completion_tokens=4,
                        total_tokens=25,
                    ),
                ),
            ),
        ]
    )
    pack = tmp_path / "test_pack"
    pack.mkdir()
    (pack / "system.j2").write_text("Follow the injected response schema.")
    (pack / "user.j2").write_text("Return the response.")
    runner = AsyncAgentRunner(provider=provider, prompt_base_path=tmp_path)
    spec = AgentSpec(
        name="strict_retry",
        prompt_pack="test_pack",
        response_model=StrictSample,
        max_schema_repair_attempts=1,
    )

    result = await runner.run(spec=spec, variables={})

    assert result.success is True
    assert result.data == StrictSample(result="fixed", count=3)
    assert result.metadata["schema_repair_attempts"] == 1
    assert result.tokens_used == 40
    assert result.prompt_tokens == 30
    assert result.completion_tokens == 7
    assert provider.generate_json_async.await_count == 2
    assert provider.generate_json_async.call_args.kwargs["response_model"] is StrictSample


def test_openai_sdk_retries_are_explicitly_disabled() -> None:
    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient"),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI") as async_openai,
    ):
        OpenAIProvider(api_key="test-key")

    assert async_openai.call_args.kwargs["max_retries"] == 0


@pytest.mark.asyncio
async def test_worst_case_request_count_is_bounded_at_eight(tmp_path) -> None:
    """Two logical attempts cap at 2 x (1 strict rejection + 3 fallback requests)."""

    def capability_rejection() -> BadRequestError:
        return BadRequestError(
            "Unsupported text.format json_schema",
            response=MagicMock(status_code=400, headers={}),
            body={"error": {"message": "json_schema is unsupported for this model"}},
        )

    timeout_request = MagicMock()
    truncated = MagicMock(
        id="resp_truncated",
        status="incomplete",
        incomplete_details=MagicMock(reason="max_output_tokens"),
        output=[],
        output_text="",
        usage=None,
    )
    valid = MagicMock(
        id="resp_valid",
        status="completed",
        incomplete_details=None,
        output=[],
        output_text='{"result": "fixed", "count": 8}',
        usage=None,
    )

    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient"),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI") as async_openai,
        patch("twinklr.core.agents.providers.openai.asyncio.sleep", new_callable=AsyncMock),
    ):
        client = MagicMock()
        client.responses.create = AsyncMock(
            side_effect=[
                capability_rejection(),
                APITimeoutError(timeout_request),
                APITimeoutError(timeout_request),
                truncated,
                capability_rejection(),
                APITimeoutError(timeout_request),
                APITimeoutError(timeout_request),
                valid,
            ]
        )
        async_openai.return_value = client
        provider = OpenAIProvider(api_key="test-key")
        pack = tmp_path / "test_pack"
        pack.mkdir()
        (pack / "system.j2").write_text("Return the strict response.")
        (pack / "user.j2").write_text("Respond now.")
        runner = AsyncAgentRunner(provider=provider, prompt_base_path=tmp_path)
        spec = AgentSpec(
            name="bounded_requests",
            prompt_pack="test_pack",
            response_model=StrictSample,
            max_schema_repair_attempts=1,
        )

        result = await runner.run(spec=spec, variables={})

    assert result.success is True
    assert client.responses.create.await_count == 8
    assert result.metadata["structured_output_mode"] == "json_object_fallback"


def test_response_schema_is_part_of_stage_cache_identity(tmp_path) -> None:
    class AlternateStrictSample(BaseModel):
        model_config = ConfigDict(extra="forbid")

        result: str
        accepted: bool

    pack = tmp_path / "test_pack"
    pack.mkdir()
    (pack / "system.j2").write_text("unchanged")
    first = AgentSpec(name="first", prompt_pack="test_pack", response_model=StrictSample)
    second = AgentSpec(name="second", prompt_pack="test_pack", response_model=AlternateStrictSample)

    assert spec_prompt_hash(tmp_path, first) != spec_prompt_hash(tmp_path, second)


def test_display_strict_dto_adapts_to_runtime_models() -> None:
    override = ParameterOverrideEntry(key="speed", value=2.5)
    placement = GroupPlacementResponse(
        placement_id="p1",
        target=PlanTarget(type=TargetType.GROUP, id="MEGA_TREE"),
        template_id="pulse",
        start=PlanningTimeRef(bar=1, beat=1, timing_hint=TimingHint.ON_BEAT),
        duration=EffectDuration.PHRASE,
        param_override_keys=[override.key],
        param_overrides=[override.value],
        intensity=IntensityLevel.MED,
    )
    section = SectionCoordinationResponse(
        section_id="chorus_1",
        theme=ThemeRef(
            theme_id="christmas.classic",
            scope=ThemeScope.SECTION,
            tags=[],
            palette_id=None,
        ),
        motif_ids=[],
        palette=None,
        lane_plans=[
            LanePlanResponse(
                lane=LaneKind.BASE,
                target_roles=["MEGA_TREE"],
                timing_driver=GPTimingDriver.BEATS,
                blend_mode=GPBlendMode.ADD,
                coordination_plans=[
                    CoordinationPlanResponse(
                        coordination_mode=CoordinationMode.UNIFIED,
                        targets=[PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")],
                        placements=[placement],
                        window=None,
                        config=None,
                    )
                ],
            )
        ],
        deviations=[],
        narrative_assets=[],
        planning_notes=None,
    )

    domain = section.to_domain()
    correction = CorrectionResponse(corrected_sections=[section]).to_domain()

    assert domain.start_ms is None
    assert domain.end_ms is None
    assert domain.lane_plans[0].coordination_plans[0].placements[0].param_overrides == {
        "speed": 2.5
    }
    assert domain.lane_plans[0].coordination_plans[0].placements[0].resolved_asset_ids == []
    assert correction.corrected_sections == [domain]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (
            MagicMock(
                status="incomplete",
                incomplete_details=MagicMock(reason="max_output_tokens"),
                output=[],
                output_text="",
            ),
            "truncation",
        ),
        (
            MagicMock(
                status="incomplete",
                incomplete_details=MagicMock(reason="content_filter"),
                output=[],
                output_text="",
            ),
            "content_filter",
        ),
        (
            MagicMock(
                status="completed",
                incomplete_details=None,
                output=[MagicMock(content=[MagicMock(type="refusal", refusal="no")])],
                output_text="",
            ),
            "refusal",
        ),
        (
            MagicMock(
                status="completed",
                incomplete_details=None,
                output=[],
                output_text='{"truncated":',
            ),
            "json_decode",
        ),
        (
            MagicMock(
                status="completed",
                incomplete_details=None,
                output=[],
                output_text="",
            ),
            "empty_response",
        ),
    ],
)
async def test_openai_classifies_recoverable_response_outcomes(response, reason: str) -> None:
    response.usage = MagicMock(
        input_tokens=11,
        output_tokens=7,
        total_tokens=18,
        output_tokens_details=MagicMock(reasoning_tokens=2),
    )
    with (
        patch("twinklr.core.agents.providers.openai.OpenAIClient"),
        patch("twinklr.core.agents.providers.openai.AsyncOpenAI") as async_openai,
    ):
        client = MagicMock()
        client.responses.create = AsyncMock(return_value=response)
        async_openai.return_value = client
        provider = OpenAIProvider(api_key="test-key")

        with pytest.raises(RecoverableLLMProviderError) as error:
            await provider.generate_json_async(
                messages=[{"role": "user", "content": "respond"}],
                model="gpt-5.6-sol",
                response_model=StrictSample,
            )

    assert error.value.reason == reason
    assert error.value.token_usage == TokenUsage(
        prompt_tokens=11,
        reasoning_tokens=2,
        completion_tokens=5,
        total_tokens=18,
    )
    assert provider.get_token_usage() == error.value.token_usage


@pytest.mark.asyncio
async def test_anthropic_strict_contract_is_gated_loudly() -> None:
    from twinklr.core.agents.providers.anthropic import AnthropicProvider

    with (
        patch("twinklr.core.agents.providers.anthropic.Anthropic"),
        patch("twinklr.core.agents.providers.anthropic.AsyncAnthropic"),
    ):
        provider = AnthropicProvider(api_key="test-key")
        with pytest.raises(LLMProviderError, match=r"does not support.*strict"):
            await provider.generate_json_async(
                messages=[{"role": "user", "content": "respond"}],
                model="claude",
                response_model=StrictSample,
            )
