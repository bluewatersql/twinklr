"""Utility functions for filesystem operations.

Provides path validation and sanitization helpers.
"""

import re


def sanitize_path_component(component: str) -> str:
    """
    Sanitize a string for use as a filesystem path component.

    Replaces unsafe characters with underscores. Useful for step_ids
    that may contain slashes or special characters.

    Args:
        component: String to sanitize

    Returns:
        Filesystem-safe string

    Example:
        >>> sanitize_path_component("audio/features")
        'audio_features'
        >>> sanitize_path_component("template:v1")
        'template_v1'
        >>> sanitize_path_component("valid_name-123")
        'valid_name-123'
    """
    # Replace anything not alphanumeric, dash, underscore, or dot
    return re.sub(r"[^a-zA-Z0-9._-]", "_", component)
