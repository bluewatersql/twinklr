"""Null logger that discards all output.

Use for testing or when logging is disabled.
"""

from typing import Any


class NullLogger:
    """Logger that discards all output.

    Useful for:
    - Testing (avoid cluttering test output)
    - Disabled logging configuration
    - Dependency injection default

    Example:
        logger = NullLogger()
        logger.info("This goes nowhere")  # No output
    """

    def log(
        self,
        level: str,
        message: str,
        context: dict[str, Any] | None = None,
        **fields: Any,
    ) -> None:
        """Discard log message.

        Args:
            level: Log level (ignored)
            message: Message (ignored)
            context: Context (ignored)
            **fields: Fields (ignored)
        """

    def debug(self, message: str, **fields: Any) -> None:
        """Discard debug message.

        Args:
            message: Message (ignored)
            **fields: Fields (ignored)
        """

    def info(self, message: str, **fields: Any) -> None:
        """Discard info message.

        Args:
            message: Message (ignored)
            **fields: Fields (ignored)
        """

    def warning(self, message: str, **fields: Any) -> None:
        """Discard warning message.

        Args:
            message: Message (ignored)
            **fields: Fields (ignored)
        """

    def error(self, message: str, **fields: Any) -> None:
        """Discard error message.

        Args:
            message: Message (ignored)
            **fields: Fields (ignored)
        """

    def flush(self) -> None:
        """No-op flush."""

    def __enter__(self) -> "NullLogger":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager (no-op)."""
