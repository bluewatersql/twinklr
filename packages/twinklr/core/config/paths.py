"""Anchoring for relative configured paths.

Configured paths like ``cache_path`` and ``cache_dir`` are relative by default.
Resolving them against the process working directory means the same job run from
two directories reads and writes two different cache trees with no diagnostic,
so they are resolved against an explicit project root instead.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from twinklr.core.config.models import AppConfig

PROJECT_ROOT_ENV_VAR = "TWINKLR_PROJECT_ROOT"

logger = logging.getLogger(__name__)


def resolve_project_root(
    app_config: AppConfig | None = None,
    fallback: Path | str | None = None,
) -> Path:
    """Resolve the directory that relative configured paths anchor to.

    Precedence, most explicit first: ``AppConfig.project_root`` (the user's
    stated root), the caller's ``fallback`` (typically the config file's
    directory), ``$TWINKLR_PROJECT_ROOT``, then the current working directory.
    The working-directory fallback is the historical behavior and is logged,
    because under it cache reuse depends on where the process was launched.

    Args:
        app_config: Config that may carry an explicit ``project_root``
        fallback: Root to use when the config does not specify one

    Returns:
        Absolute project root directory
    """
    candidates = (
        app_config.project_root if app_config else None,
        fallback,
        os.getenv(PROJECT_ROOT_ENV_VAR),
    )
    for candidate in candidates:
        if candidate:
            return Path(candidate).expanduser().resolve()

    cwd = Path.cwd()
    logger.debug(
        f"No project root configured; anchoring relative paths to {cwd}. "
        f"Set AppConfig.project_root or ${PROJECT_ROOT_ENV_VAR} "
        f"for cache reuse across working directories."
    )
    return cwd
