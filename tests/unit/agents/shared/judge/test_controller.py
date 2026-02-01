"""Unit tests for StandardIterationController."""

import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

from twinklr.core.agents.feedback import FeedbackManager
from twinklr.core.agents.result import AgentResult
from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    StandardIterationController,
)
from twinklr.core.agents.shared.judge.models import (
    IterationState,
    JudgeVerdict,
    RevisionPriority,
    VerdictStatus,
)
from twinklr.core.agents.spec import AgentSpec


@pytest.fixture
def iteration_config():
    """Create default iteration config."""
    return IterationConfig(
        max_iterations=3,
        token_budget=None,
        max_feedback_entries=25,
        include_feedback_in_prompt=True,
        approval_score_threshold=7.0,
        soft_fail_score_threshold=5.0,
    )


@pytest.fixture
def feedback_manager():
    """Create feedback manager."""
    return FeedbackManager(max_entries=25)


@pytest.fixture
def planner_spec():
    """Create mock planner spec."""
    return AgentSpec(
        name="test_planner",
        prompt_pack="test_planner",
        response_model=dict,  # Simple dict for testing
        model="gpt-4",
        temperature=0.7,
    )


@pytest.fixture
def judge_spec():
    """Create mock judge spec."""
    return AgentSpec(
        name="test_judge",
        prompt_pack="test_judge",
        response_model=JudgeVerdict,
        model="gpt-4",
        temperature=0.3,
    )


@pytest.fixture
def mock_provider():
    """Create mock LLM provider."""
    provider = Mock()
    provider.get_token_usage = Mock(return_value=Mock(total_tokens=1000))
    return provider


@pytest.fixture
def mock_llm_logger():
    """Create mock LLM logger."""
    logger = Mock()
    logger.log_call = AsyncMock()
    return logger


class TestStandardIterationControllerInit:
    """Tests for StandardIterationController initialization."""

    def test_init_with_all_dependencies(self, iteration_config, feedback_manager):
        """Test initialization with all dependencies."""
        controller: StandardIterationController[dict] = StandardIterationController(
            config=iteration_config,
            feedback_manager=feedback_manager,
        )

        assert controller.config == iteration_config
        assert controller.feedback == feedback_manager
        assert isinstance(controller.logger, logging.Logger)

    def test_init_stores_dependencies(self, iteration_config, feedback_manager):
        """Test that dependencies are stored correctly."""
        controller: StandardIterationController[dict] = StandardIterationController(
            config=iteration_config,
            feedback_manager=feedback_manager,
        )

        # Verify config is immutable (frozen)
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            controller.config.max_iterations = 5  # type: ignore[misc]


class TestStandardIterationControllerSingleIterationSuccess:
    """Tests for single iteration success (APPROVE on first try)."""

    @pytest.mark.asyncio
    async def test_single_iteration_approve(
        self,
        iteration_config,
        feedback_manager,
        planner_spec,
        judge_spec,
        mock_provider,
        mock_llm_logger,
    ):
        """Test successful approval on first iteration."""
        controller: StandardIterationController[dict] = StandardIterationController(
            config=iteration_config,
            feedback_manager=feedback_manager,
        )

        # Mock plan
        test_plan = {"sections": [{"name": "intro", "bars": [0, 8]}]}

        # Mock planner result
        planner_result = AgentResult(
            duration_seconds=0.1,
            success=True,
            data=test_plan,
            tokens_used=500,
        )

        # Mock judge verdict (APPROVE)
        judge_verdict = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.5,
            confidence=0.9,
            overall_assessment="Excellent plan",
            feedback_for_planner="Great work",
            iteration=0,
        )

        judge_result = AgentResult(
            duration_seconds=0.1,
            success=True,
            data=judge_verdict,
            tokens_used=300,
        )

        # Mock validator (no errors)
        validator = Mock(return_value=[])

        # Mock AsyncAgentRunner
        with patch("twinklr.core.agents.shared.judge.controller.AsyncAgentRunner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.run = AsyncMock(side_effect=[planner_result, judge_result])

            # Run controller
            result = await controller.run(
                planner_spec=planner_spec,
                judge_spec=judge_spec,
                initial_variables={"context": "test"},
                validator=validator,
                provider=mock_provider,
                llm_logger=mock_llm_logger,
            )

        # Verify result
        assert result.success is True
        assert result.plan == test_plan
        assert result.context.current_iteration == 1
        assert result.context.state == IterationState.COMPLETE
        assert result.context.total_tokens_used == 800  # 500 + 300
        assert len(result.context.verdicts) == 1
        assert result.context.final_verdict == judge_verdict


class TestStandardIterationControllerMultiIterationRefinement:
    """Tests for multi-iteration refinement (SOFT_FAIL → APPROVE)."""

    @pytest.mark.asyncio
    async def test_soft_fail_then_approve(
        self,
        iteration_config,
        feedback_manager,
        planner_spec,
        judge_spec,
        mock_provider,
        mock_llm_logger,
    ):
        """Test refinement loop: SOFT_FAIL → APPROVE."""
        controller: StandardIterationController[dict] = StandardIterationController(
            config=iteration_config,
            feedback_manager=feedback_manager,
        )

        plan_v1 = {"version": 1}
        plan_v2 = {"version": 2}

        planner_result_1 = AgentResult(
            duration_seconds=0.1, success=True, data=plan_v1, tokens_used=500
        )
        planner_result_2 = AgentResult(
            duration_seconds=0.1, success=True, data=plan_v2, tokens_used=600
        )

        # First verdict: SOFT_FAIL
        verdict_1 = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.8,
            overall_assessment="Needs improvement",
            feedback_for_planner="Add more variety",
            iteration=0,
        )

        # Second verdict: APPROVE
        verdict_2 = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.0,
            confidence=0.9,
            overall_assessment="Much better",
            feedback_for_planner="Excellent",
            iteration=1,
        )

        judge_result_1 = AgentResult(
            duration_seconds=0.1, success=True, data=verdict_1, tokens_used=300
        )
        judge_result_2 = AgentResult(
            duration_seconds=0.1, success=True, data=verdict_2, tokens_used=300
        )

        validator = Mock(return_value=[])

        with patch("twinklr.core.agents.shared.judge.controller.AsyncAgentRunner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.run = AsyncMock(
                side_effect=[
                    planner_result_1,
                    judge_result_1,
                    planner_result_2,
                    judge_result_2,
                ]
            )

            result = await controller.run(
                planner_spec=planner_spec,
                judge_spec=judge_spec,
                initial_variables={},
                validator=validator,
                provider=mock_provider,
                llm_logger=mock_llm_logger,
            )

        # Verify result
        assert result.success is True
        assert result.plan == plan_v2  # Final plan
        assert result.context.current_iteration == 2
        assert result.context.state == IterationState.COMPLETE
        assert len(result.context.verdicts) == 2
        assert len(result.context.revision_requests) == 1  # One revision request from SOFT_FAIL


class TestStandardIterationControllerTermination:
    """Tests for termination conditions."""

    @pytest.mark.asyncio
    async def test_max_iterations_reached(
        self,
        feedback_manager,
        planner_spec,
        judge_spec,
        mock_provider,
        mock_llm_logger,
    ):
        """Test max iterations termination."""
        config = IterationConfig(max_iterations=2)  # Only 2 iterations
        controller: StandardIterationController[dict] = StandardIterationController(
            config=config,
            feedback_manager=feedback_manager,
        )

        test_plan = {"test": "plan"}
        planner_result = AgentResult(
            duration_seconds=0.1, success=True, data=test_plan, tokens_used=500
        )

        # Both verdicts are SOFT_FAIL
        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.8,
            overall_assessment="Needs work",
            feedback_for_planner="Improve",
            iteration=0,
        )
        judge_result = AgentResult(
            duration_seconds=0.1, success=True, data=verdict, tokens_used=300
        )

        validator = Mock(return_value=[])

        with patch("twinklr.core.agents.shared.judge.controller.AsyncAgentRunner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.run = AsyncMock(
                side_effect=[
                    planner_result,
                    judge_result,
                    planner_result,
                    judge_result,
                ]
            )

            result = await controller.run(
                planner_spec=planner_spec,
                judge_spec=judge_spec,
                initial_variables={},
                validator=validator,
                provider=mock_provider,
                llm_logger=mock_llm_logger,
            )

        # Verify termination
        assert result.success is False  # Did not approve
        assert result.context.state == IterationState.MAX_ITERATIONS_REACHED
        assert result.context.current_iteration == 2
        assert result.error_message is not None
        assert "max iterations" in result.error_message.lower()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_token_budget_exceeded(
        self,
        feedback_manager,
        planner_spec,
        judge_spec,
        mock_provider,
        mock_llm_logger,
    ):
        """Test token budget termination."""
        config = IterationConfig(
            max_iterations=10,
            token_budget=1000,  # Low budget
        )
        controller: StandardIterationController[dict] = StandardIterationController(
            config=config,
            feedback_manager=feedback_manager,
        )

        test_plan = {"test": "plan"}
        planner_result = AgentResult(
            duration_seconds=0.1, success=True, data=test_plan, tokens_used=600
        )

        verdict = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.8,
            overall_assessment="Needs work",
            feedback_for_planner="Improve",
            iteration=0,
        )
        judge_result = AgentResult(
            duration_seconds=0.1, success=True, data=verdict, tokens_used=500
        )  # Total: 1100

        validator = Mock(return_value=[])

        with patch("twinklr.core.agents.shared.judge.controller.AsyncAgentRunner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.run = AsyncMock(side_effect=[planner_result, judge_result])

            result = await controller.run(
                planner_spec=planner_spec,
                judge_spec=judge_spec,
                initial_variables={},
                validator=validator,
                provider=mock_provider,
                llm_logger=mock_llm_logger,
            )

        # Verify termination
        assert result.success is False
        assert result.context.state == IterationState.TOKEN_BUDGET_EXCEEDED
        assert result.context.total_tokens_used >= 1000
        assert "token budget" in result.error_message.lower()  # type: ignore[union-attr]


class TestStandardIterationControllerValidationFailure:
    """Tests for validation failure handling."""

    @pytest.mark.asyncio
    async def test_validation_failure_then_success(
        self,
        iteration_config,
        feedback_manager,
        planner_spec,
        judge_spec,
        mock_provider,
        mock_llm_logger,
    ):
        """Test validation failure followed by success."""
        controller: StandardIterationController[dict] = StandardIterationController(
            config=iteration_config,
            feedback_manager=feedback_manager,
        )

        plan_v1 = {"invalid": "plan"}
        plan_v2 = {"valid": "plan"}

        planner_result_1 = AgentResult(
            duration_seconds=0.1, success=True, data=plan_v1, tokens_used=500
        )
        planner_result_2 = AgentResult(
            duration_seconds=0.1, success=True, data=plan_v2, tokens_used=500
        )

        verdict = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.0,
            confidence=0.9,
            overall_assessment="Good",
            feedback_for_planner="Good work",
            iteration=1,
        )
        judge_result = AgentResult(
            duration_seconds=0.1, success=True, data=verdict, tokens_used=300
        )

        # Validator fails first time, succeeds second time
        validator = Mock(side_effect=[["Missing required field"], []])

        with patch("twinklr.core.agents.shared.judge.controller.AsyncAgentRunner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.run = AsyncMock(
                side_effect=[
                    planner_result_1,
                    planner_result_2,
                    judge_result,
                ]
            )

            result = await controller.run(
                planner_spec=planner_spec,
                judge_spec=judge_spec,
                initial_variables={},
                validator=validator,
                provider=mock_provider,
                llm_logger=mock_llm_logger,
            )

        # Verify result
        assert result.success is True
        assert result.plan == plan_v2
        assert len(result.context.revision_requests) == 1  # One from validation failure
        assert result.context.revision_requests[0].priority == RevisionPriority.CRITICAL


class TestStandardIterationControllerFailureHandling:
    """Tests for planner/judge failure handling."""

    @pytest.mark.asyncio
    async def test_planner_failure(
        self,
        iteration_config,
        feedback_manager,
        planner_spec,
        judge_spec,
        mock_provider,
        mock_llm_logger,
    ):
        """Test planner failure handling."""
        controller: StandardIterationController[dict] = StandardIterationController(
            config=iteration_config,
            feedback_manager=feedback_manager,
        )

        planner_result = AgentResult(
            duration_seconds=0.1,
            success=False,
            data=None,
            tokens_used=0,
            error_message="Planner failed: timeout",
        )

        validator = Mock(return_value=[])

        with patch("twinklr.core.agents.shared.judge.controller.AsyncAgentRunner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.run = AsyncMock(return_value=planner_result)

            result = await controller.run(
                planner_spec=planner_spec,
                judge_spec=judge_spec,
                initial_variables={},
                validator=validator,
                provider=mock_provider,
                llm_logger=mock_llm_logger,
            )

        # Verify failure
        assert result.success is False
        assert result.plan is None
        assert result.context.state == IterationState.FAILED
        assert "planner failed" in result.error_message.lower()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_judge_failure(
        self,
        iteration_config,
        feedback_manager,
        planner_spec,
        judge_spec,
        mock_provider,
        mock_llm_logger,
    ):
        """Test judge failure handling."""
        controller: StandardIterationController[dict] = StandardIterationController(
            config=iteration_config,
            feedback_manager=feedback_manager,
        )

        test_plan = {"test": "plan"}
        planner_result = AgentResult(
            duration_seconds=0.1, success=True, data=test_plan, tokens_used=500
        )

        judge_result = AgentResult(
            duration_seconds=0.1,
            success=False,
            data=None,
            tokens_used=0,
            error_message="Judge failed: schema error",
        )

        validator = Mock(return_value=[])

        with patch("twinklr.core.agents.shared.judge.controller.AsyncAgentRunner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.run = AsyncMock(side_effect=[planner_result, judge_result])

            result = await controller.run(
                planner_spec=planner_spec,
                judge_spec=judge_spec,
                initial_variables={},
                validator=validator,
                provider=mock_provider,
                llm_logger=mock_llm_logger,
            )

        # Verify failure
        assert result.success is False
        assert result.plan == test_plan  # Plan was generated
        assert result.context.state == IterationState.FAILED
        assert "judge failed" in result.error_message.lower()  # type: ignore[union-attr]


class TestStandardIterationControllerFeedbackIntegration:
    """Tests for feedback integration."""

    @pytest.mark.asyncio
    async def test_feedback_included_in_planner_variables(
        self,
        iteration_config,
        feedback_manager,
        planner_spec,
        judge_spec,
        mock_provider,
        mock_llm_logger,
    ):
        """Test that feedback is included in planner variables on iteration > 0."""
        controller: StandardIterationController[dict] = StandardIterationController(
            config=iteration_config,
            feedback_manager=feedback_manager,
        )

        plan_v1 = {"version": 1}
        plan_v2 = {"version": 2}

        planner_result_1 = AgentResult(
            duration_seconds=0.1, success=True, data=plan_v1, tokens_used=500
        )
        planner_result_2 = AgentResult(
            duration_seconds=0.1, success=True, data=plan_v2, tokens_used=500
        )

        verdict_1 = JudgeVerdict(
            status=VerdictStatus.SOFT_FAIL,
            score=6.0,
            confidence=0.8,
            overall_assessment="Needs work",
            feedback_for_planner="Add variety",
            iteration=0,
        )

        verdict_2 = JudgeVerdict(
            status=VerdictStatus.APPROVE,
            score=8.0,
            confidence=0.9,
            overall_assessment="Good",
            feedback_for_planner="Good work",
            iteration=1,
        )

        judge_result_1 = AgentResult(
            duration_seconds=0.1, success=True, data=verdict_1, tokens_used=300
        )
        judge_result_2 = AgentResult(
            duration_seconds=0.1, success=True, data=verdict_2, tokens_used=300
        )

        validator = Mock(return_value=[])

        with patch("twinklr.core.agents.shared.judge.controller.AsyncAgentRunner") as MockRunner:
            mock_runner = MockRunner.return_value
            mock_runner.run = AsyncMock(
                side_effect=[
                    planner_result_1,
                    judge_result_1,
                    planner_result_2,
                    judge_result_2,
                ]
            )

            await controller.run(
                planner_spec=planner_spec,
                judge_spec=judge_spec,
                initial_variables={"context": "test"},
                validator=validator,
                provider=mock_provider,
                llm_logger=mock_llm_logger,
            )

        # Verify runner was called with feedback on second iteration
        calls = mock_runner.run.call_args_list
        assert len(calls) == 4

        # First planner call (iteration 0) - no feedback
        first_planner_vars = calls[0][1]["variables"]
        assert "feedback" not in first_planner_vars or first_planner_vars["feedback"] is None

        # Second planner call (iteration 1) - has feedback
        second_planner_vars = calls[2][1]["variables"]
        assert "feedback" in second_planner_vars
        assert "iteration" in second_planner_vars
        assert second_planner_vars["iteration"] == 1
