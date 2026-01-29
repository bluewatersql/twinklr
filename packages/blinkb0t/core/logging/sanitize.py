"""Sanitization utilities for removing sensitive data from logs."""

import re
from typing import Any

# Sensitive patterns (regex)
SENSITIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "api_key": re.compile(r"(sk|pk)-[A-Za-z0-9]{32,}"),
    "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    # Phone: Require at least 10 digits total, use word boundaries to avoid matching decimals/floats
    # Matches: +1-555-123-4567, (555) 123-4567, 555-123-4567, 5551234567
    # Does NOT match: 0.0, 5.0, 3, short numbers
    "phone": re.compile(
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"  # US/Canada: 10 digits
        r"|\b\+\d{1,3}[-.\s]?\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b"  # International: 10+ digits
    ),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    # Credit card: Require separators (space/dash) or context, avoid matching long decimals
    # Matches: 4532-1234-5678-9010, 4532 1234 5678 9010
    # Does NOT match: 0.1234567890123456 (decimal with 16 digits after point)
    "credit_card": re.compile(r"\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b"),
}

# Sensitive keys (exact match, case-insensitive)
SENSITIVE_KEYS: set[str] = {
    "api_key",
    "apikey",
    "secret",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "private_key",
    "client_secret",
}


def sanitize_string(text: str) -> str:
    """Sanitize sensitive data from string.

    Replaces sensitive patterns with <REDACTED:PATTERN_NAME>.

    Args:
        text: Input string

    Returns:
        Sanitized string with patterns redacted

    Example:
        >>> sanitize_string("API key: sk-abc123def456ghi789jkl012mno345pqr")
        'API key: <REDACTED:API_KEY>'
    """
    for pattern_name, pattern in SENSITIVE_PATTERNS.items():
        text = pattern.sub(f"<REDACTED:{pattern_name.upper()}>", text)

    return text


def sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize sensitive data from dictionary.

    Recursively processes nested dictionaries and lists.
    Replaces sensitive keys with <REDACTED>.

    Args:
        data: Input dictionary

    Returns:
        New dictionary with sensitive values redacted

    Example:
        >>> sanitize_dict({"user": "alice", "api_key": "sk-secret"})
        {'user': 'alice', 'api_key': '<REDACTED>'}
    """
    sanitized: dict[str, Any] = {}

    for key, value in data.items():
        # Check if key is sensitive
        if key.lower() in SENSITIVE_KEYS:
            sanitized[key] = "<REDACTED>"
            continue

        # Recursively sanitize nested structures
        if isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict(item)
                if isinstance(item, dict)
                else sanitize_string(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        else:
            sanitized[key] = value

    return sanitized


def add_custom_pattern(name: str, pattern: str) -> None:
    """Add custom sanitization pattern.

    Args:
        name: Pattern name (used in redaction placeholder)
        pattern: Regex pattern string

    Example:
        >>> add_custom_pattern("custom_id", r"CUST-[0-9]{8}")
    """
    SENSITIVE_PATTERNS[name] = re.compile(pattern)


def add_sensitive_key(key: str) -> None:
    """Add custom sensitive key.

    Args:
        key: Key name (case-insensitive)

    Example:
        >>> add_sensitive_key("internal_id")
    """
    SENSITIVE_KEYS.add(key.lower())
