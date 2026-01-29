"""Configuration models for BlinkB0t."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.config.poses import PoseConfig
from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.sequencer.models.enum import TransitionMode
from blinkb0t.core.sequencer.models.transition import TransitionStrategy


class AgentConfig(BaseModel):
    """Per-agent LLM configuration."""

    model: str = Field(default="gpt-5.2", description="LLM model name")

    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="LLM temperature (0=deterministic, 2=creative)"
    )

    max_tokens: int = Field(default=50000, gt=0, description="Maximum tokens for LLM response")

    timeout_seconds: int = Field(default=60, gt=0, description="Timeout for LLM API call")


class LLMLoggingConfig(BaseModel):
    """LLM call logging configuration (Phase 0).

    Controls comprehensive logging of LLM interactions including
    prompts, responses, metrics, and errors.
    """

    enabled: bool = Field(
        default=True,
        description="Enable LLM call logging (set to False for production performance)",
    )

    log_level: str = Field(
        default="standard",
        pattern="^(minimal|standard|full)$",
        description=(
            "Log detail level: "
            "'minimal' (metrics only), "
            "'standard' (prompts + responses), "
            "'full' (+ full context)"
        ),
    )

    format: str = Field(
        default="yaml",
        pattern="^(yaml|json)$",
        description="Output format: 'yaml' (human-readable) or 'json' (machine-readable)",
    )

    sanitize: bool = Field(
        default=True,
        description="Sanitize sensitive data (API keys, emails, etc.) from logs",
    )


class AgentOrchestrationConfig(BaseModel):
    """Multi-agent orchestration configuration."""

    max_iterations: int = Field(
        default=3, ge=0, description="Maximum judge/iterate loops (0=skip judge)"
    )

    token_budget: int = Field(
        default=75000, gt=0, description="Total token budget for orchestration"
    )

    enforce_token_budget: bool = Field(
        default=False, description="Hard stop if token budget exceeded (vs warning)"
    )

    token_buffer_pct: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Buffer percentage for token predictions (e.g., 0.2 = 20%)",
    )

    success_threshold: int = Field(
        default=70, ge=0, le=100, description="Minimum judge score to accept plan"
    )

    # Per-agent configurations
    plan_agent: AgentConfig = Field(default_factory=lambda: AgentConfig(temperature=0.7))

    implementation_agent: AgentConfig = Field(default_factory=lambda: AgentConfig(temperature=0.7))

    judge_agent: AgentConfig = Field(
        default_factory=lambda: AgentConfig(model="gpt-5-mini", temperature=1.0)
    )

    refinement_agent: AgentConfig = Field(default_factory=lambda: AgentConfig(temperature=0.7))

    # Phase 0: LLM Logging Configuration
    llm_logging: LLMLoggingConfig = Field(
        default_factory=LLMLoggingConfig,
        description="LLM call logging configuration for observability and debugging",
    )


class ChannelDefaults(BaseModel):
    """Job-level channel defaults.

    Applied to all sections unless overridden at section level.
    Immutable after creation to prevent accidental modification.

    Example:
        >>> defaults = ChannelDefaults()
        >>> defaults.shutter  # "open"
        >>> defaults.color    # "white"
        >>> defaults.gobo     # "open"
    """

    shutter: str = Field(
        default="open", description="Default shutter state (open, closed, strobe_fast, etc.)"
    )

    color: str = Field(default="white", description="Default color preset (red, blue, white, etc.)")

    gobo: str = Field(
        default="open", description="Default gobo pattern (open, stars, clouds, etc.)"
    )

    model_config = ConfigDict(
        extra="forbid",  # Reject unknown fields
        frozen=True,  # Immutable after creation
    )


def _get_agent_config_default() -> AgentOrchestrationConfig:
    """Return default agent orchestration config."""
    return AgentOrchestrationConfig()


class ConfigBase(BaseModel):
    """Base class for all BlinkB0t configurations.

    Provides common functionality for loading from files with defaults.
    Subclasses must implement default_path() to specify their default location.
    """

    model_config = ConfigDict(extra="ignore")  # Forward compatibility

    @classmethod
    def default_path(cls) -> Path:
        """Return the default config file path for this config type.

        Subclasses must override this to provide their default location.

        Returns:
            Path to the default config file
        """
        raise NotImplementedError(f"{cls.__name__} must implement default_path()")

    @classmethod
    def load_or_default(cls, path: Path | str | None = None) -> Self:
        """Load config from path or use default path.

        Args:
            path: Path to config file, or None to use default

        Returns:
            Loaded config instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValidationError: If config is invalid
        """
        # AppConfig needs environment variable loading for API keys
        if cls.__name__ == "AppConfig":
            from blinkb0t.core.config.loader import load_app_config

            return load_app_config(path)  # type: ignore[return-value]

        # Other config types use simple loader
        from blinkb0t.core.config.loader import load_config

        if path is None:
            path = cls.default_path()
        raw = load_config(path)
        return cls.model_validate(raw)


class AssumptionsConfig(BaseModel):
    """Music theory assumptions for beat-aligned planning."""

    beats_per_bar: int = Field(default=4, ge=1, le=12)


class AudioEnhancementConfig(BaseModel):
    """Audio enhancement configuration (v3.0 features).

    Controls metadata enrichment, lyrics resolution, and phoneme generation.
    Follows "reasonable defaults" philosophy: all features work with zero config,
    network features require explicit enablement + API keys.
    """

    model_config = ConfigDict(extra="ignore")  # Forward compatibility

    # Feature flags (gradual rollout support)
    enable_metadata: bool = Field(
        default=True, description="Enable metadata enrichment (embedded tags + providers)"
    )
    enable_lyrics: bool = Field(default=True, description="Enable lyrics resolution pipeline")
    enable_phonemes: bool = Field(default=True, description="Enable phoneme/viseme generation")

    # Network features (optional, require API keys)
    enable_acoustid: bool = Field(
        default=False,
        description="Enable AcoustID fingerprinting (requires chromaprint binary)",
    )
    enable_musicbrainz: bool = Field(
        default=False, description="Enable MusicBrainz lookups (rate limited)"
    )
    enable_lyrics_lookup: bool = Field(
        default=False, description="Enable online lyrics providers (LRCLib, Genius, etc.)"
    )
    enable_whisperx: bool = Field(
        default=False,
        description="Enable WhisperX for lyrics transcription (requires model download)",
    )
    enable_diarization: bool = Field(
        default=False,
        description="Enable speaker diarization (requires pyannote models)",
    )

    # Lyrics pipeline
    lyrics_require_timed: bool = Field(
        default=False, description="Require word-level timing (triggers WhisperX if needed)"
    )
    lyrics_min_coverage: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Minimum lyrics time coverage to avoid WhisperX fallback",
    )
    lyrics_language: str = Field(default="en", description="Language for lyrics processing")

    # WhisperX
    whisperx_model: str = Field(
        default="base",
        description="WhisperX model size (tiny, base, small, medium, large)",
    )
    whisperx_device: str = Field(default="cpu", description="Device for WhisperX (cpu, cuda, mps)")
    whisperx_batch_size: int = Field(
        default=16, ge=1, description="Batch size for WhisperX processing"
    )
    whisperx_return_char_alignments: bool = Field(
        default=False,
        description="Return character-level alignments (slower, more detailed)",
    )

    # Phonemes
    phoneme_enable_g2p_fallback: bool = Field(
        default=True, description="Use g2p_en for words not in CMUdict"
    )
    phoneme_min_duration_ms: int = Field(
        default=30, ge=10, description="Minimum phoneme duration (ms)"
    )
    phoneme_vowel_weight: float = Field(
        default=2.0, ge=0.1, description="Relative weight for vowel phoneme duration"
    )
    phoneme_consonant_weight: float = Field(
        default=1.0, ge=0.1, description="Relative weight for consonant phoneme duration"
    )

    # Viseme smoothing
    viseme_min_hold_ms: int = Field(
        default=50, ge=10, description="Minimum viseme hold duration (ms)"
    )
    viseme_min_burst_ms: int = Field(
        default=40, ge=10, description="Minimum burst duration before merging (ms)"
    )
    viseme_boundary_soften_ms: int = Field(
        default=15, ge=0, description="Boundary softening window (ms)"
    )
    viseme_mapping_version: str = Field(default="1.0", description="Viseme mapping table version")

    # Provider configuration
    acoustid_api_key: str | None = Field(
        default=None, description="AcoustID API key (load from env: ACOUSTID_API_KEY)"
    )
    genius_access_token: str | None = Field(
        default=None,
        description="Genius API access token (load from env: GENIUS_ACCESS_TOKEN or GENIUS_CLIENT_TOKEN)",
    )
    musicbrainz_rate_limit_rps: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="MusicBrainz rate limit (requests per second)",
    )
    musicbrainz_timeout_s: float = Field(
        default=10.0, ge=1.0, description="MusicBrainz request timeout (seconds)"
    )

    # HTTP client defaults
    http_max_retries: int = Field(default=3, ge=0, description="Maximum HTTP request retries")
    http_timeout_s: float = Field(
        default=30.0, ge=1.0, description="HTTP request timeout (seconds)"
    )
    http_circuit_breaker_threshold: int = Field(
        default=5, ge=1, description="Circuit breaker failure threshold"
    )
    http_circuit_breaker_timeout_s: float = Field(
        default=60.0, ge=1.0, description="Circuit breaker reset timeout (seconds)"
    )

    # Metadata merge policy
    metadata_merge_policy_version: str = Field(
        default="1.0", description="Metadata merge policy version"
    )
    metadata_min_confidence_warn: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Minimum confidence before warning",
    )


class AudioProcessingConfig(BaseModel):
    """Audio processing configuration."""

    hop_length: int = Field(default=512, ge=64, le=2048)
    frame_length: int = Field(default=2048, ge=512, le=8192)
    cache_enabled: bool = True

    # NEW: v3.0 enhancements
    enhancements: AudioEnhancementConfig = Field(
        default_factory=AudioEnhancementConfig,
        description="Audio enhancement features (metadata, lyrics, phonemes)",
    )

    def model_post_init(self, __context: object) -> None:
        """Validate audio processing parameters."""
        if self.hop_length > self.frame_length:
            raise ValueError(
                f"hop_length ({self.hop_length}) must be <= frame_length ({self.frame_length})"
            )

        # Warn about extreme values that may cause performance issues
        if self.hop_length < 256:
            logger = logging.getLogger(__name__)
            logger.warning(
                f"hop_length={self.hop_length} is very small (< 256). "
                "This will create many more frames and significantly increase processing time and memory usage. "
                "Recommended: 256-512 for most use cases."
            )

        if self.frame_length > 4096:
            logger = logging.getLogger(__name__)
            logger.warning(
                f"frame_length={self.frame_length} is very large (> 4096). "
                "This may cause performance issues. Recommended: 2048-4096 for most use cases."
            )


class PlanningContextConfig(BaseModel):
    """LLM context building configuration (token budget constraints)."""

    max_beats: int = Field(default=600, ge=100, le=2000)
    max_energy_points: int = Field(default=768, ge=100, le=2000)
    max_spectral_points: int = Field(default=256, ge=50, le=1000)
    max_transients: int = Field(default=20, ge=5, le=100)
    max_sections: int = Field(default=12, ge=4, le=50)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class PlannerFeatures(BaseModel):
    """Feature flags for planner DMX channel control.

    Controls which DMX channels the planner handles beyond the core
    pan/tilt/dimmer channels (which are always enabled).
    """

    enable_shutter: bool = Field(default=True, description="Enable shutter/strobe planning")

    enable_color: bool = Field(
        default=True,
        description="Enable color planning",
    )

    enable_gobo: bool = Field(default=True, description="Enable gobo selection planning")


class AppConfig(ConfigBase):
    """Application-level configuration (shared across all jobs/tasks)."""

    model_config = ConfigDict(extra="ignore")
    output_dir: str = "artifacts"
    cache_dir: str = "data/audio_cache"
    audio_processing: AudioProcessingConfig = AudioProcessingConfig()
    planning: PlanningContextConfig = PlanningContextConfig()
    logging: LoggingConfig = LoggingConfig()

    @classmethod
    def default_path(cls) -> Path:
        """Default path for application config."""
        return Path("config.json")


class TransitionConfig(BaseModel):
    """Global transition behavior configuration.

    Controls default transition behavior and global settings.

    Attributes:
        enabled: Enable/disable transitions globally.
        default_duration_bars: Default transition duration when not specified.
        default_mode: Default transition mode.
        default_curve: Default interpolation curve.
        min_section_duration_bars: Minimum section duration to allow transitions.
        allow_overlaps: Allow transition overlap regions.
        per_channel_defaults: Default strategy per channel type.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(default=True, description="Enable transitions globally")

    default_duration_bars: float = Field(
        default=0.5,
        ge=0.0,
        le=4.0,
        description="Default transition duration when not specified",
    )

    default_mode: TransitionMode = Field(
        default=TransitionMode.CROSSFADE, description="Default transition mode"
    )

    default_curve: CurveLibrary = Field(
        default=CurveLibrary.EASE_IN_OUT_SINE, description="Default transition curve"
    )

    min_section_duration_bars: float = Field(
        default=1.0, ge=0.5, description="Minimum section duration to allow transitions"
    )

    allow_overlaps: bool = Field(default=True, description="Allow transition overlap regions")

    per_channel_defaults: dict[str, TransitionStrategy] = Field(
        default_factory=lambda: {
            "pan": TransitionStrategy.SMOOTH_INTERPOLATION,
            "tilt": TransitionStrategy.SMOOTH_INTERPOLATION,
            "dimmer": TransitionStrategy.CROSSFADE,
            "shutter": TransitionStrategy.SEQUENCE,
            "color": TransitionStrategy.FADE_VIA_BLACK,
            "gobo": TransitionStrategy.FADE_VIA_BLACK,
        },
        description="Default strategy per channel type",
    )


class JobConfig(ConfigBase):
    """Job/task-specific configuration.

    This represents a specific sequencing job with fixture configuration,
    musical assumptions, and planner settings.

    Schema version 3.0 adds:
    - Pose configuration (custom poses + overrides)
    - Planner feature flags (DMX channel control)
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: str = "3.0"  # Bumped to 3.0 for Phase 0 Component 5
    include_notes_track: bool = True
    debug: bool = True
    assumptions: AssumptionsConfig = AssumptionsConfig()

    # Fixture configuration (uses FixtureGroup - loaded separately)
    fixture_config_path: str = "fixture_config.json"

    agent: AgentOrchestrationConfig = Field(default_factory=lambda: _get_agent_config_default())
    output_dir: str | None = None
    project_name: str | None = None
    checkpoint: bool = True

    pose_config: PoseConfig = Field(
        default_factory=PoseConfig,
        description=(
            "Pose configuration for semantic position abstraction. "
            "Standard poses loaded by default, supports custom poses and overrides."
        ),
    )

    planner_features: PlannerFeatures = Field(
        default_factory=PlannerFeatures,
        description=(
            "Feature flags for planner DMX channel control. "
            "Controls which channels beyond pan/tilt/dimmer are planned."
        ),
    )

    channel_defaults: ChannelDefaults = Field(
        default_factory=ChannelDefaults,
        description=(
            "Default channel states for entire sequence. "
            "Applied to all sections unless overridden by agent plan."
        ),
    )

    transitions: TransitionConfig = Field(
        default_factory=TransitionConfig,
        description="Transition behavior configuration for smooth blending between sections and steps",
    )

    @classmethod
    def default_path(cls) -> Path:
        """Default path for job config."""
        return Path("job_config.json")

    def is_channel_enabled(self, channel: str) -> bool:
        """Check if a specific channel is enabled for planning.

        Args:
            channel: Channel name ("shutter", "color", "gobo")

        Returns:
            True if channel planning is enabled

        Raises:
            ValueError: If channel name is unknown

        Example:
            >>> config = JobConfig()
            >>> config.is_channel_enabled("shutter")
            True
            >>> config.is_channel_enabled("invalid")
            ValueError: Unknown channel: invalid
        """
        if channel == "shutter":
            return self.planner_features.enable_shutter
        elif channel == "color":
            return self.planner_features.enable_color
        elif channel == "gobo":
            return self.planner_features.enable_gobo
        else:
            raise ValueError(f"Unknown channel: {channel}")
