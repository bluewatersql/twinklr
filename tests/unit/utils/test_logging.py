"""Tests for logging configuration utilities."""

from io import StringIO
import json
import logging
from pathlib import Path
import tempfile

from packages.blinkb0t.core.utils.logging import (
    StructuredJSONFormatter,
    configure_logging,
    get_logger,
)


class TestStructuredJSONFormatter:
    """Test suite for StructuredJSONFormatter."""

    def test_basic_log_format(self):
        """Test basic log record formatting to JSON."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"
        record.module = "test_module"
        record.thread = 12345
        record.threadName = "MainThread"
        record.process = 9999

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert "timestamp" in data
        assert data["context"]["logger_name"] == "test.logger"
        assert data["context"]["module"] == "test_module"
        assert data["context"]["function"] == "test_function"
        assert data["context"]["line"] == 42
        assert data["context"]["thread"] == 12345
        assert data["context"]["thread_name"] == "MainThread"
        assert data["context"]["process"] == 9999

    def test_log_with_extra_fields(self):
        """Test that extra fields are included in context."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.DEBUG,
            pathname="/path/to/file.py",
            lineno=10,
            msg="Debug message",
            args=(),
            exc_info=None,
        )
        record.funcName = "debug_func"
        record.module = "debug_module"
        record.thread = 1
        record.threadName = "Thread-1"
        record.process = 1000

        # Add custom fields (as LoggerAdapter would)
        record.request_id = "req-123"
        record.user_id = "user-456"
        record.custom_data = {"key": "value"}

        output = formatter.format(record)
        data = json.loads(output)

        assert data["context"]["request_id"] == "req-123"
        assert data["context"]["user_id"] == "user-456"
        assert data["context"]["custom_data"] == {"key": "value"}

    def test_log_with_exception(self):
        """Test that exception info is captured in context."""
        formatter = StructuredJSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=100,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        record.funcName = "error_func"
        record.module = "error_module"
        record.thread = 1
        record.threadName = "MainThread"
        record.process = 1000

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "ERROR"
        assert data["message"] == "Error occurred"
        assert data["context"]["error_type"] == "ValueError"
        assert data["context"]["error_message"] == "Test error"
        assert "stack_trace" in data["context"]
        assert "ValueError: Test error" in data["context"]["stack_trace"]

    def test_log_levels(self):
        """Test different log levels are captured correctly."""
        formatter = StructuredJSONFormatter()
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level_name in levels:
            level = getattr(logging, level_name)
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="/test.py",
                lineno=1,
                msg=f"{level_name} message",
                args=(),
                exc_info=None,
            )
            record.funcName = "test"
            record.module = "test"
            record.thread = 1
            record.threadName = "main"
            record.process = 1

            output = formatter.format(record)
            data = json.loads(output)

            assert data["level"] == level_name
            assert data["message"] == f"{level_name} message"


class TestConfigureLogging:
    """Test suite for configure_logging function."""

    def test_configure_standard_logging(self, capsys):
        """Test standard text logging configuration."""
        configure_logging(level="INFO", structured=False)

        logger = logging.getLogger("test.standard")
        logger.info("Test message")

        captured = capsys.readouterr()
        assert "Test message" in captured.out
        assert "test.standard" in captured.out
        assert "INFO" in captured.out

    def test_configure_structured_logging_to_stdout(self, capsys):
        """Test structured JSON logging to stdout."""
        configure_logging(level="INFO", structured=True)

        logger = logging.getLogger("test.structured")
        logger.info("Structured test message")

        captured = capsys.readouterr()
        # Parse JSON from output
        lines = [line for line in captured.out.strip().split("\n") if line]
        if lines:
            data = json.loads(lines[-1])
            assert data["level"] == "INFO"
            assert "Structured test message" in data["message"]
            assert data["context"]["logger_name"] == "test.structured"

    def test_configure_structured_logging_to_file(self):
        """Test structured JSON logging to file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
            log_file = Path(f.name)

        try:
            configure_logging(level="DEBUG", structured=True, filename=str(log_file))

            logger = logging.getLogger("test.file")
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")

            # Read and verify log file
            log_content = log_file.read_text()
            lines = [json.loads(line) for line in log_content.strip().split("\n") if line]

            assert len(lines) >= 3
            levels = [line["level"] for line in lines[-3:]]
            assert "DEBUG" in levels
            assert "INFO" in levels
            assert "WARNING" in levels

            # Verify structure
            for line in lines[-3:]:
                assert "level" in line
                assert "message" in line
                assert "timestamp" in line
                assert "context" in line
                assert "logger_name" in line["context"]

        finally:
            log_file.unlink()

    def test_configure_custom_format_string(self, capsys):
        """Test custom format string for standard logging."""
        custom_format = "%(levelname)s - %(message)s"
        configure_logging(level="INFO", format_string=custom_format, structured=False)

        logger = logging.getLogger("test.custom")
        logger.info("Custom format test")

        captured = capsys.readouterr()
        # Verify the custom format is applied
        assert "Custom format test" in captured.out
        assert "INFO" in captured.out

    def test_structured_ignores_format_string(self):
        """Test that format_string is ignored when structured=True."""
        configure_logging(
            level="INFO",
            format_string="%(message)s",
            structured=True,  # Should be ignored
        )

        # Verify a logger produces JSON output (not just the message)
        logger = logging.getLogger("test.ignore_format")

        # Create a string buffer to capture output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredJSONFormatter())
        logger.addHandler(handler)

        logger.info("Test message")
        output = stream.getvalue()

        # Should be valid JSON, not just the message
        data = json.loads(output.strip())
        assert data["message"] == "Test message"
        assert "context" in data

    def test_reconfigure_logging(self):
        """Test that logging can be reconfigured multiple times."""
        # First configure as standard
        configure_logging(level="INFO", structured=False)

        # Then reconfigure as structured
        configure_logging(level="DEBUG", structured=True)

        # Verify structured logging works
        logger = logging.getLogger("test.reconfig")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredJSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        logger.debug("Reconfigured debug message")
        output = stream.getvalue()

        data = json.loads(output.strip())
        assert data["level"] == "DEBUG"
        assert data["message"] == "Reconfigured debug message"


class TestGetLogger:
    """Test suite for get_logger function."""

    def test_get_logger_without_context(self):
        """Test getting a plain logger without context."""
        logger = get_logger("test.plain")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.plain"

    def test_get_logger_with_context(self):
        """Test getting a LoggerAdapter with context."""
        logger = get_logger("test.context", request_id="req-123", user="user-456")
        assert isinstance(logger, logging.LoggerAdapter)
        assert logger.logger.name == "test.context"
        assert logger.extra["request_id"] == "req-123"
        assert logger.extra["user"] == "user-456"

    def test_logger_adapter_includes_context_in_structured_logs(self):
        """Test that LoggerAdapter context appears in structured logs."""
        configure_logging(level="INFO", structured=True)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredJSONFormatter())

        logger = get_logger("test.adapter", trace_id="trace-789", operation="test_op")

        # Add handler directly to the underlying logger
        if isinstance(logger, logging.LoggerAdapter):
            logger.logger.addHandler(handler)
            logger.logger.setLevel(logging.INFO)
        else:
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

        logger.info("Message with context")
        output = stream.getvalue()

        data = json.loads(output.strip())
        assert data["message"] == "Message with context"
        assert data["context"]["trace_id"] == "trace-789"
        assert data["context"]["operation"] == "test_op"
