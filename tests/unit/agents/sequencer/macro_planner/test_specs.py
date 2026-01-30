"""Unit tests for MacroPlanner agent specifications."""

from twinklr.core.agents.sequencer.macro_planner.models import MacroPlan
from twinklr.core.agents.sequencer.macro_planner.specs import (
    get_judge_spec,
    get_planner_spec,
)
from twinklr.core.agents.shared.judge.models import JudgeVerdict
from twinklr.core.agents.spec import AgentMode


class TestGetPlannerSpec:
    """Tests for get_planner_spec()."""

    def test_default_planner_spec(self):
        """Test planner spec with default parameters."""
        spec = get_planner_spec()

        assert spec.name == "macro_planner"
        assert spec.prompt_pack == "sequencer/macro_planner/prompts/planner"
        assert spec.response_model == MacroPlan
        assert spec.mode == AgentMode.ONESHOT
        assert spec.model == "gpt-5.2"
        assert spec.temperature == 0.7
        assert spec.max_schema_repair_attempts == 3
        assert spec.token_budget is None

    def test_custom_planner_spec(self):
        """Test planner spec with custom parameters."""
        spec = get_planner_spec(
            model="gpt-4o",
            temperature=0.8,
            token_budget=10000,
        )

        assert spec.model == "gpt-4o"
        assert spec.temperature == 0.8
        assert spec.token_budget == 10000

    def test_planner_spec_oneshot_mode(self):
        """Test that planner uses oneshot mode (controller handles feedback via prompts)."""
        spec = get_planner_spec()

        assert spec.mode == AgentMode.ONESHOT


class TestGetJudgeSpec:
    """Tests for get_judge_spec()."""

    def test_default_judge_spec(self):
        """Test judge spec with default parameters."""
        spec = get_judge_spec()

        assert spec.name == "macro_planner_judge"
        assert spec.prompt_pack == "sequencer/macro_planner/prompts/judge"
        assert spec.response_model == JudgeVerdict
        assert spec.mode == AgentMode.ONESHOT
        assert spec.model == "gpt-5.2"
        assert spec.temperature == 0.3
        assert spec.max_schema_repair_attempts == 2
        assert spec.token_budget is None

    def test_custom_judge_spec(self):
        """Test judge spec with custom parameters."""
        spec = get_judge_spec(
            model="gpt-4o",
            temperature=0.5,
            token_budget=5000,
        )

        assert spec.model == "gpt-4o"
        assert spec.temperature == 0.5
        assert spec.token_budget == 5000

    def test_judge_spec_oneshot_mode(self):
        """Test that judge uses oneshot mode (stateless)."""
        spec = get_judge_spec()

        assert spec.mode == AgentMode.ONESHOT
