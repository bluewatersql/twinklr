"""Unit tests for macro planner pipeline stage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from twinklr.core.agents.logging import NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.sequencer.macro_planner.stage import MacroPlannerStage
from twinklr.core.caching.backends.null import NullCache
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.sequencer.planning import MacroPlan


class MockProvider(LLMProvider):
    """Mock LLM provider."""

    async def generate_json_async(self, *args, **kwargs):
        return {}


@pytest.fixture
def mock_context():
    """Create mock pipeline context with mocked session."""
    app_config = AppConfig.model_validate(
        {
            "cache": {"base_dir": "cache", "enabled": False},
            "logging": {"level": "INFO", "format": "json"},
        }
    )
    job_config = JobConfig.model_validate(
        {
            "agent": {
                "max_iterations": 3,
                "plan_agent": {"model": "gpt-5.2"},
                "validate_agent": {"model": "gpt-5.2"},
                "judge_agent": {"model": "gpt-5.2"},
                "llm_logging": {"enabled": False},
            }
        }
    )

    # Create a mock session with required properties
    mock_session = MagicMock()
    mock_session.app_config = app_config
    mock_session.job_config = job_config
    mock_session.session_id = "test_session_123"
    mock_session.llm_provider = MockProvider()
    mock_session.agent_cache = NullCache()
    mock_session.llm_logger = NullLLMCallLogger()

    return PipelineContext(session=mock_session)


@pytest.fixture
def display_groups():
    """Create mock display groups."""
    return [
        {"role_key": "OUTLINE", "model_count": 10, "group_type": "string"},
        {"role_key": "MEGA_TREE", "model_count": 1, "group_type": "tree"},
    ]


def test_macro_planner_stage_name(display_groups):
    """Test stage name property."""
    stage = MacroPlannerStage(display_groups=display_groups)
    assert stage.name == "macro_planner"


@pytest.mark.asyncio
async def test_macro_planner_missing_input(mock_context, display_groups):
    """Test macro planner with missing required input."""
    stage = MacroPlannerStage(display_groups=display_groups)

    # Missing "profile" key
    invalid_input = {"lyrics": None}

    result = await stage.execute(invalid_input, mock_context)

    assert result.success is False
    assert "Missing required input" in result.error


def test_handle_state_normalizes_cached_plan_to_model(display_groups):
    """Cached dict payloads should be normalized to MacroPlan in context state."""
    stage = MacroPlannerStage(display_groups=display_groups)
    context = MagicMock()
    normalized_plan = MacroPlan.model_construct(
        global_story=MagicMock(),
        layering_plan=MagicMock(),
        section_plans=[],
        asset_requirements=[],
    )
    result = {
        "success": True,
        "plan": {"raw": "cached"},
        "context": {
            "current_iteration": 1,
            "state": "COMPLETE",
            "verdicts": [],
            "revision_requests": [],
            "total_tokens_used": 0,
            "termination_reason": None,
            "final_verdict": None,
        },
        "error_message": None,
    }

    with patch(
        "twinklr.core.sequencer.planning.MacroPlan.model_validate",
        return_value=normalized_plan,
    ) as validate_mock:
        stage._handle_state(result, context)

    stored_plan = context.set_state.call_args[0][1]
    assert isinstance(stored_plan, MacroPlan)
    validate_mock.assert_called_once_with({"raw": "cached"})
