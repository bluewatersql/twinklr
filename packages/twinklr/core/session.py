"""Twinklr session coordinator - universal services for all domains.

The session provides shared infrastructure that all domains need:
- Configuration management (app-level and job-level)
- Audio analysis
- Sequence fingerprinting
- Project/artifact management

Domain-specific functionality (moving heads, RGB, lasers) is provided
by separate DomainManager classes that use the session.

"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import uuid4

from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger, create_llm_logger
from twinklr.core.agents.providers.base import LLMProvider
from twinklr.core.agents.providers.factory import create_llm_provider
from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.caching import Cache
from twinklr.core.caching.backends.fs import FSCache
from twinklr.core.caching.backends.null import NullCache
from twinklr.core.config.models import AppConfig, ConfigBase, JobConfig
from twinklr.core.io import RealFileSystem, absolute_path

T = TypeVar("T", bound=ConfigBase)

if TYPE_CHECKING:
    from twinklr.core.audio.analyzer import AudioAnalyzer

logger = logging.getLogger(__name__)


class TwinklrSession:
    """Universal session coordinator for Twinklr pipelines.

    Manages configuration and provides shared services (audio analysis,
    sequence fingerprinting) that all domains need. Domain-specific logic
    lives in separate DomainManager classes.
    """

    def __init__(
        self,
        *,
        app_config: AppConfig | Path | str | None = None,
        job_config: JobConfig | Path | str | None = None,
        session_id: str | None = None,
    ):
        """Initialize session with configs.

        Args:
            app_config: AppConfig instance, path, or None (uses default path)
            job_config: JobConfig instance, path, or None (uses default path)
            session_id: Optional session ID. If None, generates a new UUID.
                        Pass a deterministic ID for cache reuse across runs.

        Raises:
            FileNotFoundError: If config files don't exist
            ValidationError: If configs are invalid
        """
        # Load configs
        self.app_config: AppConfig = self._resolve_config(app_config, AppConfig)
        self.job_config: JobConfig = self._resolve_config(job_config, JobConfig)
        self.session_id = session_id or str(uuid4())

        # Set up project/artifact management
        self.project_name = self.job_config.project_name or "twinklr_project"
        self.artifact_dir = (
            Path(self.job_config.output_dir or self.app_config.output_dir) / self.project_name
        )

        logger.debug(
            f"Session initialized: project={self.project_name}, artifacts={self.artifact_dir}"
        )

    @staticmethod
    def _resolve_config(value: Any, config_cls: type[T]) -> T:
        """Resolve config from value, path, or default.

        Args:
            value: Config instance, path, or None
            config_cls: Config class to instantiate

        Returns:
            Config instance

        Raises:
            TypeError: If value is wrong type
            FileNotFoundError: If path doesn't exist
            ValidationError: If config is invalid
        """
        if value is None:
            return config_cls.load_or_default()  # type: ignore[return-value]
        elif isinstance(value, (Path, str)):
            return config_cls.load_or_default(Path(value))  # type: ignore[return-value]
        elif isinstance(value, config_cls):
            return value  # type: ignore[return-value]
        else:
            raise TypeError(
                f"Expected {config_cls.__name__}, Path, str, or None; got {type(value).__name__}"
            )

    @classmethod
    def from_directory(
        cls,
        config_dir: Path | str = ".",
        *,
        session_id: str | None = None,
    ) -> TwinklrSession:
        """Create session from a directory containing config files.

        Looks for config.json and job_config.json in the specified directory.

        Args:
            config_dir: Directory containing config files (default: current directory)
            session_id: Optional session ID for cache reuse. If None, generates new UUID.

        Returns:
            Initialized TwinklrSession

        Example:
            session = TwinklrSession.from_directory(".")
            session = TwinklrSession.from_directory("/path/to/project", session_id="my-stable-id")
        """
        config_dir = Path(config_dir)
        return cls(
            app_config=config_dir / "config.json",
            job_config=config_dir / "job_config.json",
            session_id=session_id,
        )

    @property
    def agent_cache(self) -> Cache:
        """Get agent cache for this session (universal service).

        Lazy-loaded on first access. Cache initializes itself lazily on first use.
        TTL is configured at cache creation time from job_config.

        Returns:
            Cache instance configured with session configs
        """
        if not hasattr(self, "_agent_cache"):
            cache_enabled = self.job_config.agent.agent_cache.enabled if self.job_config else False
            agent_cache: FSCache | NullCache
            if cache_enabled:
                cache_config = self.job_config.agent.agent_cache
                agent_cache = FSCache(
                    RealFileSystem(),
                    absolute_path(cache_config.cache_path),
                    ttl_seconds=cache_config.ttl_seconds,
                )
            else:
                agent_cache = NullCache()

            self._agent_cache = agent_cache

        return self._agent_cache

    @property
    def llm_provider(self) -> LLMProvider:
        """Get LLM provider for this session (universal service).

        Lazy-loaded on first access.

        Returns:
            LLMProvider instance configured with session configs
        """
        if not hasattr(self, "_llm_provider"):
            if not self.app_config or not self.app_config.llm_provider:
                raise ValueError("LLM provider not configured")

            self._llm_provider = create_llm_provider(self.app_config, self.session_id)
        return self._llm_provider

    @property
    def llm_logger(self) -> LLMCallLogger:
        """Get LLM logger for this session (universal service).

        Lazy-loaded on first access.
        Log directory structure: <log_path>/<agent>/<session_id>/<step_iteration>.json

        Returns:
            LLMCallLogger instance configured with session configs
        """
        if not hasattr(self, "_llm_logger"):
            enabled = self.job_config.agent.llm_logging.enabled if self.job_config else False

            if enabled:
                self._llm_logger = create_llm_logger(
                    enabled=enabled,
                    output_dir=self.job_config.agent.llm_logging.log_path,
                    session_id=self.session_id,
                    log_level=self.job_config.agent.llm_logging.log_level,
                    format=self.job_config.agent.llm_logging.format,
                )
            else:
                self._llm_logger = NullLLMCallLogger()

        return self._llm_logger

    @property
    def audio_analyzer(self) -> AudioAnalyzer:
        """Get audio analyzer for this session (universal service).

        Lazy-loaded on first access.

        Returns:
            AudioAnalyzer instance configured with session configs
        """
        if not hasattr(self, "_audio"):
            self._audio = AudioAnalyzer(self.app_config, self.job_config)
        return self._audio
