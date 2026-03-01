"""Sanitization utilities for LLM prompt input fields."""

_MAX_METADATA_LENGTH = 200


def sanitize_metadata_field(value: str | None, max_length: int = _MAX_METADATA_LENGTH) -> str:
    """Sanitize a metadata field for safe inclusion in LLM prompts.

    Truncates to max_length, strips control characters, and cleans
    untrusted metadata before it enters prompt templates.

    Args:
        value: Raw metadata value.
        max_length: Maximum allowed length.

    Returns:
        Sanitized string, or empty string if value is None.
    """
    if value is None:
        return ""
    cleaned = value.strip()
    # Remove control characters (keep printable + newlines + tabs)
    cleaned = "".join(c for c in cleaned if c.isprintable() or c in ("\n", "\t"))
    # Truncate
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + "..."
    return cleaned
