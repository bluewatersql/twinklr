"""Logging configuration utilities for BlinkB0t.

Provides centralized logging configuration with:
- Flexible output (stdout or file)
- Customizable format strings
- Multiple log levels
- Context-aware logging with LoggerAdapter
"""

from __future__ import annotations

import functools
import logging
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)


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


def get_renderer_logger() -> logging.Logger:
    """Get the renderer logger."""
    return logging.getLogger("TINKLR_RENDER")


def get_logger(name: str, **kwargs: Any) -> logging.Logger | logging.LoggerAdapter:
    """Get a configured logger instance.

    If context kwargs are provided, returns a LoggerAdapter that automatically
    includes the context in all log messages.

    Args:
        name: Logger name (usually __name__ from the calling module)
        **kwargs: Additional context to include in logs (e.g., request_id, user)

    Returns:
        Logger instance, or LoggerAdapter if context provided
    """
    logger = logging.getLogger(name)

    # If context provided, wrap in LoggerAdapter
    if kwargs:
        return logging.LoggerAdapter(logger, kwargs)

    return logger


def log_performance(func):
    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        get_renderer_logger().debug(
            f"Function {func.__name__!r} took {execution_time:.4f} seconds to execute."
        )
        return result

    return wrapper_timer
