"""Behavioral tests for the opt-in Ollama-compatible provider."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict
import pytest

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.providers.base import ProviderType
from twinklr.core.agents.providers.errors import LLMProviderError, RecoverableLLMProviderError
from twinklr.core.agents.providers.factory import create_llm_provider
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.agents.spec import AgentSpec
from twinklr.core.config.models import AppConfig


class TinyPlan(BaseModel):
    """Small schema used to inspect the provider boundary."""

    model_config = ConfigDict(extra="forbid")

    title: str


@pytest.mark.asyncio
async def test_ollama_structured_output_uses_chat_completions_json_schema() -> None:
    requests: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-local",
                "object": "chat.completion",
                "created": 1,
                "model": "local-test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"title":"Glow"}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 3,
                    "total_tokens": 11,
                },
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        provider = create_llm_provider(
            AppConfig(
                llm_provider="ollama",
                llm_base_url="http://127.0.0.1:11434/v1",
                llm_api_key="",
            ),
            session_id="test-local",
            http_client=http_client,
        )
        response = await provider.generate_json_async(
            messages=[{"role": "user", "content": "Make a tiny plan."}],
            model="local-test-model",
            response_model=TinyPlan,
            provider_max_attempts=1,
            allow_json_object_fallback=False,
        )

    assert provider.provider_type == ProviderType.OLLAMA
    assert response.content == {"title": "Glow"}
    assert response.metadata.structured_output_mode == "json_schema"
    assert response.metadata.response_schema_hash is not None
    assert response.metadata.token_usage.total_tokens == 11
    assert response.metadata.finish_reason == "stop"
    assert response.metadata.model == "local-test-model"
    assert len(requests) == 1
    assert requests[0].url == "http://127.0.0.1:11434/v1/chat/completions"
    body = json.loads(requests[0].content)
    assert body["messages"] == [{"role": "user", "content": "Make a tiny plan."}]
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "TinyPlan",
            "schema": {
                "additionalProperties": False,
                "description": "Small schema used to inspect the provider boundary.",
                "properties": {"title": {"title": "Title", "type": "string"}},
                "required": ["title"],
                "title": "TinyPlan",
                "type": "object",
            },
            "strict": True,
        },
    }


def test_ollama_config_accepts_blank_user_api_key_and_factory_supplies_dummy() -> None:
    config = AppConfig(
        llm_provider="ollama",
        llm_base_url="http://localhost:11434/v1",
        llm_api_key="",
    )

    provider = create_llm_provider(config, session_id="local")

    assert provider.provider_type == ProviderType.OLLAMA
    assert provider._async_client.api_key == "ollama"


def test_openai_factory_rejects_blank_api_key() -> None:
    config = AppConfig(llm_provider="openai", llm_api_key="")

    with pytest.raises(ValueError, match="API key"):
        create_llm_provider(config, session_id="cloud")


def test_ollama_config_rejects_non_loopback_endpoint() -> None:
    with pytest.raises(ValueError, match="loopback"):
        AppConfig(
            llm_provider="ollama",
            llm_base_url="http://example.com:11434/v1",
            llm_api_key="",
        )


@pytest.mark.asyncio
async def test_openai_structured_output_remains_on_responses_api() -> None:
    requests: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "resp-cloud",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": "gpt-4.1",
                "output": [
                    {
                        "id": "msg-cloud",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"title":"Cloud"}',
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 8,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens": 3,
                    "output_tokens_details": {"reasoning_tokens": 0},
                    "total_tokens": 11,
                },
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        provider = OpenAIProvider(
            api_key="test-key",
            base_url="https://api.openai.test/v1",
            http_client=http_client,
        )
        response = await provider.generate_json_async(
            messages=[{"role": "user", "content": "Make a tiny plan."}],
            model="gpt-4.1",
            response_model=TinyPlan,
            provider_max_attempts=1,
            allow_json_object_fallback=False,
        )

    assert response.content == {"title": "Cloud"}
    assert len(requests) == 1
    assert requests[0].url == "https://api.openai.test/v1/responses"
    body = json.loads(requests[0].content)
    assert body["text"]["format"]["name"] == "TinyPlan"
    assert "response_format" not in body


def test_ollama_window_never_starts_with_assistant_after_system_messages() -> None:
    provider = create_llm_provider(
        AppConfig(
            llm_provider="ollama",
            llm_base_url="http://127.0.0.1:11434/v1",
            llm_api_key="",
        ),
        session_id="local",
    )

    window = provider._window_messages(
        [
            {"role": "developer", "content": "system"},
            {"role": "assistant", "content": "orphan"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "second"},
        ],
        window_size=1,
    )

    assert window == [
        {"role": "developer", "content": "system"},
        {"role": "user", "content": "second"},
    ]


@pytest.mark.asyncio
async def test_ollama_truncation_is_recoverable_without_hidden_transport_retry() -> None:
    requests: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-truncated",
                "object": "chat.completion",
                "created": 1,
                "model": "local-test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"title":'},
                        "finish_reason": "length",
                    }
                ],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 3,
                    "total_tokens": 11,
                },
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        provider = create_llm_provider(
            AppConfig(
                llm_provider="ollama",
                llm_base_url="http://127.0.0.1:11434/v1",
                llm_api_key="",
            ),
            session_id="test-local",
            http_client=http_client,
        )
        with pytest.raises(RecoverableLLMProviderError) as error:
            await provider.generate_json_async(
                messages=[{"role": "user", "content": "Make a tiny plan."}],
                model="local-test-model",
                response_model=TinyPlan,
                provider_max_attempts=1,
                allow_json_object_fallback=False,
            )

    assert error.value.reason == "truncation"
    assert error.value.token_usage.total_tokens == 11
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_ollama_uses_runner_schema_repair_without_transport_fallback(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        content = "{}" if len(requests) == 1 else '{"title":"Repaired"}'
        return httpx.Response(
            200,
            json={
                "id": f"chatcmpl-{len(requests)}",
                "object": "chat.completion",
                "created": len(requests),
                "model": "local-test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 3,
                    "total_tokens": 11,
                },
            },
            request=request,
        )

    prompt_pack = tmp_path / "local"
    prompt_pack.mkdir()
    (prompt_pack / "system.j2").write_text("Return the requested schema.", encoding="utf-8")
    (prompt_pack / "user.j2").write_text("Make a plan.", encoding="utf-8")
    spec = AgentSpec(
        name="local_schema_repair",
        prompt_pack="local",
        response_model=TinyPlan,
        model="local-test-model",
        max_schema_repair_attempts=1,
        provider_max_attempts=1,
        allow_json_object_fallback=False,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        provider = create_llm_provider(
            AppConfig(
                llm_provider="ollama",
                llm_base_url="http://127.0.0.1:11434/v1",
                llm_api_key="",
            ),
            session_id="test-local",
            http_client=http_client,
        )
        result = await AsyncAgentRunner(provider, tmp_path).run(spec, {})

    assert result.success is True
    assert result.data == TinyPlan(title="Repaired")
    assert result.metadata["schema_repair_attempts"] == 1
    assert len(requests) == 2
    assert all(request.url.path == "/v1/chat/completions" for request in requests)
    second_messages = json.loads(requests[1].content)["messages"]
    assert "Schema validation failed" in second_messages[-1]["content"]


@pytest.mark.asyncio
async def test_ollama_rejects_vision_before_any_request() -> None:
    requests: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise AssertionError("vision must fail before transport")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        provider = create_llm_provider(
            AppConfig(
                llm_provider="ollama",
                llm_base_url="http://127.0.0.1:11434/v1",
                llm_api_key="",
            ),
            session_id="test-local",
            http_client=http_client,
        )
        with pytest.raises(LLMProviderError, match="does not support vision"):
            await provider.generate_json_async(
                messages=[{"role": "user", "content": "Inspect."}],
                model="local-test-model",
                response_model=TinyPlan,
                input_image_urls=["data:image/png;base64,AAAA"],
                provider_max_attempts=1,
            )

    assert requests == []


@pytest.mark.asyncio
async def test_ollama_refuses_redirect_without_forwarding_prompt_or_schema() -> None:
    requests: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            307,
            headers={"location": "https://attacker.example/v1/chat/completions"},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
        follow_redirects=True,
    ) as redirecting_client:
        provider = create_llm_provider(
            AppConfig(
                llm_provider="ollama",
                llm_base_url="http://127.0.0.1:11434/v1",
                llm_api_key="",
            ),
            session_id="test-local",
            http_client=redirecting_client,
        )
        with pytest.raises(LLMProviderError):
            await provider.generate_json_async(
                messages=[{"role": "user", "content": "SECRET-PROMPT"}],
                model="local-test-model",
                response_model=TinyPlan,
                provider_max_attempts=1,
                allow_json_object_fallback=False,
            )

    assert len(requests) == 1
    assert requests[0].url == "http://127.0.0.1:11434/v1/chat/completions"
    assert b"SECRET-PROMPT" in requests[0].content
    remote_requests = [request for request in requests if request.url.host == "attacker.example"]
    assert remote_requests == []
