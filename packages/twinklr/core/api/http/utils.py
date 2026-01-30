"""Utility functions for HTTP client operations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urljoin


def join_url(base_url: str, path: str) -> str:
    """Join base URL with path in a predictable way.

    Ensures base URL ends with '/' and strips leading '/' from path.

    Args:
        base_url: Base URL (e.g. "https://api.example.com")
        path: Request path (e.g. "/v1/users" or "v1/users")

    Returns:
        Joined URL (e.g. "https://api.example.com/v1/users")
    """
    base = base_url if base_url.endswith("/") else base_url + "/"
    return urljoin(base, path.lstrip("/"))


def safe_snippet(content: bytes, limit: int) -> str:
    """Extract safe text snippet from response content for logging.

    Truncates content and decodes as UTF-8 with replacement for invalid bytes.

    Args:
        content: Response body bytes
        limit: Maximum number of bytes to include

    Returns:
        Truncated, decoded text snippet
    """
    if not content:
        return ""
    c = content[:limit]
    try:
        return c.decode("utf-8", errors="replace")
    except Exception:
        return repr(c)


def get_request_id(headers: Mapping[str, str]) -> str | None:
    """Extract request ID from common tracing headers.

    Checks for: x-request-id, x-correlation-id, request-id, trace-id (case-insensitive).

    Args:
        headers: Response headers

    Returns:
        Request ID if found, None otherwise
    """
    for key in ("x-request-id", "x-correlation-id", "request-id", "trace-id"):
        for hk, hv in headers.items():
            if hk.lower() == key:
                return hv
    return None


def json_loads_strict(text: str) -> Any:
    """Load JSON with strict parsing (for future customization).

    Args:
        text: JSON string

    Returns:
        Parsed JSON data

    Raises:
        json.JSONDecodeError: If parsing fails
    """
    return json.loads(text)
