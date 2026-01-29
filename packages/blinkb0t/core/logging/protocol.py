"""Protocol definition for structured logging."""

from typing import Any, Protocol


class StructuredLogger(Protocol):
    """Protocol for structured logging implementations.

    Structured loggers write logs with rich metadata beyond
    just the message string. This enables programmatic analysis,
    querying, and aggregation.
    """

    def log(
        self,
        level: str,
        message: str,
        context: dict[str, Any] | None = None,
        **fields: Any,
    ) -> None:
        """Log a structured message with context.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Human-readable message
            context: Structured context dictionary
            **fields: Additional fields to include in log
        """
        ...

    def debug(self, message: str, **fields: Any) -> None:
        """Log debug message with structured fields.

        Args:
            message: Debug message
            **fields: Structured fields
        """
        ...

    def info(self, message: str, **fields: Any) -> None:
        """Log info message with structured fields.

        Args:
            message: Info message
            **fields: Structured fields
        """
        ...

    def warning(self, message: str, **fields: Any) -> None:
        """Log warning message with structured fields.

        Args:
            message: Warning message
            **fields: Structured fields
        """
        ...

    def error(self, message: str, **fields: Any) -> None:
        """Log error message with structured fields.

        Args:
            message: Error message
            **fields: Structured fields
        """
        ...

    def flush(self) -> None:
        """Flush any buffered logs to output."""
        ...
