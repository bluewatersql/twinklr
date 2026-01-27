from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Protocol

import httpx
from pydantic import BaseModel, Field


class TokenProvider(Protocol):
    """Protocol for providing and refreshing bearer tokens.

    Implementations can fetch tokens from various sources:
    - In-memory cache
    - File system
    - OAuth flow
    - Internal auth service

    The HTTP client only depends on this narrow interface.
    """

    def get_token(self) -> str:
        """Get current token.

        Returns:
            Valid bearer token

        Raises:
            Exception if token cannot be retrieved
        """
        ...

    def refresh_token(self) -> str:
        """Refresh and return new token.

        Returns:
            New valid bearer token

        Raises:
            Exception if token cannot be refreshed
        """
        ...


class ApiKeyAuth(httpx.Auth, BaseModel):
    """Static API key header authentication.

    Supports both sync and async requests.

    Args:
        header_name: Header name for the API key (e.g. "X-API-Key")
        api_key: API key value
        prefix: Optional prefix for the key value (e.g. "Bearer")

    Example:
        >>> auth = ApiKeyAuth(header_name="X-API-Key", api_key="secret")
        >>> # Or with bearer prefix:
        >>> auth = ApiKeyAuth(header_name="Authorization", api_key="token", prefix="Bearer")
    """

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    header_name: str
    api_key: str = Field(repr=False)  # Don't leak secrets in repr
    prefix: str | None = None

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Apply API key to request (sync).

        Args:
            request: Request to authenticate

        Yields:
            Request with API key header
        """
        value = f"{self.prefix} {self.api_key}" if self.prefix else self.api_key
        request.headers[self.header_name] = value
        yield request

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """Apply API key to request (async).

        Args:
            request: Request to authenticate

        Yields:
            Request with API key header
        """
        value = f"{self.prefix} {self.api_key}" if self.prefix else self.api_key
        request.headers[self.header_name] = value
        yield request


class BearerTokenAuth(httpx.Auth):
    """Bearer token authentication with automatic refresh on 401.

    Uses a TokenProvider to fetch and refresh tokens.

    Args:
        provider: Token provider implementation
        header_name: Header name for the token (default: "Authorization")

    Example:
        >>> class MyTokenProvider:
        ...     def get_token(self) -> str:
        ...         return "current_token"
        ...     def refresh_token(self) -> str:
        ...         return "new_token"
        >>> auth = BearerTokenAuth(provider=MyTokenProvider())
    """

    requires_response_body = True

    def __init__(self, provider: TokenProvider, header_name: str = "Authorization") -> None:
        self._provider = provider
        self._header_name = header_name

    def _apply(self, request: httpx.Request, token: str) -> None:
        """Apply bearer token to request headers.

        Args:
            request: Request to modify
            token: Token value
        """
        request.headers[self._header_name] = f"Bearer {token}"

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Apply bearer token with auto-refresh on 401 (sync).

        Args:
            request: Request to authenticate

        Yields:
            Request with bearer token header
        """
        token = self._provider.get_token()
        self._apply(request, token)
        response = yield request

        if response and response.status_code == 401:
            # Refresh and retry once
            token = self._provider.refresh_token()
            # Build new request with same params but fresh token
            new_request = request.__class__(
                method=request.method,
                url=request.url,
                headers=request.headers.copy(),
                content=request.content,
            )
            self._apply(new_request, token)
            yield new_request

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """Apply bearer token with auto-refresh on 401 (async).

        Args:
            request: Request to authenticate

        Yields:
            Request with bearer token header
        """
        token = self._provider.get_token()
        self._apply(request, token)
        response = yield request

        if response and response.status_code == 401:
            # Refresh and retry once
            token = self._provider.refresh_token()
            # Build new request with same params but fresh token
            new_request = request.__class__(
                method=request.method,
                url=request.url,
                headers=request.headers.copy(),
                content=request.content,
            )
            self._apply(new_request, token)
            yield new_request
