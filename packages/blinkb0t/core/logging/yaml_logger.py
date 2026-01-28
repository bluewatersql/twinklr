"""YAML-formatted structured logger for human-readable output."""

from pathlib import Path
from typing import Any

import yaml

from .models import LogContext, LogEntry, LogLevel
from .sanitize import sanitize_dict


class YAMLLogger:
    """YAML-formatted structured logger for human-readable output.

    Writes logs as YAML documents separated by --- for easy reading.
    Best for debugging and development, not high-volume production.

    Example:
        with YAMLLogger(Path("debug.yaml")) as logger:
            logger.info("Started", run_id="abc123")
    """

    def __init__(
        self,
        output_file: Path | None = None,
        sanitize: bool = True,
        buffer_size: int = 10,
    ):
        """Initialize YAML logger.

        Args:
            output_file: Path to output file (None = stdout)
            sanitize: Enable sanitization of sensitive data
            buffer_size: Number of entries to buffer before flush (smaller for YAML)
        """
        self.output_file = output_file
        self.sanitize_enabled = sanitize
        self.buffer_size = buffer_size
        self.buffer: list[dict[str, Any]] = []

        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        level: str,
        message: str,
        context: dict[str, Any] | None = None,
        **fields: Any,
    ) -> None:
        """Log structured message.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Human-readable message
            context: Structured context dictionary
            **fields: Additional fields to include in log
        """
        # Build log entry
        ctx_dict = context or {}
        log_context = LogContext(**ctx_dict, **fields)
        entry = LogEntry(
            level=LogLevel(level),
            message=message,
            context=log_context,
        )

        # Convert to dict
        entry_dict = entry.model_dump(mode="json")

        # Sanitize if enabled
        if self.sanitize_enabled:
            entry_dict = sanitize_dict(entry_dict)

        # Buffer entry
        self.buffer.append(entry_dict)

        # Flush if buffer full
        if len(self.buffer) >= self.buffer_size:
            self.flush()

    def debug(self, message: str, **fields: Any) -> None:
        """Log debug message.

        Args:
            message: Debug message
            **fields: Structured fields
        """
        self.log("DEBUG", message, **fields)

    def info(self, message: str, **fields: Any) -> None:
        """Log info message.

        Args:
            message: Info message
            **fields: Structured fields
        """
        self.log("INFO", message, **fields)

    def warning(self, message: str, **fields: Any) -> None:
        """Log warning message.

        Args:
            message: Warning message
            **fields: Structured fields
        """
        self.log("WARNING", message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        """Log error message.

        Args:
            message: Error message
            **fields: Structured fields
        """
        self.log("ERROR", message, **fields)

    def flush(self) -> None:
        """Flush buffered logs to file."""
        if not self.buffer:
            return

        if self.output_file:
            with self.output_file.open("a") as f:
                for entry in self.buffer:
                    f.write("---\n")
                    f.write(yaml.dump(entry, default_flow_style=False, sort_keys=False))
        else:
            # stdout
            for entry in self.buffer:
                print("---")
                print(yaml.dump(entry, default_flow_style=False, sort_keys=False), end="")

        self.buffer.clear()

    def __enter__(self) -> "YAMLLogger":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager and flush."""
        self.flush()
