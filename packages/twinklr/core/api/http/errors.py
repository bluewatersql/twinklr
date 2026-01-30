from __future__ import annotations

from pydantic import BaseModel, Field


class ApiErrorData(BaseModel):
    """Structured data for HTTP API errors.

    Args:
        message: Human-readable error description
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        status_code: HTTP status code (if available)
        request_id: Request ID for tracing (from X-Request-Id header)
        response_headers: Response headers (if available)
        response_body_snippet: Truncated response body for debugging
        cause: Original exception that caused this error
    """

    model_config = {"arbitrary_types_allowed": True}

    message: str
    method: str
    url: str
    status_code: int | None = None
    request_id: str | None = None
    response_headers: dict[str, str] | None = None
    response_body_snippet: str | None = None
    cause: BaseException | None = Field(default=None, repr=False)


class ApiError(Exception):
    """Base exception for all HTTP client errors.

    Wraps structured error data in an exception for ergonomic error handling.

    Attributes:
        data: Structured error data (ApiErrorData)
        message: Human-readable error description
        method: HTTP method
        url: Request URL
        status_code: HTTP status code (if available)
        request_id: Request ID for tracing
        response_headers: Response headers (if available)
        response_body_snippet: Truncated response body
        cause: Original exception that caused this error
    """

    def __init__(
        self,
        *,
        message: str,
        method: str,
        url: str,
        status_code: int | None = None,
        request_id: str | None = None,
        response_headers: dict[str, str] | None = None,
        response_body_snippet: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.data = ApiErrorData(
            message=message,
            method=method,
            url=url,
            status_code=status_code,
            request_id=request_id,
            response_headers=response_headers,
            response_body_snippet=response_body_snippet,
            cause=cause,
        )
        # Expose fields as attributes for convenience
        self.message = self.data.message
        self.method = self.data.method
        self.url = self.data.url
        self.status_code = self.data.status_code
        self.request_id = self.data.request_id
        self.response_headers = self.data.response_headers
        self.response_body_snippet = self.data.response_body_snippet
        self.cause = self.data.cause

        super().__init__(str(self))

    def __str__(self) -> str:
        """Format error for logging and display."""
        parts = [self.message, f"{self.method} {self.url}"]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return " | ".join(parts)


class NetworkError(ApiError):
    """Network-level error (DNS, connection reset, etc.)."""


class TimeoutError(ApiError):
    """Request timed out."""


class DecodeError(ApiError):
    """Failed to decode response body (JSON/schema)."""


class RateLimitError(ApiError):
    """HTTP 429 rate limit error."""


class AuthError(ApiError):
    """HTTP 401/403 authentication or authorization error."""


class ClientError(ApiError):
    """HTTP 4xx client error (excluding auth and rate limit)."""


class ServerError(ApiError):
    """HTTP 5xx server error."""


class UnexpectedStatusError(ApiError):
    """Non-2xx status that doesn't match a more specific category."""
