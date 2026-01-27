from __future__ import annotations

import httpx
from pydantic import BaseModel, Field, field_validator


class HttpClientConfig(BaseModel):
    """Configuration for ApiClient / AsyncApiClient.

    Production-ready HTTP client configuration with sensible defaults.

    Args:
        base_url: Base URL for all requests (e.g. "https://api.example.com")
        timeout: HTTPX timeout configuration
        limits: Connection pool limits
        follow_redirects: Whether to follow HTTP redirects
        http2: Enable HTTP/2 support
        headers: Default headers applied to all requests
        params: Default query parameters applied to all requests
        verify: TLS certificate verification (True, False, or path to CA bundle)
        cert: Client certificate (path or tuple of (cert, key))
        user_agent: User-Agent header value
        redact_headers: Headers to redact in logs (case-insensitive)
        max_response_body_for_error: Max response bytes to include in error messages
    """

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    base_url: str
    timeout: httpx.Timeout = Field(default_factory=lambda: httpx.Timeout(10.0, connect=5.0))
    limits: httpx.Limits = Field(
        default_factory=lambda: httpx.Limits(max_keepalive_connections=20, max_connections=100)
    )
    follow_redirects: bool = True
    http2: bool = False
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    verify: bool | str = True
    cert: str | tuple[str, str] | None = None
    user_agent: str = "http-client/1.0"
    redact_headers: tuple[str, ...] = (
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
    )
    max_response_body_for_error: int = 4096

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base_url is a valid URL."""
        if not v:
            raise ValueError("base_url cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v
