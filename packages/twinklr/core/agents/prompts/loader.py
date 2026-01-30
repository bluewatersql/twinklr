"""Prompt pack loader."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from blinkb0t.core.agents.prompts.renderer import PromptRenderer

logger = logging.getLogger(__name__)


class LoadError(Exception):
    """Raised when prompt pack loading fails."""

    pass


class PromptPackLoader:
    """Loads prompt packs from filesystem.

    Prompt Pack Structure:
        pack_name/
        ├── system.j2            # Required: System prompt
        ├── developer.j2         # Optional: Developer/contract prompt
        ├── user.j2              # Optional: User message template
        └── examples.jsonl       # Optional: Few-shot examples
    """

    def __init__(self, base_path: str | Path):
        """Initialize prompt pack loader.

        Args:
            base_path: Base directory containing prompt packs
        """
        self.base_path = Path(base_path)
        self.renderer = PromptRenderer()

        logger.debug(f"PromptPackLoader initialized: base_path={self.base_path}")

    def load(self, pack_name: str) -> dict[str, Any]:
        """Load prompt pack (templates not rendered).

        Args:
            pack_name: Name of the prompt pack directory

        Returns:
            Dict with prompt components:
            - "system": System prompt template
            - "developer": Developer prompt template (optional)
            - "user": User prompt template (optional)
            - "examples": List of example messages (optional)

        Raises:
            LoadError: If pack doesn't exist or required files missing
        """
        pack_dir = self.base_path / pack_name

        if not pack_dir.exists() or not pack_dir.is_dir():
            raise LoadError(f"Prompt pack '{pack_name}' does not exist at {pack_dir}")

        prompts: dict[str, Any] = {}

        # Load system prompt (required)
        system_path = pack_dir / "system.j2"
        if not system_path.exists():
            raise LoadError(
                f"Prompt pack '{pack_name}' missing required system.j2 at {system_path}"
            )

        prompts["system"] = system_path.read_text()

        # Load developer prompt (optional)
        developer_path = pack_dir / "developer.j2"
        if developer_path.exists():
            prompts["developer"] = developer_path.read_text()

        # Load user prompt (optional)
        user_path = pack_dir / "user.j2"
        if user_path.exists():
            prompts["user"] = user_path.read_text()

        # Load examples (optional)
        examples_path = pack_dir / "examples.jsonl"
        if examples_path.exists():
            try:
                examples = []
                for line in examples_path.read_text().strip().split("\n"):
                    if line.strip():
                        examples.append(json.loads(line))
                prompts["examples"] = examples
            except json.JSONDecodeError as e:
                raise LoadError(
                    f"Invalid JSON in examples.jsonl for pack '{pack_name}': {e}"
                ) from e

        logger.debug(f"Loaded prompt pack '{pack_name}': {list(prompts.keys())}")

        return prompts

    def load_and_render(self, pack_name: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Load and render prompt pack with variables.

        Args:
            pack_name: Name of the prompt pack directory
            variables: Variables for template rendering

        Returns:
            Dict with rendered prompts (same structure as load())

        Raises:
            LoadError: If loading fails
            RenderError: If rendering fails
        """
        # Load templates
        prompts = self.load(pack_name)

        # Render templates
        rendered: dict[str, Any] = {}

        if "system" in prompts:
            rendered["system"] = self.renderer.render(prompts["system"], variables)

        if "developer" in prompts:
            rendered["developer"] = self.renderer.render(prompts["developer"], variables)

        if "user" in prompts:
            rendered["user"] = self.renderer.render(prompts["user"], variables)

        # Examples are not rendered (they're already concrete messages)
        if "examples" in prompts:
            rendered["examples"] = prompts["examples"]

        return rendered
