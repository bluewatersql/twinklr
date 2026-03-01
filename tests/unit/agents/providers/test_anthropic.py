"""Tests for Anthropic Claude provider — MKT-02."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.core.agents.providers.base import LLMResponse, ProviderType, TokenUsage
from twinklr.core.agents.providers.conversation import generate_conversation_id
from twinklr.core.agents.providers.errors import LLMProviderError

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_sync_message(
    text: str = '{"result": "ok"}', input_tokens: int = 10, output_tokens: int = 5
) -> MagicMock:
    """Build a mock Anthropic sync messages.create() response."""
    block = MagicMock()
    block.text = text

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    msg = MagicMock()
    msg.content = [block]
    msg.usage = usage
    msg.id = "msg_sync_001"
    return msg


def _make_async_message(
    text: str = '{"result": "ok"}', input_tokens: int = 8, output_tokens: int = 4
) -> MagicMock:
    """Build a mock Anthropic async messages.create() response."""
    return _make_sync_message(text=text, input_tokens=input_tokens, output_tokens=output_tokens)


@pytest.fixture
def mock_anthropic_clients():
    """Patch both Anthropic and AsyncAnthropic inside the provider module."""
    sync_msg = _make_sync_message()
    async_msg = _make_async_message()

    mock_sync = MagicMock()
    mock_sync.messages.create.return_value = sync_msg

    mock_async = MagicMock()
    mock_async.messages.create = AsyncMock(return_value=async_msg)

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
    assert result.metadata.model == "claude-sonnet-4-20250514"


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

    call_kwargs = sync_client.messages.create.call_args.kwargs
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

    call_kwargs = sync_client.messages.create.call_args.kwargs
    # 'developer' must NOT appear in the messages list sent to Anthropic
    for msg in call_kwargs.get("messages", []):
        assert msg["role"] != "developer"


def test_generate_json_wraps_anthropic_error(mock_anthropic_clients: dict) -> None:
    """Anthropic API errors must be wrapped in LLMProviderError."""
    provider = _make_provider(mock_anthropic_clients)
    mock_anthropic_clients["sync_client"].messages.create.side_effect = Exception(
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
    assert result.metadata.model == "claude-sonnet-4-20250514"


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

    call_kwargs = async_client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "Be concise."
    for msg in call_kwargs["messages"]:
        assert msg["role"] != "system"


@pytest.mark.asyncio
async def test_generate_json_async_wraps_error(mock_anthropic_clients: dict) -> None:
    """Anthropic async API errors must be wrapped in LLMProviderError."""
    provider = _make_provider(mock_anthropic_clients)
    mock_anthropic_clients["async_client"].messages.create.side_effect = Exception("async failure")

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
