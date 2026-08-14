"""Unit tests for StandardIterationController."""

from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from twinklr.core.agents.providers.base import (
    LLMResponse,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    IterationContext,
    StandardIterationController,
)
from twinklr.core.agents.shared.judge.feedback import FeedbackManager
from twinklr.core.agents.shared.judge.models import (
    JudgeVerdict,
    VerdictStatus,
)
from twinklr.core.agents.spec import AgentSpec

FIXTURES_PATH = Path(__file__).parents[4] / "fixtures" / "prompts"


def _verdict(*, score: float, iteration: int, issue: bool = False) -> dict[str, Any]:
    """Build one strict judge response for controller tests."""
    issues: list[dict[str, Any]] = []
    if issue:
        issues.append(
            {
                "issue_id": "VARIETY_LOW",
                "category": "VARIETY",
                "severity": "WARN",
                "location": {
                    "section_id": "verse_1",
                    "group_id": None,
                    "effect_id": None,
                    "bar_start": 1,
                    "bar_end": 4,
                    "field_path": "sections.0.template_id",
                },
                "rule": "DON'T repeat one template without variation",
                "message": "The first verse lacks visual variety.",
                "fix_hint": "Use a contrasting template in the first verse.",
                "acceptance_test": "The first verse uses at least two visual ideas.",
                "generic_example": None,
                "targeted_actions": [],
            }
        )
    status = (
        VerdictStatus.APPROVE.value
        if score >= 7.0
        else VerdictStatus.SOFT_FAIL.value
        if score >= 5.0
        else VerdictStatus.HARD_FAIL.value
    )
    return {
        "status": status,
        "score": score,
        "confidence": 0.9,
        "strengths": ["The timing is coherent."],
        "issues": issues,
        "feedback_for_planner": "Increase variety without losing the timing structure.",
        "iteration": iteration,
    }


class _LoopProvider:
    """Deterministic planner/judge provider with call recording."""

    provider_type = ProviderType.OPENAI

    def __init__(self, judge_scores: list[float], *, first_issue: bool = False) -> None:
        self.judge_scores = list(judge_scores)
        self.first_issue = first_issue
        self.planner_calls = 0
        self.judge_calls = 0
        self.calls: list[dict[str, Any]] = []

    async def generate_json_async(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.calls.append({"messages": [dict(message) for message in messages], **kwargs})
        if kwargs.get("response_model") is JudgeVerdict:
            score = self.judge_scores[self.judge_calls]
            content = _verdict(
                score=score,
                iteration=self.judge_calls,
                issue=self.first_issue and self.judge_calls == 0,
            )
            self.judge_calls += 1
        else:
            self.planner_calls += 1
            content = {"plan_id": f"plan-{self.planner_calls}"}
        return LLMResponse(
            content=content,
            metadata=ResponseMetadata(token_usage=TokenUsage(total_tokens=10)),
        )


def _specs() -> tuple[AgentSpec, AgentSpec]:
    return (
        AgentSpec(name="planner", prompt_pack="test_pack", response_model=dict),
        AgentSpec(name="judge", prompt_pack="test_pack", response_model=JudgeVerdict),
    )


async def _run_controller(
    config: IterationConfig,
    provider: _LoopProvider,
    *,
    validator: Callable[[dict[str, Any]], list[str]] | None = None,
    judge_context_builder: Callable[[dict[str, Any], int, IterationContext], dict[str, Any]]
    | None = None,
):
    planner_spec, judge_spec = _specs()
    controller: StandardIterationController[dict[str, Any]] = StandardIterationController(
        config=config
    )
    return await controller.run(
        planner_spec=planner_spec,
        judge_spec=judge_spec,
        initial_variables={
            "agent_name": "loop",
            "iteration": 0,
            "context": {},
            "feedback": None,
        },
        validator=validator or (lambda _plan: []),
        provider=provider,
        llm_logger=Mock(),
        prompt_base_path=FIXTURES_PATH,
        judge_context_builder=judge_context_builder,
    )


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


@pytest.mark.asyncio
async def test_judge_receives_prior_verdicts_on_second_iteration() -> None:
    """The live hook receives same-run history before the second judge call."""
    provider = _LoopProvider([6.0, 8.0], first_issue=True)
    seen: list[dict[str, Any]] = []

    def build_judge_context(
        plan: dict[str, Any], iteration: int, context: IterationContext
    ) -> dict[str, Any]:
        seen.append(
            {
                "iteration": iteration,
                "verdicts": list(context.verdicts),
                "revision_requests": list(context.revision_requests),
            }
        )
        return {
            "agent_name": "judge",
            "iteration": iteration,
            "context": {"plan": plan},
            "feedback": None,
        }

    result = await _run_controller(
        IterationConfig(max_iterations=2, enable_issue_tracking=False),
        provider,
        judge_context_builder=build_judge_context,
    )

    assert result.success is True
    assert len(seen) == 2
    assert seen[0]["verdicts"] == []
    assert seen[1]["verdicts"][0].feedback_for_planner.startswith("Increase variety")
    assert seen[1]["verdicts"][0].issues[0].issue_id == "VARIETY_LOW"
    assert len(seen[1]["revision_requests"]) == 1


@pytest.mark.asyncio
async def test_success_threshold_changes_acceptance() -> None:
    """The same fixed score has different outcomes at different thresholds."""
    permissive = await _run_controller(
        IterationConfig(
            max_iterations=1,
            approval_score_threshold=6.0,
            enable_issue_tracking=False,
        ),
        _LoopProvider([6.5]),
    )
    strict = await _run_controller(
        IterationConfig(
            max_iterations=1,
            approval_score_threshold=7.0,
            enable_issue_tracking=False,
        ),
        _LoopProvider([6.5]),
    )

    assert permissive.success is True
    assert permissive.context.final_verdict is not None
    assert permissive.context.final_verdict.status == VerdictStatus.APPROVE
    assert strict.success is False
    assert strict.context.final_verdict is not None
    assert strict.context.final_verdict.status == VerdictStatus.SOFT_FAIL


@pytest.mark.asyncio
async def test_max_iterations_zero_skips_judge() -> None:
    """The documented zero value plans once, validates, and never calls the judge."""
    provider = _LoopProvider([])
    result = await _run_controller(
        IterationConfig(max_iterations=0, enable_issue_tracking=False), provider
    )

    assert result.success is True
    assert result.plan == {"plan_id": "plan-1"}
    assert result.context.current_iteration == 1
    assert result.context.final_verdict is None
    assert provider.planner_calls == 1
    assert provider.judge_calls == 0
    assert [record.role for record in result.context.call_records] == ["planner"]
    assert result.context.call_records[0].total_tokens == 10


@pytest.mark.asyncio
async def test_max_iterations_zero_still_requires_heuristic_validation() -> None:
    """Judge-disabled mode does not bypass deterministic correctness checks."""
    provider = _LoopProvider([])
    result = await _run_controller(
        IterationConfig(max_iterations=0, enable_issue_tracking=False),
        provider,
        validator=lambda _plan: ["plan is structurally invalid"],
    )

    assert result.success is False
    assert result.plan == {"plan_id": "plan-1"}
    assert provider.planner_calls == 1
    assert provider.judge_calls == 0


@pytest.mark.asyncio
async def test_call_ceiling_not_increased() -> None:
    """Three rejected cycles remain three planner plus three judge logical calls."""
    provider = _LoopProvider([6.0, 6.0, 6.0])
    result = await _run_controller(
        IterationConfig(max_iterations=3, enable_issue_tracking=False), provider
    )

    assert result.success is False
    assert provider.planner_calls == 3
    assert provider.judge_calls == 3
    assert len(provider.calls) == 6
    assert [record.role for record in result.context.call_records] == [
        "planner",
        "judge",
        "planner",
        "judge",
        "planner",
        "judge",
    ]
