"""Tests for moving heads agent specs."""

from blinkb0t.core.agents.sequencer.moving_heads.models import (
    ChoreographyPlan,
    JudgeResponse,
)
from blinkb0t.core.agents.sequencer.moving_heads.specs import (
    get_judge_spec,
    get_planner_spec,
)
from blinkb0t.core.agents.spec import AgentMode


def test_get_planner_spec():
    """Test planner spec factory."""
    spec = get_planner_spec()

    assert spec.name == "planner"
    assert spec.prompt_pack == "planner"
    assert spec.response_model == ChoreographyPlan
    assert spec.mode == AgentMode.CONVERSATIONAL  # Planner is conversational
    assert spec.model == "gpt-5.2"  # Use stronger model for creative work
    assert spec.temperature > 0.5  # Creative temperature
    assert spec.max_schema_repair_attempts >= 2


def test_get_planner_spec_with_overrides():
    """Test planner spec with custom parameters."""
    spec = get_planner_spec(model="gpt-5.2-mini", temperature=0.5, token_budget=5000)

    assert spec.model == "gpt-5.2-mini"
    assert spec.temperature == 0.5
    assert spec.token_budget == 5000


def test_get_judge_spec():
    """Test judge spec factory."""
    spec = get_judge_spec()

    assert spec.name == "judge"
    assert spec.prompt_pack == "judge"
    assert spec.response_model == JudgeResponse
    assert spec.mode == AgentMode.ONESHOT  # Judge is stateless
    assert spec.temperature > 0.3  # Creative evaluation
    assert spec.max_schema_repair_attempts >= 2


def test_get_judge_spec_with_overrides():
    """Test judge spec with custom parameters."""
    spec = get_judge_spec(model="gpt-5.2-mini", temperature=0.6, token_budget=3000)

    assert spec.model == "gpt-5.2-mini"
    assert spec.temperature == 0.6
    assert spec.token_budget == 3000


def test_all_specs_have_different_names():
    """Test all specs have unique names."""
    planner = get_planner_spec()
    judge = get_judge_spec()

    names = {planner.name, judge.name}
    assert len(names) == 2  # All unique


def test_all_specs_have_different_prompt_packs():
    """Test all specs use different prompt packs."""
    planner = get_planner_spec()
    judge = get_judge_spec()

    packs = {planner.prompt_pack, judge.prompt_pack}
    assert len(packs) == 2  # All unique


def test_all_specs_have_different_response_models():
    """Test all specs use different response models."""
    planner = get_planner_spec()
    judge = get_judge_spec()

    models = {planner.response_model, judge.response_model}
    assert len(models) == 2  # All unique


def test_specs_are_immutable():
    """Test specs are immutable once created."""
    spec = get_planner_spec()

    # Should not be able to modify
    from pydantic import ValidationError
    import pytest

    with pytest.raises((ValidationError, AttributeError)):
        spec.name = "modified"


def test_planner_conversational_judge_oneshot():
    """Test mode configuration matches design."""
    planner = get_planner_spec()
    judge = get_judge_spec()

    # Planner maintains conversation context across iterations
    assert planner.mode == AgentMode.CONVERSATIONAL

    # Judge is stateless
    assert judge.mode == AgentMode.ONESHOT
