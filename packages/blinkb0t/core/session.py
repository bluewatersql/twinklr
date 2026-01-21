"""BlinkB0t session coordinator - universal services for all domains.

The session provides shared infrastructure that all domains need:
- Configuration management (app-level and job-level)
- Audio analysis
- Sequence fingerprinting
- Project/artifact management

Domain-specific functionality (moving heads, RGB, lasers) is provided
by separate DomainManager classes that use the session.

Example:
    # Simple usage
    session = BlinkB0tSession.from_directory(".")

    # Use with domain manager
    from blinkb0t.core.domains.sequencing.moving_heads import MovingHeadManager
    mh = MovingHeadManager(session)
    mh.run_pipeline("song.mp3", "input.xsq", "output.xsq")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from blinkb0t.core.config.models import AppConfig, ConfigBase, JobConfig

T = TypeVar("T", bound=ConfigBase)

if TYPE_CHECKING:
    from blinkb0t.core.domains.audio.analyzer import AudioAnalyzer
    from blinkb0t.core.domains.sequencing.analyzer import SequenceAnalyzer

logger = logging.getLogger(__name__)


class BlinkB0tSession:
    """Universal session coordinator for BlinkB0t pipelines.

    Manages configuration and provides shared services (audio analysis,
    sequence fingerprinting) that all domains need. Domain-specific logic
    lives in separate DomainManager classes.

    Supports flexible initialization patterns:

    1. From directory (simple):
        session = BlinkB0tSession.from_directory(".")

    2. From explicit configs:
        session = BlinkB0tSession(
            app_config=app_cfg,
            job_config=job_cfg
        )

    3. From paths:
        session = BlinkB0tSession(
            app_config="config.json",
            job_config="job_config.json"
        )

    4. Mixed (some loaded, some provided):
        session = BlinkB0tSession(
            app_config=my_app_config,  # Already loaded
            job_config="job_config.json"  # Will load
        )
    """

    def __init__(
        self,
        *,
        app_config: AppConfig | Path | str | None = None,
        job_config: JobConfig | Path | str | None = None,
    ):
        """Initialize session with configs.

        Args:
            app_config: AppConfig instance, path, or None (uses default path)
            job_config: JobConfig instance, path, or None (uses default path)

        Raises:
            FileNotFoundError: If config files don't exist
            ValidationError: If configs are invalid
        """
        # Load configs
        self.app_config: AppConfig = self._resolve_config(app_config, AppConfig)
        self.job_config: JobConfig = self._resolve_config(job_config, JobConfig)

        # Set up project/artifact management
        self.project_name = self.job_config.project_name or "blinkb0t_project"
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
    def from_directory(cls, config_dir: Path | str = ".") -> BlinkB0tSession:
        """Create session from a directory containing config files.

        Looks for config.json and job_config.json in the specified directory.

        Args:
            config_dir: Directory containing config files (default: current directory)

        Returns:
            Initialized BlinkB0tSession

        Example:
            session = BlinkB0tSession.from_directory(".")
            session = BlinkB0tSession.from_directory("/path/to/project")
        """
        config_dir = Path(config_dir)
        return cls(
            app_config=config_dir / "config.json",
            job_config=config_dir / "job_config.json",
        )

    # =========================================================================
    # UNIVERSAL SERVICES (lazy-loaded properties)
    # =========================================================================

    @property
    def audio(self) -> AudioAnalyzer:
        """Get audio analyzer for this session (universal service).

        Lazy-loaded on first access.

        Returns:
            AudioAnalyzer instance configured with session configs
        """
        if not hasattr(self, "_audio"):
            from blinkb0t.core.domains.audio.analyzer import AudioAnalyzer

            self._audio = AudioAnalyzer(self.app_config, self.job_config)
        return self._audio

    @property
    def sequence(self) -> SequenceAnalyzer:
        """Get sequence analyzer for this session (universal service).

        Lazy-loaded on first access.

        Returns:
            SequenceAnalyzer instance configured with session configs
        """
        if not hasattr(self, "_sequence"):
            from blinkb0t.core.domains.sequencing.analyzer import SequenceAnalyzer

            self._sequence = SequenceAnalyzer(self.app_config, self.job_config)
        return self._sequence
