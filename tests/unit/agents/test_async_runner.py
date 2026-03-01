"""Tests for AsyncAgentRunner."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from pydantic import BaseModel
import pytest

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.logging import NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMResponse, ResponseMetadata, TokenUsage
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.state import AgentState

FIXTURES_PATH = Path(__file__).parent.parent.parent / "fixtures" / "prompts"


class SampleResponse(BaseModel):
    """Sample response model for testing."""

    result: str
    count: int


@pytest.fixture
def test_spec():
    """Create test agent spec."""
    return AgentSpec(
        name="test_agent",
        prompt_pack="test_pack",
        response_model=SampleResponse,
        max_schema_repair_attempts=2,
    )


@pytest.fixture
def mock_async_provider():
    """Mock LLM provider with async methods."""
    provider = MagicMock()

    # Track tokens (simulate accumulation)
    token_counter = {"total": 0}

    async def generate_json_async_side_effect(*args, **kwargs):
        token_counter["total"] += 150
        return LLMResponse(
            content={"result": "success", "count": 5},
            metadata=ResponseMetadata(
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
                model="gpt-5.2-mini",
            ),
        )

    provider.generate_json_async = AsyncMock(side_effect=generate_json_async_side_effect)

    # Mock get_token_usage to return cumulative tokens
    provider.get_token_usage.side_effect = lambda: TokenUsage(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=token_counter["total"],
    )

    provider.provider_type = MagicMock()
    provider.provider_type.value = "mock"

    return provider


@pytest.fixture
def mock_llm_logger():
    """Mock LLM call logger."""
    logger = MagicMock(spec=NullLLMCallLogger)
    logger.start_call_async = AsyncMock(return_value="call_123")
    logger.complete_call_async = AsyncMock()
    logger.flush_async = AsyncMock()
    return logger


@pytest.mark.asyncio
async def test_async_runner_init(mock_async_provider):
    """Test async runner initialization."""
    runner = AsyncAgentRunner(
        provider=mock_async_provider,
        prompt_base_path=FIXTURES_PATH,
    )

    assert runner.provider == mock_async_provider
    assert runner.prompt_loader is not None


@pytest.mark.asyncio
async def test_async_run_oneshot_success(test_spec, mock_async_provider, mock_llm_logger):
    """Test successful async oneshot execution."""
    runner = AsyncAgentRunner(
        provider=mock_async_provider,
        prompt_base_path=FIXTURES_PATH,
        llm_logger=mock_llm_logger,
    )

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = await runner.run(spec=test_spec, variables=variables)

    # Should succeed
    assert result.success is True
    assert result.data is not None
    assert isinstance(result.data, SampleResponse)
    assert result.data.result == "success"
    assert result.data.count == 5
    assert result.tokens_used == 150
    assert result.error_message is None

    # Logger should be called
    assert mock_llm_logger.start_call_async.called
    assert mock_llm_logger.complete_call_async.called


@pytest.mark.asyncio
async def test_async_run_with_state(test_spec, mock_async_provider):
    """Test async execution with state tracking."""
    runner = AsyncAgentRunner(
        provider=mock_async_provider,
        prompt_base_path=FIXTURES_PATH,
    )

    state = AgentState(name="test_agent")
    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = await runner.run(spec=test_spec, variables=variables, state=state)

    assert result.success is True
    # State should be updated
    assert state.attempt_count == 1


@pytest.mark.asyncio
async def test_async_run_conversational_mode(mock_async_provider):
    """Test async conversational agent execution."""
    spec = AgentSpec(
        name="conv_agent",
        prompt_pack="test_pack",
        response_model=SampleResponse,
        mode=AgentMode.CONVERSATIONAL,
    )

    # Mock async conversational response
    async def conv_async_side_effect(*args, **kwargs):
        return LLMResponse(
            content={"result": "conv_success", "count": 3},
            metadata=ResponseMetadata(
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
                conversation_id="test_conv_123",
            ),
        )

    mock_async_provider.generate_json_with_conversation_async = AsyncMock(
        side_effect=conv_async_side_effect
    )

    runner = AsyncAgentRunner(
        provider=mock_async_provider,
        prompt_base_path=FIXTURES_PATH,
    )
    state = AgentState(name="conv_agent")

    variables = {"agent_name": "conv", "iteration": 1, "context": {}, "feedback": None}

    # First call - should create conversation
    result1 = await runner.run(spec=spec, variables=variables, state=state)

    assert result1.success is True
    assert state.conversation_id is not None
    assert result1.conversation_id == state.conversation_id

    # Second call - should reuse conversation
    result2 = await runner.run(spec=spec, variables=variables, state=state)

    assert result2.success is True
    assert result2.conversation_id == state.conversation_id


@pytest.mark.asyncio
async def test_async_run_schema_validation_failure_and_repair(test_spec, mock_async_provider):
    """Test async schema validation failure with automatic repair."""
    runner = AsyncAgentRunner(
        provider=mock_async_provider,
        prompt_base_path=FIXTURES_PATH,
    )

    # First response: invalid (missing 'count')
    # Second response: valid
    responses = [
        LLMResponse(
            content={"result": "invalid"},  # Missing 'count'
            metadata=ResponseMetadata(
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            ),
        ),
        LLMResponse(
            content={"result": "fixed", "count": 10},
            metadata=ResponseMetadata(
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            ),
        ),
    ]
    response_iter = iter(responses)

    async def async_side_effect(*args, **kwargs):
        return next(response_iter)

    mock_async_provider.generate_json_async = AsyncMock(side_effect=async_side_effect)

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = await runner.run(spec=test_spec, variables=variables)

    # Should succeed after repair
    assert result.success is True
    assert result.data.result == "fixed"
    assert result.data.count == 10

    # Should have metadata about repair
    assert "schema_repair_attempts" in result.metadata
    assert result.metadata["schema_repair_attempts"] == 1


@pytest.mark.asyncio
async def test_async_run_provider_error(test_spec, mock_async_provider):
    """Test async provider error handling."""
    from twinklr.core.agents.providers.errors import LLMProviderError

    runner = AsyncAgentRunner(
        provider=mock_async_provider,
        prompt_base_path=FIXTURES_PATH,
    )

    # Make async provider raise error
    mock_async_provider.generate_json_async = AsyncMock(side_effect=LLMProviderError("API Error"))

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = await runner.run(spec=test_spec, variables=variables)

    # Should fail with error message
    assert result.success is False
    assert "API Error" in result.error_message


@pytest.mark.asyncio
async def test_async_run_dict_response_model(mock_async_provider):
    """Test async execution with dict response model (no validation)."""
    spec = AgentSpec(
        name="test_agent",
        prompt_pack="test_pack",
        response_model=dict,  # No schema validation
    )

    async def return_any_dict_async(*args, **kwargs):
        return LLMResponse(
            content={"any": "structure", "works": True},
            metadata=ResponseMetadata(
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            ),
        )

    mock_async_provider.generate_json_async = AsyncMock(side_effect=return_any_dict_async)

    runner = AsyncAgentRunner(
        provider=mock_async_provider,
        prompt_base_path=FIXTURES_PATH,
    )

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = await runner.run(spec=spec, variables=variables)

    # Should succeed without schema validation
    assert result.success is True
    assert result.data == {"any": "structure", "works": True}


# =========================================================================
# PERF-11: Schema Repair Trimming Tests
# =========================================================================


class TestSchemaRepairTrimming:
    """Tests for PERF-11: repair message sends errors only, no schema echo."""

    @pytest.mark.asyncio
    async def test_repair_message_contains_error_details(self, mock_async_provider) -> None:
        """Repair message should include the specific validation error details."""
        spec = AgentSpec(
            name="test_repair",
            prompt_pack="test_pack",
            response_model=SampleResponse,
            max_schema_repair_attempts=2,
        )

        # First response: invalid (missing 'count'), second: valid
        responses = [
            LLMResponse(
                content={"result": "bad"},  # Missing 'count'
                metadata=ResponseMetadata(
                    token_usage=TokenUsage(
                        prompt_tokens=100, completion_tokens=50, total_tokens=150
                    )
                ),
            ),
            LLMResponse(
                content={"result": "fixed", "count": 1},
                metadata=ResponseMetadata(
                    token_usage=TokenUsage(
                        prompt_tokens=100, completion_tokens=50, total_tokens=150
                    )
                ),
            ),
        ]
        call_count = {"n": 0}

        async def side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx]

        mock_async_provider.generate_json_async = AsyncMock(side_effect=side_effect)

        runner = AsyncAgentRunner(
            provider=mock_async_provider,
            prompt_base_path=FIXTURES_PATH,
        )

        variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}
        result = await runner.run(spec=spec, variables=variables)

        assert result.success is True

        # Inspect the messages passed to the second call to verify error details
        second_call_kwargs = mock_async_provider.generate_json_async.call_args_list[1]
        messages_arg = second_call_kwargs.kwargs.get("messages") or second_call_kwargs.args[0]

        # Find the repair message (last user message before second call)
        repair_msgs = [
            m
            for m in messages_arg
            if m["role"] == "user" and "Schema validation failed" in m["content"]
        ]
        assert len(repair_msgs) >= 1
        repair_content = repair_msgs[-1]["content"]

        # Should contain error details (Pydantic error about missing 'count')
        assert "count" in repair_content.lower()

    @pytest.mark.asyncio
    async def test_repair_message_does_not_contain_full_schema(self, mock_async_provider) -> None:
        """Repair message should NOT echo the full JSON schema."""
        spec = AgentSpec(
            name="test_repair_no_schema",
            prompt_pack="test_pack",
            response_model=SampleResponse,
            max_schema_repair_attempts=2,
        )

        # First response: invalid, second: valid
        responses = [
            LLMResponse(
                content={"result": "bad"},
                metadata=ResponseMetadata(
                    token_usage=TokenUsage(
                        prompt_tokens=100, completion_tokens=50, total_tokens=150
                    )
                ),
            ),
            LLMResponse(
                content={"result": "fixed", "count": 1},
                metadata=ResponseMetadata(
                    token_usage=TokenUsage(
                        prompt_tokens=100, completion_tokens=50, total_tokens=150
                    )
                ),
            ),
        ]
        call_count = {"n": 0}

        async def side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx]

        mock_async_provider.generate_json_async = AsyncMock(side_effect=side_effect)

        runner = AsyncAgentRunner(
            provider=mock_async_provider,
            prompt_base_path=FIXTURES_PATH,
        )

        variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}
        result = await runner.run(spec=spec, variables=variables)

        assert result.success is True

        # Inspect the repair message
        second_call_kwargs = mock_async_provider.generate_json_async.call_args_list[1]
        messages_arg = second_call_kwargs.kwargs.get("messages") or second_call_kwargs.args[0]

        repair_msgs = [
            m
            for m in messages_arg
            if m["role"] == "user" and "Schema validation failed" in m["content"]
        ]
        assert len(repair_msgs) >= 1
        repair_content = repair_msgs[-1]["content"]

        # Should NOT contain the full schema output from get_json_schema_example
        # The schema contains "properties", "$defs", "required" etc.
        from twinklr.core.agents.schema_utils import get_json_schema_example

        full_schema = get_json_schema_example(SampleResponse)
        assert full_schema not in repair_content
        assert '"properties"' not in repair_content

        # Should reference the system prompt instead
        assert "system prompt" in repair_content.lower()

    @pytest.mark.asyncio
    async def test_repair_still_succeeds_functionally(self, mock_async_provider) -> None:
        """Schema repair should still work end-to-end after trimming."""
        spec = AgentSpec(
            name="test_repair_functional",
            prompt_pack="test_pack",
            response_model=SampleResponse,
            max_schema_repair_attempts=2,
        )

        # First: invalid, second: still invalid, third: valid
        responses = [
            LLMResponse(
                content={"result": "bad"},
                metadata=ResponseMetadata(
                    token_usage=TokenUsage(
                        prompt_tokens=100, completion_tokens=50, total_tokens=150
                    )
                ),
            ),
            LLMResponse(
                content={"result": "still_bad"},
                metadata=ResponseMetadata(
                    token_usage=TokenUsage(
                        prompt_tokens=100, completion_tokens=50, total_tokens=150
                    )
                ),
            ),
            LLMResponse(
                content={"result": "finally_good", "count": 42},
                metadata=ResponseMetadata(
                    token_usage=TokenUsage(
                        prompt_tokens=100, completion_tokens=50, total_tokens=150
                    )
                ),
            ),
        ]
        call_count = {"n": 0}

        async def side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx]

        mock_async_provider.generate_json_async = AsyncMock(side_effect=side_effect)

        runner = AsyncAgentRunner(
            provider=mock_async_provider,
            prompt_base_path=FIXTURES_PATH,
        )

        variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}
        result = await runner.run(spec=spec, variables=variables)

        # Should ultimately succeed after 2 repairs
        assert result.success is True
        assert result.data.result == "finally_good"
        assert result.data.count == 42
        assert result.metadata["schema_repair_attempts"] == 2
