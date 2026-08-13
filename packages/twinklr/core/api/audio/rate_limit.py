"""Paced-request helper for providers with a published rate policy.

MusicBrainz allows one request per second and no concurrent requests
(https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting). Enforcing that at
the call site rather than in a comment means every current and future caller
inherits the pacing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import time
from types import TracebackType

Monotonic = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]


class AsyncRateLimiter:
    """Serializes requests and spaces their starts by ``1 / rate_per_second``.

    Used as an async context manager. The lock is held for the whole body, so
    no two holders overlap; the wait is computed from the previous holder's
    start time, so work that already took longer than the interval does not
    wait again.

    Args:
        rate_per_second: Maximum request starts per second.
        monotonic: Clock source (injectable for tests).
        sleep: Awaitable delay (injectable for tests).

    Example:
        >>> limiter = AsyncRateLimiter(rate_per_second=1.0)
        >>> async with limiter:  # doctest: +SKIP
        ...     await http_client.get(url)
    """

    def __init__(
        self,
        *,
        rate_per_second: float,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError(f"rate_per_second must be positive, got {rate_per_second}")

        self.rate_per_second = rate_per_second
        self._min_interval_s = 1.0 / rate_per_second
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._last_start_s: float | None = None

    async def __aenter__(self) -> AsyncRateLimiter:
        await self._lock.acquire()
        try:
            if self._last_start_s is not None:
                wait_s = self._min_interval_s - (self._monotonic() - self._last_start_s)
                if wait_s > 0:
                    await self._sleep(wait_s)
            self._last_start_s = self._monotonic()
        except BaseException:
            self._lock.release()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._lock.release()
