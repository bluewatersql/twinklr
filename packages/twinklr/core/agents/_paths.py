"""Canonical filesystem paths for the agents package.

This module is intentionally import-free (no agents submodule imports) to
avoid circular-import issues when consumed from within the package tree.
"""

from __future__ import annotations

from pathlib import Path

AGENTS_BASE_PATH: Path = Path(__file__).resolve().parent
"""Root directory of the agents package — used as ``prompt_base_path``
for :class:`AsyncAgentRunner` so prompt packs are resolved relative to
the package install location, not the current working directory."""
