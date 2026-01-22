"""Template Loader for the moving head sequencer.

This module provides the TemplateLoader class for loading and managing
templates from JSON files. Templates are validated against Pydantic
models and can be looked up by ID.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from blinkb0t.core.sequencer.models.template import (
    Template,
    TemplateDoc,
    TemplatePreset,
)
from blinkb0t.core.sequencer.moving_heads.compile.preset import apply_preset


class TemplateNotFoundError(Exception):
    """Raised when a template or preset is not found."""

    pass


class TemplateLoadError(Exception):
    """Raised when template loading fails."""

    pass


class TemplateLoader:
    """Loads and manages templates from JSON files.

    Templates are stored in a dictionary keyed by template_id.
    Provides methods for loading from files, dictionaries, and
    directories, as well as querying and applying presets.

    Example:
        >>> loader = TemplateLoader()
        >>> loader.load_from_file(Path("templates/fan_pulse.json"))
        >>> doc = loader.get("fan_pulse")
        >>> template = loader.get_with_preset("fan_pulse", "CHILL")
    """

    def __init__(self) -> None:
        """Initialize an empty template loader."""
        self._templates: dict[str, TemplateDoc] = {}

    def load_from_dict(self, data: dict[str, Any]) -> None:
        """Load a template from a dictionary.

        Args:
            data: Dictionary containing template data in TemplateDoc format.

        Raises:
            TemplateLoadError: If validation fails.
        """
        try:
            doc = TemplateDoc.model_validate(data)
            self._templates[doc.template.template_id] = doc
        except ValidationError as e:
            raise TemplateLoadError(f"Template validation failed: {e}") from e

    def load_from_file(self, path: Path) -> None:
        """Load a template from a JSON file.

        Args:
            path: Path to the JSON file.

        Raises:
            TemplateLoadError: If file not found, JSON invalid, or validation fails.
        """
        if not path.exists():
            raise TemplateLoadError(f"Template file not found: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise TemplateLoadError(f"Invalid JSON in {path}: {e}") from e

        try:
            self.load_from_dict(data)
        except TemplateLoadError as e:
            raise TemplateLoadError(f"Error loading {path}: {e}") from e

    def load_directory(self, directory: Path, *, recursive: bool = False) -> None:
        """Load all templates from a directory.

        Args:
            directory: Path to directory containing template JSON files.
            recursive: If True, also load from subdirectories.

        Note:
            Only files with .json extension are loaded.
            Files that fail to load are silently skipped.
        """
        pattern = "**/*.json" if recursive else "*.json"
        for json_file in directory.glob(pattern):
            if json_file.is_file():
                try:
                    self.load_from_file(json_file)
                except TemplateLoadError:
                    # Skip files that fail to load
                    pass

    def has(self, template_id: str) -> bool:
        """Check if a template is loaded.

        Args:
            template_id: The template ID to check.

        Returns:
            True if the template is loaded, False otherwise.
        """
        return template_id in self._templates

    def get(self, template_id: str) -> TemplateDoc:
        """Get a template document by ID.

        Args:
            template_id: The template ID to retrieve.

        Returns:
            The TemplateDoc for the requested template.

        Raises:
            TemplateNotFoundError: If template not found.
        """
        if template_id not in self._templates:
            raise TemplateNotFoundError(f"Template '{template_id}' not found")
        return self._templates[template_id]

    def list_templates(self) -> list[str]:
        """List all loaded template IDs.

        Returns:
            List of template IDs.
        """
        return list(self._templates.keys())

    def get_presets(self, template_id: str) -> list[TemplatePreset]:
        """Get all presets for a template.

        Args:
            template_id: The template ID.

        Returns:
            List of presets for the template.

        Raises:
            TemplateNotFoundError: If template not found.
        """
        doc = self.get(template_id)
        return doc.presets

    def get_preset(self, template_id: str, preset_id: str) -> TemplatePreset:
        """Get a specific preset for a template.

        Args:
            template_id: The template ID.
            preset_id: The preset ID.

        Returns:
            The requested preset.

        Raises:
            TemplateNotFoundError: If template or preset not found.
        """
        presets = self.get_presets(template_id)
        for preset in presets:
            if preset.preset_id == preset_id:
                return preset
        raise TemplateNotFoundError(f"Preset '{preset_id}' not found for template '{template_id}'")

    def get_with_preset(self, template_id: str, preset_id: str) -> Template:
        """Get a template with a preset applied.

        Creates a new Template instance with the preset's defaults
        and step patches applied. The original template is not modified.

        Args:
            template_id: The template ID.
            preset_id: The preset ID to apply.

        Returns:
            A new Template with the preset applied.

        Raises:
            TemplateNotFoundError: If template or preset not found.
        """
        doc = self.get(template_id)
        preset = self.get_preset(template_id, preset_id)
        return apply_preset(doc.template, preset)
