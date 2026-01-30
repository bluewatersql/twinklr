"""Configuration loading utilities with JSON and YAML support."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.utils.json import read_json

logger = logging.getLogger(__name__)

# Default app config path (can be overridden)
_DEFAULT_APP_CONFIG_PATH = Path("config.json")
_app_config_cache: AppConfig | None = None


def detect_format(file_path: Path | str) -> str:
    """Detect config file format from extension.

    Args:
        file_path: Path to config file

    Returns:
        Format string: "json" or "yaml"

    Raises:
        ValueError: If format cannot be determined

    Example:
        >>> detect_format("config.json")
        'json'
        >>> detect_format("config.yaml")
        'yaml'
        >>> detect_format("config.yml")
        'yaml'
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".json":
        return "json"
    elif suffix in [".yaml", ".yml"]:
        return "yaml"
    else:
        raise ValueError(f"Unsupported config format: {suffix}")


def load_config(path: str | Path) -> dict[str, Any]:
    """Load and return raw configuration dictionary.

    Supports both JSON and YAML formats. Format is auto-detected
    from file extension.

    Args:
        path: Path to config file (.json, .yaml, or .yml)

    Returns:
        Raw configuration dictionary

    Raises:
        FileNotFoundError: If config file does not exist
        ValueError: If format is not supported or file content is invalid

    Example:
        >>> config = load_config("config.json")
        >>> config = load_config("config.yaml")
    """
    path = Path(path)

    # Check file exists
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")

    # Detect format
    fmt = detect_format(path)

    # Load based on format
    if fmt == "json":
        try:
            return read_json(path)
        except Exception as e:
            raise ValueError(f"Invalid JSON in {path}: {e}") from e
    elif fmt == "yaml":
        try:
            with path.open("r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                # safe_load returns None for empty files
                return content if content is not None else {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {path}: {e}") from e
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def load_app_config(path: str | Path | None = None) -> AppConfig:
    """Load and validate application configuration.

    Supports both JSON and YAML formats. Environment variables are loaded
    automatically for API keys when config values are None.

    Args:
        path: Path to app config file (.json, .yaml, or .yml)
              Defaults to config.json

    Returns:
        Validated AppConfig instance with defaults for missing values

    Raises:
        ValidationError: If config is invalid
    """
    global _app_config_cache

    if path is None:
        path = _DEFAULT_APP_CONFIG_PATH

    # Use cached config if available and path matches default
    if _app_config_cache is not None and path == _DEFAULT_APP_CONFIG_PATH:
        return _app_config_cache

    # Load config if file exists, otherwise use defaults
    if Path(path).exists():
        raw_config = load_config(path)
        config = AppConfig.model_validate(raw_config)
    else:
        # Use all defaults
        config = AppConfig()

    # Load environment variables for API keys if not set in config
    _load_env_vars_into_config(config)

    # Cache if using default path
    if path == _DEFAULT_APP_CONFIG_PATH:
        _app_config_cache = config

    return config


def configure_logging(config: AppConfig | None = None) -> None:
    """Configure Python logging from app config.

    Args:
        config: AppConfig instance (loads default if None)
    """
    if config is None:
        config = load_app_config()

    logging.basicConfig(
        level=getattr(logging, config.logging.level),
        format=config.logging.format,
        force=True,  # Override any existing configuration
    )


def load_job_config(path: str | Path) -> JobConfig:
    """Load and validate job/task configuration.

    Supports both JSON and YAML formats.

    Args:
        path: Path to job config file (.json, .yaml, or .yml)

    Returns:
        Validated JobConfig instance

    Raises:
        ValidationError: If config is invalid

    Example:
        >>> config = load_job_config("job_config.json")
        >>> config = load_job_config("job_config.yaml")
    """
    raw_config = load_config(path)
    return JobConfig.model_validate(raw_config)


def load_fixture_group(path: str | Path) -> FixtureGroup:
    """Load and validate fixture group configuration.

    Supports both JSON and YAML formats.

    Args:
        path: Path to fixture config file (.json, .yaml, or .yml)

    Returns:
        Validated FixtureGroup instance

    Raises:
        ValidationError: If config is invalid
        FileNotFoundError: If config file does not exist

    Example:
        >>> group = load_fixture_group("fixture_config.json")
        >>> mh1 = group.get_fixture("MH1")
    """
    raw_config = load_config(path)
    return FixtureGroup.model_validate(raw_config)


def load_full_config(job_config_path: str | Path) -> tuple[JobConfig, FixtureGroup]:
    """Load complete configuration (job config + fixture group).

    This is the main entry point for loading all configuration needed for sequencing.

    Args:
        job_config_path: Path to job config file

    Returns:
        Tuple of (JobConfig, FixtureGroup)

    Raises:
        ValidationError: If either config is invalid
        FileNotFoundError: If either config file does not exist

    Example:
        >>> job_cfg, fixtures = load_full_config("job_config.json")
        >>> mh1 = fixtures.get_fixture("MH1")
    """
    # Load job config
    job_cfg = load_job_config(job_config_path)

    # Load fixture config (path is relative to job config directory)
    job_dir = Path(job_config_path).parent
    fixture_path = job_dir / job_cfg.fixture_config_path
    fixtures = load_fixture_group(fixture_path)

    return (job_cfg, fixtures)


def get_openai_api_key() -> str | None:
    """Get OpenAI API key from environment.

    Returns:
        API key or None if not set
    """
    return os.getenv("OPENAI_API_KEY")


def _load_env_vars_into_config(config: AppConfig) -> None:
    """Load environment variables into config for API keys.

    This mutates the config object to fill in None values from environment.

    Args:
        config: AppConfig instance to populate
    """
    updates = {}

    # Load AcoustID API key from environment if not in config
    if config.audio_processing.enhancements.acoustid_api_key is None:
        acoustid_key = os.getenv("ACOUSTID_API_KEY")
        if acoustid_key:
            logger.debug("Loaded ACOUSTID_API_KEY from environment")
            updates["acoustid_api_key"] = acoustid_key

    # Load Genius access token from environment if not in config
    # Support both GENIUS_ACCESS_TOKEN (preferred) and GENIUS_CLIENT_TOKEN (legacy)
    if config.audio_processing.enhancements.genius_access_token is None:
        genius_token = os.getenv("GENIUS_ACCESS_TOKEN") or os.getenv("GENIUS_CLIENT_TOKEN")
        if genius_token:
            env_var_used = (
                "GENIUS_ACCESS_TOKEN" if os.getenv("GENIUS_ACCESS_TOKEN") else "GENIUS_CLIENT_TOKEN"
            )
            logger.debug(f"Loaded Genius token from {env_var_used}")
            if env_var_used == "GENIUS_CLIENT_TOKEN":
                logger.warning(
                    "Using deprecated GENIUS_CLIENT_TOKEN. Please rename to GENIUS_ACCESS_TOKEN in your .env file"
                )
            updates["genius_access_token"] = genius_token

    # Apply updates if any
    if updates:
        config.audio_processing.enhancements = config.audio_processing.enhancements.model_copy(
            update=updates
        )
