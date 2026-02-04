"""Unit tests for StandardIterationController."""

import logging
from unittest.mock import AsyncMock, Mock

import pytest

from twinklr.core.agents.shared.judge.controller import (
    IterationConfig,
    StandardIterationController,
)
from twinklr.core.agents.shared.judge.feedback import FeedbackManager
from twinklr.core.agents.shared.judge.models import (
    JudgeVerdict,
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
