"""Logging configuration utilities for Twinklr.

Provides centralized logging configuration with:
- Flexible output (stdout or file)
- Customizable format strings
- Multiple log levels
- Context-aware logging with LoggerAdapter
- Structured logging support (JSON format)
"""

from __future__ import annotations

import functools
import json
import logging
import sys
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class StructuredJSONFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs.

    Produces logs in the same format as core.logging.json_logger.JSONLogger,
    making them compatible with existing log analysis tools.

    Format follows LogEntry model:
    {
        "level": "INFO",
        "message": "...",
        "timestamp": "2026-01-29T12:00:00.000000Z",
        "context": {
            "logger_name": "...",
            "module": "...",
            "function": "...",
            "line": 42,
            ...extra fields...
        }
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON.

        Args:
            record: LogRecord to format

        Returns:
            JSON-formatted log string
        """
        # Build context from record attributes
        context: dict[str, Any] = {
            "logger_name": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
            "process": record.process,
        }

        # Add exception info if present
        if record.exc_info:
            context["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            context["error_message"] = str(record.exc_info[1]) if record.exc_info[1] else None
            if record.exc_text:
                context["stack_trace"] = record.exc_text
            elif record.exc_info:
                context["stack_trace"] = self.formatException(record.exc_info)

        # Add extra fields from LoggerAdapter or extra kwargs
        if hasattr(record, "__dict__"):
            # Standard record attributes to exclude from context
            standard_attrs = {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
            }
            for key, value in record.__dict__.items():
                if key not in standard_attrs and not key.startswith("_"):
                    context[key] = value

        # Build log entry in LogEntry format
        log_entry = {
            "level": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "context": context,
        }

        # Serialize to JSON
        return json.dumps(log_entry, default=str)


def _supress_noisy_loggers() -> None:
    """Supress noisy loggers."""
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("openai").setLevel(logging.ERROR)
    logging.getLogger("numba").setLevel(logging.ERROR)
    logging.getLogger("asyncio").setLevel(logging.ERROR)
    logging.getLogger("matplotlib").setLevel(logging.ERROR)
    logging.getLogger("speechbrain").setLevel(logging.ERROR)
    logging.getLogger("speechbrain.utils.checkpoints").setLevel(logging.ERROR)
    logging.getLogger("fsspec.local").setLevel(logging.ERROR)


def configure_logging(
    level: str = "INFO",
    format_string: str | None = None,
    filename: str | None = None,
    structured: bool = False,
) -> None:
    """Configure application-wide logging.

    This function sets up logging for the entire application. It can be called
    multiple times to reconfigure logging (uses force=True to override).

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Case-insensitive.
        format_string: Custom format string for log messages.
                      If None, uses a default format with timestamp and level.
                      Ignored if structured=True.
        filename: Path to log file. If None, logs to stdout.
        structured: If True, use structured JSON logging format.
                   If False, use standard text format.

    Examples:
        Standard text logging:
        >>> configure_logging(level="INFO")

        Structured JSON logging:
        >>> configure_logging(level="INFO", structured=True)

        Structured JSON to file:
        >>> configure_logging(level="DEBUG", structured=True, filename="app.jsonl")
    """
    # Create handlers list
    handlers: list[logging.Handler] = []

    handler: logging.Handler
    if filename:
        # Log to file
        handler = logging.FileHandler(filename)
    else:
        # Log to stdout
        handler = logging.StreamHandler(sys.stdout)

    # Apply formatter based on structured flag
    formatter: logging.Formatter
    if structured:
        # Use structured JSON formatter
        formatter = StructuredJSONFormatter()
    else:
        # Use standard text formatter
        if format_string is None:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        formatter = logging.Formatter(format_string)

    handler.setFormatter(formatter)
    handlers.append(handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=handlers,
        force=True,  # Allow reconfiguration
    )

    _supress_noisy_loggers()


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
