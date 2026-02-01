"""Pipeline context for shared state and dependencies.

Provides dependency injection and state management across pipeline stages.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.config.models import AppConfig, JobConfig


@dataclass
class PipelineContext:
    """Shared context across pipeline stages.

    Provides dependency injection for services, configuration, and state management.
    Mutable to allow state updates during pipeline execution.

    Attributes:
        provider: LLM provider for agent stages
        app_config: Application configuration
        job_config: Job configuration
        llm_logger: LLM call logger (defaults to NullLLMCallLogger)
        checkpoint_dir: Optional checkpoint directory
        output_dir: Optional output directory for artifacts
        state: Mutable state dictionary for sharing data between stages
        metrics: Mutable metrics dictionary (timing, tokens, etc.)
        cancel_token: Optional cancellation token (asyncio.Event)

    Example:
        >>> context = PipelineContext(
        ...     provider=provider,
        ...     app_config=app_config,
        ...     job_config=job_config,
        ...     output_dir=Path("artifacts/demo"),
        ... )
        >>>
        >>> # Access in stage
        >>> async def execute(self, input, context):
        ...     analyzer = AudioAnalyzer(context.app_config, context.job_config)
        ...     # Store intermediate state
        ...     context.state["has_lyrics"] = bundle.lyrics is not None
        ...     # Track metrics
        ...     context.metrics["audio_duration_ms"] = bundle.timing.duration_ms
    """

    # Required dependencies
    provider: LLMProvider
    app_config: AppConfig
    job_config: JobConfig

    # Optional dependencies
    llm_logger: LLMCallLogger = field(default_factory=NullLLMCallLogger)

    # Paths
    checkpoint_dir: Path | None = None
    output_dir: Path | None = None

    # Mutable state
    state: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    # Cancellation support
    cancel_token: asyncio.Event | None = None

    def is_cancelled(self) -> bool:
        """Check if pipeline has been cancelled.

        Returns:
            True if cancel_token is set and signaled
        """
        return self.cancel_token is not None and self.cancel_token.is_set()

    def add_metric(self, key: str, value: Any) -> None:
        """Add or update metric.

        Args:
            key: Metric key
            value: Metric value
        """
        self.metrics[key] = value

    def increment_metric(self, key: str, delta: int | float = 1) -> None:
        """Increment numeric metric.

        Args:
            key: Metric key
            delta: Amount to increment (default: 1)
        """
        self.metrics[key] = self.metrics.get(key, 0) + delta

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state value with optional default.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        return self.state.get(key, default)

    def set_state(self, key: str, value: Any) -> None:
        """Set state value.

        Args:
            key: State key
            value: State value
        """
        self.state[key] = value
