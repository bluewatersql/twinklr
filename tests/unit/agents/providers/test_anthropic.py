"""Tests for Anthropic Claude provider — MKT-02."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.providers.base import LLMResponse, ProviderType, TokenUsage
from twinklr.core.agents.providers.conversation import generate_conversation_id
from twinklr.core.agents.providers.errors import LLMProviderError, RecoverableLLMProviderError
from twinklr.core.agents.spec import AgentSpec
from twinklr.core.sequencer.planning.models import MacroPlan

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_sync_message(
    text: str = '{"result": "ok"}', input_tokens: int = 10, output_tokens: int = 5
) -> MagicMock:
    """Build a mock final Anthropic message as returned by a stream."""
    block = MagicMock()
    block.type = "text"
    block.text = text

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_creation_input_tokens = 0
    usage.cache_read_input_tokens = 0

    msg = MagicMock()
    msg.content = [block]
    msg.usage = usage
    msg.id = "msg_sync_001"
    msg.model = "claude-opus-5-5"
    msg.stop_reason = "end_turn"
    return msg


def _make_async_message(
    text: str = '{"result": "ok"}', input_tokens: int = 8, output_tokens: int = 4
) -> MagicMock:
    """Build a mock final Anthropic message for the async stream."""
    return _make_sync_message(text=text, input_tokens=input_tokens, output_tokens=output_tokens)


@pytest.fixture
def mock_anthropic_clients():
    """Patch both Anthropic and AsyncAnthropic inside the provider module."""
    sync_msg = _make_sync_message()
    async_msg = _make_async_message()

    sync_stream = MagicMock()
    sync_stream.get_final_message.return_value = sync_msg
    mock_sync = MagicMock()
    mock_sync.messages.stream.return_value.__enter__.return_value = sync_stream

    async_stream = MagicMock()
    async_stream.get_final_message = AsyncMock(return_value=async_msg)
    mock_async = MagicMock()
    mock_async.messages.stream.return_value.__aenter__ = AsyncMock(return_value=async_stream)
    mock_async.messages.stream.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "twinklr.core.agents.providers.anthropic.Anthropic",
            return_value=mock_sync,
        ) as mock_anthropic_cls,
        patch(
            "twinklr.core.agents.providers.anthropic.AsyncAnthropic",
            return_value=mock_async,
        ) as mock_async_cls,
    ):
        yield {
            "sync_client": mock_sync,
            "async_client": mock_async,
            "sync_msg": sync_msg,
            "async_msg": async_msg,
            "Anthropic": mock_anthropic_cls,
            "AsyncAnthropic": mock_async_cls,
        }


def _make_provider(mock_clients: dict) -> AnthropicProvider:  # noqa: F821
    """Import and construct an AnthropicProvider with mocked clients."""
    from twinklr.core.agents.providers.anthropic import AnthropicProvider

    return AnthropicProvider(api_key="test-key")


# ---------------------------------------------------------------------------
# provider_type
# ---------------------------------------------------------------------------


def test_provider_type_is_anthropic(mock_anthropic_clients: dict) -> None:
    """provider_type must return ProviderType.ANTHROPIC."""
    provider = _make_provider(mock_anthropic_clients)
    assert provider.provider_type == ProviderType.ANTHROPIC


# ---------------------------------------------------------------------------
# generate_json (sync)
# ---------------------------------------------------------------------------


def test_generate_json_returns_llm_response(mock_anthropic_clients: dict) -> None:
    """generate_json must return a valid LLMResponse with parsed JSON content."""
    provider = _make_provider(mock_anthropic_clients)

    messages = [{"role": "user", "content": "Give me JSON"}]
    result = provider.generate_json(messages=messages, model="claude-sonnet-4-20250514")

    assert isinstance(result, LLMResponse)
    assert result.content == {"result": "ok"}
    # Metadata reports the model that actually served the response.
    assert result.metadata.model == "claude-opus-5-5"
    assert result.metadata.actual_model_present


def test_generate_json_token_usage(mock_anthropic_clients: dict) -> None:
    """generate_json must populate token usage in the response metadata."""
    provider = _make_provider(mock_anthropic_clients)

    messages = [{"role": "user", "content": "test"}]
    result = provider.generate_json(messages=messages, model="claude-sonnet-4-20250514")

    assert result.metadata.token_usage.prompt_tokens == 10
    assert result.metadata.token_usage.completion_tokens == 5
    assert result.metadata.token_usage.total_tokens == 15


def test_generate_json_extracts_system_message(mock_anthropic_clients: dict) -> None:
    """System messages must be extracted and passed as the 'system' kwarg, not in messages list."""
    provider = _make_provider(mock_anthropic_clients)
    sync_client = mock_anthropic_clients["sync_client"]

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
    ]
    provider.generate_json(messages=messages, model="claude-sonnet-4-20250514")

    call_kwargs = sync_client.messages.stream.call_args.kwargs
    assert call_kwargs["system"] == "You are a helpful assistant."
    # The messages list passed to the API must NOT include the system message
    for msg in call_kwargs["messages"]:
        assert msg["role"] != "system"


def test_generate_json_no_developer_role(mock_anthropic_clients: dict) -> None:
    """OpenAI 'developer' role messages must be converted to system, not passed as 'developer'."""
    provider = _make_provider(mock_anthropic_clients)
    sync_client = mock_anthropic_clients["sync_client"]

    messages = [
        {"role": "developer", "content": "System instructions"},
        {"role": "user", "content": "Hello"},
    ]
    provider.generate_json(messages=messages, model="claude-sonnet-4-20250514")

    call_kwargs = sync_client.messages.stream.call_args.kwargs
    # 'developer' must NOT appear in the messages list sent to Anthropic
    for msg in call_kwargs.get("messages", []):
        assert msg["role"] != "developer"


def test_generate_json_wraps_anthropic_error(mock_anthropic_clients: dict) -> None:
    """Anthropic API errors must be wrapped in LLMProviderError."""
    provider = _make_provider(mock_anthropic_clients)
    mock_anthropic_clients["sync_client"].messages.stream.side_effect = Exception(
        "Anthropic API failure"
    )

    with pytest.raises(LLMProviderError, match="Provider error"):
        provider.generate_json(
            messages=[{"role": "user", "content": "test"}],
            model="claude-sonnet-4-20250514",
        )


# ---------------------------------------------------------------------------
# generate_json_async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_json_async_returns_llm_response(mock_anthropic_clients: dict) -> None:
    """generate_json_async must return a valid LLMResponse with parsed JSON content."""
    provider = _make_provider(mock_anthropic_clients)

    messages = [{"role": "user", "content": "Give me JSON"}]
    result = await provider.generate_json_async(messages=messages, model="claude-sonnet-4-20250514")

    assert isinstance(result, LLMResponse)
    assert result.content == {"result": "ok"}


@pytest.mark.asyncio
async def test_generate_json_async_maps_effort_and_drops_temperature(
    mock_anthropic_clients: dict,
) -> None:
    """Effort goes to output_config; sampling parameters are never sent to Claude."""
    provider = _make_provider(mock_anthropic_clients)

    await provider.generate_json_async(
        messages=[{"role": "user", "content": "test"}],
        model="claude-configured",
        temperature=0.7,
        reasoning_effort="high",
        max_tokens=1234,
        timeout_seconds=17,
    )

    request = mock_anthropic_clients["async_client"].messages.stream.call_args.kwargs
    assert request["output_config"] == {"effort": "high"}
    assert "reasoning_effort" not in request
    assert "temperature" not in request
    assert request["max_tokens"] == 1234
    assert request["timeout"] == 17


@pytest.mark.asyncio
async def test_async_runner_sends_effort_to_anthropic(
    mock_anthropic_clients: dict, tmp_path: Path
) -> None:
    """The runner forwards the spec's effort; the provider maps it to output_config."""
    provider = _make_provider(mock_anthropic_clients)
    runner = AsyncAgentRunner(provider=provider, prompt_base_path=tmp_path)
    spec = AgentSpec(
        name="anthropic-test",
        prompt_pack="unused",
        response_model=dict,
        model="claude-configured",
        reasoning_effort="high",
        max_tokens=2222,
        timeout_seconds=19,
    )

    await runner._call_oneshot_async(spec, [{"role": "user", "content": "test"}])

    request = mock_anthropic_clients["async_client"].messages.stream.call_args.kwargs
    assert request["output_config"] == {"effort": "high"}
    assert "reasoning" not in request
    assert request["max_tokens"] == 2222
    assert request["timeout"] == 19


@pytest.mark.asyncio
async def test_generate_json_async_token_usage(mock_anthropic_clients: dict) -> None:
    """generate_json_async must populate token usage."""
    provider = _make_provider(mock_anthropic_clients)

    result = await provider.generate_json_async(
        messages=[{"role": "user", "content": "test"}],
        model="claude-sonnet-4-20250514",
    )

    assert result.metadata.token_usage.prompt_tokens == 8
    assert result.metadata.token_usage.completion_tokens == 4
    assert result.metadata.token_usage.total_tokens == 12


@pytest.mark.asyncio
async def test_generate_json_async_extracts_system_message(mock_anthropic_clients: dict) -> None:
    """Async path must also extract system messages and pass separately."""
    provider = _make_provider(mock_anthropic_clients)
    async_client = mock_anthropic_clients["async_client"]

    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Hi"},
    ]
    await provider.generate_json_async(messages=messages, model="claude-sonnet-4-20250514")

    call_kwargs = async_client.messages.stream.call_args.kwargs
    assert call_kwargs["system"] == "Be concise."
    for msg in call_kwargs["messages"]:
        assert msg["role"] != "system"


@pytest.mark.asyncio
async def test_generate_json_async_wraps_error(mock_anthropic_clients: dict) -> None:
    """Anthropic async API errors must be wrapped in LLMProviderError."""
    provider = _make_provider(mock_anthropic_clients)
    mock_anthropic_clients["async_client"].messages.stream.side_effect = Exception("async failure")

    with pytest.raises(LLMProviderError, match="Provider error"):
        await provider.generate_json_async(
            messages=[{"role": "user", "content": "test"}],
            model="claude-sonnet-4-20250514",
        )


# ---------------------------------------------------------------------------
# Conversation management
# ---------------------------------------------------------------------------


def test_add_message_to_conversation(mock_anthropic_clients: dict) -> None:
    """add_message_to_conversation must append a message to the stored conversation."""
    provider = _make_provider(mock_anthropic_clients)
    conv_id = generate_conversation_id("test", 1)

    # Create conversation via generate_json_with_conversation
    provider.generate_json_with_conversation(
        user_message="Hello",
        conversation_id=conv_id,
        model="claude-sonnet-4-20250514",
    )

    provider.add_message_to_conversation(conv_id, role="user", content="follow-up")
    history = provider.get_conversation_history(conv_id)
    assert history[-1]["role"] == "user"
    assert history[-1]["content"] == "follow-up"


def test_add_message_to_nonexistent_conversation_raises(mock_anthropic_clients: dict) -> None:
    """add_message_to_conversation must raise ValueError for unknown conversation."""
    provider = _make_provider(mock_anthropic_clients)

    with pytest.raises(ValueError, match="not found"):
        provider.add_message_to_conversation("no-such-id", role="user", content="x")


def test_get_conversation_history_returns_copy(mock_anthropic_clients: dict) -> None:
    """get_conversation_history must return a copy (mutations do not affect internal state)."""
    provider = _make_provider(mock_anthropic_clients)
    conv_id = generate_conversation_id("test", 1)

    provider.generate_json_with_conversation(
        user_message="Hello",
        conversation_id=conv_id,
        model="claude-sonnet-4-20250514",
    )

    history = provider.get_conversation_history(conv_id)
    original_len = len(history)
    history.append({"role": "user", "content": "mutated"})

    # Internal state should be unaffected
    assert len(provider.get_conversation_history(conv_id)) == original_len


def test_get_conversation_history_nonexistent_raises(mock_anthropic_clients: dict) -> None:
    """get_conversation_history must raise ValueError for unknown conversation."""
    provider = _make_provider(mock_anthropic_clients)

    with pytest.raises(ValueError, match="not found"):
        provider.get_conversation_history("ghost-id")


def test_generate_json_with_conversation_new_with_system_prompt(
    mock_anthropic_clients: dict,
) -> None:
    """New conversation with system_prompt stores it and includes developer/assistant messages."""
    provider = _make_provider(mock_anthropic_clients)
    conv_id = generate_conversation_id("planner", 1)

    response = provider.generate_json_with_conversation(
        user_message="Plan something",
        conversation_id=conv_id,
        model="claude-sonnet-4-20250514",
        system_prompt="You are a planner.",
    )

    assert isinstance(response, LLMResponse)
    assert response.metadata.conversation_id == conv_id

    history = provider.get_conversation_history(conv_id)
    roles = [m["role"] for m in history]
    assert "user" in roles
    assert "assistant" in roles


def test_generate_json_with_conversation_continues_existing(
    mock_anthropic_clients: dict,
) -> None:
    """Continuing an existing conversation appends messages correctly."""
    provider = _make_provider(mock_anthropic_clients)
    conv_id = generate_conversation_id("agent", 1)

    provider.generate_json_with_conversation(
        user_message="First", conversation_id=conv_id, model="claude-sonnet-4-20250514"
    )
    provider.generate_json_with_conversation(
        user_message="Second", conversation_id=conv_id, model="claude-sonnet-4-20250514"
    )

    history = provider.get_conversation_history(conv_id)
    user_messages = [m for m in history if m["role"] == "user"]
    assert len(user_messages) == 2
    assert user_messages[0]["content"] == "First"
    assert user_messages[1]["content"] == "Second"


# ---------------------------------------------------------------------------
# Token usage tracking (thread-safe accumulation)
# ---------------------------------------------------------------------------


def test_token_usage_accumulates_across_calls(mock_anthropic_clients: dict) -> None:
    """Token usage must accumulate across multiple generate_json calls."""
    provider = _make_provider(mock_anthropic_clients)

    # Initial usage is zero
    assert provider.get_token_usage().total_tokens == 0

    provider.generate_json(
        messages=[{"role": "user", "content": "call 1"}],
        model="claude-sonnet-4-20250514",
    )
    provider.generate_json(
        messages=[{"role": "user", "content": "call 2"}],
        model="claude-sonnet-4-20250514",
    )

    # Each call: input=10, output=5, total=15 => 2 calls = 30 total
    usage = provider.get_token_usage()
    assert isinstance(usage, TokenUsage)
    assert usage.total_tokens == 30


def test_reset_token_tracking(mock_anthropic_clients: dict) -> None:
    """reset_token_tracking must zero out accumulated token counts."""
    provider = _make_provider(mock_anthropic_clients)

    provider.generate_json(
        messages=[{"role": "user", "content": "call"}],
        model="claude-sonnet-4-20250514",
    )
    assert provider.get_token_usage().total_tokens > 0

    provider.reset_token_tracking()
    assert provider.get_token_usage().total_tokens == 0


# ---------------------------------------------------------------------------
# _window_messages (same algorithm as OpenAI)
# ---------------------------------------------------------------------------


class TestAnthropicWindowMessages:
    """Tests that AnthropicProvider._window_messages mirrors OpenAI behaviour."""

    def _make_provider(self, mock_clients: dict):
        from twinklr.core.agents.providers.anthropic import AnthropicProvider

        return AnthropicProvider(api_key="test-key")

    def test_short_conversation_kept_in_full(self, mock_anthropic_clients: dict) -> None:
        provider = self._make_provider(mock_anthropic_clients)
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        result = provider._window_messages(messages, window_size=2)
        assert len(result) == 3

    def test_long_conversation_trimmed(self, mock_anthropic_clients: dict) -> None:
        provider = self._make_provider(mock_anthropic_clients)
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "u3"},
            {"role": "assistant", "content": "a3"},
        ]
        result = provider._window_messages(messages, window_size=2)
        # system + last 2 pairs (4 messages) = 5 total
        assert len(result) == 5
        assert result[0]["role"] == "system"
        assert result[1]["content"] == "u2"
        assert result[-1]["content"] == "a3"

    def test_system_and_developer_always_preserved(self, mock_anthropic_clients: dict) -> None:
        provider = self._make_provider(mock_anthropic_clients)
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "developer", "content": "dev"},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
        ]
        result = provider._window_messages(messages, window_size=1)
        # system + developer + last 1 pair = 4
        assert len(result) == 4
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "developer"


# ---------------------------------------------------------------------------
# Factory integration
# ---------------------------------------------------------------------------


def test_factory_creates_anthropic_provider() -> None:
    """create_llm_provider must return an AnthropicProvider when configured."""
    from twinklr.core.agents.providers.factory import create_llm_provider

    mock_config = MagicMock()
    mock_config.llm_provider = "anthropic"
    mock_config.llm_api_key.get_secret_value.return_value = "fake-key"

    with (
        patch(
            "twinklr.core.agents.providers.anthropic.Anthropic",
            return_value=MagicMock(),
        ),
        patch(
            "twinklr.core.agents.providers.anthropic.AsyncAnthropic",
            return_value=MagicMock(),
        ),
    ):
        from twinklr.core.agents.providers.anthropic import AnthropicProvider

        provider = create_llm_provider(mock_config, session_id="test-session")

    assert isinstance(provider, AnthropicProvider)
    assert provider.provider_type == ProviderType.ANTHROPIC


# ---------------------------------------------------------------------------
# Structured outputs, refusal fallback, and stop-reason classification
# ---------------------------------------------------------------------------


def _walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_claude_schema_strips_unsupported_constraints_but_keeps_enums() -> None:
    from twinklr.core.agents.providers.anthropic import claude_json_schema

    schema = claude_json_schema(MacroPlan)
    nodes = list(_walk(schema))
    unsupported = {"minimum", "maximum", "minLength", "maxLength", "maxItems", "default"}
    assert not any(unsupported & node.keys() for node in nodes)
    assert all(node.get("minItems", 0) in (0, 1) for node in nodes)
    assert any("enum" in node for node in nodes)
    assert all(set(node) == {"$ref"} for node in nodes if "$ref" in node)
    assert all(
        node.get("additionalProperties") is False for node in nodes if node.get("type") == "object"
    )


@pytest.mark.asyncio
async def test_structured_request_uses_output_config_and_default_fallback(
    mock_anthropic_clients: dict,
) -> None:
    provider = _make_provider(mock_anthropic_clients)
    mock_anthropic_clients["async_msg"].content[0].text = '{"result": "ok"}'

    from pydantic import BaseModel, ConfigDict

    class Result(BaseModel):
        model_config = ConfigDict(extra="forbid")

        result: str

    response = await provider.generate_json_async(
        messages=[
            {"role": "developer", "content": "Schema here."},
            {"role": "user", "content": "test"},
        ],
        model="claude-opus-5-5",
        response_model=Result,
        reasoning_effort="medium",
        provider_max_attempts=1,
        allow_json_object_fallback=False,
    )

    request = mock_anthropic_clients["async_client"].messages.stream.call_args.kwargs
    assert request["system"] == "Schema here."
    assert request["output_config"]["effort"] == "medium"
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert request["output_config"]["format"]["schema"]["required"] == ["result"]
    assert request["extra_headers"] == {"anthropic-beta": "server-side-fallback-2026-07-01"}
    assert request["extra_body"] == {"fallbacks": "default"}
    assert response.metadata.structured_output_mode == "json_schema"
    assert response.metadata.response_schema_hash is not None
    assert response.metadata.finish_reason == "end_turn"


@pytest.mark.asyncio
async def test_models_without_server_fallback_send_no_fallback(
    mock_anthropic_clients: dict,
) -> None:
    provider = _make_provider(mock_anthropic_clients)
    await provider.generate_json_async(
        messages=[{"role": "user", "content": "test"}], model="claude-haiku-5-5"
    )
    request = mock_anthropic_clients["async_client"].messages.stream.call_args.kwargs
    assert "extra_body" not in request
    assert "extra_headers" not in request


def test_response_text_skips_thinking_and_pre_fallback_blocks() -> None:
    from twinklr.core.agents.providers.anthropic import AnthropicProvider

    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text='{"partial": '),
            SimpleNamespace(type="fallback"),
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text='{"result": "ok"}'),
        ]
    )
    assert AnthropicProvider._response_text(response) == '{"result": "ok"}'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stop_reason", "text", "reason"),
    [
        ("max_tokens", '{"result": ', "truncation"),
        ("refusal", "", "refusal"),
        ("end_turn", "", "empty_response"),
        ("end_turn", "not json", "json_decode"),
    ],
)
async def test_response_outcomes_are_recoverable_with_usage(
    mock_anthropic_clients: dict, stop_reason: str, text: str, reason: str
) -> None:
    provider = _make_provider(mock_anthropic_clients)
    message = mock_anthropic_clients["async_msg"]
    message.stop_reason = stop_reason
    message.stop_details = SimpleNamespace(category="cyber")
    message.content[0].text = text

    with pytest.raises(RecoverableLLMProviderError) as caught:
        await provider.generate_json_async(
            messages=[{"role": "user", "content": "test"}], model="claude-opus-5-5"
        )

    assert caught.value.reason == reason
    assert caught.value.token_usage.total_tokens == 12


@pytest.mark.asyncio
async def test_unknown_request_options_fail_loudly(mock_anthropic_clients: dict) -> None:
    provider = _make_provider(mock_anthropic_clients)
    with pytest.raises(LLMProviderError, match="top_p"):
        await provider.generate_json_async(
            messages=[{"role": "user", "content": "test"}], model="claude-opus-5-5", top_p=0.9
        )
    mock_anthropic_clients["async_client"].messages.stream.assert_not_called()


def test_app_config_uses_anthropic_key_for_anthropic_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from twinklr.core.config.models import AppConfig

    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    assert AppConfig(llm_provider="anthropic").llm_api_key.get_secret_value() == "sk-ant"
    assert AppConfig().llm_api_key.get_secret_value() == "sk-openai"
    explicit = AppConfig(llm_provider="anthropic", llm_api_key="explicit")
    assert explicit.llm_api_key.get_secret_value() == "explicit"
