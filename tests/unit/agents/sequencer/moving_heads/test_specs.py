"""Tests for moving heads agent specs.

V2 Migration: Uses JudgeVerdict (shared model) instead of JudgeResponse.
"""

from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.specs import (
    get_judge_spec,
    get_planner_spec,
)
from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.agents.spec import AgentMode


def test_get_planner_spec_defaults():
    """Test planner spec has sensible defaults."""
    spec = get_planner_spec()

    assert spec.response_model == ChoreographyPlan
    assert spec.mode == AgentMode.CONVERSATIONAL  # Planner is conversational
    assert spec.temperature > 0.5  # Creative temperature
    assert spec.max_schema_repair_attempts >= 2


def test_get_planner_spec_with_overrides():
    """Test planner spec with custom parameters."""
    spec = get_planner_spec(model="gpt-5.2-mini", temperature=0.5, token_budget=5000)

    assert spec.model == "gpt-5.2-mini"
    assert spec.temperature == 0.5
    assert spec.token_budget == 5000


def test_get_judge_spec_defaults():
    """Test judge spec has sensible defaults (V2: uses JudgeVerdict)."""
    spec = get_judge_spec()

    # V2: Uses shared JudgeVerdict instead of domain-specific JudgeResponse
    assert spec.response_model == JudgeVerdict
    assert spec.mode == AgentMode.ONESHOT  # Judge is stateless
    # V2: Lower temperature for more consistent evaluation
    assert spec.temperature <= 0.5
    assert spec.max_schema_repair_attempts >= 2


def test_get_judge_spec_with_overrides():
    """Test judge spec with custom parameters."""
    spec = get_judge_spec(model="gpt-5.2-mini", temperature=0.6, token_budget=3000)

    assert spec.model == "gpt-5.2-mini"
    assert spec.temperature == 0.6
    assert spec.token_budget == 3000


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
