"""LLM call logging infrastructure for agents.

This module provides comprehensive logging of LLM interactions including
prompts, responses, metrics, and errors.

Example:
    from blinkb0t.core.agents.logging import AsyncFileLogger, NullLLMCallLogger

    # For production: use file logger
    logger = AsyncFileLogger(
        output_dir=Path("artifacts"),
        run_id="run_123",
        format="yaml",
    )

    # For testing: use null logger
    logger = NullLLMCallLogger()

    # Using factory (recommended):
    from blinkb0t.core.agents.logging import create_llm_logger
    logger = create_llm_logger(
        enabled=True,
        output_dir=Path("artifacts"),
        run_id="run_123",
        log_level="standard",
        format="yaml",
    )
"""

import os
from pathlib import Path

from .async_file_logger import AsyncFileLogger
from .models import AgentCallSummary, CallSummary, LLMCallLog
from .null_logger import NullLLMCallLogger
from .protocol import LLMCallLogger


def create_llm_logger(
    enabled: bool = True,
    output_dir: Path | str | None = None,
    run_id: str | None = None,
    log_level: str = "standard",
    format: str = "yaml",
    sanitize: bool = True,
) -> LLMCallLogger:
    """Factory function to create an LLM call logger.

    Creates the appropriate logger implementation based on configuration.
    Respects environment variable overrides.

    Environment Variables:
        BLINKBOT_DISABLE_LLM_LOGGING: Set to "1" or "true" to disable logging
        BLINKBOT_LLM_LOG_LEVEL: Override log level ("minimal", "standard", "full")
        BLINKBOT_LLM_LOG_FORMAT: Override format ("yaml", "json")

    Args:
        enabled: Enable LLM call logging (False returns NullLLMCallLogger)
        output_dir: Output directory for log files
        run_id: Unique run identifier (generated if not provided)
        log_level: Detail level ("minimal", "standard", "full")
        format: Output format ("yaml", "json")
        sanitize: Sanitize sensitive data from logs

    Returns:
        LLMCallLogger implementation (AsyncFileLogger or NullLLMCallLogger)

    Example:
        # Basic usage
        logger = create_llm_logger(
            output_dir=Path("artifacts"),
            run_id="run_2024_01_28_123456",
        )

        # Disabled (returns NullLLMCallLogger)
        logger = create_llm_logger(enabled=False)

        # Full detail logging
        logger = create_llm_logger(
            output_dir=Path("artifacts"),
            run_id="debug_run",
            log_level="full",
            format="json",
        )
    """
    # Check environment variable overrides
    env_disable = os.environ.get("BLINKBOT_DISABLE_LLM_LOGGING", "").lower()
    if env_disable in ("1", "true", "yes"):
        enabled = False

    env_level = os.environ.get("BLINKBOT_LLM_LOG_LEVEL")
    if env_level and env_level in ("minimal", "standard", "full"):
        log_level = env_level

    env_format = os.environ.get("BLINKBOT_LLM_LOG_FORMAT")
    if env_format and env_format in ("yaml", "json"):
        format = env_format

    # Return NullLogger if disabled
    if not enabled:
        return NullLLMCallLogger()

    # Generate run_id if not provided
    if run_id is None:
        from datetime import datetime

        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Use default output_dir if not provided
    if output_dir is None:
        output_dir = Path("artifacts")

    # Create and return AsyncFileLogger
    return AsyncFileLogger(
        output_dir=Path(output_dir),
        run_id=run_id,
        log_level=log_level,
        format=format,
        sanitize=sanitize,
    )


__all__ = [
    # Protocol
    "LLMCallLogger",
    # Implementations
    "AsyncFileLogger",
    "NullLLMCallLogger",
    # Factory
    "create_llm_logger",
    # Models
    "LLMCallLog",
    "CallSummary",
    "AgentCallSummary",
]
