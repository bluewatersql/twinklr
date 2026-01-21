"""Tests for logging utilities.

Following TDD: These tests are written BEFORE implementation.
They should FAIL initially (RED phase).
"""

import logging

# Import logging module directly to avoid circular import
import blinkb0t.core.utils.logging as log_utils


def test_configure_logging_default(tmp_path):
    """Test default logging configuration."""
    # Use file output for testing to avoid caplog issues
    log_file = tmp_path / "default.log"
    log_utils.configure_logging(filename=str(log_file))

    # Create a test logger and log a message
    logger = logging.getLogger("test_default")
    logger.info("Test message")

    # Verify message was captured in file
    content = log_file.read_text()
    assert "Test message" in content


def test_configure_logging_with_level(tmp_path):
    """Test logging configuration with custom level."""
    log_file = tmp_path / "level.log"
    log_utils.configure_logging(level="DEBUG", filename=str(log_file))

    logger = logging.getLogger("test_level")
    logger.debug("Debug message")
    logger.info("Info message")

    # Both should be captured with DEBUG level
    content = log_file.read_text()
    assert "Debug message" in content
    assert "Info message" in content


def test_configure_logging_with_file(tmp_path):
    """Test logging to file."""
    log_file = tmp_path / "test.log"
    log_utils.configure_logging(level="DEBUG", filename=str(log_file))

    logger = logging.getLogger("test_file")
    logger.debug("Debug to file")
    logger.info("Info to file")

    # Verify file was created and contains messages
    assert log_file.exists()
    content = log_file.read_text()
    assert "Debug to file" in content
    assert "Info to file" in content


def test_configure_logging_with_custom_format(tmp_path):
    """Test logging with custom format string."""
    log_file = tmp_path / "test.log"
    custom_format = "%(levelname)s - %(message)s"

    log_utils.configure_logging(level="INFO", format_string=custom_format, filename=str(log_file))

    logger = logging.getLogger("test_format")
    logger.info("Test message")

    content = log_file.read_text()
    # Should have format: "INFO - Test message"
    assert "INFO - Test message" in content


def test_get_logger():
    """Test logger retrieval."""
    logger = log_utils.get_logger("test_module")

    assert logger.name == "test_module"
    assert isinstance(logger, logging.Logger)


def test_get_logger_with_context():
    """Test logger with additional context."""
    logger = log_utils.get_logger("test_module", request_id="123", user="test")

    # Logger adapter wraps the logger with extra context
    assert isinstance(logger, logging.LoggerAdapter)
    assert logger.extra["request_id"] == "123"
    assert logger.extra["user"] == "test"


def test_get_logger_logs_with_context(tmp_path):
    """Test that context is included in log messages."""
    log_file = tmp_path / "test.log"
    log_utils.configure_logging(
        level="INFO", format_string="%(message)s - %(request_id)s", filename=str(log_file)
    )

    logger = log_utils.get_logger("test_context", request_id="456")
    logger.info("Context test")

    content = log_file.read_text()
    assert "Context test - 456" in content


def test_configure_logging_multiple_calls():
    """Test that reconfiguring logging works (force=True)."""
    log_utils.configure_logging(level="ERROR")
    log_utils.configure_logging(level="DEBUG")  # Should override

    logger = logging.getLogger("test_multi")

    # Should be at DEBUG level after second call
    assert logger.getEffectiveLevel() == logging.DEBUG


def test_configure_logging_case_insensitive():
    """Test that log level is case insensitive."""
    # Should work with lowercase, uppercase, mixed case
    log_utils.configure_logging(level="debug")
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG

    log_utils.configure_logging(level="INFO")
    assert logging.getLogger().getEffectiveLevel() == logging.INFO

    log_utils.configure_logging(level="WaRnInG")
    assert logging.getLogger().getEffectiveLevel() == logging.WARNING
