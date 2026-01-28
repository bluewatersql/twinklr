"""Core logging abstraction for BlinkB0t.

This module provides structured logging with protocol-based
implementations for JSON, YAML, and null outputs.
"""

from .json_logger import JSONLogger
from .models import LogContext, LogEntry, LogLevel
from .null_logger import NullLogger
from .protocol import StructuredLogger
from .sanitize import add_custom_pattern, add_sensitive_key, sanitize_dict, sanitize_string
from .yaml_logger import YAMLLogger

__all__ = [
    # Protocol
    "StructuredLogger",
    # Implementations
    "JSONLogger",
    "YAMLLogger",
    "NullLogger",
    # Models
    "LogLevel",
    "LogContext",
    "LogEntry",
    # Sanitization
    "sanitize_string",
    "sanitize_dict",
    "add_custom_pattern",
    "add_sensitive_key",
]
