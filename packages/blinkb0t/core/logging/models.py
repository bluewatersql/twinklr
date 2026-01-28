"""Data models for structured logging."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LogLevel(str, Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogContext(BaseModel):
    """Structured log context with rich metadata.

    All fields are optional to allow flexible usage.
    Additional fields can be added via extra="allow".
    """

    # Identification
    run_id: str | None = None
    job_id: str | None = None
    agent_name: str | None = None
    iteration: int | None = None

    # Timing
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float | None = None

    # Performance
    tokens_used: int | None = None
    memory_mb: float | None = None

    # Status
    success: bool | None = None
    error_type: str | None = None
    error_message: str | None = None

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class LogEntry(BaseModel):
    """Complete log entry with message and context."""

    level: LogLevel
    message: str
    context: LogContext
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}
