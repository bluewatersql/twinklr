"""Tests for TokenBudgetManager component."""

from __future__ import annotations

import pytest

from blinkb0t.core.agents.moving_heads.context import Stage
from blinkb0t.core.agents.moving_heads.token_budget_manager import (
    BudgetExceededError,
    BudgetStatus,
    StageTokenUsage,
    TokenBudgetManager,
    TokenBudgetReport,
)
from blinkb0t.core.config.models import AgentOrchestrationConfig, JobConfig


@pytest.fixture
def job_config() -> JobConfig:
    """Create test job config."""
    return JobConfig(
        openai_api_key="test-key",
        agent=AgentOrchestrationConfig(
            token_budget=20000,
            enforce_token_budget=True,
        ),
    )


@pytest.fixture
def manager(job_config: JobConfig) -> TokenBudgetManager:
    """Create token budget manager."""
    return TokenBudgetManager(job_config=job_config)


class TestStageTokenUsage:
    """Test StageTokenUsage dataclass."""

    def test_stage_token_usage_creation(self):
        """Test creating StageTokenUsage."""
        usage = StageTokenUsage(
            stage=Stage.PLAN,
            input_tokens=4000,
            output_tokens=1500,
            total_tokens=5500,
        )

        assert usage.stage == Stage.PLAN
        assert usage.input_tokens == 4000
        assert usage.output_tokens == 1500
        assert usage.total_tokens == 5500

    def test_cost_estimate_usd(self):
        """Test cost estimation in USD."""
        usage = StageTokenUsage(
            stage=Stage.PLAN,
            input_tokens=4000,
            output_tokens=1500,
            total_tokens=5500,
        )

        cost = usage.cost_estimate_usd

        # Rough calculation: (4000/1M * 5) + (1500/1M * 15)
        expected = (4000 / 1_000_000 * 5.0) + (1500 / 1_000_000 * 15.0)
        assert abs(cost - expected) < 0.0001


class TestBudgetStatus:
    """Test BudgetStatus dataclass."""

    def test_budget_status_creation(self):
        """Test creating BudgetStatus."""
        status = BudgetStatus(
            total_used=5500,
            total_budget=20000,
            remaining=14500,
            used_pct=27.5,
            can_continue=True,
        )

        assert status.total_used == 5500
        assert status.total_budget == 20000
        assert status.remaining == 14500
        assert status.used_pct == 27.5
        assert status.can_continue is True


class TestTokenBudgetReport:
    """Test TokenBudgetReport dataclass."""

    def test_report_creation(self):
        """Test creating TokenBudgetReport."""
        report = TokenBudgetReport(
            stage_usage=[],
            total_used=5500,
            total_budget=20000,
            budget_exceeded=False,
            iterations=1,
        )

        assert report.total_used == 5500
        assert report.budget_exceeded is False
        assert report.iterations == 1

    def test_total_cost_estimate(self):
        """Test total cost estimation."""
        usage1 = StageTokenUsage(
            stage=Stage.PLAN,
            input_tokens=4000,
            output_tokens=1500,
            total_tokens=5500,
        )
        usage2 = StageTokenUsage(
            stage=Stage.IMPLEMENTATION,
            input_tokens=6000,
            output_tokens=2500,
            total_tokens=8500,
        )

        report = TokenBudgetReport(
            stage_usage=[usage1, usage2],
            total_used=14000,
            total_budget=20000,
            budget_exceeded=False,
            iterations=1,
        )

        total_cost = report.total_cost_estimate_usd
        expected = usage1.cost_estimate_usd + usage2.cost_estimate_usd

        assert abs(total_cost - expected) < 0.0001


class TestTokenBudgetManagerInit:
    """Test TokenBudgetManager initialization."""

    def test_init(self, manager: TokenBudgetManager, job_config: JobConfig):
        """Test basic initialization."""
        assert manager.job_config == job_config
        assert manager.total_budget == 20000
        assert manager.enforce_budget is True
        assert manager.total_used == 0
        assert manager.iterations == 0
        assert len(manager.stage_usage) == 0

    def test_stage_estimates_exist(self, manager: TokenBudgetManager):
        """Test that stage estimates are defined."""
        assert Stage.PLAN in manager.stage_estimates
        assert Stage.VALIDATE in manager.stage_estimates
        assert Stage.IMPLEMENTATION in manager.stage_estimates
        assert Stage.JUDGE in manager.stage_estimates
        assert Stage.REFINEMENT in manager.stage_estimates

        # Validate stage has 0 tokens (no LLM call)
        assert manager.stage_estimates[Stage.VALIDATE] == 0


class TestTokenBudgetManagerRecordStage:
    """Test recording stage usage."""

    def test_record_stage(self, manager: TokenBudgetManager):
        """Test recording stage usage."""
        manager.record_stage(Stage.PLAN, 4000, 1500)

        assert manager.total_used == 5500
        assert len(manager.stage_usage) == 1
        assert manager.stage_usage[0].stage == Stage.PLAN
        assert manager.stage_usage[0].input_tokens == 4000
        assert manager.stage_usage[0].output_tokens == 1500
        assert manager.stage_usage[0].total_tokens == 5500

    def test_record_multiple_stages(self, manager: TokenBudgetManager):
        """Test recording multiple stages."""
        manager.record_stage(Stage.PLAN, 4000, 1500)
        manager.record_stage(Stage.IMPLEMENTATION, 6000, 2500)

        assert manager.total_used == 14000
        assert len(manager.stage_usage) == 2

    def test_record_stage_budget_exceeded_enforced(self, job_config: JobConfig):
        """Test budget exceeded with enforcement."""
        job_config.agent.enforce_token_budget = True
        manager = TokenBudgetManager(job_config=job_config)

        with pytest.raises(BudgetExceededError) as exc_info:
            manager.record_stage(Stage.PLAN, 15000, 6000)

        assert "Token budget exceeded" in str(exc_info.value)
        assert "used 21000" in str(exc_info.value)

    def test_record_stage_budget_exceeded_warning_only(self, job_config: JobConfig):
        """Test budget exceeded without enforcement (warning only)."""
        job_config.agent.enforce_token_budget = False
        manager = TokenBudgetManager(job_config=job_config)

        # Should not raise, just warn
        manager.record_stage(Stage.PLAN, 15000, 6000)

        assert manager.total_used == 21000
        assert len(manager.stage_usage) == 1


class TestTokenBudgetManagerGetStatus:
    """Test getting budget status."""

    def test_get_status_empty(self, manager: TokenBudgetManager):
        """Test getting status with no usage."""
        status = manager.get_status()

        assert status.total_used == 0
        assert status.total_budget == 20000
        assert status.remaining == 20000
        assert status.used_pct == 0.0
        assert status.can_continue is True

    def test_get_status_with_usage(self, manager: TokenBudgetManager):
        """Test getting status after recording usage."""
        manager.record_stage(Stage.PLAN, 4000, 1500)

        status = manager.get_status()

        assert status.total_used == 5500
        assert status.remaining == 14500
        assert status.used_pct == pytest.approx(27.5)
        assert status.can_continue is True

    def test_get_status_budget_exhausted(self, job_config: JobConfig):
        """Test getting status when budget is exhausted."""
        # Turn off enforcement to test status after exceeding budget
        job_config.agent.enforce_token_budget = False
        manager = TokenBudgetManager(job_config=job_config)

        manager.record_stage(Stage.PLAN, 15000, 6000)

        status = manager.get_status()

        assert status.total_used == 21000
        assert status.remaining == -1000
        assert status.used_pct == pytest.approx(105.0)
        # can_continue is True when remaining <= 0 but enforcement is off
        assert status.can_continue is True


class TestTokenBudgetManagerCanAffordRetry:
    """Test retry affordability checks."""

    def test_can_afford_retry_with_budget(self, manager: TokenBudgetManager):
        """Test retry affordability with sufficient budget."""
        manager.record_stage(Stage.PLAN, 4000, 1500)

        # Should be able to afford another plan stage
        assert manager.can_afford_retry(Stage.PLAN) is True

    def test_can_afford_retry_insufficient_budget(self, manager: TokenBudgetManager):
        """Test retry affordability with insufficient budget."""
        # Use most of the budget
        manager.record_stage(Stage.PLAN, 8000, 3000)
        manager.record_stage(Stage.IMPLEMENTATION, 7000, 2000)

        # total_used = 20000, remaining = 0
        # Can't afford implementation retry (estimate ~8500 * 1.2 = 10200)
        assert manager.can_afford_retry(Stage.IMPLEMENTATION) is False

    def test_can_afford_retry_includes_buffer(self, manager: TokenBudgetManager):
        """Test that retry check includes buffer."""
        # Plan estimate is 5500, with 20% buffer = 6600
        # Leave exactly 6000 tokens
        manager.record_stage(Stage.PLAN, 10000, 4000)  # 14000 used, 6000 remaining

        # Should not be affordable (6000 < 6600)
        assert manager.can_afford_retry(Stage.PLAN) is False


class TestTokenBudgetManagerPredictRemainingCost:
    """Test remaining cost prediction."""

    def test_predict_remaining_cost(self, manager: TokenBudgetManager):
        """Test predicting remaining cost."""
        remaining_stages = [Stage.IMPLEMENTATION, Stage.JUDGE]
        predicted = manager.predict_remaining_cost(remaining_stages)

        # Should be sum of estimates + buffer
        expected_base = (
            manager.stage_estimates[Stage.IMPLEMENTATION] + manager.stage_estimates[Stage.JUDGE]
        )
        expected_with_buffer = int(expected_base * (1 + manager.buffer_pct))

        assert predicted == expected_with_buffer

    def test_predict_remaining_cost_no_buffer(self, manager: TokenBudgetManager):
        """Test predicting cost without buffer."""
        remaining_stages = [Stage.IMPLEMENTATION, Stage.JUDGE]
        predicted = manager.predict_remaining_cost(remaining_stages, include_buffer=False)

        # Should be sum of estimates without buffer
        expected = (
            manager.stage_estimates[Stage.IMPLEMENTATION] + manager.stage_estimates[Stage.JUDGE]
        )

        assert predicted == expected

    def test_predict_empty_stages(self, manager: TokenBudgetManager):
        """Test predicting cost for no stages."""
        predicted = manager.predict_remaining_cost([])

        assert predicted == 0


class TestTokenBudgetManagerGetReport:
    """Test getting budget report."""

    def test_get_report_empty(self, manager: TokenBudgetManager):
        """Test getting report with no usage."""
        report = manager.get_report()

        assert report.total_used == 0
        assert report.total_budget == 20000
        assert report.budget_exceeded is False
        assert report.iterations == 0
        assert len(report.stage_usage) == 0

    def test_get_report_with_usage(self, manager: TokenBudgetManager):
        """Test getting report after recording usage."""
        manager.record_stage(Stage.PLAN, 4000, 1500)
        manager.record_stage(Stage.IMPLEMENTATION, 6000, 2500)
        manager.increment_iteration()

        report = manager.get_report()

        assert report.total_used == 14000
        assert report.budget_exceeded is False
        assert report.iterations == 1
        assert len(report.stage_usage) == 2

    def test_get_report_budget_exceeded(self, job_config: JobConfig):
        """Test getting report when budget exceeded."""
        # Turn off enforcement to test report after exceeding budget
        job_config.agent.enforce_token_budget = False
        manager = TokenBudgetManager(job_config=job_config)

        manager.record_stage(Stage.PLAN, 15000, 6000)

        report = manager.get_report()

        assert report.budget_exceeded is True


class TestTokenBudgetManagerIterations:
    """Test iteration management."""

    def test_increment_iteration(self, manager: TokenBudgetManager):
        """Test incrementing iteration counter."""
        assert manager.iterations == 0

        manager.increment_iteration()
        assert manager.iterations == 1

        manager.increment_iteration()
        assert manager.iterations == 2

    def test_iterations_in_report(self, manager: TokenBudgetManager):
        """Test iterations appear in report."""
        manager.increment_iteration()
        manager.increment_iteration()

        report = manager.get_report()
        assert report.iterations == 2


class TestTokenBudgetManagerReset:
    """Test reset functionality."""

    def test_reset(self, manager: TokenBudgetManager):
        """Test resetting budget tracking."""
        manager.record_stage(Stage.PLAN, 4000, 1500)
        manager.increment_iteration()

        assert manager.total_used > 0
        assert manager.iterations > 0

        manager.reset()

        assert manager.total_used == 0
        assert manager.iterations == 0
        assert len(manager.stage_usage) == 0
