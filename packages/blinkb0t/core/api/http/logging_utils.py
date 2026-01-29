from __future__ import annotations

import logging
import time
from collections.abc import Mapping

from pydantic import BaseModel

logger = logging.getLogger("blinkb0t.core.api.http")


def _lower_set(values: tuple[str, ...]) -> set[str]:
    """Convert tuple of strings to lowercase set."""
    return {v.lower() for v in values}


def redact_headers(headers: Mapping[str, str], redact: tuple[str, ...]) -> dict[str, str]:
    """Redact sensitive headers for logging.

    Args:
        headers: Headers to redact
        redact: Header names to redact (case-insensitive)

    Returns:
        Headers with sensitive values replaced with "***REDACTED***"
    """
    red = _lower_set(redact)
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in red:
            out[k] = "***REDACTED***"
        else:
            out[k] = v
    return out


class RequestLogContext(BaseModel):
    """Context for structured HTTP request logging.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Full request URL
        attempt: Attempt number (1-indexed)
        request_id: Request ID for tracing
    """

    method: str
    url: str
    attempt: int
    request_id: str | None = None


def log_request(
    ctx: RequestLogContext, headers: Mapping[str, str], redact: tuple[str, ...]
) -> float:
    """Log HTTP request with redacted headers.

    Args:
        ctx: Request log context
        headers: Request headers
        redact: Header names to redact

    Returns:
        Start timestamp for elapsed time calculation
    """
    start = time.perf_counter()
    safe_headers = redact_headers(headers, redact)
    logger.debug(
        "HTTP request",
        extra={
            "method": ctx.method,
            "url": ctx.url,
            "attempt": ctx.attempt,
            "request_id": ctx.request_id,
            "headers": safe_headers,
        },
    )
    return start


def log_response(ctx: RequestLogContext, status_code: int, elapsed_s: float) -> None:
    """Log HTTP response with timing information.

    Args:
        ctx: Request log context
        status_code: HTTP response status code
        elapsed_s: Elapsed time in seconds
    """
    logger.debug(
        "HTTP response",
        extra={
            "method": ctx.method,
            "url": ctx.url,
            "attempt": ctx.attempt,
            "request_id": ctx.request_id,
            "status_code": status_code,
            "elapsed_ms": int(elapsed_s * 1000),
        },
    )
