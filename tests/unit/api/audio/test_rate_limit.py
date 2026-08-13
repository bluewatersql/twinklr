"""Tests for the paced-request helper used to honor provider rate policies."""

from __future__ import annotations

import asyncio

import pytest

from twinklr.core.api.audio.rate_limit import AsyncRateLimiter


class FakeClock:
    """Monotonic clock that only advances when the paired sleep is awaited."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
        await asyncio.sleep(0)


def make_limiter(rate_per_second: float) -> tuple[AsyncRateLimiter, FakeClock]:
    clock = FakeClock()
    limiter = AsyncRateLimiter(
        rate_per_second=rate_per_second, monotonic=clock.monotonic, sleep=clock.sleep
    )
    return limiter, clock


def test_rate_must_be_positive():
    with pytest.raises(ValueError, match="rate_per_second"):
        AsyncRateLimiter(rate_per_second=0.0)


async def test_first_acquisition_does_not_wait():
    limiter, clock = make_limiter(1.0)

    async with limiter:
        pass

    assert clock.sleeps == []
    assert clock.now == 0.0


async def test_successive_acquisitions_are_spaced_by_the_interval():
    limiter, clock = make_limiter(1.0)
    observed: list[float] = []

    for _ in range(3):
        async with limiter:
            observed.append(clock.now)

    assert observed == [0.0, 1.0, 2.0]


async def test_time_already_elapsed_is_credited():
    """Work that took longer than the interval does not wait again."""
    limiter, clock = make_limiter(1.0)

    async with limiter:
        clock.now += 5.0  # simulate a slow request

    async with limiter:
        pass

    assert clock.sleeps == []


async def test_concurrent_holders_are_serialized():
    limiter, _clock = make_limiter(1.0)
    in_flight = 0
    max_in_flight = 0

    async def worker() -> None:
        nonlocal in_flight, max_in_flight
        async with limiter:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0)
            in_flight -= 1

    await asyncio.gather(*(worker() for _ in range(4)))

    assert max_in_flight == 1


async def test_lock_is_released_when_the_body_raises():
    limiter, _clock = make_limiter(1.0)

    with pytest.raises(RuntimeError):
        async with limiter:
            raise RuntimeError("boom")

    async with limiter:  # would deadlock if the lock leaked
        pass
