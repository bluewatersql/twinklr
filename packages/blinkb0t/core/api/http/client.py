"""Production-ready HTTP client wrapper built on HTTPX.

Provides:
- Automatic retries with exponential backoff
- Structured error handling
- Request/response logging with redaction
- Auth integration (API key, Bearer token)
- Pydantic response parsing
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

import httpx

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
from blinkb0t.core.api.http.logging_utils import RequestLogContext, log_request, log_response
from blinkb0t.core.api.http.retry import RetryPolicy, parse_retry_after_seconds
from blinkb0t.core.api.http.utils import get_request_id, join_url, safe_snippet

T = TypeVar("T")


def _merge_headers(base: Mapping[str, str], extra: Mapping[str, str] | None) -> dict[str, str]:
    """Merge base headers with request-specific headers."""
    out = dict(base)
    if extra:
        out.update(extra)
    return out


def _merge_params(base: Mapping[str, str], extra: Mapping[str, str] | None) -> dict[str, str]:
    """Merge base params with request-specific params."""
    out = dict(base)
    if extra:
        out.update({k: str(v) for k, v in extra.items()})
    return out


def _default_request_id() -> str:
    """Generate simple timestamp-based request ID."""
    return f"req_{int(time.time() * 1000)}"


def _is_json_response(resp: httpx.Response) -> bool:
    """Check if response content-type indicates JSON."""
    ctype = resp.headers.get("content-type", "")
    return "application/json" in ctype or "+json" in ctype


def _categorize_http_error(status_code: int) -> type[ApiError]:
    """Map HTTP status code to appropriate error class."""
    if status_code in (401, 403):
        return AuthError
    if status_code == 429:
        return RateLimitError
    if 400 <= status_code < 500:
        return ClientError
    if 500 <= status_code < 600:
        return ServerError
    return UnexpectedStatusError


def _build_api_error(
    *,
    exc_type: type[ApiError],
    message: str,
    method: str,
    url: str,
    status_code: int | None = None,
    response: httpx.Response | None = None,
    request_id: str | None = None,
    body_snippet_limit: int = 4096,
    cause: BaseException | None = None,
) -> ApiError:
    """Build API error with response context.

    Args:
        exc_type: Error class to instantiate
        message: Human-readable error message
        method: HTTP method
        url: Request URL
        status_code: HTTP status code (if available)
        response: HTTP response (if available)
        request_id: Request ID for tracing
        body_snippet_limit: Max bytes to include in error
        cause: Original exception that triggered this error

    Returns:
        Constructed API error
    """
    headers: dict[str, str] | None = None
    snippet: str | None = None
    if response is not None:
        headers = dict(response.headers)
        snippet = safe_snippet(response.content or b"", body_snippet_limit)
        request_id = request_id or get_request_id(response.headers)

    return exc_type(
        message=message,
        method=method,
        url=url,
        status_code=status_code,
        request_id=request_id,
        response_headers=headers,
        response_body_snippet=snippet,
        cause=cause,
    )


class ApiClient:
    """Synchronous production-grade HTTP API client.

    Built on httpx.Client with automatic retries, structured errors, and observability.

    Args:
        config: Client configuration
        auth: Optional authentication handler (e.g. ApiKeyAuth, BearerTokenAuth)
        retry_policy: Retry policy (defaults to safe retries on GET/HEAD/OPTIONS/DELETE)
        transport: Optional custom transport (useful for testing)

    Example:
        >>> from blinkb0t.core.api.http import ApiClient, HttpClientConfig, ApiKeyAuth
        >>> config = HttpClientConfig(base_url="https://api.example.com")
        >>> auth = ApiKeyAuth(header_name="X-API-Key", api_key="secret")
        >>> with ApiClient(config, auth=auth) as client:
        ...     resp = client.get("/v1/users")
        ...     data = client.json(resp)
    """

    def __init__(
        self,
        config: HttpClientConfig,
        *,
        auth: httpx.Auth | None = None,
        retry_policy: RetryPolicy | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.auth = auth
        self.retry_policy = retry_policy or RetryPolicy()
        self._client = httpx.Client(
            base_url=config.base_url,
            headers={"User-Agent": config.user_agent, **config.headers},
            params=config.params,
            timeout=config.timeout,
            limits=config.limits,
            follow_redirects=config.follow_redirects,
            http2=config.http2,
            verify=config.verify,
            cert=config.cert,
            auth=auth,
            transport=transport,
        )

    def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        self._client.close()

    def __enter__(self) -> ApiClient:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Context manager exit."""
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Any = None,
        data: Any = None,
        files: Any = None,
        timeout: httpx.Timeout | None = None,
        idempotency_key: str | None = None,
        expected_status: Sequence[int] | None = None,
    ) -> httpx.Response:
        method_u = method.upper()
        url = join_url(str(self._client.base_url), path)
        req_id = headers.get("X-Request-Id") if headers else None
        req_id = req_id or _default_request_id()

        merged_headers = _merge_headers(self._client.headers, headers)
        merged_headers.setdefault("X-Request-Id", req_id)
        if idempotency_key:
            merged_headers.setdefault("Idempotency-Key", idempotency_key)

        merged_params = _merge_params(self._client.params, params)

        # Retry loop
        attempts = 0

        while True:
            attempts += 1
            ctx = RequestLogContext(method=method_u, url=url, attempt=attempts, request_id=req_id)
            start = log_request(ctx, merged_headers, self.config.redact_headers)

            try:
                resp = self._client.request(
                    method_u,
                    url,
                    params=merged_params,
                    headers=merged_headers,
                    json=json_body,
                    data=data,
                    files=files,
                    timeout=timeout or self.config.timeout,
                )
                elapsed = time.perf_counter() - start
                log_response(ctx, resp.status_code, elapsed)

                if expected_status is not None:
                    if resp.status_code not in expected_status:
                        exc_cls = _categorize_http_error(resp.status_code)
                        raise _build_api_error(
                            exc_type=exc_cls,
                            message=f"Unexpected status code (expected {list(expected_status)})",
                            method=method_u,
                            url=url,
                            status_code=resp.status_code,
                            response=resp,
                            request_id=req_id,
                            body_snippet_limit=self.config.max_response_body_for_error,
                        )
                else:
                    if resp.status_code >= 400:
                        exc_cls = _categorize_http_error(resp.status_code)
                        raise _build_api_error(
                            exc_type=exc_cls,
                            message="HTTP error response",
                            method=method_u,
                            url=url,
                            status_code=resp.status_code,
                            response=resp,
                            request_id=req_id,
                            body_snippet_limit=self.config.max_response_body_for_error,
                        )

                return resp

            except ApiError as e:
                # Already normalized; decide retry based on status.
                status = e.status_code
                if status is None:
                    raise

                if not self.retry_policy.allows_method(method_u):
                    raise

                if status not in self.retry_policy.retry_on_status:
                    raise

                if attempts >= self.retry_policy.max_attempts:
                    raise

                retry_after = None
                if e.response_headers:
                    retry_after = parse_retry_after_seconds(e.response_headers.get("Retry-After"))
                delay = (
                    retry_after
                    if retry_after is not None
                    else self.retry_policy.compute_delay(attempts)
                )
                time.sleep(delay)
                continue

            except httpx.TimeoutException as e:
                if (
                    not self.retry_policy.allows_method(method_u)
                    or attempts >= self.retry_policy.max_attempts
                ):
                    raise _build_api_error(
                        exc_type=TimeoutError,
                        message="Request timed out",
                        method=method_u,
                        url=url,
                        status_code=None,
                        response=None,
                        request_id=req_id,
                        body_snippet_limit=self.config.max_response_body_for_error,
                        cause=e,
                    ) from e
                time.sleep(self.retry_policy.compute_delay(attempts))
                continue

            except httpx.RequestError as e:
                if (
                    not self.retry_policy.allows_method(method_u)
                    or attempts >= self.retry_policy.max_attempts
                ):
                    raise _build_api_error(
                        exc_type=NetworkError,
                        message="Network error while sending request",
                        method=method_u,
                        url=url,
                        status_code=None,
                        response=None,
                        request_id=req_id,
                        body_snippet_limit=self.config.max_response_body_for_error,
                        cause=e,
                    ) from e
                time.sleep(self.retry_policy.compute_delay(attempts))
                continue

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Perform GET request.

        Args:
            path: Request path (relative to base_url)
            **kwargs: Additional arguments passed to request()

        Returns:
            HTTP response

        Raises:
            ApiError: On request failure
        """
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Perform POST request.

        Args:
            path: Request path (relative to base_url)
            **kwargs: Additional arguments passed to request()

        Returns:
            HTTP response

        Raises:
            ApiError: On request failure
        """
        return self.request("POST", path, **kwargs)

    def json(self, response: httpx.Response) -> Any:
        """Decode JSON response with structured error handling.

        Args:
            response: HTTP response to decode

        Returns:
            Decoded JSON data (dict, list, etc.)

        Raises:
            DecodeError: If response is not JSON or parsing fails
        """
        if response.status_code == 204 or not response.content:
            return None
        if not _is_json_response(response):
            raise _build_api_error(
                exc_type=DecodeError,
                message="Response is not JSON (content-type mismatch)",
                method=response.request.method,
                url=str(response.request.url),
                status_code=response.status_code,
                response=response,
                request_id=get_request_id(response.headers),
                body_snippet_limit=self.config.max_response_body_for_error,
            )
        try:
            return response.json()
        except Exception as e:
            raise _build_api_error(
                exc_type=DecodeError,
                message="Failed to parse JSON response",
                method=response.request.method,
                url=str(response.request.url),
                status_code=response.status_code,
                response=response,
                request_id=get_request_id(response.headers),
                body_snippet_limit=self.config.max_response_body_for_error,
                cause=e,
            ) from e

    def parse_pydantic(self, response: httpx.Response, model: Any) -> Any:
        """Parse and validate JSON response with Pydantic model.

        Args:
            response: HTTP response to parse
            model: Pydantic model class with model_validate method

        Returns:
            Validated model instance

        Raises:
            DecodeError: If JSON parsing or validation fails
        """
        data = self.json(response)
        try:
            return model.model_validate(data)
        except Exception as e:
            raise _build_api_error(
                exc_type=DecodeError,
                message="Failed to validate response with Pydantic model",
                method=response.request.method,
                url=str(response.request.url),
                status_code=response.status_code,
                response=response,
                request_id=get_request_id(response.headers),
                body_snippet_limit=self.config.max_response_body_for_error,
                cause=e,
            ) from e


class AsyncApiClient:
    """Asynchronous production-grade HTTP API client.

    Built on httpx.AsyncClient with automatic retries, structured errors, and observability.

    Args:
        config: Client configuration
        auth: Optional authentication handler (e.g. ApiKeyAuth, BearerTokenAuth)
        retry_policy: Retry policy (defaults to safe retries on GET/HEAD/OPTIONS/DELETE)
        transport: Optional custom transport (useful for testing)

    Example:
        >>> from blinkb0t.core.api.http import AsyncApiClient, HttpClientConfig
        >>> config = HttpClientConfig(base_url="https://api.example.com")
        >>> async with AsyncApiClient(config) as client:
        ...     resp = await client.get("/v1/users")
        ...     data = client.json(resp)
    """

    def __init__(
        self,
        config: HttpClientConfig,
        *,
        auth: httpx.Auth | None = None,
        retry_policy: RetryPolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.auth = auth
        self.retry_policy = retry_policy or RetryPolicy()
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={"User-Agent": config.user_agent, **config.headers},
            params=config.params,
            timeout=config.timeout,
            limits=config.limits,
            follow_redirects=config.follow_redirects,
            http2=config.http2,
            verify=config.verify,
            cert=config.cert,
            auth=auth,
            transport=transport,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client and release resources."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncApiClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Async context manager exit."""
        await self.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Any = None,
        data: Any = None,
        files: Any = None,
        timeout: httpx.Timeout | None = None,
        idempotency_key: str | None = None,
        expected_status: Sequence[int] | None = None,
    ) -> httpx.Response:
        method_u = method.upper()
        url = join_url(str(self._client.base_url), path)
        req_id = headers.get("X-Request-Id") if headers else None
        req_id = req_id or _default_request_id()

        merged_headers = _merge_headers(self._client.headers, headers)
        merged_headers.setdefault("X-Request-Id", req_id)
        if idempotency_key:
            merged_headers.setdefault("Idempotency-Key", idempotency_key)

        merged_params = _merge_params(self._client.params, params)

        attempts = 0

        while True:
            attempts += 1
            ctx = RequestLogContext(method=method_u, url=url, attempt=attempts, request_id=req_id)
            start = log_request(ctx, merged_headers, self.config.redact_headers)

            try:
                resp = await self._client.request(
                    method_u,
                    url,
                    params=merged_params,
                    headers=merged_headers,
                    json=json_body,
                    data=data,
                    files=files,
                    timeout=timeout or self.config.timeout,
                )
                elapsed = time.perf_counter() - start
                log_response(ctx, resp.status_code, elapsed)

                if expected_status is not None:
                    if resp.status_code not in expected_status:
                        exc_cls = _categorize_http_error(resp.status_code)
                        raise _build_api_error(
                            exc_type=exc_cls,
                            message=f"Unexpected status code (expected {list(expected_status)})",
                            method=method_u,
                            url=url,
                            status_code=resp.status_code,
                            response=resp,
                            request_id=req_id,
                            body_snippet_limit=self.config.max_response_body_for_error,
                        )
                else:
                    if resp.status_code >= 400:
                        exc_cls = _categorize_http_error(resp.status_code)
                        raise _build_api_error(
                            exc_type=exc_cls,
                            message="HTTP error response",
                            method=method_u,
                            url=url,
                            status_code=resp.status_code,
                            response=resp,
                            request_id=req_id,
                            body_snippet_limit=self.config.max_response_body_for_error,
                        )

                return resp

            except ApiError as e:
                status = e.status_code
                if status is None:
                    raise

                if not self.retry_policy.allows_method(method_u):
                    raise

                if status not in self.retry_policy.retry_on_status:
                    raise

                if attempts >= self.retry_policy.max_attempts:
                    raise

                retry_after = None
                if e.response_headers:
                    retry_after = parse_retry_after_seconds(e.response_headers.get("Retry-After"))
                delay = (
                    retry_after
                    if retry_after is not None
                    else self.retry_policy.compute_delay(attempts)
                )
                await asyncio.sleep(delay)
                continue

            except httpx.TimeoutException as e:
                if (
                    not self.retry_policy.allows_method(method_u)
                    or attempts >= self.retry_policy.max_attempts
                ):
                    raise _build_api_error(
                        exc_type=TimeoutError,
                        message="Request timed out",
                        method=method_u,
                        url=url,
                        status_code=None,
                        response=None,
                        request_id=req_id,
                        body_snippet_limit=self.config.max_response_body_for_error,
                        cause=e,
                    ) from e
                await asyncio.sleep(self.retry_policy.compute_delay(attempts))
                continue

            except httpx.RequestError as e:
                if (
                    not self.retry_policy.allows_method(method_u)
                    or attempts >= self.retry_policy.max_attempts
                ):
                    raise _build_api_error(
                        exc_type=NetworkError,
                        message="Network error while sending request",
                        method=method_u,
                        url=url,
                        status_code=None,
                        response=None,
                        request_id=req_id,
                        body_snippet_limit=self.config.max_response_body_for_error,
                        cause=e,
                    ) from e
                await asyncio.sleep(self.retry_policy.compute_delay(attempts))
                continue

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Perform async GET request.

        Args:
            path: Request path (relative to base_url)
            **kwargs: Additional arguments passed to request()

        Returns:
            HTTP response

        Raises:
            ApiError: On request failure
        """
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Perform async POST request.

        Args:
            path: Request path (relative to base_url)
            **kwargs: Additional arguments passed to request()

        Returns:
            HTTP response

        Raises:
            ApiError: On request failure
        """
        return await self.request("POST", path, **kwargs)

    def json(self, response: httpx.Response) -> Any:
        """Decode JSON response with structured error handling.

        Args:
            response: HTTP response to decode

        Returns:
            Decoded JSON data (dict, list, etc.)

        Raises:
            DecodeError: If response is not JSON or parsing fails
        """
        if response.status_code == 204 or not response.content:
            return None
        if not _is_json_response(response):
            raise _build_api_error(
                exc_type=DecodeError,
                message="Response is not JSON (content-type mismatch)",
                method=response.request.method,
                url=str(response.request.url),
                status_code=response.status_code,
                response=response,
                request_id=get_request_id(response.headers),
                body_snippet_limit=self.config.max_response_body_for_error,
            )
        try:
            return response.json()
        except Exception as e:
            raise _build_api_error(
                exc_type=DecodeError,
                message="Failed to parse JSON response",
                method=response.request.method,
                url=str(response.request.url),
                status_code=response.status_code,
                response=response,
                request_id=get_request_id(response.headers),
                body_snippet_limit=self.config.max_response_body_for_error,
                cause=e,
            ) from e

    def parse_pydantic(self, response: httpx.Response, model: Any) -> Any:
        """Parse and validate JSON response with Pydantic model.

        Args:
            response: HTTP response to parse
            model: Pydantic model class with model_validate method

        Returns:
            Validated model instance

        Raises:
            DecodeError: If JSON parsing or validation fails
        """
        data = self.json(response)
        try:
            return model.model_validate(data)
        except Exception as e:
            raise _build_api_error(
                exc_type=DecodeError,
                message="Failed to validate response with Pydantic model",
                method=response.request.method,
                url=str(response.request.url),
                status_code=response.status_code,
                response=response,
                request_id=get_request_id(response.headers),
                body_snippet_limit=self.config.max_response_body_for_error,
                cause=e,
            ) from e
