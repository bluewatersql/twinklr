"""Production-ready HTTPX wrapper.

Exposes a small, ergonomic surface:
- ApiClient / AsyncApiClient: high-level clients
- HttpClientConfig: configuration
- Exceptions: ApiError and subclasses
- Auth helpers: ApiKeyAuth, BearerTokenAuth, TokenProvider
"""

from blinkb0t.core.api.http.auth import ApiKeyAuth, BearerTokenAuth, TokenProvider
from blinkb0t.core.api.http.client import ApiClient, AsyncApiClient
from blinkb0t.core.api.http.config import HttpClientConfig
from blinkb0t.core.api.http.errors import (
    ApiError,
    AuthError,
    ClientError,
    DecodeError,
    NetworkError,
    RateLimitError,
    ServerError,
    TimeoutError,
    UnexpectedStatusError,
)

__all__ = [
    "ApiClient",
    "AsyncApiClient",
    "HttpClientConfig",
    "ApiKeyAuth",
    "BearerTokenAuth",
    "TokenProvider",
    "ApiError",
    "NetworkError",
    "TimeoutError",
    "DecodeError",
    "RateLimitError",
    "AuthError",
    "ClientError",
    "ServerError",
    "UnexpectedStatusError",
]
