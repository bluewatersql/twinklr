"""Unit tests for iteration controller models."""

from twinklr.core.agents.shared.judge.models import (
    IterationState,
    JudgeVerdict,
    RevisionRequest,
    VerdictStatus,
)


class TestIterationConfig:
    """Tests for IterationConfig model."""

    def test_valid_config_minimal(self):
        """Test creating valid config with defaults."""
        from twinklr.core.agents.shared.judge.controller import IterationConfig

        config = IterationConfig()

        assert config.max_iterations == 3
        assert config.token_budget is None
        assert config.max_feedback_entries == 25
        assert config.include_feedback_in_prompt is True
        assert config.approval_score_threshold == 7.0
        assert config.soft_fail_score_threshold == 5.0

    def test_valid_config_full(self):
        """Test creating valid config with all fields."""
        from twinklr.core.agents.shared.judge.controller import IterationConfig

        config = IterationConfig(
            max_iterations=5,
            token_budget=100000,
            max_feedback_entries=10,
            include_feedback_in_prompt=False,
            approval_score_threshold=8.0,
            soft_fail_score_threshold=6.0,
        )

        assert config.max_iterations == 5
        assert config.token_budget == 100000
        assert config.max_feedback_entries == 10
        assert config.include_feedback_in_prompt is False
        assert config.approval_score_threshold == 8.0
        assert config.soft_fail_score_threshold == 6.0

    def test_valid_context_defaults(self):
        """Test creating valid context with defaults."""
        from twinklr.core.agents.shared.judge.controller import IterationContext

        context = IterationContext()

        assert context.current_iteration == 0
        assert context.state == IterationState.NOT_STARTED
        assert context.verdicts == []
        assert context.revision_requests == []
        assert context.total_tokens_used == 0
        assert context.termination_reason is None
        assert context.final_verdict is None

    def test_add_verdict(self):
        """Test add_verdict method."""
        from twinklr.core.agents.shared.judge.controller import IterationContext

        context = IterationContext()

        verdict = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.0,
            confidence=0.9,
            overall_assessment="Good",
            feedback_for_planner="Keep it up",
            iteration=1,
        )

        context.add_verdict(verdict)

        assert len(context.verdicts) == 1
        assert context.final_verdict == verdict

    def test_add_revision_request(self):
        """Test add_revision_request method."""
        from twinklr.core.agents.shared.judge.controller import IterationContext

        context = IterationContext()

        request = RevisionRequest(
            priority="HIGH",
            focus_areas=["Timing"],
            specific_fixes=["Fix overlap"],
            context_for_planner="Focus on timing",
        )

        context.add_revision_request(request)

        assert len(context.revision_requests) == 1

    def test_increment_iteration(self):
        """Test increment_iteration method."""
        from twinklr.core.agents.shared.judge.controller import IterationContext

        context = IterationContext()

        context.increment_iteration()
        assert context.current_iteration == 1

        context.increment_iteration()
        assert context.current_iteration == 2

    def test_add_tokens(self):
        """Test add_tokens method."""
        from twinklr.core.agents.shared.judge.controller import IterationContext

        context = IterationContext()

        context.add_tokens(100)
        assert context.total_tokens_used == 100

        context.add_tokens(50)
        assert context.total_tokens_used == 150

    def test_valid_result_success(self):
        """Test creating valid result for success case."""
        from twinklr.core.agents.shared.judge.controller import (
            IterationContext,
            IterationResult,
        )

        context = IterationContext()
        context.update_state(IterationState.COMPLETE)

        plan = {"test": "plan"}

        result = IterationResult(
            success=True,
            plan=plan,
            context=context,
        )

        assert result.success is True
        assert result.plan == plan
        assert result.context == context
        assert result.error_message is None

    def test_valid_result_failure(self):
        """Test creating valid result for failure case."""
        from twinklr.core.agents.shared.judge.controller import (
            IterationContext,
            IterationResult,
        )

        context = IterationContext()
        context.update_state(IterationState.FAILED)

        result = IterationResult(
            success=False,
            plan=None,
            context=context,
            error_message="Planner failed",
        )

        assert result.success is False
        assert result.plan is None
        assert result.context == context
        assert result.error_message == "Planner failed"
