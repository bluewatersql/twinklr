"""Tests for agent specification models."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.agents.spec import AgentMode, AgentSpec


def test_agent_spec_minimal():
    """Test minimal agent spec."""
    spec = AgentSpec(
        name="test_agent",
        prompt_pack="test_pack",
        response_model=dict,
    )

    assert spec.name == "test_agent"
    assert spec.prompt_pack == "test_pack"
    assert spec.response_model is dict
    assert spec.mode == AgentMode.ONESHOT  # Default
    assert spec.model == "gpt-5.2"  # Default
    assert spec.temperature == 0.7  # Default
    assert spec.max_schema_repair_attempts == 2  # Default


def test_agent_spec_full():
    """Test full agent spec with all fields."""
    default_vars = {"context": {}, "iteration": 1}

    spec = AgentSpec(
        name="planner",
        prompt_pack="planning",
        response_model=dict,
        mode=AgentMode.CONVERSATIONAL,
        model="gpt-5.2",
        temperature=0.9,
        max_schema_repair_attempts=3,
        default_variables=default_vars,
        token_budget=5000,
    )

    assert spec.name == "planner"
    assert spec.prompt_pack == "planning"
    assert spec.mode == AgentMode.CONVERSATIONAL
    assert spec.model == "gpt-5.2"
    assert spec.temperature == 0.9
    assert spec.max_schema_repair_attempts == 3
    assert spec.default_variables == default_vars
    assert spec.token_budget == 5000


def test_agent_spec_immutable():
    """Test agent spec is immutable."""
    spec = AgentSpec(
        name="test",
        prompt_pack="test",
        response_model=dict,
    )

    with pytest.raises((ValidationError, AttributeError)):
        spec.name = "changed"  # Should not be allowed


def test_agent_spec_temperature_validation():
    """Test temperature validation."""
    # Valid temperatures
    spec1 = AgentSpec(name="test", prompt_pack="test", response_model=dict, temperature=0.0)
    assert spec1.temperature == 0.0

    spec2 = AgentSpec(name="test", prompt_pack="test", response_model=dict, temperature=2.0)
    assert spec2.temperature == 2.0

    # Invalid temperature
    with pytest.raises(ValidationError):
        AgentSpec(name="test", prompt_pack="test", response_model=dict, temperature=2.5)


def test_agent_spec_token_budget_validation():
    """Test token budget validation."""
    # Valid budget
    spec = AgentSpec(name="test", prompt_pack="test", response_model=dict, token_budget=1000)
    assert spec.token_budget == 1000

    # Invalid budget (negative)
    with pytest.raises(ValidationError):
        AgentSpec(name="test", prompt_pack="test", response_model=dict, token_budget=-100)


def test_agent_spec_max_attempts_validation():
    """Test max schema repair attempts validation."""
    # Valid attempts
    spec = AgentSpec(
        name="test",
        prompt_pack="test",
        response_model=dict,
        max_schema_repair_attempts=5,
    )
    assert spec.max_schema_repair_attempts == 5

    # Invalid attempts (negative)
    with pytest.raises(ValidationError):
        AgentSpec(
            name="test",
            prompt_pack="test",
            response_model=dict,
            max_schema_repair_attempts=-1,
        )


def test_agent_mode_enum():
    """Test AgentMode enum values."""
    assert AgentMode.ONESHOT == "oneshot"
    assert AgentMode.CONVERSATIONAL == "conversational"

    # Should only have 2 modes
    modes = list(AgentMode)
    assert len(modes) == 2


def test_agent_spec_with_pydantic_response_model():
    """Test agent spec with Pydantic model."""
    from pydantic import BaseModel

    class TestResponse(BaseModel):
        result: str

    spec = AgentSpec(name="test", prompt_pack="test", response_model=TestResponse)

    assert spec.response_model == TestResponse


def test_agent_spec_serialization():
    """Test agent spec can be serialized."""
    spec = AgentSpec(
        name="test",
        prompt_pack="test",
        response_model=dict,
        temperature=0.8,
    )

    # Should be able to convert to dict
    data = spec.model_dump()

    assert data["name"] == "test"
    assert data["prompt_pack"] == "test"
    assert data["temperature"] == 0.8
