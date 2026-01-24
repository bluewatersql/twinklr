"""Logging configuration utilities for BlinkB0t.

Provides centralized logging configuration with:
- Flexible output (stdout or file)
- Customizable format strings
- Multiple log levels
- Context-aware logging with LoggerAdapter
"""

from __future__ import annotations

import logging
import sys
from typing import Any


def configure_logging(
    level: str = "INFO", format_string: str | None = None, filename: str | None = None
) -> None:
    """Configure application-wide logging.

    This function sets up logging for the entire application. It can be called
    multiple times to reconfigure logging (uses force=True to override).

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Case-insensitive.
        format_string: Custom format string for log messages.
                      If None, uses a default format with timestamp and level.
        filename: Path to log file. If None, logs to stdout.

    Example:
        >>> configure_logging(level="DEBUG")
        >>> configure_logging(level="INFO", filename="app.log")
        >>> configure_logging(
        ...     level="DEBUG",
        ...     format_string="%(levelname)s - %(message)s",
        ...     filename="debug.log"
        ... )
    """
    # Use default format if not provided
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Create handlers list
    handlers: list[logging.Handler] = []

    if filename:
        # Log to file
        handlers.append(logging.FileHandler(filename))
    else:
        # Log to stdout
        handlers.append(logging.StreamHandler(sys.stdout))

    # Configure root logger
    # Use force=True to override any existing configuration
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=handlers,
        force=True,  # Allow reconfiguration
    )


def get_logger(name: str, **kwargs: Any) -> logging.Logger | logging.LoggerAdapter:
    """Get a configured logger instance.

    If context kwargs are provided, returns a LoggerAdapter that automatically
    includes the context in all log messages.

    Args:
        name: Logger name (usually __name__ from the calling module)
        **kwargs: Additional context to include in logs (e.g., request_id, user)

    Returns:
        Logger instance, or LoggerAdapter if context provided

    Example:
        >>> # Simple logger
        >>> logger = get_logger(__name__)
        >>> logger.debug("Starting process")

        >>> # Logger with context
        >>> logger = get_logger(__name__, request_id="123", user="alice")
        >>> logger.debug("Processing request")
        >>> # Output: ... - Processing request - 123
    """
    logger = logging.getLogger(name)

    # If context provided, wrap in LoggerAdapter
    if kwargs:
        return logging.LoggerAdapter(logger, kwargs)

    return logger
