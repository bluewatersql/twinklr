"""Unit tests for pipeline execution helpers (execute_step).

Tests for execute_step() which handles:
- Deterministic caching (load/store)
- Default state storage
- Default metrics tracking
- Custom handlers
- Error handling
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

from pydantic import BaseModel
import pytest

from twinklr.core.pipeline.execution import execute_step
from twinklr.core.pipeline.result import StageResult

if TYPE_CHECKING:
    from twinklr.core.caching import CacheKey
    from twinklr.core.pipeline.result import StageResult

# ============================================================================
# Test Models
# ============================================================================


class MockIterationContext(BaseModel):
    """Mock iteration context with tracking fields."""

    current_iteration: int = 1
    total_tokens_used: int = 1000
    final_verdict: MockVerdict | None = None
    termination_reason: str | None = None


class MockVerdict(BaseModel):
    """Mock verdict with score."""

    score: float = 8.5


class MockOrchestrationResult(BaseModel):
    """Mock orchestration result matching IterationResult pattern."""

    success: bool = True
    plan: MockPlan | None = None
    context: MockIterationContext = MockIterationContext()


class MockPlan(BaseModel):
    """Mock plan data."""

    sections: list[str] = ["intro", "verse", "chorus"]


class SimpleResult(BaseModel):
    """Simple result for non-orchestration cases."""

    value: str = "test"


# ============================================================================
# Fixtures & Helpers
# ============================================================================


def make_async_cache_key(key: str) -> Callable[[], Awaitable[str]]:
    """Helper to create async cache key function."""

    async def get_key() -> str:
        return key

    return get_key


@pytest.fixture
def mock_context() -> MagicMock:
    """Create mock pipeline context."""
    ctx = MagicMock()
    ctx.cache = MagicMock()
    ctx.set_state = MagicMock()
    ctx.add_metric = MagicMock()
    # Provide proper session with session_id string for cache key generation
    ctx.session = MagicMock()
    ctx.session.session_id = "test_session_123"
    return ctx


@pytest.fixture
def mock_orchestration_result() -> MockOrchestrationResult:
    """Create successful orchestration result."""
    verdict = MockVerdict(score=8.5)
    iter_context = MockIterationContext(
        current_iteration=2, total_tokens_used=1500, final_verdict=verdict
    )
    return MockOrchestrationResult(
        success=True, plan=MockPlan(sections=["intro", "verse", "chorus"]), context=iter_context
    )


# ============================================================================
# Test: Cache Hit Scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_execute_step_cache_hit(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test cache hit: loads from cache, skips computation."""
    # Setup: Cache returns result
    mock_context.cache.load = AsyncMock(return_value=mock_orchestration_result)

    # Mock compute should NOT be called
    compute_called = False

    async def mock_compute() -> MockOrchestrationResult:
        nonlocal compute_called
        compute_called = True
        return mock_orchestration_result

    # Execute
    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=mock_compute,
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        cache_key_fn=make_async_cache_key("test_cache_key"),
    )

    # Assertions
    assert result.success is True
    assert result.output == ["intro", "verse", "chorus"]
    assert compute_called is False, "Compute should not be called on cache hit"

    # Verify cache was checked
    mock_context.cache.load.assert_called_once()

    # Verify metrics tracked
    mock_context.add_metric.assert_any_call("test_stage_from_cache", True)
    mock_context.add_metric.assert_any_call("test_stage_iterations", 2)
    mock_context.add_metric.assert_any_call("test_stage_tokens", 1500)
    mock_context.add_metric.assert_any_call("test_stage_score", 8.5)

    # Verify state stored
    mock_context.set_state.assert_called_once_with("test_stage_result", mock_orchestration_result)


@pytest.mark.asyncio
async def test_execute_step_cache_hit_no_verdict(mock_context: MagicMock) -> None:
    """Test cache hit with no final_verdict (score metric not tracked)."""
    result_no_verdict = MockOrchestrationResult(
        success=True,
        plan=MockPlan(),
        context=MockIterationContext(current_iteration=1, final_verdict=None),
    )

    mock_context.cache.load = AsyncMock(return_value=result_no_verdict)

    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=result_no_verdict)(),
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        cache_key_fn=make_async_cache_key("test_key"),
    )

    assert result.success is True

    # Score metric should NOT be tracked (no verdict)
    score_calls = [call for call in mock_context.add_metric.call_args_list if "score" in str(call)]
    assert len(score_calls) == 0, "Score should not be tracked without verdict"


# ============================================================================
# Test: Cache Miss Scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_execute_step_cache_miss(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test cache miss: computes, stores in cache."""
    # Setup: Cache miss
    mock_context.cache.load = AsyncMock(return_value=None)
    mock_context.cache.store = AsyncMock()

    compute_called = False

    async def mock_compute() -> MockOrchestrationResult:
        nonlocal compute_called
        compute_called = True
        return mock_orchestration_result

    # Execute
    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=mock_compute,
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        cache_key_fn=make_async_cache_key("test_cache_key"),
    )

    # Assertions
    assert result.success is True
    assert result.output == ["intro", "verse", "chorus"]
    assert compute_called is True, "Compute should be called on cache miss"

    # Verify cache operations
    mock_context.cache.load.assert_called_once()
    mock_context.cache.store.assert_called_once()

    # Verify from_cache=False
    mock_context.add_metric.assert_any_call("test_stage_from_cache", False)


@pytest.mark.asyncio
async def test_execute_step_no_cache(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test no caching (cache_key_fn=None): always computes."""
    mock_context.cache = None  # No cache available

    compute_called = False

    async def mock_compute() -> MockOrchestrationResult:
        nonlocal compute_called
        compute_called = True
        return mock_orchestration_result

    # Execute WITHOUT cache_key_fn
    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=mock_compute,
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        cache_key_fn=None,  # No caching
    )

    assert result.success is True
    assert compute_called is True
    mock_context.add_metric.assert_any_call("test_stage_from_cache", False)


# ============================================================================
# Test: State Handling
# ============================================================================


@pytest.mark.asyncio
async def test_execute_step_default_state(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test default state storage: stores full result."""
    mock_context.cache = None

    result = await execute_step(
        stage_name="my_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=mock_orchestration_result)(),
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
    )

    assert result.success is True

    # Verify default state stored
    mock_context.set_state.assert_called_once_with("my_stage_result", mock_orchestration_result)


@pytest.mark.asyncio
async def test_execute_step_custom_state_handler(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test custom state handler: extends defaults."""
    mock_context.cache = None

    custom_state_called = False

    def custom_state_handler(result: MockOrchestrationResult, context: Any) -> None:
        nonlocal custom_state_called
        custom_state_called = True
        context.set_state("custom_key", result.plan)

    result = await execute_step(
        stage_name="my_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=mock_orchestration_result)(),
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        state_handler=custom_state_handler,
    )

    assert result.success is True
    assert custom_state_called is True

    # Verify BOTH default and custom state stored
    assert mock_context.set_state.call_count == 2
    mock_context.set_state.assert_any_call("my_stage_result", mock_orchestration_result)
    mock_context.set_state.assert_any_call("custom_key", mock_orchestration_result.plan)


# ============================================================================
# Test: Metrics Handling
# ============================================================================


@pytest.mark.asyncio
async def test_execute_step_default_metrics(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test default metrics: iterations, tokens, score, from_cache."""
    mock_context.cache = None

    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=mock_orchestration_result)(),
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
    )

    assert result.success is True

    # Verify all default metrics tracked
    mock_context.add_metric.assert_any_call("test_stage_iterations", 2)
    mock_context.add_metric.assert_any_call("test_stage_tokens", 1500)
    mock_context.add_metric.assert_any_call("test_stage_score", 8.5)
    mock_context.add_metric.assert_any_call("test_stage_from_cache", False)


@pytest.mark.asyncio
async def test_execute_step_custom_metrics_handler(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test custom metrics handler: extends defaults."""
    mock_context.cache = None

    custom_metrics_called = False

    def custom_metrics_handler(result: MockOrchestrationResult, context: Any) -> None:
        nonlocal custom_metrics_called
        custom_metrics_called = True
        context.add_metric("section_count", len(result.plan.sections))  # type: ignore[union-attr]

    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=mock_orchestration_result)(),
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        metrics_handler=custom_metrics_handler,
    )

    assert result.success is True
    assert custom_metrics_called is True

    # Verify BOTH default and custom metrics tracked
    mock_context.add_metric.assert_any_call("test_stage_iterations", 2)
    mock_context.add_metric.assert_any_call("test_stage_from_cache", False)
    mock_context.add_metric.assert_any_call("section_count", 3)  # Custom metric


@pytest.mark.asyncio
async def test_execute_step_no_context_field(mock_context: MagicMock) -> None:
    """Test result without .context field: no iteration/token metrics."""
    simple_result = SimpleResult(value="test")
    mock_context.cache = None

    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=simple_result)(),
        result_extractor=lambda r: r.value,
        result_type=SimpleResult,
    )

    assert result.success is True
    assert result.output == "test"

    # Only from_cache metric should be tracked (no iterations/tokens/score)
    mock_context.add_metric.assert_any_call("test_stage_from_cache", False)

    # Verify NO iteration/token metrics
    iteration_calls = [
        call for call in mock_context.add_metric.call_args_list if "iteration" in str(call)
    ]
    token_calls = [call for call in mock_context.add_metric.call_args_list if "token" in str(call)]
    assert len(iteration_calls) == 0
    assert len(token_calls) == 0


# ============================================================================
# Test: Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_execute_step_compute_returns_none(mock_context: MagicMock) -> None:
    """Test compute returns None: returns failure result."""
    mock_context.cache = None

    async def compute_none() -> None:
        return None

    result: StageResult[Any] = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=compute_none,  # type: ignore[arg-type]
        result_extractor=lambda r: r,
        result_type=SimpleResult,
    )

    assert result.success is False
    assert "None" in result.error


@pytest.mark.asyncio
async def test_execute_step_result_success_false(mock_context: MagicMock) -> None:
    """Test result.success=False: returns failure result."""
    mock_context.cache = None

    failed_result = MockOrchestrationResult(
        success=False,
        plan=None,
        context=MockIterationContext(current_iteration=1, total_tokens_used=500),
    )
    # Add termination_reason
    failed_result.context.termination_reason = "Max iterations reached"  # type: ignore[attr-defined]

    result: StageResult[Any] = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=failed_result)(),
        result_extractor=lambda r: r.plan.sections if r.plan else [],  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
    )

    assert result.success is False
    assert "Max iterations reached" in result.error


@pytest.mark.asyncio
async def test_execute_step_extraction_fails(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test result extraction raises exception: returns failure result."""
    mock_context.cache = None

    def bad_extractor(r: MockOrchestrationResult) -> list[str]:
        raise ValueError("Extraction failed")

    result: StageResult[Any] = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=mock_orchestration_result)(),
        result_extractor=bad_extractor,
        result_type=MockOrchestrationResult,
    )

    assert result.success is False
    assert "extraction failed" in result.error.lower()


@pytest.mark.asyncio
async def test_execute_step_cache_load_fails(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test cache load raises exception: falls back to compute."""
    # Setup: Cache load fails
    mock_context.cache.load = AsyncMock(side_effect=Exception("Cache error"))
    mock_context.cache.store = AsyncMock()

    compute_called = False

    async def mock_compute() -> MockOrchestrationResult:
        nonlocal compute_called
        compute_called = True
        return mock_orchestration_result

    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=mock_compute,
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        cache_key_fn=make_async_cache_key("test_key"),
    )

    assert result.success is True
    assert compute_called is True, "Should fall back to compute on cache error"


@pytest.mark.asyncio
async def test_execute_step_cache_store_fails(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test cache store raises exception: continues execution."""
    mock_context.cache.load = AsyncMock(return_value=None)
    mock_context.cache.store = AsyncMock(side_effect=Exception("Store error"))

    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=mock_orchestration_result)(),
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        cache_key_fn=make_async_cache_key("test_key"),
    )

    # Should succeed despite cache store failure
    assert result.success is True
    assert result.output == ["intro", "verse", "chorus"]


@pytest.mark.asyncio
async def test_execute_step_state_handler_fails(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test state handler raises exception: continues execution."""
    mock_context.cache = None

    def bad_state_handler(result: MockOrchestrationResult, context: Any) -> None:
        raise ValueError("State handler error")

    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=mock_orchestration_result)(),
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        state_handler=bad_state_handler,
    )

    # Should succeed despite handler failure
    assert result.success is True


@pytest.mark.asyncio
async def test_execute_step_metrics_handler_fails(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test metrics handler raises exception: continues execution."""
    mock_context.cache = None

    def bad_metrics_handler(result: MockOrchestrationResult, context: Any) -> None:
        raise ValueError("Metrics handler error")

    result = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=mock_orchestration_result)(),
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        metrics_handler=bad_metrics_handler,
    )

    # Should succeed despite handler failure
    assert result.success is True


# ============================================================================
# Test: Cache Key Generation
# ============================================================================


@pytest.mark.asyncio
async def test_execute_step_cache_key_structure(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test cache key is built correctly from components."""
    mock_context.cache.load = AsyncMock(return_value=None)
    mock_context.cache.store = AsyncMock()

    cache_key_hash = "abc123def456"

    result = await execute_step(
        stage_name="my_stage",
        context=mock_context,
        compute=lambda: AsyncMock(return_value=mock_orchestration_result)(),
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        cache_key_fn=make_async_cache_key(cache_key_hash),
        cache_version="v2",
    )

    assert result.success is True

    # Verify cache.load was called with correct CacheKey
    assert mock_context.cache.load.called, "cache.load should have been called"
    load_call_args = mock_context.cache.load.call_args
    assert load_call_args is not None, "load_call_args should not be None"

    # Extract CacheKey from call args (first positional argument)
    cache_key: CacheKey = load_call_args.args[0]

    # Domain is now stage_name for isolation: <cache>/<domain>/<session>/<step>/<fingerprint>
    assert cache_key.domain == "my_stage"
    assert cache_key.session_id == mock_context.session.session_id
    assert cache_key.step_id == "my_stage"
    assert cache_key.step_version == "v2"
    assert cache_key.input_fingerprint == cache_key_hash


# ============================================================================
# Test: Integration
# ============================================================================


@pytest.mark.asyncio
async def test_execute_step_full_flow_cache_miss_to_hit(
    mock_context: MagicMock, mock_orchestration_result: MockOrchestrationResult
) -> None:
    """Test full flow: cache miss -> compute -> store, then cache hit."""
    # First call: cache miss
    mock_context.cache.load = AsyncMock(return_value=None)
    mock_context.cache.store = AsyncMock()

    compute_count = 0

    async def mock_compute() -> MockOrchestrationResult:
        nonlocal compute_count
        compute_count += 1
        return mock_orchestration_result

    result1 = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=mock_compute,
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        cache_key_fn=make_async_cache_key("key"),
    )

    assert result1.success is True
    assert compute_count == 1
    mock_context.add_metric.assert_any_call("test_stage_from_cache", False)

    # Second call: cache hit (reset mock)
    mock_context.reset_mock()
    mock_context.cache.load = AsyncMock(return_value=mock_orchestration_result)

    result2 = await execute_step(
        stage_name="test_stage",
        context=mock_context,
        compute=mock_compute,
        result_extractor=lambda r: r.plan.sections,  # type: ignore[union-attr]
        result_type=MockOrchestrationResult,
        cache_key_fn=make_async_cache_key("key"),
    )

    assert result2.success is True
    assert compute_count == 1, "Compute should not be called again on cache hit"
    mock_context.add_metric.assert_any_call("test_stage_from_cache", True)
