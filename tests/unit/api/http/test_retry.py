"""Shared retry-policy behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from twinklr.core.api.http.retry import RetryDeadlineExceededError, RetryPolicy


class RetryAfterError(Exception):
    def __init__(self, value: str) -> None:
        self.response = MagicMock(headers={"Retry-After": value})


@pytest.mark.asyncio
async def test_async_policy_rejects_success_that_arrives_after_deadline() -> None:
    async def slow_success() -> str:
        await asyncio.sleep(0.05)
        return "too late"

    policy = RetryPolicy(max_attempts=1, deadline_s=0.01)

    with pytest.raises(RetryDeadlineExceededError, match=r"0\.010 seconds"):
        await policy.execute_async(slow_success, is_retryable=lambda _: True)


@pytest.mark.asyncio
async def test_async_policy_bounds_second_attempt_by_only_remaining_budget() -> None:
    operation = AsyncMock(side_effect=[OSError("retry"), "ok"])
    policy = RetryPolicy(
        max_attempts=2,
        base_delay_s=1.0,
        max_delay_s=1.0,
        jitter=0.0,
        deadline_s=10.0,
    )
    budgets: list[float] = []

    class CaptureTimeout:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *args: object) -> None:
            return None

        def expired(self) -> bool:
            return False

    def capture_timeout(seconds: float) -> CaptureTimeout:
        budgets.append(seconds)
        return CaptureTimeout()

    with (
        patch(
            "twinklr.core.api.http.retry._monotonic",
            side_effect=[0.0, 0.0, 1.0, 3.0],
        ),
        patch("twinklr.core.api.http.retry.asyncio.timeout", side_effect=capture_timeout),
        patch("twinklr.core.api.http.retry.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await policy.execute_async(operation, is_retryable=lambda _: True)

    assert result == "ok"
    assert budgets == [10.0, 7.0]


@pytest.mark.asyncio
async def test_async_policy_propagates_external_cancellation_without_retry() -> None:
    operation = AsyncMock(side_effect=asyncio.CancelledError())
    classifier = MagicMock(return_value=True)
    policy = RetryPolicy(max_attempts=3, deadline_s=10.0)

    with pytest.raises(asyncio.CancelledError):
        await policy.execute_async(operation, is_retryable=classifier)

    assert operation.await_count == 1
    classifier.assert_not_called()


@pytest.mark.asyncio
async def test_async_policy_preserves_operation_timeout_before_deadline() -> None:
    operation = AsyncMock(side_effect=TimeoutError("upstream timed out"))
    policy = RetryPolicy(max_attempts=1, deadline_s=10.0)

    with pytest.raises(TimeoutError, match="upstream timed out") as raised:
        await policy.execute_async(operation, is_retryable=lambda _: False)

    assert not isinstance(raised.value, RetryDeadlineExceededError)


@pytest.mark.asyncio
async def test_async_policy_honors_retry_after_within_deadline() -> None:
    operation = AsyncMock(
        side_effect=[
            RetryAfterError("2"),
            "ok",
        ]
    )
    policy = RetryPolicy(
        max_attempts=2,
        base_delay_s=0.5,
        max_delay_s=5.0,
        jitter=0.0,
        deadline_s=10.0,
    )

    with (
        patch(
            "twinklr.core.api.http.retry._monotonic",
            side_effect=[0.0, 0.0, 1.0, 1.0],
        ),
        patch("twinklr.core.api.http.retry.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        result = await policy.execute_async(
            operation,
            is_retryable=lambda error: hasattr(error, "response"),
        )

    assert result == "ok"
    sleep.assert_awaited_once_with(2.0)


@pytest.mark.asyncio
async def test_async_policy_refuses_delay_that_exceeds_deadline() -> None:
    error = OSError("offline")
    operation = AsyncMock(side_effect=error)
    policy = RetryPolicy(
        max_attempts=3,
        base_delay_s=2.0,
        max_delay_s=2.0,
        jitter=0.0,
        deadline_s=1.0,
    )

    with (
        patch("twinklr.core.api.http.retry._monotonic", side_effect=[0.0, 0.0, 0.5]),
        pytest.raises(OSError, match="offline"),
    ):
        await policy.execute_async(operation, is_retryable=lambda _: True)

    assert operation.await_count == 1
