"""Unit tests for pipeline framework."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from twinklr.core.agents.logging import NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.caching.backends.null import NullCache
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.pipeline import (
    ExecutionPattern,
    PipelineContext,
    PipelineDefinition,
    PipelineExecutor,
    StageDefinition,
    failure_result,
    success_result,
)
from twinklr.core.pipeline.definition import RetryConfig

if TYPE_CHECKING:
    from twinklr.core.pipeline import StageResult

# ============================================================================
# Mock Stages
# ============================================================================


class MockStage:
    """Mock stage for testing."""

    def __init__(self, stage_name: str, output: Any, should_fail: bool = False):
        self._name = stage_name
        self._output = output
        self._should_fail = should_fail
        self.execution_count = 0

    @property
    def name(self) -> str:
        return self._name

    async def execute(
        self,
        input: Any,
        context: PipelineContext,
    ) -> StageResult[Any]:
        self.execution_count += 1

        if self._should_fail:
            return failure_result(f"Mock failure in {self._name}", stage_name=self._name)

        # Simulate async work
        await asyncio.sleep(0.01)

        return success_result(self._output, stage_name=self._name)


class MockProvider(LLMProvider):
    """Mock LLM provider for testing."""

    async def generate_json_async(self, *args: Any, **kwargs: Any) -> Any:
        return {}


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_context() -> PipelineContext:
    """Create mock pipeline context with mocked session."""
    # Create minimal mock configs
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


# ============================================================================
# Tests: Pipeline Definition
# ============================================================================


def test_pipeline_definition_validation():
    """Test pipeline definition validation."""
    # Valid pipeline
    pipeline = PipelineDefinition(
        name="test",
        stages=[
            StageDefinition("a", MockStage("a", "output_a")),
            StageDefinition("b", MockStage("b", "output_b"), inputs=["a"]),
        ],
    )

    errors = pipeline.validate_pipeline()
    assert len(errors) == 0


def test_pipeline_validation_duplicate_ids():
    """Test validation catches duplicate stage IDs."""
    pipeline = PipelineDefinition(
        name="test",
        stages=[
            StageDefinition("a", MockStage("a", "output_a")),
            StageDefinition("a", MockStage("a", "output_a")),  # Duplicate!
        ],
    )

    errors = pipeline.validate_pipeline()
    assert len(errors) > 0
    assert "Duplicate stage IDs" in errors[0]


def test_pipeline_validation_missing_input():
    """Test validation catches missing input dependencies."""
    pipeline = PipelineDefinition(
        name="test",
        stages=[
            StageDefinition("a", MockStage("a", "output_a")),
            StageDefinition("b", MockStage("b", "output_b"), inputs=["missing"]),
        ],
    )

    errors = pipeline.validate_pipeline()
    assert len(errors) > 0
    assert "unknown stage" in errors[0].lower()


def test_pipeline_validation_circular_dependency():
    """Test validation catches circular dependencies."""
    pipeline = PipelineDefinition(
        name="test",
        stages=[
            StageDefinition("a", MockStage("a", "output_a"), inputs=["b"]),
            StageDefinition("b", MockStage("b", "output_b"), inputs=["a"]),
        ],
    )

    errors = pipeline.validate_pipeline()
    assert len(errors) > 0
    assert "circular" in errors[0].lower()


# ============================================================================
# Tests: Pipeline Execution
# ============================================================================


@pytest.mark.asyncio
async def test_simple_sequential_pipeline(mock_context):
    """Test simple sequential pipeline execution."""
    pipeline = PipelineDefinition(
        name="sequential",
        stages=[
            StageDefinition("stage1", MockStage("stage1", "output1")),
            StageDefinition("stage2", MockStage("stage2", "output2"), inputs=["stage1"]),
        ],
    )

    executor = PipelineExecutor()
    result = await executor.execute(pipeline, "initial_input", mock_context)

    assert result.success is True
    assert len(result.outputs) == 2
    assert result.outputs["stage1"] == "output1"
    assert result.outputs["stage2"] == "output2"
    assert len(result.failed_stages) == 0


@pytest.mark.asyncio
async def test_parallel_execution(mock_context):
    """Test parallel stage execution."""
    stage_a = MockStage("a", "output_a")
    stage_b = MockStage("b", "output_b")

    pipeline = PipelineDefinition(
        name="parallel",
        stages=[
            StageDefinition("input", MockStage("input", "initial")),
            StageDefinition("a", stage_a, inputs=["input"]),
            StageDefinition("b", stage_b, inputs=["input"]),
        ],
    )

    executor = PipelineExecutor()
    result = await executor.execute(pipeline, "initial", mock_context)

    assert result.success is True
    assert len(result.outputs) == 3
    # Both stages executed (parallel)
    assert stage_a.execution_count == 1
    assert stage_b.execution_count == 1


@pytest.mark.asyncio
async def test_conditional_stage_skipped(mock_context):
    """Test conditional stage is skipped when condition is False."""
    pipeline = PipelineDefinition(
        name="conditional",
        stages=[
            StageDefinition("stage1", MockStage("stage1", "output1")),
            StageDefinition(
                "stage2",
                MockStage("stage2", "output2"),
                pattern=ExecutionPattern.CONDITIONAL,
                inputs=["stage1"],
                condition=lambda ctx: False,  # Always skip
            ),
        ],
    )

    executor = PipelineExecutor()
    result = await executor.execute(pipeline, "initial", mock_context)

    assert result.success is True
    assert "stage1" in result.outputs
    # Skipped stages appear in outputs with None value
    assert result.outputs.get("stage2") is None
    # Skipped metadata is in stage_results metadata
    assert result.stage_results["stage2"].metadata.get("skipped") is True


@pytest.mark.asyncio
async def test_conditional_stage_executed(mock_context):
    """Test conditional stage executes when condition is True."""
    mock_context.set_state("execute_stage2", True)

    pipeline = PipelineDefinition(
        name="conditional",
        stages=[
            StageDefinition("stage1", MockStage("stage1", "output1")),
            StageDefinition(
                "stage2",
                MockStage("stage2", "output2"),
                pattern=ExecutionPattern.CONDITIONAL,
                inputs=["stage1"],
                condition=lambda ctx: ctx.get_state("execute_stage2", False),
            ),
        ],
    )

    executor = PipelineExecutor()
    result = await executor.execute(pipeline, "initial", mock_context)

    assert result.success is True
    assert "stage1" in result.outputs
    assert "stage2" in result.outputs  # Executed


@pytest.mark.asyncio
async def test_fan_out_execution(mock_context):
    """Test fan-out pattern execution."""
    pipeline = PipelineDefinition(
        name="fanout",
        stages=[
            # Stage that produces list of inputs
            StageDefinition("producer", MockStage("producer", ["input1", "input2", "input3"])),
            # Stage that executes once per input
            StageDefinition(
                "consumer",
                MockStage("consumer", "processed"),
                pattern=ExecutionPattern.FAN_OUT,
                inputs=["producer"],
            ),
        ],
    )

    executor = PipelineExecutor()
    result = await executor.execute(pipeline, "initial", mock_context)

    assert result.success is True
    assert "consumer" in result.outputs
    # Fan-out returns list of outputs
    assert isinstance(result.outputs["consumer"], list)
    assert len(result.outputs["consumer"]) == 3
    assert all(out == "processed" for out in result.outputs["consumer"])


@pytest.mark.asyncio
async def test_stage_failure_stops_pipeline(mock_context):
    """Test that stage failure stops pipeline (fail_fast=True)."""
    pipeline = PipelineDefinition(
        name="failure",
        fail_fast=True,
        stages=[
            StageDefinition("stage1", MockStage("stage1", "output1")),
            StageDefinition(
                "stage2", MockStage("stage2", "output2", should_fail=True), inputs=["stage1"]
            ),
            StageDefinition("stage3", MockStage("stage3", "output3"), inputs=["stage2"]),
        ],
    )

    executor = PipelineExecutor()
    result = await executor.execute(pipeline, "initial", mock_context)

    assert result.success is False
    assert "stage2" in result.failed_stages
    assert "stage1" in result.outputs  # Completed before failure
    assert "stage3" not in result.outputs  # Not executed


@pytest.mark.asyncio
async def test_retry_on_failure(mock_context):
    """Test retry logic on stage failure."""

    class FlakeyStage:
        def __init__(self):
            self.attempt_count = 0

        @property
        def name(self) -> str:
            return "flakey"

        async def execute(self, input: Any, context: PipelineContext) -> StageResult[str]:
            self.attempt_count += 1
            if self.attempt_count < 2:
                # Fail first attempt
                return failure_result("Transient error", stage_name=self.name)
            # Succeed on retry
            return success_result("success", stage_name=self.name)

    flakey = FlakeyStage()
    pipeline = PipelineDefinition(
        name="retry",
        stages=[
            StageDefinition(
                "flakey",
                flakey,
                retry_config=RetryConfig(max_attempts=3, initial_delay_ms=10),
            ),
        ],
    )

    executor = PipelineExecutor()
    result = await executor.execute(pipeline, "initial", mock_context)

    assert result.success is True
    assert flakey.attempt_count == 2  # Failed once, succeeded on retry


# ============================================================================
# Tests: Context
# ============================================================================


def test_context_state_management(mock_context):
    """Test context state management."""
    mock_context.set_state("key1", "value1")
    mock_context.set_state("key2", 42)

    assert mock_context.get_state("key1") == "value1"
    assert mock_context.get_state("key2") == 42
    assert mock_context.get_state("missing", "default") == "default"


def test_context_metrics(mock_context):
    """Test context metrics tracking."""
    mock_context.add_metric("tokens", 100)
    mock_context.increment_metric("requests")
    mock_context.increment_metric("requests")

    assert mock_context.metrics["tokens"] == 100
    assert mock_context.metrics["requests"] == 2


def test_context_cancellation(mock_context):
    """Test context cancellation support."""
    assert mock_context.is_cancelled() is False

    mock_context.cancel_token = asyncio.Event()
    assert mock_context.is_cancelled() is False

    mock_context.cancel_token.set()
    assert mock_context.is_cancelled() is True
