"""Tests for agent runner."""

from pathlib import Path
from unittest.mock import MagicMock

from pydantic import BaseModel
import pytest

from blinkb0t.core.agents.providers.base import LLMResponse, ResponseMetadata, TokenUsage
from blinkb0t.core.agents.runner import AgentRunner
from blinkb0t.core.agents.spec import AgentMode, AgentSpec
from blinkb0t.core.agents.state import AgentState

FIXTURES_PATH = Path(__file__).parent.parent.parent / "fixtures" / "prompts"


class SampleResponse(BaseModel):
    """Sample response model for testing (renamed to avoid pytest collection)."""

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
def mock_provider():
    """Mock LLM provider."""
    provider = MagicMock()

    # Track tokens (simulate accumulation)
    token_counter = {"total": 0}

    def generate_json_side_effect(*args, **kwargs):
        token_counter["total"] += 150
        return LLMResponse(
            content={"result": "success", "count": 5},
            metadata=ResponseMetadata(
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
                model="gpt-5.2-mini",
            ),
        )

    provider.generate_json.side_effect = generate_json_side_effect

    # Mock get_token_usage to return cumulative tokens
    provider.get_token_usage.side_effect = lambda: TokenUsage(
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=token_counter["total"],
    )

    return provider


def test_runner_init():
    """Test runner initialization."""
    provider = MagicMock()

    runner = AgentRunner(
        provider=provider,
        prompt_base_path=FIXTURES_PATH,
    )

    assert runner.provider == provider
    assert runner.prompt_loader is not None


def test_run_oneshot_success(test_spec, mock_provider):
    """Test successful oneshot execution."""
    runner = AgentRunner(provider=mock_provider, prompt_base_path=FIXTURES_PATH)

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = runner.run(spec=test_spec, variables=variables)

    # Should succeed
    assert result.success is True
    assert result.data is not None
    assert isinstance(result.data, SampleResponse)
    assert result.data.result == "success"
    assert result.data.count == 5
    assert result.tokens_used == 150
    assert result.error_message is None


def test_run_with_state(test_spec, mock_provider):
    """Test execution with state tracking."""
    runner = AgentRunner(provider=mock_provider, prompt_base_path=FIXTURES_PATH)

    state = AgentState(name="test_agent")
    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = runner.run(spec=test_spec, variables=variables, state=state)

    assert result.success is True
    # State should be updated
    assert state.attempt_count == 1


def test_run_conversational_mode(mock_provider):
    """Test conversational agent execution."""
    spec = AgentSpec(
        name="conv_agent",
        prompt_pack="test_pack",
        response_model=SampleResponse,
        mode=AgentMode.CONVERSATIONAL,
    )

    # Mock conversational response
    mock_provider.generate_json_with_conversation.return_value = LLMResponse(
        content={"result": "conv_success", "count": 3},
        metadata=ResponseMetadata(
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            conversation_id="test_conv_123",
        ),
    )

    runner = AgentRunner(provider=mock_provider, prompt_base_path=FIXTURES_PATH)
    state = AgentState(name="conv_agent")

    variables = {"agent_name": "conv", "iteration": 1, "context": {}, "feedback": None}

    # First call - should create conversation
    result1 = runner.run(spec=spec, variables=variables, state=state)

    assert result1.success is True
    assert state.conversation_id is not None
    assert result1.conversation_id == state.conversation_id

    # Second call - should reuse conversation
    result2 = runner.run(spec=spec, variables=variables, state=state)

    assert result2.success is True
    assert result2.conversation_id == state.conversation_id


def test_run_schema_validation_failure_and_repair(test_spec, mock_provider):
    """Test schema validation failure with automatic repair."""
    runner = AgentRunner(provider=mock_provider, prompt_base_path=FIXTURES_PATH)

    # First response: invalid (missing 'count')
    # Second response: valid
    mock_provider.generate_json.side_effect = [
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

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = runner.run(spec=test_spec, variables=variables)

    # Should succeed after repair
    assert result.success is True
    assert result.data.result == "fixed"
    assert result.data.count == 10

    # Should have metadata about repair
    assert "schema_repair_attempts" in result.metadata
    assert result.metadata["schema_repair_attempts"] == 1


def test_run_schema_validation_exhausted(test_spec):
    """Test schema validation exhausted all repair attempts."""
    # Create fresh mock provider for this test
    provider = MagicMock()

    # Track tokens
    token_counter = {"total": 0}

    def always_invalid(*args, **kwargs):
        token_counter["total"] += 150
        return LLMResponse(
            content={"result": "invalid"},  # Always missing 'count'
            metadata=ResponseMetadata(
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            ),
        )

    provider.generate_json.side_effect = always_invalid
    provider.get_token_usage.side_effect = lambda: TokenUsage(
        prompt_tokens=0, completion_tokens=0, total_tokens=token_counter["total"]
    )

    runner = AgentRunner(provider=provider, prompt_base_path=FIXTURES_PATH)

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = runner.run(spec=test_spec, variables=variables)

    # Should fail after exhausting attempts
    assert result.success is False
    assert result.error_message is not None
    assert "schema validation" in result.error_message.lower()
    assert result.metadata["schema_repair_attempts"] == test_spec.max_schema_repair_attempts


def test_run_provider_error(test_spec, mock_provider):
    """Test provider error handling."""
    from blinkb0t.core.agents.providers.errors import LLMProviderError

    runner = AgentRunner(provider=mock_provider, prompt_base_path=FIXTURES_PATH)

    # Make provider raise error
    mock_provider.generate_json.side_effect = LLMProviderError("API Error")

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = runner.run(spec=test_spec, variables=variables)

    # Should fail with error message
    assert result.success is False
    assert "API Error" in result.error_message


def test_run_with_examples(test_spec, mock_provider):
    """Test execution includes examples from prompt pack."""
    runner = AgentRunner(provider=mock_provider, prompt_base_path=FIXTURES_PATH)

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    _result = runner.run(spec=test_spec, variables=variables)

    # Check that generate_json was called
    assert mock_provider.generate_json.called

    # Get the messages passed to provider
    call_args = mock_provider.generate_json.call_args
    messages = call_args.kwargs["messages"]

    # Should include examples (from examples.jsonl)
    message_contents = [m["content"] for m in messages]
    assert any("Example" in str(content) for content in message_contents)


def test_run_merges_default_variables(test_spec, mock_provider):
    """Test that default variables are merged with provided variables."""
    # Create spec with default variables
    spec_with_defaults = AgentSpec(
        name="test_agent",
        prompt_pack="test_pack",
        response_model=SampleResponse,
        default_variables={"context": {"default": "data"}, "iteration": 999, "feedback": None},
    )

    runner = AgentRunner(provider=mock_provider, prompt_base_path=FIXTURES_PATH)

    # Provide variables that override some defaults
    variables = {"agent_name": "test", "context": {"actual": "data"}}

    result = runner.run(spec=spec_with_defaults, variables=variables)

    # Should succeed (testing merge happened)
    assert result.success is True


def test_run_dict_response_model():
    """Test execution with dict response model (no validation)."""
    spec = AgentSpec(
        name="test_agent",
        prompt_pack="test_pack",
        response_model=dict,  # No schema validation
    )

    # Create fresh mock for this test
    provider = MagicMock()
    token_counter = {"total": 0}

    def return_any_dict(*args, **kwargs):
        token_counter["total"] += 150
        return LLMResponse(
            content={"any": "structure", "works": True},
            metadata=ResponseMetadata(
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
            ),
        )

    provider.generate_json.side_effect = return_any_dict
    provider.get_token_usage.side_effect = lambda: TokenUsage(
        prompt_tokens=0, completion_tokens=0, total_tokens=token_counter["total"]
    )

    runner = AgentRunner(provider=provider, prompt_base_path=FIXTURES_PATH)

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = runner.run(spec=spec, variables=variables)

    # Should succeed without schema validation
    assert result.success is True
    assert result.data == {"any": "structure", "works": True}


def test_run_tracks_duration(test_spec, mock_provider):
    """Test execution tracks duration."""
    runner = AgentRunner(provider=mock_provider, prompt_base_path=FIXTURES_PATH)

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    result = runner.run(spec=test_spec, variables=variables)

    # Should have positive duration
    assert result.duration_seconds > 0


def test_run_with_temperature(mock_provider):
    """Test execution passes temperature to provider."""
    spec = AgentSpec(
        name="test_agent",
        prompt_pack="test_pack",
        response_model=dict,
        temperature=0.9,
    )

    runner = AgentRunner(provider=mock_provider, prompt_base_path=FIXTURES_PATH)

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    runner.run(spec=spec, variables=variables)

    # Verify temperature was passed
    call_args = mock_provider.generate_json.call_args
    assert call_args.kwargs["temperature"] == 0.9


def test_run_with_model_override(mock_provider):
    """Test execution uses spec model."""
    spec = AgentSpec(
        name="test_agent",
        prompt_pack="test_pack",
        response_model=dict,
        model="gpt-5.2",
    )

    runner = AgentRunner(provider=mock_provider, prompt_base_path=FIXTURES_PATH)

    variables = {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}

    runner.run(spec=spec, variables=variables)

    # Verify model was passed
    call_args = mock_provider.generate_json.call_args
    assert call_args.kwargs["model"] == "gpt-5.2"
