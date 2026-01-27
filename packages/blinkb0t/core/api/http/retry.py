from __future__ import annotations

import random

from pydantic import BaseModel, Field, field_validator


class RetryPolicy(BaseModel):
    """Retry policy configuration for HTTP requests.

    Controls exponential backoff with jitter for failed requests.

    Args:
        max_attempts: Maximum number of attempts (including initial request)
        base_delay_s: Base delay in seconds for exponential backoff
        max_delay_s: Maximum delay in seconds (caps exponential growth)
        jitter: Jitter as fraction of delay (0.15 = ±15% randomization)
        retry_on_status: HTTP status codes that trigger retries
        retry_methods: HTTP methods eligible for retry (idempotent by default)
        allow_non_idempotent: Allow retrying non-idempotent methods (POST, PUT, PATCH)

    Notes:
        - By default, only safe/idempotent methods are retried
        - For POST/PUT/PATCH, set allow_non_idempotent=True only when using idempotency keys
          or when you know the endpoint is safe to retry
    """

    model_config = {"frozen": True}

    max_attempts: int = Field(default=3, ge=1)
    base_delay_s: float = Field(default=0.25, ge=0.0)
    max_delay_s: float = Field(default=5.0, ge=0.0)
    jitter: float = Field(default=0.15, ge=0.0, le=1.0)
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_methods: tuple[str, ...] = ("GET", "HEAD", "OPTIONS", "DELETE")
    allow_non_idempotent: bool = False

    @field_validator("max_delay_s")
    @classmethod
    def validate_max_delay(cls, v: float, info) -> float:
        """Ensure max_delay_s >= base_delay_s."""
        base = info.data.get("base_delay_s", 0.25)
        if v < base:
            raise ValueError("max_delay_s must be >= base_delay_s")
        return v

    def allows_method(self, method: str) -> bool:
        """Check if the given HTTP method is eligible for retry.

        Args:
            method: HTTP method (case-insensitive)

        Returns:
            True if method can be retried
        """
        m = method.upper()
        if m in self.retry_methods:
            return True
        return self.allow_non_idempotent

    def compute_delay(self, attempt: int) -> float:
        """Compute retry delay with exponential backoff and jitter.

        Args:
            attempt: Attempt number (1-indexed, 1 = first retry after initial failure)

        Returns:
            Delay in seconds before next retry
        """
        delay: float = min(self.max_delay_s, self.base_delay_s * (2 ** (attempt - 1)))
        if self.jitter > 0:
            spread: float = delay * self.jitter
            jitter_value: float = random.uniform(-spread, spread)
            delay = max(0.0, delay + jitter_value)
        return delay


def parse_retry_after_seconds(value: str | None) -> float | None:
    """Parse Retry-After header value to seconds.

    Handles numeric seconds format only (not HTTP-date format).

    Args:
        value: Retry-After header value

    Returns:
        Seconds to wait, or None if invalid or not provided
    """
    if not value:
        return None
    v = value.strip()
    try:
        seconds = float(v)
        if seconds < 0:
            return None
        return seconds
    except ValueError:
        return None
